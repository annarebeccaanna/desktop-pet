"""Pause automatisch bei Bildschirmfreigabe (experimentell, ab Werk aus).

Schalter: Einstellungen → „Pause & Freigabe“ (``pause.auto_detect``).

* Freigabe erkannt → Pause-Modus an (nur wenn er nicht schon an war).
* Freigabe beendet → Pause-Modus wieder aus – aber nur, wenn ihn diese Automatik
  eingeschaltet hat. Wer schon vorher manuell pausiert hat, bleibt pausiert.
* Manuell überstimmbar: Schaltet man während der Freigabe die Pause aus, bleibt
  sie aus, bis die nächste Freigabe beginnt.
"""

from __future__ import annotations

from ..core import paths
from ..core.modes import Mode
from ..win.share_detect import ShareDetector
from .base import Feature, register

CHECK_EVERY = 1.0   # Sekunden


@register
class ShareAutoPause(Feature):
    id = "share_autopause"
    name = "Pause bei Bildschirmfreigabe"
    description = "Startet den Pause-Modus automatisch, wenn eine Freigabe erkannt wird"
    category = "work"
    default_enabled = False
    allowed_in_pause = True
    pause_label = "ja"
    listed = False                      # Schalter im Tab „Pause & Freigabe“
    settings_key = "pause.auto_detect"

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.detector = ShareDetector(user_file=paths.user_data_dir() / "share_signatures.json")
        self.sharing: list = []          # [(App, Fenster)] der letzten Prüfung
        self.auto_paused = False
        self._switching = False
        self._since = CHECK_EVERY

    @property
    def sharing_app(self) -> str:
        return self.sharing[0][0] if self.sharing else ""

    def enable(self) -> None:
        self.detector.reload()
        self._since = CHECK_EVERY

    def disable(self) -> None:
        self.sharing = []
        if self.auto_paused and self.ctx.modes.paused:
            self._set_paused(False)
        self.auto_paused = False

    def tick(self, dt: float) -> None:
        self._since += dt
        if self._since < CHECK_EVERY:
            return
        self._since = 0.0
        was_sharing = bool(self.sharing)
        self.sharing = self.detector.check()
        now_sharing = bool(self.sharing)
        if now_sharing and not was_sharing and not self.ctx.modes.paused:
            self.auto_paused = True
            self._set_paused(True)
        elif was_sharing and not now_sharing:
            if self.auto_paused and self.ctx.modes.paused:
                self._set_paused(False)
            self.auto_paused = False
        if now_sharing != was_sharing and self.ctx.app is not None:
            self.ctx.app.tray.refresh()

    def on_mode_changed(self, mode: Mode) -> None:
        # Manuell ausgeschaltet → nicht wieder einschalten, bis die nächste Freigabe beginnt
        if not self._switching and mode != Mode.PAUSE:
            self.auto_paused = False

    def _set_paused(self, paused: bool) -> None:
        self._switching = True
        try:
            self.ctx.modes.set_paused(paused)
        finally:
            self._switching = False
