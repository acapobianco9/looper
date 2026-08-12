#!/usr/bin/env python3
"""Looper CLI — never miss a tee time.

Commands:
  python run.py run            One polling pass; push alerts for NEW times. (use this on a schedule)
  python run.py loop           Poll forever locally (default every 10 min).
  python run.py selftest       Hit every configured course/date and print what's found (no de-dup).
  python run.py list           Show all courses you can watch (and ones you can't, with why).
  python run.py classes KEY    Discover the missing IDs for a course (booking_class / uuid / facility).
  python run.py test-notify    Send a single test push so you know alerts work.

Options: --config PATH  --state PATH  --debug  --interval MINUTES  (loop only)
"""
from __future__ import annotations

import argparse
import sys
import time as _time
from datetime import datetime

from teewatch import catalog, config as cfgmod
from teewatch.core import collect, run_once
from teewatch.discover import discover
from teewatch.notify import Notifier


def cmd_run(args):
    cfg = cfgmod.load(args.config)
    run_once(cfg, seen_path=args.state, debug=args.debug)


def cmd_loop(args):
    cfg = cfgmod.load(args.config)
    interval = max(60, int(args.interval * 60))
    print(f"[loop] polling every {args.interval} min. Ctrl-C to stop.")
    while True:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[loop] {stamp}")
        try:
            run_once(cfg, seen_path=args.state, debug=args.debug)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"[loop] error: {e}")
        try:
            _time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[loop] stopped.")
            return


def cmd_selftest(args):
    cfg = cfgmod.load(args.config)
    dates = cfg.target_dates()
    print(f"Config OK. Courses: {', '.join(cfg.courses)}")
    print(f"Target dates: {', '.join(d.isoformat() for d in dates) or '(none — check dates/weekdays)'}")
    print(f"Window {cfg.earliest}–{cfg.latest}, holes={cfg.holes or 'any'}, "
          f"players>={cfg.players_min}, max_price={cfg.max_price}")
    print("-" * 60)
    times = collect(cfg, debug=True)
    print("-" * 60)
    if not times:
        print("No matching tee times right now. That can be normal (nothing open yet),")
        print("or an ID may need filling in — run:  python run.py classes <course_key>")
        return
    for t in sorted(times, key=lambda x: (x.course_key, x.when))[:40]:
        print(f"  {t.course_name:38} {t.when:%a %b %d}  {t.summary()}")
    print(f"\n{len(times)} matching tee times found. (selftest does not send pushes.)")


def cmd_list(args):
    print("Courses you can watch (use the key in config.yaml `courses:`):\n")
    by_provider: dict[str, list] = {}
    for key, c in catalog.CATALOG.items():
        by_provider.setdefault(c["provider"], []).append((key, c["name"]))
    for prov in ("foreup", "teeitup", "chronogolf"):
        print(f"  [{prov}]")
        for key, name in sorted(by_provider.get(prov, [])):
            print(f"    {key:20} {name}")
        print()
    print("Not available automatically:\n")
    for key, why in catalog.UNSUPPORTED.items():
        print(f"    {key:20} {why}")


def cmd_classes(args):
    if not args.key:
        print("Usage: python run.py classes <course_key>")
        sys.exit(1)
    discover(args.key)


def cmd_test_notify(args):
    cfg = cfgmod.load(args.config)
    n = Notifier(cfg.notify)
    n.send_text("⛳ Looper — test alert",
                "If you got this on your phone, Looper alerts are working. Good luck out there.")
    print("Sent a test notification via backend:", n.backend)


def main():
    p = argparse.ArgumentParser(description="Watch LI/NYC golf courses for open tee times.")
    p.add_argument("command",
                   choices=["run", "loop", "selftest", "list", "classes", "test-notify"])
    p.add_argument("key", nargs="?", help="course key (for `classes`)")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--state", default="seen.json")
    p.add_argument("--interval", type=float, default=10.0, help="loop interval in minutes")
    p.add_argument("--debug", action="store_true")
    args = p.parse_args()

    {
        "run": cmd_run,
        "loop": cmd_loop,
        "selftest": cmd_selftest,
        "list": cmd_list,
        "classes": cmd_classes,
        "test-notify": cmd_test_notify,
    }[args.command](args)


if __name__ == "__main__":
    main()
