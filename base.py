"""Provider base class + shared HTTP session."""
from __future__ import annotations

from datetime import date
from typing import Optional

import requests

from ..models import TeeTime

# A realistic desktop User-Agent. These are the booking sites' own internal
# APIs; we identify as a normal browser and keep request rates modest.
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": _UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return s


class Provider:
    """One booking platform. Subclasses turn (course, date) into TeeTimes."""

    name = "base"

    def __init__(self, session: Optional[requests.Session] = None, debug: bool = False):
        self.session = session or make_session()
        self.debug = debug

    def fetch(self, course_key: str, course: dict, day: date,
              override: dict | None = None) -> list[TeeTime]:
        raise NotImplementedError

    # helper for subclasses
    def _log(self, *a):
        if self.debug:
            print("[debug]", self.name, *a)
