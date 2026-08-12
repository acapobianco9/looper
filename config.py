"""Load and validate config.yaml, and expand the date rules into concrete dates."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Optional

import yaml

_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _parse_time(s: str | None, default: time) -> time:
    if not s:
        return default
    return datetime.strptime(str(s).strip(), "%H:%M").time()


@dataclass
class Config:
    courses: list[str]
    # date selection
    dates: list[date]
    weekdays: list[int]
    horizon_days: int
    # per-day time window (course local time)
    earliest: time
    latest: time
    # slot filters
    holes: Optional[int]        # 9, 18, or None = any
    players_min: int
    max_price: Optional[float]
    # notification
    notify: dict
    # per-course overrides (e.g. booking_class)
    overrides: dict = field(default_factory=dict)

    def target_dates(self, today: Optional[date] = None) -> list[date]:
        """Concrete list of dates to check: explicit `dates` plus any `weekdays`
        falling within `horizon_days` from today. Past dates are dropped."""
        today = today or date.today()
        out: set[date] = set()
        for d in self.dates:
            if d >= today:
                out.add(d)
        if self.weekdays:
            for i in range(self.horizon_days + 1):
                d = today + timedelta(days=i)
                if d.weekday() in self.weekdays:
                    out.add(d)
        return sorted(out)

    def override_for(self, course_key: str) -> dict:
        return self.overrides.get(course_key, {})


def load(path: str | os.PathLike = "config.yaml") -> Config:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Config file not found: {p}. Copy config.example.yaml to config.yaml and edit it."
        )
    data = yaml.safe_load(p.read_text()) or {}

    courses = data.get("courses") or []
    if not courses:
        raise ValueError("config.yaml has no `courses:` — add at least one course key.")

    # dates: accept YYYY-MM-DD strings or date objects
    raw_dates = data.get("dates") or []
    dates: list[date] = []
    for d in raw_dates:
        if isinstance(d, date):
            dates.append(d)
        else:
            dates.append(datetime.strptime(str(d).strip(), "%Y-%m-%d").date())

    weekdays: list[int] = []
    for w in (data.get("weekdays") or []):
        key = str(w).strip().lower()[:3]
        if key not in _WEEKDAYS:
            raise ValueError(f"Bad weekday '{w}'. Use Mon/Tue/Wed/Thu/Fri/Sat/Sun.")
        weekdays.append(_WEEKDAYS[key])

    window = data.get("time_window") or {}
    filt = data.get("filters") or {}
    holes = filt.get("holes")
    holes = None if holes in (None, "any", "Any", "ANY") else int(holes)

    return Config(
        courses=list(courses),
        dates=dates,
        weekdays=weekdays,
        horizon_days=int(data.get("horizon_days", 7)),
        earliest=_parse_time(window.get("earliest"), time(5, 0)),
        latest=_parse_time(window.get("latest"), time(20, 0)),
        holes=holes,
        players_min=int(filt.get("players_min", 1)),
        max_price=(float(filt["max_price"]) if filt.get("max_price") not in (None, "") else None),
        notify=data.get("notify") or {},
        overrides=data.get("overrides") or {},
    )
