"""TeeItUp / GolfNow provider (kenna.io backend).

Covers Smithtown Landing, Stonebridge, Middle Island, Cherry Creek, Great
Rock, Bergen Point, and every NYC American Golf municipal.

Public read endpoint (no login to VIEW availability):
  GET https://phx-api-be-east-1b.kenna.io/v2/tee-times
      ?date=YYYY-MM-DD&facilityIds=<ID>&returnPromotedRates=true

`facilityIds` is the numeric ?course= value from the booking page. When the
catalog leaves facility_id blank we resolve it once from the course's
book.teeitup.com sub-domain (`alias`) and cache it in memory for the run.

Times come back in UTC ISO; we convert to America/New_York.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from ..models import TeeTime
from .base import Provider

API = "https://phx-api-be-east-1b.kenna.io/v2/tee-times"
NY = ZoneInfo("America/New_York")


class TeeItUpProvider(Provider):
    name = "teeitup"

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._facility_cache: dict[str, int] = {}

    def fetch(self, course_key, course, day, override=None) -> list[TeeTime]:
        fid = course.get("facility_id") or self._resolve_facility(course)
        if not fid:
            self._log(course_key, "could not resolve facility_id — skipping")
            return []

        alias = course.get("alias", "")
        origin = self._booking_origin(course)
        headers = {
            "Origin": origin,
            "Referer": origin + "/",
        }
        if alias:
            headers["x-be-alias"] = alias
        params = {
            "date": day.strftime("%Y-%m-%d"),
            "facilityIds": str(fid),
            "returnPromotedRates": "true",
        }
        r = self.session.get(API, params=params, headers=headers, timeout=25)
        self._log(course_key, day, "-> ", r.status_code, f"{len(r.text)}b")
        if r.status_code != 200:
            return []
        try:
            data = r.json()
        except ValueError:
            return []

        rows = _extract_rows(data)
        out: list[TeeTime] = []
        for row in rows:
            out.extend(self._parse_row(course_key, course, row))
        return out

    # ------------------------------------------------------------------
    def _parse_row(self, course_key, course, row: dict) -> list[TeeTime]:
        when = _to_local(row.get("time") or row.get("teetime") or row.get("teeTime"))
        if not when:
            return []
        cname = row.get("courseName") or row.get("course_name") or course["name"]
        rates = row.get("rates") or row.get("teeTimeRates") or []

        # group by holes -> (min price, max players)
        by_holes: dict[Optional[int], list] = {}
        if rates:
            for rate in rates:
                holes = _int(rate.get("holes"))
                price = _num(rate.get("greenFeeWalking"), rate.get("price"),
                             rate.get("greenFee"), rate.get("rate"))
                players = _players(rate) or _int(row.get("maxPlayers"))
                by_holes.setdefault(holes, []).append((price, players))
        else:
            by_holes[_int(row.get("holes"))] = [
                (_num(row.get("price")), _int(row.get("maxPlayers")))
            ]

        results = []
        for holes, entries in by_holes.items():
            prices = [p for p, _ in entries if p is not None]
            players = [pl for _, pl in entries if pl is not None]
            results.append(TeeTime(
                course_key=course_key,
                course_name=str(cname),
                when=when,
                holes=holes,
                players=max(players) if players else None,
                price=min(prices) if prices else None,
                booking_url=course.get("booking_url", ""),
                raw=row,
            ))
        return results

    # ------------------------------------------------------------------
    def _booking_origin(self, course: dict) -> str:
        alias = course.get("alias", "")
        tld = course.get("tld", "com")
        if alias:
            return f"https://{alias}.book.teeitup.{tld}"
        # fall back to the booking_url's origin
        m = re.match(r"(https?://[^/]+)", course.get("booking_url", ""))
        return m.group(1) if m else "https://book.teeitup.com"

    def _resolve_facility(self, course: dict) -> Optional[int]:
        alias = course.get("alias")
        if not alias:
            return None
        if alias in self._facility_cache:
            return self._facility_cache[alias]
        url = self._booking_origin(course) + "/"
        try:
            r = self.session.get(url, timeout=25)
        except Exception as e:  # network hiccup
            self._log("resolve", alias, "error", e)
            return None
        if r.status_code != 200:
            return None
        fid = _find_facility_id(r.text)
        if fid:
            self._facility_cache[alias] = fid
            self._log("resolved", alias, "->", fid)
        return fid


# ---------------------------------------------------------------- helpers
def _extract_rows(data):
    """kenna responses vary: a bare list, or {'teeTimes': [...]}, or grouped."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("teeTimes", "tee_times", "times", "data", "results"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


_FID_PATTERNS = [
    re.compile(r'[?&]course=(\d+)'),
    re.compile(r'"facilityId"\s*:\s*(\d+)'),
    re.compile(r'"facility"\s*:\s*{[^}]*?"id"\s*:\s*(\d+)'),
    re.compile(r'"facilityIds?"\s*:\s*\[?\s*(\d+)'),
]


def _find_facility_id(html: str) -> Optional[int]:
    for pat in _FID_PATTERNS:
        m = pat.search(html)
        if m:
            return int(m.group(1))
    return None


def _to_local(s) -> Optional[datetime]:
    if not s:
        return None
    txt = str(s).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                dt = datetime.strptime(str(s)[:19], fmt)
                break
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


def _num(*vals):
    for v in vals:
        try:
            if v is None:
                continue
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


def _players(rate: dict):
    rule = rate.get("playerRule") or rate.get("player_rule") or {}
    if isinstance(rule, dict):
        mx = rule.get("maxPlayer") or rule.get("max") or rule.get("maxPlayers")
        if mx is not None:
            return _int(mx)
    allowed = rate.get("allowedPlayers") or rate.get("players")
    if isinstance(allowed, list) and allowed:
        return _int(max(allowed))
    return _int(rate.get("maxPlayers"))
