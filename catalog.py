"""Built-in catalog of Long Island / NYC golf courses and how to reach their
tee-time feeds.

Each entry is keyed by a short slug you use in config.yaml (under `courses:`).

Fields:
  name        human label
  provider    "foreup" | "teeitup" | "chronogolf"
  booking_url where a human goes to book (also used as the notification click link)
  ...plus provider-specific ids (see each provider module).

VERIFICATION STATUS
-------------------
IDs marked  ✅  were confirmed against the live booking page during research.
IDs marked  ⚠️  still need confirming in YOUR environment — run:  python run.py selftest
The teeitup provider can auto-resolve a numeric facility id from its `alias`
(the course's book.teeitup.com sub-domain) at runtime, so those work even
where `facility_id` is left blank.
"""

CATALOG: dict[str, dict] = {
    # ------------------------------------------------------------------ ForeUp
    # NY State Parks courses. Availability is public (no login to read).
    # booking_class picks the golfer type; non-resident shown by default.
    # If you are a verified NY resident you'll see more inventory — set your
    # resident booking_class id in config once you know it (see README).
    "bethpage": {
        "name": "Bethpage State Park (all 5 courses)",
        "provider": "foreup",
        "course_id": 19765,                       # ✅
        "schedule_ids": [2517, 2431, 2433, 2539, 2538, 2434, 2432, 2435],  # ✅ Black/Red/Blue/Green/Yellow + sheets
        "booking_class": 2137,                    # ✅ Non-Resident
        "booking_url": "https://foreupsoftware.com/index.php/booking/19765/2431#teetimes",
    },
    "montauk_downs": {
        "name": "Montauk Downs State Park",
        "provider": "foreup",
        "course_id": 19756,                       # ✅
        "schedule_ids": [2436],                   # ✅
        "booking_class": 2155,                    # ✅ Non-Resident
        "booking_url": "https://foreupsoftware.com/index.php/booking/19756/2436#teetimes",
    },
    "sunken_meadow": {
        "name": "Sunken Meadow State Park (Red/Green/Blue)",
        "provider": "foreup",
        "course_id": 19766,                       # ✅
        "schedule_ids": [2437],                   # ✅
        "booking_class": None,                    # ⚠️ discover with: python run.py classes sunken_meadow
        "booking_url": "https://foreupsoftware.com/index.php/booking/19766/2437#teetimes",
    },
    "rock_hill": {
        "name": "Rock Hill Golf & Country Club (Manorville)",
        "provider": "foreup",
        "course_id": 20662,                       # ✅
        "schedule_ids": [],                       # ⚠️ discover: python run.py classes rock_hill
        "booking_class": None,                    # ⚠️
        "booking_url": "https://foreupsoftware.com/index.php/booking/20662#/teetimes",
    },

    # ------------------------------------------------------------------ TeeItUp / GolfNow
    # facility_id is the numeric ?course= value on the booking page.
    # If left as None, the provider resolves it from `alias` at runtime.
    "smithtown_landing": {
        "name": "Smithtown Landing Country Club",
        "provider": "teeitup",
        "alias": "smithtown-landing-country-club",     # .book.teeitup.com
        "facility_id": None,                            # ⚠️ auto-resolved
        "booking_url": "https://smithtown-landing-country-club.book.teeitup.com",
    },
    "stonebridge": {
        "name": "Stonebridge Golf Links & CC (Smithtown)",
        "provider": "teeitup",
        "alias": "stonebridge-golf-links-and-country-club",
        "tld": "golf",                                  # this one is .book.teeitup.golf
        "facility_id": None,
        "booking_url": "https://stonebridge-golf-links-and-country-club.book.teeitup.golf/",
    },
    "middle_island": {
        "name": "Middle Island Country Club",
        "provider": "teeitup",
        "alias": "middle-island-country-club",
        "tld": "golf",
        "facility_id": None,
        "booking_url": "https://middle-island-country-club.book.teeitup.golf/",
    },
    "great_rock": {
        "name": "Great Rock Golf Club (Wading River)",
        "provider": "teeitup",
        "alias": "great-rock-golf-club",
        "facility_id": None,
        "booking_url": "https://go.teeitup.com/3862",
    },
    "cherry_creek": {
        "name": "Cherry Creek Golf Links (Riverhead)",
        "provider": "teeitup",
        "alias": "the-woods-at-cherry-creek",
        "tld": "golf",
        "facility_id": None,
        "booking_url": "https://the-woods-at-cherry-creek.book.teeitup.golf/",
    },
    "bergen_point": {
        "name": "Bergen Point Golf Course (Babylon)",
        "provider": "teeitup",
        "alias": "bergen-point-golf-course",
        "facility_id": None,
        "booking_url": "https://bergen-point-golf-course.book.teeitup.com/",
    },
    # --- NYC municipals (American Golf), all on TeeItUp ---
    "douglaston": {
        "name": "Douglaston Golf Course (Queens)",
        "provider": "teeitup",
        "alias": "douglaston-golf-course",
        "facility_id": 5044,                            # ✅
        "booking_url": "https://douglaston-golf-course.book.teeitup.com/?course=5044",
    },
    "clearview": {
        "name": "Clearview Park Golf Course (Queens)",
        "provider": "teeitup",
        "alias": "clearview-park-golf-course",
        "facility_id": None,
        "booking_url": "https://clearview-park-golf-course.book.teeitup.com/",
    },
    "forest_park": {
        "name": "Forest Park Golf Course (Queens)",
        "provider": "teeitup",
        "alias": "forest-park-golf-course",
        "facility_id": None,
        "booking_url": "https://forest-park-golf-course.book.teeitup.com/",
    },
    "pelham_split_rock": {
        "name": "Pelham / Split Rock Golf Courses (Bronx)",
        "provider": "teeitup",
        "alias": "pelham-split-rock-golf-courses",
        "facility_id": None,
        "booking_url": "https://pelham-split-rock-golf-courses.book.teeitup.com/",
    },
    "van_cortlandt": {
        "name": "Van Cortlandt Park Golf Course (Bronx)",
        "provider": "teeitup",
        "alias": "van-cortlandt-golf-course",
        "facility_id": None,
        "booking_url": "https://van-cortlandt-golf-course.book.teeitup.com/",
    },
    "mosholu": {
        "name": "Mosholu Golf Course (Bronx)",
        "provider": "teeitup",
        "alias": "mosholu-golf-course",
        "facility_id": None,
        "booking_url": "https://mosholu-golf-course.book.teeitup.com/",
    },
    "marine_park": {
        "name": "Marine Park Golf Course (Brooklyn)",
        "provider": "teeitup",
        "alias": "marine-park-golf-course",
        "facility_id": None,
        "booking_url": "https://marine-park-golf-course.book.teeitup.com/",
    },
    "dyker_beach": {
        "name": "Dyker Beach Golf Course (Brooklyn)",
        "provider": "teeitup",
        "alias": "dyker-beach-golf-course",
        "facility_id": None,
        "booking_url": "https://dyker-beach-golf-course.book.teeitup.com/",
    },
    "silver_lake": {
        "name": "Silver Lake Golf Course (Staten Island)",
        "provider": "teeitup",
        "alias": "silver-lake-golf-course",
        "facility_id": None,
        "booking_url": "https://silver-lake-golf-course.book.teeitup.com/",
    },
    "split_rock": {
        "name": "Split Rock Golf Course (Bronx)",
        "provider": "teeitup",
        "alias": "split-rock-golf-course",
        "facility_id": None,
        "booking_url": "https://split-rock-golf-course.book.teeitup.com/",
    },

    # ------------------------------------------------------------------ Chronogolf / Lightspeed
    "pine_hills": {
        "name": "Pine Hills Country Club (Manorville)",
        "provider": "chronogolf",
        "course_uuid": None,                            # ⚠️ discover: python run.py classes pine_hills
        "booking_url": "https://www.chronogolf.com/club/pine-hills-country-club-new-york",
    },
    "beaver_island": {
        "name": "Beaver Island State Park (Grand Island)",
        "provider": "chronogolf",
        "course_uuid": "609f6a83-10b5-47d5-a79a-203c3e17f231",  # ✅
        "booking_url": "https://www.chronogolf.com/club/beaver-island-state-park-golf-club",
    },

    # ------------------------------------------------------------------ Nassau County (login-walled)
    # ⚠️ Requires your resident Leisure Pass login AND the authenticated
    # availability endpoint captured from a real session (see nassau.py header).
    # Set credentials via env NASSAU_USER / NASSAU_PASS. `availability_url` must
    # be filled in before this returns times — Looper won't guess it.
    "nassau_eisenhower": {
        "name": "Eisenhower Park (Red / White / Blue)",
        "provider": "nassau",
        "login_url": "https://golf.nassaucountyny.gov/login",
        "user_field": "email",              # ⚠️ confirm real field name
        "availability_url": None,           # ⚠️ e.g. ".../tee-times?date={date}&course={course_id}"
        "course_id": "",                    # ⚠️
        "booking_url": "https://golf.nassaucountyny.gov/",
    },
    "nassau_cantiague": {
        "name": "Cantiague Park Golf Course",
        "provider": "nassau",
        "login_url": "https://golf.nassaucountyny.gov/login",
        "user_field": "email",
        "availability_url": None,           # ⚠️
        "course_id": "",                    # ⚠️
        "booking_url": "https://golf.nassaucountyny.gov/",
    },
}


# Courses that exist but can't be watched automatically, with the reason.
# Surfaced by `python run.py list` so expectations stay clear.
UNSUPPORTED: dict[str, str] = {
    "nassau_*": "Nassau County (Eisenhower, Cantiague) — now in the catalog as `nassau_eisenhower` "
                "/ `nassau_cantiague`, but LOGIN-ONLY: needs your Leisure Pass login + the "
                "authenticated endpoint captured once (see teewatch/providers/nassau.py).",
    "suffolk_county": "Suffolk County (Timber Point, West Sayville, Indian Island) — runs "
                      "Vermont Systems WebTrac; its rules forbid automated access (robots.txt).",
    "willow_creek": "Willow Creek (Mt. Sinai) — public times are on GolfBack; endpoint not yet "
                    "reverse-engineered. Ask to add if you want it.",
}


def get(course_key: str) -> dict:
    if course_key not in CATALOG:
        raise KeyError(
            f"Unknown course '{course_key}'. Run `python run.py list` to see valid keys."
        )
    return CATALOG[course_key]
