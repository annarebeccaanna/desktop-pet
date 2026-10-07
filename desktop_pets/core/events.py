"""Einfacher Publish/Subscribe-Bus.

Fehler in einem Abonnenten werden geloggt und unterbrechen die anderen nicht.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from .log import get_logger

log = get_logger("events")

Handler = Callable[..., Any]

# Bekannte Themen (nur zur Dokumentation – beliebige Strings sind erlaubt)
MODE_CHANGED = "mode_changed"            # mode=Mode, previous=Mode
SETTINGS_CHANGED = "settings_changed"    # key=str, value=Any
FEATURE_TOGGLED = "feature_toggled"      # feature_id=str, enabled=bool
PET_CHANGED = "pet_changed"              # pet_id=str
NOTIFY = "notify"                        # title=str, text=str
NEEDS_CHANGED = "needs_changed"          # needs=Needs
PET_REACTION = "pet_reaction"            # reaction=str ("happy", "angry", ...)


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Handler) -> Callable[[], None]:
        self._handlers[topic].append(handler)
        return lambda: self.unsubscribe(topic, handler)

    def unsubscribe(self, topic: str, handler: Handler) -> None:
        try:
            self._handlers[topic].remove(handler)
        except ValueError:
            pass

    def publish(self, topic: str, **data: Any) -> None:
        for handler in list(self._handlers.get(topic, ())):
            try:
                handler(**data)
            except Exception:  # noqa: BLE001 – ein defekter Abonnent darf die App nicht stoppen
                log.exception("Fehler im Event-Handler für %r", topic)
