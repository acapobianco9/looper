"""Tiny JSON-file state store so we only alert on tee times we haven't seen.

Stores {uid: last_seen_iso}. Entries for tee times whose date has passed are
pruned on save so the file doesn't grow forever.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path


class SeenStore:
    def __init__(self, path: str = "seen.json"):
        self.path = Path(path)
        self._data: dict[str, str] = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def is_new(self, uid: str) -> bool:
        return uid not in self._data

    def mark(self, uid: str, tee_date: date | None = None) -> None:
        # store the tee date so we can prune later; fall back to today
        stamp = (tee_date or date.today()).isoformat()
        self._data[uid] = stamp

    def prune(self, today: date | None = None) -> None:
        today = today or date.today()
        self._data = {
            uid: d for uid, d in self._data.items()
            if _safe_date(d) >= today
        }

    def save(self) -> None:
        self.prune()
        self.path.write_text(json.dumps(self._data, indent=0, sort_keys=True))


def _safe_date(s: str) -> date:
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return date.today()
