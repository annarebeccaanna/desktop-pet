"""Schlafen bei Inaktivität: nach X Minuten ohne Eingabe einschlafen, beim Tippen aufwachen."""

from __future__ import annotations

from ..pet.brain import Behaviour, Brain, Intent, Perception, State
from .base import Feature, Option, register

WAKE_WITHIN = 2.0   # s: so frisch muss eine Eingabe sein, um das Tier zu wecken


class IdleSleepBehaviour(Behaviour):
    phase = "pre"

    def __init__(self, timeout: float = 300.0) -> None:
        self.timeout = timeout
        self.holding = False

    def step(self, brain: Brain, dt: float, p: Perception) -> Intent | None:
        if p.user_idle >= self.timeout:
            if brain.state != State.SLEEP:
                brain.task = None
                brain.set_state(State.SLEEP, 1e9)
            self.holding = brain.sleep_hold = True
            return brain.intent()
        if self.holding:
            if brain.state != State.SLEEP:
                # anderweitig geweckt (Klick, Füttern …)
                self.release(brain)
            elif p.user_idle < WAKE_WITHIN:
                self.release(brain)
                brain.events.append("woke")
                brain.set_state(State.GROOM, 1.8)   # streckt/putzt sich nach dem Aufwachen
        return None

    def release(self, brain: Brain | None) -> None:
        self.holding = False
        if brain is not None:
            brain.sleep_hold = False


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

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.behaviour = IdleSleepBehaviour()

    @property
    def timeout_seconds(self) -> float:
        try:
            return max(1, int(self.option("minutes"))) * 60.0
        except (TypeError, ValueError):
            return 300.0

    def behaviours(self) -> list:
        self.behaviour.timeout = self.timeout_seconds
        return [self.behaviour]

    def tick(self, dt: float) -> None:
        app = self.ctx.app
        if app is not None:
            self.ctx.modes.set_sleeping(self.active and app.user_idle >= self.timeout_seconds)

    def disable(self) -> None:
        self.ctx.modes.set_sleeping(False)
        app = self.ctx.app
        self.behaviour.release(app.brain if app is not None else None)
