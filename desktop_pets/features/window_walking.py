"""Fenster-Klettern: Das Tier läuft auf Oberkanten von Fenstern, springt von
Fenster zu Fenster und fällt, wenn ein Fenster verschwindet."""

from __future__ import annotations

from .base import Feature, register

REFRESH_EVERY = 0.25   # max. alle 250 ms (Spezifikation Abschnitt 9)


@register
class WindowWalking(Feature):
    id = "window_walking"
    name = "Fenster-Klettern"
    description = "Läuft auf Fensterkanten, springt, fällt"
    default_enabled = True
    allowed_in_pause = False
    pause_label = "aus"
    order = 70

    def enable(self) -> None:
        self._since = REFRESH_EVERY

    def disable(self) -> None:
        if self.ctx.app is not None:
            self.ctx.app.update_platforms(include_windows=False)

    def tick(self, dt: float) -> None:
        # Im Pause-Modus bleiben die Kanten eingefroren: Das Tier bewegt sich nicht.
        if not self.active or self.ctx.app is None:
            return
        self._since = getattr(self, "_since", 0.0) + dt
        if self._since >= REFRESH_EVERY:
            self._since = 0.0
            self.ctx.app.update_platforms(include_windows=True)
