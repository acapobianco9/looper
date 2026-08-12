"""Orchestration: fetch every configured course/date, filter, de-dup, notify."""
from __future__ import annotations

import time as _time
from datetime import date

from . import catalog
from .config import Config
from .models import TeeTime
from .notify import Notifier
from .providers import get_provider, make_session
from .state import SeenStore


def collect(cfg: Config, debug: bool = False, only_course: str | None = None) -> list[TeeTime]:
    """Fetch all matching tee times across configured courses and dates."""
    session = make_session()
    providers: dict[str, object] = {}
    dates = cfg.target_dates()
    course_keys = [only_course] if only_course else cfg.courses

    all_times: list[TeeTime] = []
    for course_key in course_keys:
        try:
            course = catalog.get(course_key)
        except KeyError as e:
            print(f"[warn] {e}")
            continue
        pname = course["provider"]
        if pname not in providers:
            providers[pname] = get_provider(pname, session=session, debug=debug)
        provider = providers[pname]
        override = cfg.override_for(course_key)

        for day in dates:
            try:
                found = provider.fetch(course_key, course, day, override)
            except Exception as e:
                print(f"[warn] {course_key} {day}: {e}")
                found = []
            kept = [t for t in found if _passes(t, cfg)]
            all_times.extend(kept)
            if debug:
                print(f"[debug] {course_key} {day}: {len(found)} raw, {len(kept)} after filter")
            _time.sleep(0.7)  # be polite to the booking servers
    return all_times


def _passes(t: TeeTime, cfg: Config) -> bool:
    # time-of-day window
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


def run_once(cfg: Config, seen_path: str = "seen.json", debug: bool = False,
             quiet: bool = False) -> list[TeeTime]:
    """One polling pass. Returns the list of NEW tee times (also notified)."""
    times = collect(cfg, debug=debug)
    store = SeenStore(seen_path)
    new_times = [t for t in times if store.is_new(t.uid)]
    for t in new_times:
        store.mark(t.uid, t.when.date())
    store.save()

    if not quiet:
        print(f"[run] {len(times)} matching tee times, {len(new_times)} new")
    if new_times:
        Notifier(cfg.notify).send_new_times(new_times)
    return new_times
