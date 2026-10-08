"""Verhalten & Persönlichkeit: Herumstreunen, Streicheln, Tagesrhythmus,
Gedächtnis, Umfärben. (Bedürfnisse: needs.py, Körbchen: bed.py, …)"""

from __future__ import annotations

from .base import Feature, register


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

    STROKE_NEEDED = 140.0       # px Mausweg über dem Tier
    COOLDOWN = 1.2

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self._stroke = 0.0
        self._cooldown = 0.0
        self._connected = False

    def enable(self) -> None:
        app = self.ctx.app
        if app is not None and not self._connected:
            app.pet_window.stroked.connect(self._on_stroke)
            self._connected = True

    def disable(self) -> None:
        app = self.ctx.app
        if app is not None and self._connected:
            app.pet_window.stroked.disconnect(self._on_stroke)
            self._connected = False

    def tick(self, dt: float) -> None:
        self._cooldown = max(0.0, self._cooldown - dt)
        self._stroke = max(0.0, self._stroke - 60.0 * dt)

    def _on_stroke(self, dist: float) -> None:
        app = self.ctx.app
        if not self.active or app is None or app.dragging:
            return
        self._stroke += dist
        if self._stroke >= self.STROKE_NEEDED and self._cooldown <= 0:
            self._stroke = 0.0
            self._cooldown = self.COOLDOWN
            app.pet_pet()


@register
class DayRhythm(Feature):
    """Abends schläfriger, morgens verspielter (regelt das Gehirn über die Uhrzeit).

    Abends und nachts hält das Tier sein Nickerchen lieber im Körbchen.
    """

    order = 80
    id = "day_rhythm"
    name = "Tagesrhythmus"
    description = "Abends schläfrig (ab ins Körbchen), morgens verspielt"
    default_enabled = True
    allowed_in_pause = True
    pause_label = "ja"

    EVENING_FROM = 21     # Uhr
    MORNING_UNTIL = 6

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        from datetime import datetime

        self.clock = datetime.now      # in Tests ersetzbar

    def is_night(self) -> bool:
        hour = self.clock().hour
        return hour >= self.EVENING_FROM or hour < self.MORNING_UNTIL

    def on_brain_event(self, event: str) -> None:
        app = self.ctx.app
        if event != "nap" or app is None or not self.active or self.ctx.modes.paused or not self.is_night():
            return
        bed = app.features.get("bed")
        if bed is not None and bed.enabled and not bed.is_near(app.body.x, app.body.y):
            bed.send_pet()


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
