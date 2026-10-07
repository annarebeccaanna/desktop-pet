"""Globale Modi: Normal / Pause (Bildschirmfreigabe) / Schlafen (Inaktivität).

Der Pause-Modus wird vom Benutzer geschaltet, Schlafen ergibt sich aus der
Inaktivität. Pause hat Vorrang. Meldungen während der Pause werden gesammelt
und danach als *eine* dezente Sprechblase ausgegeben.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .events import MODE_CHANGED, NOTIFY, EventBus


class Mode(str, Enum):
    NORMAL = "normal"
    PAUSE = "pause"
    SLEEP = "sleep"

    @property
    def label(self) -> str:
        return {"normal": "Normal", "pause": "Pause", "sleep": "Schlafen"}[self.value]


@dataclass
class Notification:
    title: str
    text: str
    key: str = ""          # gleiche Schlüssel werden in der Sammlung zusammengefasst


class ModeManager:
    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._paused = False
        self._sleeping = False
        self._queued: list[Notification] = []

    # ---------- Zustand ----------
    @property
    def mode(self) -> Mode:
        if self._paused:
            return Mode.PAUSE
        if self._sleeping:
            return Mode.SLEEP
        return Mode.NORMAL

    @property
    def paused(self) -> bool:
        return self._paused

    def set_paused(self, paused: bool) -> None:
        if paused == self._paused:
            return
        previous = self.mode
        self._paused = paused
        self.bus.publish(MODE_CHANGED, mode=self.mode, previous=previous)
        if not paused:
            self._flush_queue()

    def toggle_pause(self) -> bool:
        self.set_paused(not self._paused)
        return self._paused

    def set_sleeping(self, sleeping: bool) -> None:
        if sleeping == self._sleeping:
            return
        previous = self.mode
        self._sleeping = sleeping
        if self.mode != previous:
            self.bus.publish(MODE_CHANGED, mode=self.mode, previous=previous)

    # ---------- Meldungen ----------
    @property
    def pending_count(self) -> int:
        return len(self._queued)

    def notify(self, title: str, text: str, key: str = "") -> bool:
        """Zeigt eine Meldung oder merkt sie sich bis nach der Pause.

        Gibt True zurück, wenn sie sofort angezeigt wurde.
        """
        if self._paused:
            if key:
                self._queued = [n for n in self._queued if n.key != key]
            self._queued.append(Notification(title, text, key))
            return False
        self.bus.publish(NOTIFY, title=title, text=text)
        return True

    def _flush_queue(self) -> None:
        if not self._queued:
            return
        items, self._queued = self._queued, []
        if len(items) == 1:
            self.bus.publish(NOTIFY, title=items[0].title, text=items[0].text)
            return
        lines = "\n".join(f"• {n.title}: {n.text}" for n in items)
        self.bus.publish(NOTIFY, title="Während der Pause", text=lines)
