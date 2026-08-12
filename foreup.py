"""ForeUp provider — NY State Parks courses (Bethpage, Montauk Downs, Sunken
Meadow) and Rock Hill.

Public read endpoint (no login needed to VIEW availability):
  GET https://foreupsoftware.com/index.php/api/booking/times
      ?time=all&date=MM-DD-YYYY&holes=all&players=0
      &booking_class=<id>&schedule_id=<id>&schedule_ids[]=<id>...
      &specials_only=0&api_key=no_limits

Returns a JSON array of tee-time objects. Field names seen in the wild:
  time            "YYYY-MM-DD HH:MM"  (course local time)
  available_spots int
  holes           int
  green_fee       number
  course_name / schedule / teesheet_name  string
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from ..models import TeeTime
from .base import Provider

API = "https://foreupsoftware.com/index.php/api/booking/times"


class ForeUpProvider(Provider):
    name = "foreup"

    def fetch(self, course_key, course, day, override=None) -> list[TeeTime]:
        override = override or {}
        booking_class = override.get("booking_class", course.get("booking_class"))
        schedule_ids = course.get("schedule_ids") or []
        course_id = course.get("course_id")

        if booking_class is None:
            self._log(course_key, "no booking_class set — skipping. Run: python run.py classes", course_key)
            return []

        params = [
            ("time", "all"),
            ("date", day.strftime("%m-%d-%Y")),
            ("holes", "all"),
            ("players", "0"),
            ("booking_class", str(booking_class)),
            ("specials_only", "0"),
            ("api_key", "no_limits"),
        ]
        if schedule_ids:
            params.append(("schedule_id", str(schedule_ids[0])))
            for sid in schedule_ids:
                params.append(("schedule_ids[]", str(sid)))
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": course.get("booking_url", "https://foreupsoftware.com/"),
        }
        r = self.session.get(API, params=params, headers=headers, timeout=25)
        self._log(course_key, day, "->", r.status_code, f"{len(r.text)}b")
        if r.status_code != 200:
            return []
        try:
            data = r.json()
        except ValueError:
            return []
        if isinstance(data, dict):  # some responses wrap the array
            data = data.get("times") or data.get("data") or []

        out: list[TeeTime] = []
        for row in data:
            tt = self._parse(course_key, course, row)
            if tt:
                out.append(tt)
        return out

    def _parse(self, course_key, course, row: dict) -> Optional[TeeTime]:
        when = _parse_dt(row.get("time"))
        if not when:
            return None
        holes = _int(row.get("holes"))
        players = _int(row.get("available_spots"))
        price = _num(row.get("green_fee"))
        cname = (row.get("course_name") or row.get("schedule")
                 or row.get("teesheet_name") or course["name"])
        return TeeTime(
            course_key=course_key,
            course_name=str(cname),
            when=when,
            holes=holes,
            players=players,
            price=price,
            booking_url=course.get("booking_url", ""),
            raw=row,
        )


def _parse_dt(s) -> Optional[datetime]:
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(s), fmt)
        except ValueError:
            continue
    return None


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
