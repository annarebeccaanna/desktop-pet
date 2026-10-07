"""Bedürfnisse: Hunger, Laune, Energie – mit Füttern-Ablauf und Napf.

Füttern: Napf erscheint neben dem Körbchen (ohne Körbchen neben dem Tier), das
Tier läuft hin (springt dafür auch vom Fenster), frisst, zeigt Herzchen bzw.
„Mampf!“, putzt sich. Der leere Napf verschwindet nach ein paar Sekunden.
Zu oft gefüttert → dreht sich weg und schläft. Hungrig → kleine Quengel-Blase
(nie im Pause-Modus). Die Werte selbst liegen in ``app.needs`` (pet/needs.py).
"""

from __future__ import annotations

import time
from datetime import datetime

from ..core.modes import Mode
from ..pet.brain import State
from ..pet.needs import Activity, FeedResult
from .base import Feature, MenuAction, Option, register

NAG_EVERY = 20 * 60     # höchstens alle 20 Minuten quengeln
NAG_CHECK = 60.0
BOWL_LINGER_MS = 5000


@register
class NeedsFeature(Feature):
    id = "needs"
    name = "Bedürfnisse"
    description = "Hunger, Laune, Energie. Füttern per Rechtsklick"
    default_enabled = True
    allowed_in_pause = False    # Werte ruhen im Pause-Modus
    pause_label = "ruht"
    order = 50
    options = [
        Option("speed", "Tempo", "normal", kind="choice",
               choices=[("slow", "gemütlich"), ("normal", "normal"), ("fast", "schnell")]),
        Option("nag", "Quengeln bei Hunger (kleine Sprechblase)", True, kind="bool"),
    ]

    RATES = {"slow": 0.5, "normal": 1.0, "fast": 2.5}

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.bowl = None
        self._bowl_timer = None
        self._result: FeedResult | None = None
        self._nag_check = 0.0
        self._last_nag = 0.0

    # ------------------------------------------------------------------ #
    # Werte fortschreiben
    # ------------------------------------------------------------------ #
    def tick(self, dt: float) -> None:
        app = self.ctx.app
        if not self.active or app is None:
            return
        state = app.brain.state
        if state == State.SLEEP:
            bed = app.features.get("bed")
            in_bed = bool(bed and bed.enabled and bed.is_near(app.body.x, app.body.y))
            activity = Activity.BED_SLEEP if in_bed else Activity.SLEEP
        elif state == State.RUN:
            activity = Activity.RUN
        elif state == State.WALK:
            activity = Activity.WALK
        else:
            activity = Activity.REST
        rate = self.RATES.get(self.option("speed"), 1.0)
        if app.features.is_active("day_rhythm"):
            hour = datetime.now().hour
            if hour >= 22 or hour < 6:
                rate *= 0.6     # nachts alles langsamer
        app.needs.tick(dt, activity, rate)

        self._nag_check += dt
        if self._nag_check >= NAG_CHECK:
            self._nag_check = 0.0
            self._maybe_nag()

    def _maybe_nag(self) -> None:
        app = self.ctx.app
        if self.ctx.modes.paused or not self.option("nag") or not app.needs.is_hungry:
            return
        if self._last_nag and time.monotonic() - self._last_nag < NAG_EVERY:
            return
        self._last_nag = time.monotonic()
        app.say("Hunger!", f"Ein bisschen {app.pack.food} wäre jetzt toll …", 8,
                [("Füttern", self.feed, True), ("Später", lambda: None, False)])

    # ------------------------------------------------------------------ #
    # Füttern
    # ------------------------------------------------------------------ #
    def _ensure_bowl(self):
        if self.bowl is None:
            from PySide6.QtCore import QTimer

            from ..pet.pet_window import PropWindow

            self.bowl = PropWindow(bottom=False, draggable=False)
            self.bowl.setWindowTitle("Desktop Pets – Napf")
            self.bowl.clicked.connect(self.bowl.hide)
            if self.ctx.app is not None:
                self.bowl.shown.connect(self.ctx.app.apply_capture)
            self._bowl_timer = QTimer(self.bowl)
            self._bowl_timer.setSingleShot(True)
            self._bowl_timer.timeout.connect(self.bowl.hide)
        return self.bowl

    def feed(self) -> None:
        app = self.ctx.app
        if app is None or not self.active:
            return
        result = app.needs.feed()
        if result == FeedResult.TURN_AWAY:
            app.brain.turn_away_and_sleep()
            app.say("", "Zu viel … *dreht sich weg und schläft*", 4)
            return
        self._result = result
        pos = self._bowl_position()
        bowl = self._ensure_bowl()
        empty = app.sprites.extra("bowl.png") if app.sprites else None
        food = app.sprites.extra("food.png") if app.sprites else None
        if empty is not None:
            bowl.set_pixmap(empty, food)
            bowl.place_bottom_center(pos)
            bowl.show()
        self._bowl_timer.stop()
        app.leave_window_edge(target_y=pos.y())
        app.brain.go_to(pos.x(), then=State.EAT, duration=3.2, tag="feed")

    def _bowl_position(self):
        from PySide6.QtCore import QPoint

        app = self.ctx.app
        bed = app.features.get("bed")
        anchor = bed.bowl_anchor() if bed is not None and bed.enabled else None
        if anchor is not None:
            return anchor
        offset = int(app.sprites.frame_w if app.sprites else 40) * app.brain.facing
        return QPoint(int(app.body.x + offset), int(app.body.y))

    # ------------------------------------------------------------------ #
    # Andockpunkte
    # ------------------------------------------------------------------ #
    def on_brain_event(self, event: str) -> None:
        app = self.ctx.app
        if app is None:
            return
        if event == "petted":
            app.needs.pet()
        elif event == "caught":
            app.needs.play()
        elif event == "arrived:feed":
            app.sound.play(app.pack.sounds.get("eat"), app.pack.path)
        elif event == "done:feed":
            if self.bowl is not None:
                self.bowl.set_overlay(None)
                self._bowl_timer.start(BOWL_LINGER_MS)
            if self._result == FeedResult.EATEN:
                app.hearts(3)
                app.say("", "Mampf! 😋", 2.5)
                app.brain.react("groom", 3.0)
            else:
                app.say("", "Bin satt.", 2.5)
                app.brain.react("sit", 3.0)
            self._result = None

    def on_mode_changed(self, mode: Mode) -> None:
        if mode == Mode.PAUSE and self.bowl is not None:
            self.bowl.hide()

    def disable(self) -> None:
        if self.bowl is not None:
            self.bowl.hide()

    def menu_actions(self, where: str) -> list[MenuAction]:
        enabled = not self.ctx.modes.paused
        return [MenuAction("Füttern", self.feed, enabled=enabled, order=30 if where == "tray" else 10)]

    @property
    def windows(self) -> list:
        return [self.bowl] if self.bowl is not None else []
