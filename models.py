"""Core data model: a single tee time, normalized across every booking platform."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class TeeTime:
    """A normalized tee time from any provider.

    Every provider converts its raw JSON into this shape so the rest of the
    app (filtering, de-dup, notifications) never has to care which platform a
    time came from.
    """
    course_key: str          # catalog key, e.g. "bethpage"
    course_name: str         # human label, e.g. "Bethpage Black Course"
    when: datetime           # tee time in the COURSE's local time (naive, America/New_York)
    holes: Optional[int]     # 9, 18, or None if unknown
    players: Optional[int]   # max players bookable in this slot
    price: Optional[float]   # green fee in USD (walking rate when available)
    booking_url: str         # where to go to actually book
    raw: dict = field(default_factory=dict, repr=False)  # original object, for debugging

    @property
    def date_str(self) -> str:
        return self.when.strftime("%Y-%m-%d")

    @property
    def time_str(self) -> str:
        # 7:05a / 1:40p style
        s = self.when.strftime("%-I:%M%p").lower()
        return s.replace("am", "a").replace("pm", "p")

    @property
    def uid(self) -> str:
        """Stable identity for a slot, so we only alert on genuinely new times.

        Keyed on course + exact datetime + holes. Price/availability are
        intentionally excluded so a price tweak doesn't re-alert, but a brand
        new slot at a new time does.
        """
        basis = f"{self.course_key}|{self.when.isoformat()}|{self.holes}"
        return hashlib.sha1(basis.encode()).hexdigest()[:16]

    def summary(self) -> str:
        bits = [self.time_str]
        if self.holes:
            bits.append(f"{self.holes}h")
        if self.players:
            bits.append(f"{self.players}p")
        if self.price is not None:
            bits.append(f"${self.price:g}")
        return " · ".join(bits)
