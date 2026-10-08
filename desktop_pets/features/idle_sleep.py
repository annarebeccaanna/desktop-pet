"""Schlafen bei Inaktivität: nach X Minuten ohne Eingabe einschlafen, beim Tippen aufwachen.

Gibt es ein Körbchen, geht das Tier zum Schlafen erst dorthin (Spezifikation 5.2).
"""

from __future__ import annotations

from typing import Callable

from ..pet.brain import Behaviour, Brain, Intent, Perception, State
from .base import Feature, Option, register

WAKE_WITHIN = 2.0   # s: so frisch muss eine Eingabe sein, um das Tier zu wecken


class IdleSleepBehaviour(Behaviour):
    phase = "pre"

    def __init__(self, timeout: float = 300.0, go_to_bed: Callable[[], bool] | None = None) -> None:
        self.timeout = timeout
        self.go_to_bed = go_to_bed      # True, wenn das Tier sich auf den Weg ins Körbchen macht
        self.holding = False

    def step(self, brain: Brain, dt: float, p: Perception) -> Intent | None:
        if p.user_idle >= self.timeout:
            if not self.holding:
                self.holding = brain.sleep_hold = True
                if brain.state != State.SLEEP and self.go_to_bed is not None and self.go_to_bed():
                    return None                 # läuft/fliegt/schwimmt erst ins Körbchen
            if brain.task is not None:
                return None                     # noch unterwegs zum Körbchen
            if brain.state != State.SLEEP:
                brain.set_state(State.SLEEP, 1e9)
            return brain.intent()
        if self.holding:
            if p.user_idle < WAKE_WITHIN:
                self.release(brain)
                if brain.state == State.SLEEP or brain.task is not None:
                    brain.task = None
                    brain.forced_sleep = 0.0
                    brain.events.append("woke")
                    brain.set_state(State.GROOM, 1.8)   # streckt/putzt sich nach dem Aufwachen
            elif brain.state != State.SLEEP and brain.task is None:
                self.release(brain)             # anderweitig geweckt (Klick, Füttern …)
        return None

    def release(self, brain: Brain | None) -> None:
        self.holding = False
        if brain is not None:
            brain.sleep_hold = False


@register
class IdleSleep(Feature):
    id = "idle_sleep"
    name = "Schlafen bei Inaktivität"
    description = "Schläft nach 5 Min. (im Körbchen), wacht beim Tippen auf"
    default_enabled = True
    allowed_in_pause = True
    pause_label = "ja"
    order = 30
    options = [
        Option("minutes", "Einschlafen nach", 5, kind="int", minimum=1, maximum=120, suffix=" Min."),
    ]

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.behaviour = IdleSleepBehaviour(go_to_bed=self._go_to_bed)

    @property
    def timeout_seconds(self) -> float:
        try:
            return max(1, int(self.option("minutes"))) * 60.0
        except (TypeError, ValueError):
            return 300.0

    def _go_to_bed(self) -> bool:
        app = self.ctx.app
        bed = app.features.get("bed") if app is not None else None
        return bool(bed and bed.enabled and bed.send_pet())

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
