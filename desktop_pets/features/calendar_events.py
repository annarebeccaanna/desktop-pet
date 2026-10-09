"""Termine aus ICS-Kalendern (reine Logik, ohne Qt): einlesen, Wiederholungen auflösen,
fällige Erinnerungen bestimmen, Besprechungslinks finden."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

JOIN_LINK = re.compile(
    r"https://(?:teams\.microsoft\.com/l/meetup-join|teams\.live\.com/meet|[\w.-]*zoom\.us/[jw]/|"
    r"meet\.google\.com/|[\w.-]*webex\.com/)[^\s<>\"'\\]+", re.IGNORECASE)


@dataclass(frozen=True)
class Event:
    uid: str
    title: str
    start: dt.datetime          # mit Zeitzone
    end: dt.datetime | None = None
    location: str = ""
    link: str = ""

    @property
    def key(self) -> str:
        return f"{self.uid}@{self.start.isoformat()}"


def find_link(*texts: str) -> str:
    for text in texts:
        m = JOIN_LINK.search(text or "")
        if m:
            return m.group(0).rstrip(".,;)>")
    return ""


def _aware(value) -> dt.datetime | None:
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.astimezone()   # „schwebende“ Zeit = Ortszeit
    return None                                                 # ganztägig (date) → keine Erinnerung


def parse_ics(data: bytes | str, now: dt.datetime, hours: float = 24.0) -> list[Event]:
    """Termine (inkl. Wiederholungen) zwischen jetzt und ``hours`` Stunden später."""
    import icalendar
    import recurring_ical_events

    cal = icalendar.Calendar.from_ical(data)
    end = now + dt.timedelta(hours=hours)
    events: list[Event] = []
    for comp in recurring_ical_events.of(cal, skip_bad_series=True).between(now - dt.timedelta(hours=1), end):
        if str(comp.get("STATUS", "")).upper() == "CANCELLED":
            continue
        start = _aware(comp.decoded("DTSTART")) if comp.get("DTSTART") else None
        if start is None:
            continue
        title = str(comp.get("SUMMARY", "") or "Termin")
        if title.lower().startswith(("abgesagt:", "canceled:", "cancelled:")):
            continue
        stop = _aware(comp.decoded("DTEND")) if comp.get("DTEND") else None
        location = str(comp.get("LOCATION", "") or "")
        description = str(comp.get("DESCRIPTION", "") or "")
        url = str(comp.get("URL", "") or "")
        events.append(Event(uid=str(comp.get("UID", title)), title=title, start=start, end=stop,
                            location=location, link=find_link(url, location, description)))
    return sorted(events, key=lambda e: e.start)


def due(events: list[Event], now: dt.datetime, minutes: float, done: set[str]) -> list[Event]:
    """Termine, an die jetzt erinnert werden soll (je Termin nur einmal)."""
    out = []
    for e in events:
        lead = (e.start - now).total_seconds() / 60.0
        if e.key not in done and -1.0 <= lead <= minutes:
            out.append(e)
    return out


def describe(event: Event, now: dt.datetime) -> str:
    mins = round((event.start - now).total_seconds() / 60.0)
    when = "jetzt" if mins <= 0 else ("in 1 Minute" if mins == 1 else f"in {mins} Minuten")
    where = f" ({event.location})" if event.location and not event.location.startswith("http") else ""
    return f"{event.title}{where} – {when}, um {event.start.astimezone():%H:%M} Uhr."
