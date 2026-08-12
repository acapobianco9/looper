#!/usr/bin/env python3
"""Looper — never miss a tee time.

Watches Long Island / NYC golf courses for newly-opened tee times on the dates
you want and pushes an alert to your phone (ntfy) or texts you (Twilio SMS).

Single-file build so it's trivial to host. Commands:
  python looper.py run          one pass; alert on NEW times (use on a schedule)
  python looper.py loop         poll forever locally (--interval MINUTES)
  python looper.py selftest     show what's open right now (no alerts) [--debug]
  python looper.py list         list watchable courses
  python looper.py test-notify  send one test alert
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time as _time
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import requests

try:
    import yaml
except ImportError:
    yaml = None

NY = ZoneInfo("America/New_York")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# ============================================================ catalog
CATALOG: dict[str, dict] = {
    # --- ForeUp (public booking classes verified live) ---
    "bethpage": {"name": "Bethpage State Park (all 5 courses)", "provider": "foreup",
        "course_id": 19765, "schedule_ids": [2517, 2431, 2433, 2539, 2538, 2434, 2432, 2435],
        "booking_class": 2137,
        "booking_url": "https://foreupsoftware.com/index.php/booking/19765/2431#teetimes"},
    "montauk_downs": {"name": "Montauk Downs State Park", "provider": "foreup",
        "course_id": 19756, "schedule_ids": [2436], "booking_class": 2155,
        "booking_url": "https://foreupsoftware.com/index.php/booking/19756/2436#teetimes"},
    "sunken_meadow": {"name": "Sunken Meadow State Park", "provider": "foreup",
        "course_id": 19766, "schedule_ids": [2437], "booking_class": 2147,
        "booking_url": "https://foreupsoftware.com/index.php/booking/19766/2437#teetimes"},
    "rock_hill": {"name": "Rock Hill Golf & Country Club (Manorville)", "provider": "foreup",
        "course_id": 20662, "schedule_ids": [5270], "booking_class": 5743,
        "booking_url": "https://foreupsoftware.com/index.php/booking/20662/5270#teetimes"},
    "crab_meadow": {"name": "Crab Meadow Golf Course (Northport)", "provider": "foreup",
        "course_id": 21593, "schedule_ids": [8314], "booking_class": 10785,
        "booking_url": "https://foreupsoftware.com/index.php/booking/21593/8314#teetimes"},
    "gull_haven": {"name": "Gull Haven Golf Course (Central Islip)", "provider": "foreup",
        "course_id": 19106, "schedule_ids": [958], "booking_class": 406,
        "booking_url": "https://foreupsoftware.com/index.php/booking/19106/958#teetimes"},
    "holbrook": {"name": "Holbrook Country Club (Holbrook)", "provider": "foreup",
        "course_id": 19107, "schedule_ids": [959], "booking_class": 408,
        "booking_url": "https://foreupsoftware.com/index.php/booking/19107/959#teetimes"},
    "tall_grass": {"name": "Tall Grass Golf Club (Shoreham)", "provider": "foreup",
        "course_id": 20290, "schedule_ids": [3782], "booking_class": 3686,
        "booking_url": "https://foreupsoftware.com/index.php/booking/20290/3782#teetimes"},

    "smithtown_landing": {"name": "Smithtown Landing Country Club", "provider": "teeitup",
        "alias": "smithtown-landing-country-club", "facility_id": None,
        "booking_url": "https://smithtown-landing-country-club.book.teeitup.com"},
    "stonebridge": {"name": "Stonebridge Golf Links & CC (Smithtown)", "provider": "teeitup",
        "alias": "stonebridge-golf-links-and-country-club", "tld": "golf", "facility_id": None,
        "booking_url": "https://stonebridge-golf-links-and-country-club.book.teeitup.golf/"},
    "middle_island": {"name": "Middle Island Country Club", "provider": "teeitup",
        "alias": "middle-island-country-club", "tld": "golf", "facility_id": None,
        "booking_url": "https://middle-island-country-club.book.teeitup.golf/"},
    "great_rock": {"name": "Great Rock Golf Club (Wading River)", "provider": "teeitup",
        "alias": "great-rock-golf-club", "facility_id": None,
        "booking_url": "https://go.teeitup.com/3862"},
    "cherry_creek": {"name": "Cherry Creek Golf Links (Riverhead)", "provider": "teeitup",
        "alias": "the-woods-at-cherry-creek", "tld": "golf", "facility_id": None,
        "booking_url": "https://the-woods-at-cherry-creek.book.teeitup.golf/"},
    "bergen_point": {"name": "Bergen Point Golf Course (Babylon)", "provider": "teeitup",
        "alias": "bergen-point-golf-course", "tld": "golf", "facility_id": None,
        "booking_url": "https://bergen-point-golf-course.book.teeitup.golf/"},
    "poxabogue": {"name": "Poxabogue Golf Center (Sagaponack)", "provider": "teeitup",
        "alias": "poxabogue-golf-center", "facility_id": None,
        "booking_url": "https://poxabogue-golf-center.book.teeitup.com/"},
    "peninsula": {"name": "Peninsula Golf Club (Massapequa)", "provider": "teeitup",
        "alias": "87b5ee21-e1ec-4d44-8a82-db692b9ed452", "tld": "golf", "facility_id": None,
        "booking_url": "https://87b5ee21-e1ec-4d44-8a82-db692b9ed452.book.teeitup.golf/"},

    # --- Chronogolf / Lightspeed ---
    "swan_lake": {"name": "Swan Lake Golf Club (Manorville)", "provider": "chronogolf",
        "course_uuid": "7f42c719-4d75-4e47-8d52-b464cc1c0842",
        "booking_url": "https://www.chronogolf.com/club/swan-lake-golf-club"},
    "hamlet_wind_watch": {"name": "Hamlet Wind Watch Golf Club (Hauppauge)", "provider": "chronogolf",
        "course_uuid": "a9a988d0-a742-4f9e-9d8f-4fabd95b4e0a",
        "booking_url": "https://www.chronogolf.com/club/hamlet-wind-watch-golf-club"},

    "nassau_eisenhower": {"name": "Eisenhower Park (Red / White / Blue)", "provider": "nassau",
        "login_url": "https://golf.nassaucountyny.gov/login", "user_field": "email",
        "availability_url": None, "course_id": "",
        "booking_url": "https://golf.nassaucountyny.gov/"},
    "nassau_cantiague": {"name": "Cantiague Park Golf Course", "provider": "nassau",
        "login_url": "https://golf.nassaucountyny.gov/login", "user_field": "email",
        "availability_url": None, "course_id": "",
        "booking_url": "https://golf.nassaucountyny.gov/"},
}

# ============================================================ helpers
def as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None

def as_num(*vals):
    for v in vals:
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None

def iso_to_local(s):
    """Parse an ISO timestamp (maybe UTC/offset) -> naive America/New_York."""
    if not s:
        return None
    txt = str(s).replace("Z", "+00:00")
    dt = None
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                    "%Y-%m-%d %I:%M %p"):
            try:
                dt = datetime.strptime(str(s)[:19], fmt); break
            except ValueError:
                dt = None
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(NY).replace(tzinfo=None)
    return dt

def foreup_dt(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(s), fmt)
        except ValueError:
            continue
    return None

def new_session():
    s = requests.Session()
    s.headers.update({"User-Agent": UA,
                      "Accept": "application/json, text/plain, */*",
                      "Accept-Language": "en-US,en;q=0.9"})
    return s

# ============================================================ model
@dataclass
class TeeTime:
    course_key: str
    course_name: str
    when: datetime
    holes: Optional[int]
    players: Optional[int]
    price: Optional[float]
    booking_url: str
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def date_str(self): return self.when.strftime("%Y-%m-%d")

    @property
    def time_str(self):
        return self.when.strftime("%I:%M%p").lstrip("0").lower().replace("am", "a").replace("pm", "p")

    @property
    def uid(self):
        basis = f"{self.course_key}|{self.when.isoformat()}|{self.holes}"
        return hashlib.sha1(basis.encode()).hexdigest()[:16]

    def summary(self):
        bits = [self.time_str]
        if self.holes: bits.append(f"{self.holes}h")
        if self.players: bits.append(f"{self.players} spots")
        if self.price is not None: bits.append(f"${self.price:g}")
        return " · ".join(bits)

# ============================================================ providers
def fetch_foreup(session, key, course, day, override, debug=False):
    bc = override.get("booking_class", course.get("booking_class"))
    if bc is None:
        return []
    params = [("time", "all"), ("date", day.strftime("%m-%d-%Y")), ("holes", "all"),
              ("players", "0"), ("booking_class", str(bc)), ("specials_only", "0"),
              ("api_key", "no_limits")]
    sids = course.get("schedule_ids") or []
    if sids:
        params.append(("schedule_id", str(sids[0])))
        for s in sids:
            params.append(("schedule_ids[]", str(s)))
    try:
        r = session.get("https://foreupsoftware.com/index.php/api/booking/times",
                        params=params, timeout=25,
                        headers={"X-Requested-With": "XMLHttpRequest",
                                 "Referer": course.get("booking_url", "https://foreupsoftware.com/")})
    except Exception as e:
        if debug: print("[foreup]", key, "err", e)
        return []
    if debug: print("[foreup]", key, day, "->", r.status_code, len(r.text))
    if r.status_code != 200:
        return []
    try:
        data = r.json()
    except ValueError:
        return []
    if isinstance(data, dict):
        data = data.get("times") or data.get("data") or []
    out = []
    for row in data:
        when = foreup_dt(row.get("time"))
        if not when:
            continue
        out.append(TeeTime(key, str(row.get("course_name") or row.get("schedule") or course["name"]),
                           when, as_int(row.get("holes")), as_int(row.get("available_spots")),
                           as_num(row.get("green_fee")), course.get("booking_url", ""), row))
    return out


_FID_PATS = [re.compile(r'[?&]course=(\d+)'), re.compile(r'"facilityId"\s*:\s*(\d+)'),
             re.compile(r'"facility"\s*:\s*{[^}]*?"id"\s*:\s*(\d+)'),
             re.compile(r'"facilityIds?"\s*:\s*\[?\s*(\d+)')]

def _teeitup_origin(course):
    alias = course.get("alias", "")
    if alias:
        return f"https://{alias}.book.teeitup.{course.get('tld','com')}"
    m = re.match(r"(https?://[^/]+)", course.get("booking_url", ""))
    return m.group(1) if m else "https://book.teeitup.com"

_FID_CACHE: dict[str, int] = {}

def _resolve_facility(session, course, debug=False):
    alias = course.get("alias")
    if not alias:
        return None
    if alias in _FID_CACHE:
        return _FID_CACHE[alias]
    try:
        r = session.get(_teeitup_origin(course) + "/", timeout=25)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    for pat in _FID_PATS:
        m = pat.search(r.text)
        if m:
            _FID_CACHE[alias] = int(m.group(1))
            if debug: print("[teeitup] resolved", alias, "->", _FID_CACHE[alias])
            return _FID_CACHE[alias]
    return None

def _players_from_rate(rate, row):
    rule = rate.get("playerRule") or rate.get("player_rule") or {}
    if isinstance(rule, dict):
        mx = rule.get("maxPlayer") or rule.get("max") or rule.get("maxPlayers")
        if mx is not None:
            return as_int(mx)
    allowed = rate.get("allowedPlayers") or rate.get("players")
    if isinstance(allowed, list) and allowed:
        return as_int(max(allowed))
    return as_int(rate.get("maxPlayers") or row.get("maxPlayers"))

def fetch_teeitup(session, key, course, day, override, debug=False):
    fid = course.get("facility_id") or _resolve_facility(session, course, debug)
    if not fid:
        if debug: print("[teeitup]", key, "no facility id")
        return []
    origin = _teeitup_origin(course)
    headers = {"Origin": origin, "Referer": origin + "/"}
    if course.get("alias"):
        headers["x-be-alias"] = course["alias"]
    try:
        r = session.get("https://phx-api-be-east-1b.kenna.io/v2/tee-times",
                        params={"date": day.strftime("%Y-%m-%d"), "facilityIds": str(fid),
                                "returnPromotedRates": "true"}, headers=headers, timeout=25)
    except Exception as e:
        if debug: print("[teeitup]", key, "err", e)
        return []
    if debug: print("[teeitup]", key, day, "->", r.status_code, len(r.text))
    if r.status_code != 200:
        return []
    try:
        data = r.json()
    except ValueError:
        return []
    if isinstance(data, dict):
        for k in ("teeTimes", "tee_times", "times", "data", "results"):
            if isinstance(data.get(k), list):
                data = data[k]; break
        else:
            data = []
    out = []
    for row in data:
        when = iso_to_local(row.get("time") or row.get("teetime") or row.get("teeTime"))
        if not when:
            continue
        cname = row.get("courseName") or row.get("course_name") or course["name"]
        rates = row.get("rates") or row.get("teeTimeRates") or []
        by_holes: dict = {}
        if rates:
            for rate in rates:
                h = as_int(rate.get("holes"))
                price = as_num(rate.get("greenFeeWalking"), rate.get("price"),
                               rate.get("greenFee"), rate.get("rate"))
                pl = _players_from_rate(rate, row)
                by_holes.setdefault(h, []).append((price, pl))
        else:
            by_holes[as_int(row.get("holes"))] = [(as_num(row.get("price")), as_int(row.get("maxPlayers")))]
        for h, entries in by_holes.items():
            prices = [p for p, _ in entries if p is not None]
            players = [pl for _, pl in entries if pl is not None]
            out.append(TeeTime(key, str(cname), when, h,
                               max(players) if players else None,
                               min(prices) if prices else None,
                               course.get("booking_url", ""), row))
    return out


def fetch_chronogolf(session, key, course, day, override, debug=False):
    uuid = course.get("course_uuid")
    if not uuid:
        return []
    try:
        r = session.get("https://www.chronogolf.com/marketplace/v2/teetimes",
                        params={"start_date": day.strftime("%Y-%m-%d"), "course_ids": uuid,
                                "holes": "9,18", "start_time": "05:00", "page": "1"}, timeout=25)
    except Exception as e:
        if debug: print("[chrono]", key, "err", e)
        return []
    if debug: print("[chrono]", key, day, "->", r.status_code, len(r.text))
    if r.status_code != 200:
        return []
    try:
        data = r.json()
    except ValueError:
        return []
    if isinstance(data, dict):
        data = data.get("teetimes") or data.get("data") or []
    out = []
    for row in data:
        if row.get("out_of_capacity"):
            continue
        when = iso_to_local(row.get("start_time") or row.get("date_time") or row.get("datetime"))
        if not when:
            continue
        pr = row.get("player_range") or row.get("players_range") or {}
        players = as_int(row.get("players")) or (as_int(pr.get("to")) if isinstance(pr, dict) else None)
        fees = row.get("green_fees") or row.get("greenFees") or []
        by_holes: dict = {}
        if fees:
            for fee in fees:
                by_holes.setdefault(as_int(fee.get("holes")), []).append(as_num(fee.get("price"), fee.get("green_fee")))
        else:
            by_holes[None] = [None]
        for h, prices in by_holes.items():
            valid = [p for p in prices if p is not None]
            out.append(TeeTime(key, course["name"], when, h, players,
                               min(valid) if valid else None, course.get("booking_url", ""), row))
    return out


_NASSAU_SESSION = {"in": False}

def fetch_nassau(session, key, course, day, override, debug=False):
    avail = course.get("availability_url")
    if not avail:
        if debug: print("[nassau]", key, "no availability_url configured")
        return []
    user = os.environ.get("NASSAU_USER") or override.get("user")
    pw = os.environ.get("NASSAU_PASS") or override.get("password")
    if not (user and pw):
        if debug: print("[nassau]", key, "no credentials")
        return []
    if not _NASSAU_SESSION["in"]:
        try:
            page = session.get(course.get("login_url"), timeout=25)
            m = (re.search(r'name="csrf-token"\s+content="([^"]+)"', page.text) or
                 re.search(r'name="_token"\s+value="([^"]+)"', page.text))
            fields = dict(override.get("login_fields") or {})
            fields.setdefault(course.get("user_field", "email"), user)
            fields.setdefault("password", pw)
            if m: fields["_token"] = m.group(1)
            r = session.post(course.get("login_url"), data=fields, timeout=25,
                             headers={"Referer": course.get("login_url")})
            _NASSAU_SESSION["in"] = r.status_code < 400 and "login" not in r.url.split("/")[-1].lower()
        except Exception as e:
            if debug: print("[nassau] login err", e)
            return []
    if not _NASSAU_SESSION["in"]:
        return []
    url = avail.format(date=day.strftime(course.get("date_fmt", "%Y-%m-%d")),
                       course_id=course.get("course_id", ""))
    try:
        r = session.get(url, timeout=25, headers={"X-Requested-With": "XMLHttpRequest"})
    except Exception:
        return []
    if r.status_code != 200:
        return []
    out = []
    try:
        data = r.json()
        rows = data if isinstance(data, list) else (data.get("teetimes") or data.get("times") or data.get("data") or [])
        for row in rows:
            when = iso_to_local(row.get("time") or row.get("start_time") or row.get("datetime"))
            if when:
                out.append(TeeTime(key, course["name"], when, as_int(row.get("holes")),
                                   as_int(row.get("available") or row.get("spots")),
                                   as_num(row.get("price") or row.get("fee")),
                                   course.get("booking_url", ""), row))
    except ValueError:
        seen = set()
        for m in re.finditer(r'(\d{1,2}:\d{2}\s*[APap][Mm])', r.text):
            try:
                t = datetime.strptime(m.group(1).upper().replace(" ", ""), "%I:%M%p").time()
            except ValueError:
                continue
            when = datetime.combine(day, t)
            if when not in seen:
                seen.add(when)
                out.append(TeeTime(key, course["name"], when, None, None, None, course.get("booking_url", ""), {}))
    return out


PROVIDERS = {"foreup": fetch_foreup, "teeitup": fetch_teeitup,
             "chronogolf": fetch_chronogolf, "nassau": fetch_nassau}

# ============================================================ notify
def send_ntfy(cfg, title, body, click):
    server = cfg.get("server", "https://ntfy.sh")
    topic = os.environ.get("NTFY_TOPIC") or cfg.get("topic")
    if not topic:
        raise ValueError("ntfy needs a topic (env NTFY_TOPIC or notify.topic)")
    headers = {"Title": title.encode("utf-8"), "Priority": str(cfg.get("priority", "high")), "Tags": "golf"}
    if click:
        headers["Click"] = click
    tok = os.environ.get("NTFY_TOKEN") or cfg.get("token")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    r = requests.post(f"{server.rstrip('/')}/{topic}", data=body.encode("utf-8"), headers=headers, timeout=20)
    r.raise_for_status()
    print(f"[notify] ntfy -> {topic}: {title}")

def send_twilio(cfg, title, body, click):
    sid = os.environ.get("TWILIO_SID") or cfg.get("account_sid")
    tok = os.environ.get("TWILIO_TOKEN") or cfg.get("auth_token")
    frm = os.environ.get("TWILIO_FROM") or cfg.get("from")
    to = os.environ.get("TWILIO_TO") or cfg.get("to")
    if not all([sid, tok, frm, to]):
        raise ValueError("Twilio needs account_sid, auth_token, from, to")
    text = f"{title}\n{body}" + (f"\n{click}" if click else "")
    if len(text) > 1500:
        text = text[:1490] + "…"
    for dest in [d.strip() for d in str(to).split(",") if d.strip()]:
        r = requests.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                          data={"From": frm, "To": dest, "Body": text}, auth=(sid, tok), timeout=20)
        if r.status_code >= 300:
            raise RuntimeError(f"Twilio {r.status_code}: {r.text[:200]}")
        print(f"[notify] sms -> {dest}: {title}")

def send_pushover(cfg, title, body, click):
    tok = os.environ.get("PUSHOVER_TOKEN") or cfg.get("token")
    usr = os.environ.get("PUSHOVER_USER") or cfg.get("user")
    if not (tok and usr):
        raise ValueError("pushover needs token + user")
    payload = {"token": tok, "user": usr, "title": title, "message": body, "priority": cfg.get("priority", 1)}
    if click:
        payload["url"] = click; payload["url_title"] = "Book now"
    r = requests.post("https://api.pushover.net/1/messages.json", data=payload, timeout=20)
    r.raise_for_status()
    print(f"[notify] pushover: {title}")

def console(title, body, click):
    print("\n" + "-" * 60 + f"\n{title}\n{body}" + (f"\n-> {click}" if click else "") + "\n" + "-" * 60)

def notify_new(cfg, times):
    if not times:
        return
    backend = (cfg.get("backend") or "ntfy").lower()
    groups: dict = {}
    for t in times:
        groups.setdefault((t.course_key, t.date_str), []).append(t)
    for (ckey, dstr), slots in groups.items():
        slots.sort(key=lambda s: s.when)
        title = f"⛳ {len(slots)} tee time{'s' if len(slots)!=1 else ''} — {slots[0].course_name}, {slots[0].when.strftime('%a %b %-d')}"
        lines = [s.summary() for s in slots[:12]]
        if len(slots) > 12:
            lines.append(f"…and {len(slots)-12} more")
        body = "\n".join(lines)
        click = slots[0].booking_url
        try:
            if backend == "ntfy": send_ntfy(cfg, title, body, click)
            elif backend in ("sms", "twilio"): send_twilio(cfg, title, body, click)
            elif backend == "pushover": send_pushover(cfg, title, body, click)
            else: console(title, body, click)
        except Exception as e:
            print(f"[notify] FAILED ({backend}): {e}")
            console(title, body, click)

def notify_text(cfg, title, body):
    backend = (cfg.get("backend") or "ntfy").lower()
    try:
        if backend == "ntfy": send_ntfy(cfg, title, body, None)
        elif backend in ("sms", "twilio"): send_twilio(cfg, title, body, None)
        elif backend == "pushover": send_pushover(cfg, title, body, None)
        else: console(title, body, None)
    except Exception as e:
        print(f"[notify] FAILED ({backend}): {e}"); console(title, body, None)

# ============================================================ state
def load_seen(path):
    p = Path(path)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}

def save_seen(path, data):
    today = date.today()
    pruned = {}
    for uid, d in data.items():
        try:
            if datetime.strptime(str(d)[:10], "%Y-%m-%d").date() >= today:
                pruned[uid] = d
        except Exception:
            pass
    Path(path).write_text(json.dumps(pruned, indent=0, sort_keys=True))

# ============================================================ config
_WD = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}

@dataclass
class Config:
    courses: list
    dates: list
    weekdays: list
    horizon_days: int
    earliest: time
    latest: time
    holes: Optional[int]
    players_min: int
    max_price: Optional[float]
    notify: dict
    overrides: dict

    def target_dates(self, today=None):
        today = today or date.today()
        out = set(d for d in self.dates if d >= today)
        if self.weekdays:
            for i in range(self.horizon_days + 1):
                d = today + timedelta(days=i)
                if d.weekday() in self.weekdays:
                    out.add(d)
        return sorted(out)

def _ptime(s, default):
    if not s:
        return default
    return datetime.strptime(str(s).strip(), "%H:%M").time()

def load_config(path="config.yaml"):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    if yaml is None:
        raise RuntimeError("PyYAML not installed. Run: pip install pyyaml")
    data = yaml.safe_load(p.read_text()) or {}
    if not data.get("courses"):
        raise ValueError("config.yaml has no `courses:`")
    dates = []
    for d in (data.get("dates") or []):
        dates.append(d if isinstance(d, date) else datetime.strptime(str(d).strip(), "%Y-%m-%d").date())
    weekdays = []
    for w in (data.get("weekdays") or []):
        k = str(w).strip().lower()[:3]
        if k in _WD:
            weekdays.append(_WD[k])
    win = data.get("time_window") or {}
    filt = data.get("filters") or {}
    holes = filt.get("holes")
    holes = None if holes in (None, "any", "Any", "ANY") else int(holes)
    mp = filt.get("max_price")
    return Config(list(data["courses"]), dates, weekdays, int(data.get("horizon_days", 7)),
                  _ptime(win.get("earliest"), time(5, 0)), _ptime(win.get("latest"), time(20, 0)),
                  holes, int(filt.get("players_min", 1)),
                  (float(mp) if mp not in (None, "") else None),
                  data.get("notify") or {}, data.get("overrides") or {})

# ============================================================ core
def passes(t, cfg):
    tod = t.when.time()
    if tod < cfg.earliest or tod > cfg.latest:
        return False
    if cfg.holes is not None and t.holes is not None and t.holes != cfg.holes:
        return False
    if cfg.players_min > 1 and t.players is not None and t.players < cfg.players_min:
        return False
    if cfg.max_price is not None and t.price is not None and t.price > cfg.max_price:
        return False
    return True

def collect(cfg, debug=False):
    session = new_session()
    dates = cfg.target_dates()
    all_times = []
    for key in cfg.courses:
        course = CATALOG.get(key)
        if not course:
            print(f"[warn] unknown course '{key}'"); continue
        fn = PROVIDERS.get(course["provider"])
        if not fn:
            continue
        override = cfg.overrides.get(key, {})
        for day in dates:
            try:
                found = fn(session, key, course, day, override, debug)
            except Exception as e:
                print(f"[warn] {key} {day}: {e}"); found = []
            kept = [t for t in found if passes(t, cfg)]
            all_times.extend(kept)
            if debug:
                print(f"[debug] {key} {day}: {len(found)} raw, {len(kept)} kept")
            _time.sleep(0.7)
    return all_times

def run_once(cfg, seen_path="seen.json", debug=False):
    times = collect(cfg, debug)
    first_run = not Path(seen_path).exists()
    seen = load_seen(seen_path)
    new = [t for t in times if t.uid not in seen]
    for t in new:
        seen[t.uid] = t.when.date().isoformat()
    save_seen(seen_path, seen)
    print(f"[run] {len(times)} matching, {len(new)} new{' (first run: primed, no per-slot alerts)' if first_run else ''}")
    if first_run:
        # Prime the baseline quietly; send ONE friendly summary instead of spamming.
        notify_text(cfg.notify, "⛳ Looper is live!",
                    f"Watching {len(cfg.courses)} Long Island courses for your tee-time dates. "
                    f"{len(times)} open slot(s) match your filters right now — from here I'll only "
                    f"ping you when NEW times open up. Good luck out there.")
        return []
    if new:
        notify_new(cfg.notify, new)
    return new

# ============================================================ cli
def cmd_run(a):
    run_once(load_config(a.config), a.state, a.debug)

def cmd_loop(a):
    cfg = load_config(a.config)
    interval = max(60, int(a.interval * 60))
    print(f"[loop] every {a.interval} min. Ctrl-C to stop.")
    while True:
        print(f"\n[loop] {datetime.now():%Y-%m-%d %H:%M:%S}")
        try:
            run_once(cfg, a.state, a.debug)
        except KeyboardInterrupt:
            print("\nstopped."); return
        except Exception as e:
            print("[loop] error:", e)
        try:
            _time.sleep(interval)
        except KeyboardInterrupt:
            print("\nstopped."); return

def cmd_selftest(a):
    cfg = load_config(a.config)
    dates = cfg.target_dates()
    print("Courses:", ", ".join(cfg.courses))
    print("Dates:", ", ".join(d.isoformat() for d in dates) or "(none)")
    print(f"Window {cfg.earliest}-{cfg.latest}, holes={cfg.holes or 'any'}, players>={cfg.players_min}")
    print("-" * 60)
    times = collect(cfg, debug=True)
    print("-" * 60)
    for t in sorted(times, key=lambda x: (x.course_key, x.when))[:40]:
        print(f"  {t.course_name:36} {t.when:%a %b %d}  {t.summary()}")
    print(f"\n{len(times)} matching tee times. (selftest sends no alerts.)")

def cmd_list(a):
    by = {}
    for k, c in CATALOG.items():
        by.setdefault(c["provider"], []).append((k, c["name"]))
    for prov in ("foreup", "teeitup", "chronogolf", "nassau"):
        print(f"\n[{prov}]")
        for k, n in sorted(by.get(prov, [])):
            print(f"  {k:20} {n}")

def cmd_test(a):
    cfg = load_config(a.config)
    notify_text(cfg.notify, "⛳ Looper — test alert",
                "If you got this, Looper alerts are working. Good luck out there.")
    print("Test sent via:", (cfg.notify.get("backend") or "ntfy"))

def main():
    p = argparse.ArgumentParser(description="Looper — never miss a tee time.")
    p.add_argument("command", choices=["run", "loop", "selftest", "list", "test-notify"])
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--state", default="seen.json")
    p.add_argument("--interval", type=float, default=10.0)
    p.add_argument("--debug", action="store_true")
    a = p.parse_args()
    {"run": cmd_run, "loop": cmd_loop, "selftest": cmd_selftest,
     "list": cmd_list, "test-notify": cmd_test}[a.command](a)

if __name__ == "__main__":
    main()
