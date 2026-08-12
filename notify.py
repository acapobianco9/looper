"""Push notifications. Default is ntfy.sh (free, no account). Pushover also
supported. Falls back to printing so the app is always testable.

Secrets are read from the environment first (so you never commit them), then
from the `notify:` block in config.yaml as a convenience for local use.
"""
from __future__ import annotations

import os
from typing import Iterable

import requests

from .models import TeeTime


class Notifier:
    def __init__(self, cfg: dict):
        self.cfg = cfg or {}
        self.backend = (self.cfg.get("backend") or "ntfy").lower()

    # ---- public API -----------------------------------------------------
    def send_new_times(self, times: list[TeeTime]) -> None:
        """Group new times by course+date and send one push per group."""
        if not times:
            return
        groups: dict[tuple, list[TeeTime]] = {}
        for t in times:
            groups.setdefault((t.course_key, t.date_str), []).append(t)

        for (course_key, date_str), slots in groups.items():
            slots.sort(key=lambda s: s.when)
            course_name = slots[0].course_name
            when = slots[0].when.strftime("%a %b %-d")
            title = f"⛳ {len(slots)} tee time{'s' if len(slots) != 1 else ''} — {course_name}, {when}"
            lines = [s.summary() for s in slots[:12]]
            if len(slots) > 12:
                lines.append(f"…and {len(slots) - 12} more")
            body = "\n".join(lines)
            self._dispatch(title, body, click=slots[0].booking_url)

    def send_text(self, title: str, body: str) -> None:
        self._dispatch(title, body, click=None)

    # ---- backends -------------------------------------------------------
    def _dispatch(self, title: str, body: str, click: str | None) -> None:
        try:
            if self.backend == "ntfy":
                self._ntfy(title, body, click)
            elif self.backend == "pushover":
                self._pushover(title, body, click)
            elif self.backend in ("sms", "twilio"):
                self._twilio(title, body, click)
            elif self.backend == "console":
                self._console(title, body, click)
            else:
                raise ValueError(f"Unknown notify backend '{self.backend}'")
        except Exception as e:  # never let a notify failure kill a run
            print(f"[notify] FAILED ({self.backend}): {e}")
            self._console(title, body, click)

    def _ntfy(self, title: str, body: str, click: str | None) -> None:
        server = self.cfg.get("server", "https://ntfy.sh")
        topic = os.environ.get("NTFY_TOPIC") or self.cfg.get("topic")
        if not topic:
            raise ValueError("ntfy needs a topic (env NTFY_TOPIC or notify.topic in config)")
        headers = {
            "Title": title.encode("utf-8"),
            "Priority": str(self.cfg.get("priority", "high")),
            "Tags": "golf",
        }
        if click:
            headers["Click"] = click
        token = os.environ.get("NTFY_TOKEN") or self.cfg.get("token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        r = requests.post(f"{server.rstrip('/')}/{topic}", data=body.encode("utf-8"),
                          headers=headers, timeout=20)
        r.raise_for_status()
        print(f"[notify] ntfy → {topic}: {title}")

    def _pushover(self, title: str, body: str, click: str | None) -> None:
        token = os.environ.get("PUSHOVER_TOKEN") or self.cfg.get("token")
        user = os.environ.get("PUSHOVER_USER") or self.cfg.get("user")
        if not (token and user):
            raise ValueError("pushover needs token + user (env PUSHOVER_TOKEN / PUSHOVER_USER)")
        payload = {"token": token, "user": user, "title": title, "message": body,
                   "priority": self.cfg.get("priority", 1)}
        if click:
            payload["url"] = click
            payload["url_title"] = "Book now"
        r = requests.post("https://api.pushover.net/1/messages.json", data=payload, timeout=20)
        r.raise_for_status()
        print(f"[notify] pushover: {title}")

    def _twilio(self, title: str, body: str, click: str | None) -> None:
        """Real SMS text via Twilio. Needs a Twilio account:
          - a phone number (~$1.15/mo) and ~$0.0079 per text
          - Account SID + Auth Token from console.twilio.com
        Secrets via env (TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM, TWILIO_TO) or
        the notify: block in config.yaml.
        """
        sid = os.environ.get("TWILIO_SID") or self.cfg.get("account_sid")
        token = os.environ.get("TWILIO_TOKEN") or self.cfg.get("auth_token")
        from_ = os.environ.get("TWILIO_FROM") or self.cfg.get("from")
        to = os.environ.get("TWILIO_TO") or self.cfg.get("to")
        if not all([sid, token, from_, to]):
            raise ValueError("Twilio SMS needs account_sid, auth_token, from, to "
                             "(env TWILIO_SID / TWILIO_TOKEN / TWILIO_FROM / TWILIO_TO)")
        # SMS is plain text: fold title + times + link into one compact message
        text = f"{title}\n{body}"
        if click:
            text += f"\n{click}"
        if len(text) > 1500:                 # stay well under carrier segment limits
            text = text[:1490] + "…"
        # allow multiple recipients: comma-separated
        for dest in [t.strip() for t in str(to).split(",") if t.strip()]:
            r = requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                data={"From": from_, "To": dest, "Body": text},
                auth=(sid, token), timeout=20,
            )
            if r.status_code >= 300:
                raise RuntimeError(f"Twilio {r.status_code}: {r.text[:200]}")
            print(f"[notify] sms → {dest}: {title}")

    def _console(self, title: str, body: str, click: str | None) -> None:
        print("\n" + "─" * 60)
        print(title)
        print(body)
        if click:
            print(f"→ {click}")
        print("─" * 60)
