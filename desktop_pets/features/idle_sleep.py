"""Schlafen bei Inaktivität: nach X Minuten ohne Eingabe einschlafen, beim Tippen aufwachen."""

from __future__ import annotations

from .base import Feature, Option, register


@register
class IdleSleep(Feature):
    id = "idle_sleep"
    name = "Schlafen bei Inaktivität"
    description = "Schläft nach 5 Min., wacht beim Tippen auf"
    default_enabled = True
    allowed_in_pause = True
    pause_label = "ja"
    order = 30
    options = [
        Option("minutes", "Einschlafen nach", 5, kind="int", minimum=1, maximum=120, suffix=" Min."),
    ]

    @property
    def timeout_seconds(self) -> float:
        try:
            return max(1, int(self.option("minutes"))) * 60.0
        except (TypeError, ValueError):
            return 300.0
