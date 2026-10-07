"""Fenster-Klettern: Das Tier läuft auf Oberkanten von Fenstern, springt von
Fenster zu Fenster, läuft ab und zu über die Kante und fällt, wenn ein Fenster
verschwindet."""

from __future__ import annotations

from ..pet.brain import Behaviour, Brain, Intent, Perception, State
from .base import Feature, register

REFRESH_EVERY = 0.25    # max. alle 250 ms (Spezifikation Abschnitt 9)
WALK_OFF_CHANCE = 0.2   # bei jeder neuen Entscheidung auf einem Fenster


class WalkOffEdge(Behaviour):
    """Auf einem Fenster ab und zu absichtlich über die Kante laufen – egal wie hoch."""

    phase = "post"
    CALM = (State.IDLE, State.SIT, State.GROOM, State.SULK)

    def step(self, brain: Brain, dt: float, p: Perception) -> Intent | None:
        if not p.on_window or brain.state not in self.CALM or brain.timer > 0:
            return None
        if brain.rng.random() >= WALK_OFF_CHANCE:
            return None
        direction = brain.rng.choice((-1, 1))
        edge = p.walk_left if direction < 0 else p.walk_right
        brain.target_x = edge + direction * p.height * 2   # bewusst hinter die Kante
        brain.set_state(State.WALK, 1e9)
        return brain.walk_towards(brain.target_x, p, run=False, on_arrive=lambda: None)


@register
class WindowWalking(Feature):
    id = "window_walking"
    name = "Fenster-Klettern"
    description = "Läuft auf Fensterkanten, springt, fällt"
    default_enabled = True
    allowed_in_pause = False
    pause_label = "aus"
    order = 70

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.walk_off = WalkOffEdge()
        self._since = REFRESH_EVERY

    def enable(self) -> None:
        self._since = REFRESH_EVERY

    def disable(self) -> None:
        if self.ctx.app is not None:
            self.ctx.app.update_platforms(include_windows=False)

    def tick(self, dt: float) -> None:
        # Im Pause-Modus bleiben die Kanten eingefroren: Das Tier bewegt sich nicht.
        if not self.active or self.ctx.app is None:
            return
        self._since += dt
        if self._since >= REFRESH_EVERY:
            self._since = 0.0
            self.ctx.app.update_platforms(include_windows=True)

    def behaviours(self) -> list:
        return [self.walk_off]

    def contribute(self, p: Perception) -> None:
        app = self.ctx.app
        if app is None or not app.body.on_ground:
            return
        body = app.body
        reach = 260 * app.scale_factor / 4
        targets = []
        for plat in app.world.platforms_near(body, max_dx=reach * 1.6, max_up=reach * 1.2, max_down=reach * 3):
            x = min(max(body.x, plat.left + body.width), plat.right - body.width)
            targets.append((x, plat.y))
        p.jump_targets = tuple(targets)
