"""Chronogolf / Lightspeed provider — Pine Hills, Beaver Island.

Public read endpoint (no login to VIEW availability):
  GET https://www.chronogolf.com/marketplace/v2/teetimes
      ?start_date=YYYY-MM-DD&course_ids=<UUID>&holes=9,18&start_time=05:00&page=1

`course_ids` is a UUID (not numeric). Response is a JSON array; each element
has a local `start_time` and a `green_fees` list.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from ..models import TeeTime
from .base import Provider

API = "https://www.chronogolf.com/marketplace/v2/teetimes"
NY = ZoneInfo("America/New_York")


class ChronogolfProvider(Provider):
    name = "chronogolf"

    def fetch(self, course_key, course, day, override=None) -> list[TeeTime]:
        uuid = course.get("course_uuid")
        if not uuid:
            self._log(course_key, "no course_uuid set — skipping. Run: python run.py classes", course_key)
            return []
        params = {
            "start_date": day.strftime("%Y-%m-%d"),
            "course_ids": uuid,
            "holes": "9,18",
            "start_time": "05:00",
            "page": "1",
        }
        r = self.session.get(API, params=params, timeout=25)
        self._log(course_key, day, "->", r.status_code, f"{len(r.text)}b")
        if r.status_code != 200:
            return []
        try:
            data = r.json()
        except ValueError:
            return []
        if isinstance(data, dict):
            data = data.get("teetimes") or data.get("data") or []

        out: list[TeeTime] = []
        for row in data:
            out.extend(self._parse(course_key, course, row))
        return out

    def _parse(self, course_key, course, row: dict) -> list[TeeTime]:
        if row.get("out_of_capacity"):
            return []
        when = _to_local(row.get("start_time") or row.get("date_time") or row.get("datetime"))
        if not when:
            return []
        fees = row.get("green_fees") or row.get("greenFees") or []
        players = _int(row.get("players")) or _player_range(row)

        by_holes: dict[Optional[int], list] = {}
        if fees:
            for fee in fees:
                holes = _int(fee.get("holes"))
                price = _num(fee.get("price"), fee.get("green_fee"))
                by_holes.setdefault(holes, []).append(price)
        else:
            by_holes[None] = [None]

        results = []
        for holes, prices in by_holes.items():
            valid = [p for p in prices if p is not None]
            results.append(TeeTime(
                course_key=course_key,
                course_name=course["name"],
                when=when,
                holes=holes,
                players=players,
                price=min(valid) if valid else None,
                booking_url=course.get("booking_url", ""),
                raw=row,
            ))
        return results


def _to_local(s) -> Optional[datetime]:
    if not s:
        return None
    txt = str(s).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        try:
            dt = datetime.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(NY).replace(tzinfo=None)
    return dt


def _player_range(row: dict):
    pr = row.get("player_range") or row.get("players_range") or {}
    if isinstance(pr, dict) and pr.get("to") is not None:
        return _int(pr["to"])
    return None


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
