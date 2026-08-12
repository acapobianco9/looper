"""Helpers to fill in the IDs the catalog leaves blank, by reading the course's
own booking page. Run against YOUR network (these hosts are blocked in some
sandboxes):  python run.py classes <course_key>
"""
from __future__ import annotations

import re

from . import catalog
from .providers.base import make_session


def discover(course_key: str) -> None:
    course = catalog.get(course_key)
    provider = course["provider"]
    s = make_session()
    print(f"\n=== discovering IDs for {course_key} ({course['name']}, {provider}) ===")

    if provider == "foreup":
        _foreup(s, course)
    elif provider == "chronogolf":
        _chronogolf(s, course)
    elif provider == "teeitup":
        _teeitup(s, course)
    else:
        print("no discovery for this provider")


def _foreup(s, course):
    cid = course.get("course_id")
    # 1) booking-class list endpoint
    for url in (
        f"https://foreupsoftware.com/index.php/api/booking/users/booking_classes?course_id={cid}",
        course.get("booking_url", ""),
    ):
        if not url:
            continue
        try:
            r = s.get(url, timeout=25)
        except Exception as e:
            print(f"  {url} -> error {e}")
            continue
        print(f"  {url} -> {r.status_code}")
        # ids that look like booking classes / schedules
        classes = re.findall(r'"(?:booking_class_id|id)"\s*:\s*(\d+)\s*,\s*"(?:name|title)"\s*:\s*"([^"]+)"', r.text)
        if classes:
            print("  candidate booking classes (id : name):")
            for cid_, name in dict(classes).items():
                print(f"    {cid_} : {name}")
        sids = sorted(set(re.findall(r'"schedule_id"\s*:\s*(\d+)', r.text)))
        if sids:
            print("  schedule_ids seen:", ", ".join(sids))
    print("  → put the resident/non-resident id you want in config overrides: "
          f"\n      overrides:\n        {_key(course)}:\n          booking_class: <id>")


def _chronogolf(s, course):
    url = course.get("booking_url", "")
    try:
        r = s.get(url, timeout=25)
    except Exception as e:
        print(f"  {url} -> error {e}")
        return
    print(f"  {url} -> {r.status_code}")
    uuids = re.findall(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', r.text)
    ids = sorted(set(uuids))
    if ids:
        print("  candidate course UUID(s) — set course_uuid in the catalog:")
        for u in ids[:8]:
            print("    ", u)
    else:
        print("  no UUID found; open the booking page and check the network tab for course_ids=")


def _teeitup(s, course):
    from .providers.teeitup import _find_facility_id
    origin = f"https://{course['alias']}.book.teeitup.{course.get('tld','com')}/"
    try:
        r = s.get(origin, timeout=25)
    except Exception as e:
        print(f"  {origin} -> error {e}")
        return
    print(f"  {origin} -> {r.status_code}")
    fid = _find_facility_id(r.text)
    print("  facility_id:", fid if fid else "not found (check ?course= in the booking URL)")


def _key(course):
    for k, v in catalog.CATALOG.items():
        if v is course:
            return k
    return "<course_key>"
