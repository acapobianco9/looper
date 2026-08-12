# ⛳ Looper

*Never miss a tee time.*

Brand assets are in `assets/` (wordmark, dark version, and app icon — SVG + PNG).

Looper watches Long Island & NYC golf courses for **newly opened tee times** on the
dates you want to play, and **pushes an alert to your phone** with the open
times and a booking link the moment they show up.

You pick the courses, the dates, the time window, and how many players — it
polls the courses' own booking feeds on a schedule and only ever pings you for
times it hasn't already told you about.

---

## What it can watch

Run `python run.py list` for the full, current list. Highlights:

| Platform | Courses |
|---|---|
| **NY State Parks (ForeUp)** | Bethpage (all 5), Montauk Downs, Sunken Meadow, Rock Hill |
| **TeeItUp / GolfNow** | Smithtown Landing, Stonebridge, Middle Island, Cherry Creek, Great Rock, Bergen Point, and every NYC American Golf course (Douglaston, Clearview, Forest Park, Pelham/Split Rock, Van Cortlandt, Mosholu, Marine Park, Dyker Beach, Silver Lake) |
| **Chronogolf / Lightspeed** | Pine Hills, Beaver Island |

**Not supported (yet), and why:**
- **Nassau County** (Eisenhower, Cantiague) — their system requires a resident
  *Leisure Pass login* even to *view* times, so there's no feed to watch. The
  only way to automate it is to plug in your own login (ask me and I'll build
  that path).
- **Suffolk County** (Timber Point, West Sayville, Indian Island) — runs a
  system whose rules forbid automated access. Can be revisited carefully.

---

## Quick start (5 minutes)

### 1. Get the alerts working
Two good options — pick one in `config.yaml` under `notify: backend:`.

**Free push (ntfy):**
1. Install the **ntfy** app ([iPhone](https://apps.apple.com/us/app/ntfy/id1625396347) / [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)).
2. In the app, tap **+** and subscribe to a **topic** — a long, secret string,
   e.g. `amg-golf-a7f3k92xq`. (Anyone who knows the topic can ping you.)
3. Put that same string in `config.yaml` under `notify: topic:`.

**Real SMS text (Twilio):** set `backend: sms` and add your Twilio
`account_sid`, `auth_token`, `from` (your Twilio number) and `to` (your cell) —
ideally as env vars `TWILIO_SID / TWILIO_TOKEN / TWILIO_FROM / TWILIO_TO`.
A Twilio number is ~$1.15/mo plus ~$0.008 per text. `to` can be several numbers,
comma-separated.

### 2. Configure what you want
```bash
cp config.example.yaml config.yaml
```
Edit `config.yaml`: choose `courses`, set `dates`/`weekdays`, your `time_window`,
and filters. `python run.py list` shows valid course keys.

### 3. Test it
```bash
pip install -r requirements.txt
python run.py test-notify     # should buzz your phone
python run.py selftest        # shows the open times it can see right now
```
`selftest` prints what each course returns. If a course shows nothing and you
think it should, run `python run.py classes <course_key>` to fill in a missing
id (see **Filling in IDs** below).

### 4. Let it run for real
```bash
python run.py run     # one pass — this is what the scheduler calls
```

---

## Running it 24/7 — recommended: GitHub Actions (free, always on)

Your PC isn't always on, and tee times often drop overnight (Bethpage releases
new inventory at **7:00 PM** daily). The simplest always-on option that costs
nothing and needs no server is **GitHub Actions** — a workflow file is already
included at `.github/workflows/watch.yml`.

1. Create a free GitHub account and a **private** repo; push this folder to it.
2. Repo → **Settings → Secrets and variables → Actions** → add a secret
   `NTFY_TOPIC` = your secret topic string.
3. Repo → **Settings → Actions → General → Workflow permissions** → enable
   **Read and write permissions** (lets it save `seen.json` so you aren't
   re-alerted).
4. That's it. It checks every 10 minutes and pushes when new times appear.
   (GitHub's scheduler can lag a few minutes under load — fine for this.)

> Want me to walk you through the GitHub setup, or set it up on your own PC with
> Windows Task Scheduler instead? Just ask.

### Alternative: run on your own PC
```bash
python run.py loop --interval 10
```
Leave that running in a terminal, or wire `python run.py run` into **Windows
Task Scheduler** every 10–15 minutes. Free, but only checks while the PC is on.

---

## Filling in IDs

Most courses are ready out of the box. A few need one id discovered from your
own network (some are blank in the catalog on purpose):

```bash
python run.py classes sunken_meadow   # ForeUp booking_class
python run.py classes pine_hills      # Chronogolf course UUID
python run.py classes clearview       # TeeItUp facility id (usually auto-resolves)
```
It prints the candidate ids and tells you where to paste them (catalog or the
`overrides:` block in `config.yaml`).

**Resident vs non-resident (Bethpage etc.):** the default shows *non-resident*
inventory. If you're a verified NY resident and know your resident
`booking_class` id (run the `classes` command to list them), set it under
`overrides:` to see the earlier resident release window.

---

## How it works

```
config.yaml ──► core ──► providers (foreup / teeitup / chronogolf)  ──► booking feeds
                 │                                                        (public JSON)
                 ├─ filter by date / time / holes / players / price
                 ├─ de-dup against seen.json  (only NEW times)
                 └─ notify  (ntfy push, or pushover / console)
```

- **`teewatch/catalog.py`** — the course list and their ids. Add courses here.
- **`teewatch/providers/`** — one file per booking platform.
- **`seen.json`** — remembers what it already alerted on (auto-pruned).

## Notes & honesty
- These are the booking sites' *own* internal feeds, read the same way your
  browser reads them, with no login and modest request rates. They're
  undocumented and can change without notice — if a course stops returning
  data, a field name probably moved; run `selftest --debug` and it's a quick fix.
- Nothing here books for you or bypasses any queue — it only *watches* and
  *tells you*. You book in the app as normal.
- NY State actively discourages booking *bots*; this is a personal watcher, not
  a booking bot. Keep the schedule reasonable (the 10-minute default is fine).

## Commands
```
python run.py run            one pass; push alerts for new times (use on a schedule)
python run.py loop           poll forever locally (--interval MINUTES)
python run.py selftest       show what's open now (no alerts) — add --debug for detail
python run.py list           list watchable courses (and unsupported ones)
python run.py classes KEY    discover missing ids for a course
python run.py test-notify    send one test push
```
