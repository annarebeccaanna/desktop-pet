"""Mausjagd: Das Tier folgt dem Zeiger und „fängt“ ihn, wenn er stillsteht.

Die ganze Logik steckt hier (``ChaseBehaviour``, ohne Qt, testbar) und klinkt
sich über ``behaviours()`` ins Gehirn ein.
"""

from __future__ import annotations

from ..pet.brain import ONE_SHOT, Behaviour, Brain, Intent, Perception, State
from .base import Feature, Option, register

START_SPEED = 250.0     # px/s: so schnell muss der Zeiger sein, damit die Jagd losgeht
NEAR = 28.0             # px: „unter dem Zeiger“
CATCH_HEIGHT = 220.0    # px: so hoch kann das Tier springen
BELOW = 12.0            # px: Zeiger so weit unter den Füßen → liegt unterhalb der Fensterkante


class ChaseBehaviour(Behaviour):
    phase = "post"

    def __init__(self, eagerness: float = 1.0) -> None:
        self.eagerness = eagerness
        self.cooldown = 8.0
        self.time_left = 0.0

    @property
    def chasing(self) -> bool:
        return self.time_left > 0

    def step(self, brain: Brain, dt: float, p: Perception) -> Intent | None:
        self.cooldown = max(0.0, self.cooldown - dt)
        if p.cursor is None:
            return None
        cx, cy = p.cursor
        if self.chasing and brain.state == State.RUN:
            return self._chase(brain, dt, p, cx, cy)
        self.time_left = 0.0
        if self.cooldown > 0 or brain.state in ONE_SHOT or brain.state == State.SLEEP:
            return None
        if p.cursor_speed * self.eagerness > START_SPEED and abs(cx - p.x) < 900:
            # Je verspielter, besser gelaunt und wacher, desto eher geht es los (~1×/s bei Höchstwerten)
            interest = brain.playfulness * (0.6 + p.mood / 250) * (0.5 + p.energy / 200) * self.eagerness
            if brain.rng.random() < interest * dt * 1.5:
                self.time_left = 4 + 6 * brain.playfulness
                brain.target_x = min(max(cx, p.walk_left), p.walk_right)
                brain.set_state(State.RUN, 1e9)
                return brain.walk_towards(brain.target_x, p, run=True, on_arrive=lambda: None)
        return None

    def _chase(self, brain: Brain, dt: float, p: Perception, cx: float, cy: float) -> Intent:
        self.time_left -= dt
        if self.time_left > 0 and p.on_window and (cx < p.walk_left or cx > p.walk_right or cy > p.y + BELOW):
            # Zeiger neben oder unter dem Fenster: über die Kante hinterher – und nach der
            # Landung gleich weiterjagen
            if p.walk_left <= cx <= p.walk_right:
                go_left = cx - p.walk_left <= p.walk_right - cx
                brain.target_x = p.walk_left - p.height * 2 if go_left else p.walk_right + p.height * 2
            else:
                brain.target_x = cx
            brain.after_landing = State.RUN
            return brain.walk_towards(brain.target_x, p, run=True, on_arrive=lambda: None)
        if brain.after_landing == State.RUN:
            brain.after_landing = None
        brain.target_x = min(max(cx, p.walk_left), p.walk_right)
        dx = cx - p.x
        near = abs(dx) < NEAR
        if near and p.cursor_still_for > 0.5 and 0 < p.y - cy < CATCH_HEIGHT:
            # Fangen: hochspringen zum Zeiger, danach freuen
            self.time_left = 0.0
            self.cooldown = 25 + 40 * (1 - brain.playfulness)
            brain.after_landing = State.HAPPY
            brain.events.append("caught")
            brain.set_state(State.JUMP, 1e9)
            brain.target_x = None
            return brain.intent(jump=(cx, cy + p.height * 0.7))
        if near:
            # Unter dem Zeiger warten und hochschauen
            brain.facing = 1 if dx >= 0 else -1
            return Intent(animation="sit", vx=0.0, facing=brain.facing)
        if self.time_left <= 0:
            brain.target_x = None
            self.cooldown = 15 + 30 * (1 - brain.playfulness)
            brain.set_state(State.SIT, 2.0)
            return brain.intent()
        return brain.walk_towards(brain.target_x, p, run=True, on_arrive=lambda: None)


@register
class MouseChase(Feature):
    id = "mouse_chase"
    name = "Mausjagd"
    description = "Folgt dem Mauszeiger und fängt ihn"
    default_enabled = True
    allowed_in_pause = False
    pause_label = "aus"
    order = 20
    requires = "wander"          # ohne Herumstreunen keine Jagd
    options = [
        Option("eagerness", "Jagdlust", 100, kind="int", minimum=0, maximum=200, suffix=" %"),
    ]

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.behaviour = ChaseBehaviour()

    def behaviours(self) -> list:
        try:
            self.behaviour.eagerness = max(0.0, float(self.option("eagerness")) / 100.0)
        except (TypeError, ValueError):
            self.behaviour.eagerness = 1.0
        return [self.behaviour]

    def on_brain_event(self, event: str) -> None:
        if event == "caught" and self.ctx.app is not None:
            self.ctx.app.sound.play("jump.wav")
