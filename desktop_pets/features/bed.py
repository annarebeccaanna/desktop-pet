"""Körbchen: eigener Schlafplatz auf dem Desktop (immer hinter allen Fenstern)."""

from __future__ import annotations

from .base import Feature, register


@register
class Bed(Feature):
    id = "bed"
    name = "Körbchen"
    description = "Eigener Schlafplatz auf dem Desktop"
    default_enabled = True
    allowed_in_pause = True
    pause_label = "schläft"
    order = 60

    def enable(self) -> None:
        if self.ctx.app is not None:
            self.ctx.app.show_bed(True)

    def disable(self) -> None:
        if self.ctx.app is not None:
            self.ctx.app.show_bed(False)
