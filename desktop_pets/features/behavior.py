"""Verhalten & Persönlichkeit: Herumstreunen, Streicheln, Bedürfnisse,
Tagesrhythmus, Gedächtnis, Umfärben."""

from __future__ import annotations

from .base import Feature, Option, register


@register
class Wander(Feature):
    order = 10
    id = "wander"
    name = "Herumstreunen"
    description = "Läuft, sitzt, gähnt, streckt und putzt sich"
    default_enabled = True
    allowed_in_pause = True     # im Pause-Modus nur sitzen/liegen (regelt das Gehirn)
    pause_label = "liegt"


@register
class Petting(Feature):
    order = 40
    id = "petting"
    name = "Streicheln"
    description = "Maus über dem Tier bewegen: Schnurren und Herzchen"
    default_enabled = True
    allowed_in_pause = True     # still: keine Sounds
    pause_label = "still"


@register
class NeedsFeature(Feature):
    order = 50
    id = "needs"
    name = "Bedürfnisse"
    description = "Hunger, Laune, Energie. Füttern per Rechtsklick"
    default_enabled = True
    allowed_in_pause = False    # Werte ruhen im Pause-Modus
    pause_label = "ruht"
    options = [
        Option("speed", "Tempo", "normal", kind="choice",
               choices=[("slow", "gemütlich"), ("normal", "normal"), ("fast", "schnell")]),
        Option("nag", "Quengeln bei Hunger (kleine Sprechblase)", True, kind="bool"),
    ]

    RATES = {"slow": 0.5, "normal": 1.0, "fast": 2.5}

    def tick(self, dt: float) -> None:
        if not self.active:
            return
        app = self.ctx.app
        if app is not None:
            app.tick_needs(dt, self.RATES.get(self.option("speed"), 1.0))


@register
class DayRhythm(Feature):
    order = 80
    id = "day_rhythm"
    name = "Tagesrhythmus"
    description = "Abends schläfrig, morgens verspielt"
    default_enabled = True
    allowed_in_pause = True
    pause_label = "ja"


@register
class Memory(Feature):
    order = 90
    id = "memory"
    name = "Gedächtnis"
    description = "Merkt sich Laune, Hunger und Position"
    default_enabled = True
    allowed_in_pause = True
    pause_label = "ja"

    SAVE_EVERY = 60.0

    def enable(self) -> None:
        self._since = 0.0

    def tick(self, dt: float) -> None:
        self._since = getattr(self, "_since", 0.0) + dt
        if self._since >= self.SAVE_EVERY:
            self._since = 0.0
            if self.ctx.app is not None:
                self.ctx.app.save_memory()


@register
class Recolor(Feature):
    order = 95
    id = "recolor"
    name = "Umfärben"
    description = "Fellfarbe über die Paint-Palette"
    default_enabled = True
    allowed_in_pause = True
    pause_label = "ja"

    def enable(self) -> None:
        if self.ctx.app is not None:
            self.ctx.app.refresh_sprites()

    def disable(self) -> None:
        if self.ctx.app is not None:
            self.ctx.app.refresh_sprites(force_original=True)
