"""Rücksicht bei Vollbild: Läuft eine Vollbild-Anwendung (Spiel, Präsentation),
versteckt sich das Tier und kommt danach von selbst wieder (Spezifikation Abschnitt 9)."""

from __future__ import annotations

from ..win.windows_enum import foreground_is_fullscreen
from .base import Feature, register

CHECK_EVERY = 1.0   # Sekunden


def physical_screen_rects() -> list[tuple[int, int, int, int]]:
    """Bildschirme in physischen Pixeln (so liefert Win32 die Fensterkanten)."""
    from PySide6.QtGui import QGuiApplication

    out = []
    for s in QGuiApplication.screens():
        g, dpr = s.geometry(), s.devicePixelRatio()
        out.append((g.left(), g.top(), g.left() + round(g.width() * dpr), g.top() + round(g.height() * dpr)))
    return out


@register
class FullscreenHide(Feature):
    id = "fullscreen_hide"
    name = "Rücksicht bei Vollbild"
    description = "Versteckt sich bei Spielen und Präsentationen"
    default_enabled = True
    allowed_in_pause = True
    pause_label = "ja"
    order = 85
    listed = False                      # Schalter im Tab „Pause & Freigabe“
    settings_key = "pause.fullscreen_hide"

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.detector = foreground_is_fullscreen     # in Tests ersetzbar
        self._since = CHECK_EVERY

    def tick(self, dt: float) -> None:
        app = self.ctx.app
        if app is None:
            return
        self._since += dt
        if self._since < CHECK_EVERY:
            return
        self._since = 0.0
        app.set_hidden("fullscreen", bool(self.detector(physical_screen_rects())))

    def disable(self) -> None:
        if self.ctx.app is not None:
            self.ctx.app.set_hidden("fullscreen", False)
