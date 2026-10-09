"""Kalender: Das Tier meldet sich kurz vor Terminen („Gleich: Weekly Sync um 10:00“).

* Quelle (Zahnrad): automatisch, Outlook (Desktop-App, muss laufen) oder ICS-Link/-Datei.
  Der ICS-Link ist wie ein Passwort (wer ihn hat, sieht den Kalender) – er liegt deshalb
  im Windows-Anmeldeinformationsspeicher, nicht in settings.json.
* Alle 10 Minuten neu laden (im Hintergrund), alle 20 Sekunden prüfen.
* Erinnerung X Minuten vorher (Standard 5): Ruf + Sprechblase, bei Online-Terminen mit
  „Beitreten“ (Teams, Zoom, Meet, Webex). Im Pause-Modus kommt sie gesammelt danach.
"""

from __future__ import annotations

import datetime as dt
import threading
import urllib.request
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Signal

from ..core.log import get_logger
from ..pet.brain import State
from ..win import outlook
from .ai.keys import KeyStore
from .base import Feature, Option, register
from .calendar_events import Event, describe, due, parse_ics

log = get_logger("calendar")

REFRESH_EVERY = 10 * 60.0
CHECK_EVERY = 20.0
SECRET = "calendar_ics"


class _Bridge(QObject):
    loaded = Signal(object, object, object)      # Termine, Fehlertext, Rückruf


def fetch_ics(source: str) -> bytes:
    source = source.strip()
    if source.lower().startswith("webcal://"):
        source = "https://" + source[len("webcal://"):]
    if source.lower().startswith(("http://", "https://")):
        req = urllib.request.Request(source, headers={"User-Agent": "DesktopPets"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read()
    return Path(source.strip('"')).expanduser().read_bytes()


@register
class CalendarAlerts(Feature):
    id = "calendar_alerts"
    name = "Kalender"
    description = "Meldet sich vor Terminen (Outlook oder ICS-Link)"
    category = "work"
    default_enabled = True
    allowed_in_pause = True          # Erinnerungen kommen gesammelt nach der Pause
    pause_label = "später"
    order = 30
    options = [
        Option("source", "Quelle", "auto", kind="choice",
               choices=[("auto", "Automatisch (Outlook, sonst ICS)"), ("outlook", "Outlook (Desktop-App)"),
                        ("ics", "ICS-Link oder -Datei")]),
        Option("ics", "ICS-Link oder Datei", "", kind="secret"),
        Option("minutes", "Erinnern", 5, kind="int", minimum=1, maximum=60, suffix=" Min. vorher"),
        Option("check", "Jetzt laden", "check_now", kind="button"),
    ]

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.keys = KeyStore()
        self.events: list[Event] = []
        self.done: set[str] = set()
        self.last_error = ""
        self.loading = False
        self.now: Callable[[], dt.datetime] = lambda: dt.datetime.now().astimezone()   # in Tests ersetzbar
        self.outlook_upcoming = outlook.upcoming
        self.outlook_available = outlook.available
        self.fetch = fetch_ics
        self._refresh_t = REFRESH_EVERY
        self._check_t = 0.0
        self._bridge = _Bridge()
        self._bridge.loaded.connect(self._on_loaded)

    # ---------- Geheimnis (ICS-Link) ----------
    def secret_get(self, key: str) -> str:
        return self.keys.get(SECRET) if key == "ics" else ""

    def secret_set(self, key: str, value: str) -> None:
        if key == "ics":
            self.keys.set(SECRET, value)
            self._refresh_t = REFRESH_EVERY          # gleich neu laden

    # ---------- Laden ----------
    def source(self) -> str:
        choice = str(self.option("source"))
        if choice == "auto":
            if self.keys.has(SECRET):
                return "ics"
            return "outlook" if self.outlook_available() else ""
        return choice

    def load_events(self) -> list[Event]:
        """Blockierend (im Hintergrund-Thread aufrufen)."""
        src = self.source()
        if src == "outlook":
            return self.outlook_upcoming(24.0)
        if src == "ics":
            link = self.keys.get(SECRET)
            if not link:
                raise RuntimeError("Noch kein ICS-Link hinterlegt.")
            return parse_ics(self.fetch(link), self.now(), 24.0)
        raise RuntimeError("Keine Quelle: Outlook läuft nicht und kein ICS-Link hinterlegt.")

    def refresh(self, callback: Callable[[str], None] | None = None) -> None:
        if self.loading:
            return
        self.loading = True

        def work() -> None:
            try:
                events = self.load_events()
                self._bridge.loaded.emit(events, None, callback)
            except Exception as exc:  # noqa: BLE001 – Netzwerk, Datei, Outlook …
                self._bridge.loaded.emit(None, str(exc) or type(exc).__name__, callback)

        threading.Thread(target=work, name="calendar", daemon=True).start()

    def _on_loaded(self, events, error, callback) -> None:
        self.loading = False
        if error:
            self.last_error = error
            log.info("Kalender nicht geladen: %s", error)
            message = f"Nicht geladen: {error}"
        else:
            self.events, self.last_error = list(events), ""
            nxt = next((e for e in self.events if e.start >= self.now()), None)
            message = f"{len(self.events)} Termine in den nächsten 24 Std." + (
                f" Nächster: {nxt.title} um {nxt.start.astimezone():%H:%M}" if nxt else "")
            self.check()
        if callback is not None:
            callback(message)

    def check_now(self, callback: Callable[[str], None]) -> None:
        """Knopf „Jetzt laden“ im Zahnrad-Dialog."""
        callback("Lade …")
        self.loading = False
        self.refresh(callback)

    # ---------- Takt ----------
    def enable(self) -> None:
        self._refresh_t = REFRESH_EVERY

    def tick(self, dt_: float) -> None:
        self._refresh_t += dt_
        self._check_t += dt_
        if self._refresh_t >= REFRESH_EVERY:
            self._refresh_t = 0.0
            if self.source():
                self.refresh()
        if self._check_t >= CHECK_EVERY:
            self._check_t = 0.0
            self.check()

    def check(self) -> None:
        now = self.now()
        for event in due(self.events, now, float(self.option("minutes")), self.done):
            self.done.add(event.key)
            self.remind(event, now)

    def remind(self, event: Event, now: dt.datetime) -> None:
        app = self.ctx.app
        if app is None:
            return
        text = describe(event, now)
        if self.ctx.modes.paused:
            self.ctx.modes.notify("Termin", text, key=event.key)
            return
        app.sound.play(app.pack.sounds.get("call"), app.pack.path)
        if not app.pet_hidden and not app.in_bed:
            app.brain.task = None
            app.brain.set_state(State.HAPPY, 1.5)
        buttons = [("Danke", lambda: None, not event.link)]
        if event.link:
            buttons.insert(0, ("Beitreten", lambda link=event.link: self.open_link(link), True))
        app.say("Gleich: Termin", text, 45, buttons=buttons)

    @staticmethod
    def open_link(link: str) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl(link))
