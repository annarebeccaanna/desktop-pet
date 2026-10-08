"""Bedürfnisse: Hunger, Laune, Energie – mit Füttern-Ablauf und Napf.

Länger nicht gefüttert: Der leere Napf steht bereit, das Tier setzt sich ab und
zu daneben und schaut zur Maus (nie krank, kein Strafsystem).

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
from ..pet.brain import Behaviour, Brain, Intent, Perception, State
from ..pet.needs import Activity, FeedResult
from .base import Feature, MenuAction, Option, register

NAG_EVERY = 20 * 60     # höchstens alle 20 Minuten quengeln
NAG_CHECK = 60.0
BOWL_LINGER_MS = 5000
WAIT_EVERY = (90.0, 180.0)   # Sekunden zwischen zwei „Ich warte am Napf“-Besuchen
WAIT_SECONDS = 25.0


class WaitAtBowl(Behaviour):
    """Hungrig: sich ab und zu neben den leeren Napf setzen und zur Maus schauen.

    Phase "pre", weil das Sitzen am Napf als Aufgabe läuft – das Zur-Maus-Schauen
    muss auch währenddessen greifen.
    """

    phase = "pre"
    CALM = (State.IDLE, State.SIT, State.GROOM, State.SULK)

    def __init__(self, bowl_x, on_start=None) -> None:
        self.bowl_x = bowl_x            # Callable → x-Position des Napfs oder None
        self.on_start = on_start        # z. B. vom Fenster herunterspringen
        self.cooldown = 20.0

    def step(self, brain: Brain, dt: float, p: Perception) -> Intent | None:
        self.cooldown = max(0.0, self.cooldown - dt)
        bx = self.bowl_x()
        if bx is None:
            return None
        near = abs(p.x - bx) < p.height * 1.6
        if near and brain.state == State.SIT and p.cursor is not None and brain.rng.random() < dt * 0.6:
            brain.facing = 1 if p.cursor[0] >= p.x else -1     # schaut zur Maus
        if self.cooldown > 0 or brain.task is not None or brain.state not in self.CALM or brain.timer > 0 or near:
            return None
        self.cooldown = brain.rng.uniform(*WAIT_EVERY)
        side = -1 if p.x < bx else 1
        if self.on_start is not None:
            self.on_start()
        brain.go_to(bx + side * p.height * 0.9, then=State.SIT, duration=WAIT_SECONDS, tag="bowl_wait")
        return brain.walk_towards(brain.task.x, p, run=False, on_arrive=lambda: None)


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
        self.waiting = WaitAtBowl(self._waiting_bowl_x, on_start=self._leave_edge_for_bowl)

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
        self._update_empty_bowl()

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
        bowl = self._ensure_bowl()
        # Steht der leere Napf schon bereit, kommt das Futter genau dort hinein
        pos = bowl.bottom_center() if bowl.isVisible() else self._bowl_position()
        empty = app.sprites.extra("bowl.png") if app.sprites else None
        food = app.sprites.extra("food.png") if app.sprites else None
        if empty is not None:
            bowl.set_pixmap(empty, food)
            bowl.place_bottom_center(pos)
            bowl.show()
        self._bowl_timer.stop()
        app.leave_window_edge(target_y=pos.y())
        app.brain.go_to(pos.x(), then=State.EAT, duration=3.2, tag="feed")

    # ------------------------------------------------------------------ #
    # Hungrig: leerer Napf steht bereit
    # ------------------------------------------------------------------ #
    @property
    def feeding(self) -> bool:
        return self._result is not None

    def _update_empty_bowl(self) -> None:
        app = self.ctx.app
        want = app.needs.is_hungry and not self.feeding and not app.pet_hidden
        if want and (self.bowl is None or not self.bowl.isVisible()):
            empty = app.sprites.extra("bowl.png") if app.sprites else None
            if empty is not None:
                bowl = self._ensure_bowl()
                self._bowl_timer.stop()
                bowl.set_pixmap(empty, None)
                bowl.place_bottom_center(self._bowl_position())
                bowl.show()
        elif not want and not self.feeding and self.bowl is not None and self.bowl.isVisible() \
                and not self._bowl_timer.isActive():
            self.bowl.hide()

    def _waiting_bowl_x(self) -> float | None:
        app = self.ctx.app
        if app is None or not app.needs.is_hungry or self.feeding or self.bowl is None or not self.bowl.isVisible():
            return None
        return float(self.bowl.bottom_center().x())

    def _leave_edge_for_bowl(self) -> None:
        if self.ctx.app is not None and self.bowl is not None:
            self.ctx.app.leave_window_edge(target_y=self.bowl.bottom_center().y())

    def behaviours(self) -> list:
        return [self.waiting]

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

    def on_visibility_changed(self, visible: bool) -> None:
        if not visible and self.bowl is not None:
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
