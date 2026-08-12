"""Nassau County provider — Eisenhower Park (Red/White/Blue) & Cantiague.

⚠️ DIFFERENT FROM EVERY OTHER COURSE. Nassau runs a custom login-walled app
(golf.nassaucountyny.gov). You cannot even *view* tee times without a resident
**Leisure Pass** account, so this provider must log in as you.

Two things are required before it can work:
  1. Your Leisure Pass login (set env NASSAU_USER / NASSAU_PASS, or config).
  2. The exact authenticated availability endpoint + field names, captured once
     from a real login session (the site is a bespoke Laravel app, so these
     aren't publicly documented). Fill them into the catalog entry / overrides.

Until #2 is filled in, this provider logs in and returns nothing rather than
guessing wrong. Run `python run.py classes nassau_eisenhower` for guidance, or
ask Looper's author to capture the endpoint with you in a browser session.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from ..models import TeeTime
from .base import Provider

NY = ZoneInfo("America/New_York")
BASE = "https://golf.nassaucountyny.gov"


class NassauProvider(Provider):
    name = "nassau"
    _logged_in = False

    def _login(self, course, override) -> bool:
        if self._logged_in:
            return True
        import os
        user = os.environ.get("NASSAU_USER") or override.get("user")
        pw = os.environ.get("NASSAU_PASS") or override.get("password")
        if not (user and pw):
            self._log("no Nassau credentials set (NASSAU_USER / NASSAU_PASS) — skipping")
            return False
        login_url = course.get("login_url", f"{BASE}/login")
        try:
            page = self.session.get(login_url, timeout=25)
        except Exception as e:
            self._log("login page error", e)
            return False
        token = _csrf(page.text)
        # field names default to Laravel conventions; override if the real form differs
        fields = dict(override.get("login_fields") or {})
        fields.setdefault(course.get("user_field", "email"), user)
        fields.setdefault("password", pw)
        if token:
            fields["_token"] = token
        headers = {"Referer": login_url, "Origin": BASE}
        try:
            r = self.session.post(login_url, data=fields, headers=headers, timeout=25,
                                  allow_redirects=True)
        except Exception as e:
            self._log("login post error", e)
            return False
        ok = r.status_code < 400 and "login" not in r.url.split("/")[-1].lower()
        self._logged_in = ok
        self._log("login", "ok" if ok else f"failed ({r.status_code}, {r.url})")
        return ok

    def fetch(self, course_key, course, day, override=None) -> list[TeeTime]:
        override = override or {}
        avail = course.get("availability_url")
        if not avail:
            self._log(course_key, "no availability_url configured yet — see nassau.py header")
            return []
        if not self._login(course, override):
            return []
        url = avail.format(date=day.strftime(course.get("date_fmt", "%Y-%m-%d")),
                           course_id=course.get("course_id", ""))
        try:
            r = self.session.get(url, headers={"Referer": BASE, "X-Requested-With": "XMLHttpRequest"},
                                 timeout=25)
        except Exception as e:
            self._log(course_key, "fetch error", e)
            return []
        if r.status_code != 200:
            self._log(course_key, day, "->", r.status_code)
            return []
        # try JSON first, then fall back to HTML table scraping
        try:
            data = r.json()
            return self._parse_json(course_key, course, data)
        except ValueError:
            return self._parse_html(course_key, course, r.text, day)

    def _parse_json(self, course_key, course, data) -> list[TeeTime]:
        rows = data if isinstance(data, list) else (
            data.get("teetimes") or data.get("times") or data.get("data") or [])
        out = []
        for row in rows:
            when = _to_local(row.get("time") or row.get("start_time") or row.get("datetime"))
            if not when:
                continue
            out.append(TeeTime(
                course_key=course_key, course_name=course["name"], when=when,
                holes=_int(row.get("holes")),
                players=_int(row.get("available") or row.get("spots") or row.get("players")),
                price=_num(row.get("price") or row.get("fee")),
                booking_url=course.get("booking_url", BASE), raw=row,
            ))
        return out

    def _parse_html(self, course_key, course, html, day) -> list[TeeTime]:
        # Generic fallback: find HH:MM AM/PM tokens in the availability page.
        out = []
        for m in re.finditer(r'(\d{1,2}:\d{2}\s*[APap][Mm])', html):
            try:
                t = datetime.strptime(m.group(1).upper().replace(" ", ""), "%I:%M%p").time()
            except ValueError:
                continue
            when = datetime.combine(day, t)
            out.append(TeeTime(course_key, course["name"], when, None, None, None,
                               course.get("booking_url", BASE), {"src": "html"}))
        # de-dup identical times
        seen, uniq = set(), []
        for t in out:
            if t.when not in seen:
                seen.add(t.when); uniq.append(t)
        self._log(course_key, "html fallback parsed", len(uniq), "times")
        return uniq


def _csrf(html: str) -> Optional[str]:
    m = re.search(r'name="csrf-token"\s+content="([^"]+)"', html) or \
        re.search(r'name="_token"\s+value="([^"]+)"', html)
    return m.group(1) if m else None


def _to_local(s):
    if not s:
        return None
    txt = str(s).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %I:%M %p"):
            try:
                dt = datetime.strptime(str(s)[:19], fmt); break
            except ValueError:
                dt = None
        if dt is None:
            return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(NY).replace(tzinfo=None)
    return dt


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
