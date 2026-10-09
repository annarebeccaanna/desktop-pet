"""Copilot-Taste für Desktop Pets nutzen (Einstellungen → Allgemein, ab Werk aus).

Solange das Häkchen gesetzt ist, öffnet die Copilot-Taste (Win + Umschalt + F23)
nicht Copilot, sondern führt die gewählte Aktion aus. Häkchen raus oder App
beendet → die Taste gehört wieder Windows.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from ..win.keyhook import CopilotKeyHook
from .base import Feature, register

# Wert → Anzeige (später kommt „KI-Chat öffnen“ dazu)
ACTIONS = [
    ("settings", "Einstellungen öffnen"),
    ("call", "Tier zu mir rufen"),
    ("pause", "Pause-Modus umschalten"),
]


class _Bridge(QObject):
    """Hook-Thread → GUI-Thread (Qt stellt das Signal automatisch in die Warteschlange)."""

    fired = Signal()


@register
class CopilotKey(Feature):
    id = "copilot_key"
    name = "Copilot-Taste"
    description = "Copilot-Taste löst eine Desktop-Pets-Aktion aus"
    default_enabled = False
    allowed_in_pause = True
    pause_label = "ja"
    listed = False                       # Schalter unter Allgemein
    settings_key = "general.copilot_key"

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self._bridge = _Bridge()
        self._bridge.fired.connect(self.trigger)
        self.hook = CopilotKeyHook(on_fire=self._bridge.fired.emit)
        self.fired_count = 0

    @property
    def action(self) -> str:
        value = self.ctx.settings.get("general.copilot_action", "settings")
        return value if value in dict(ACTIONS) else "settings"

    @property
    def status(self) -> str:
        if not self.hook.available:
            return "Nur unter Windows verfügbar."
        if not self.enabled:
            return "Aus – die Copilot-Taste öffnet wie gewohnt Copilot."
        if self.hook.running:
            return "Aktiv – die Copilot-Taste gehört jetzt Desktop Pets."
        return "Konnte die Taste nicht übernehmen (siehe log.txt)."

    def enable(self) -> None:
        self.hook.start()

    def disable(self) -> None:
        self.hook.stop()

    def trigger(self) -> None:
        """Copilot-Taste gedrückt (läuft im GUI-Thread)."""
        app = self.ctx.app
        if app is None or not self.enabled:
            return
        self.fired_count += 1
        action = self.action
        if action == "settings":
            app.open_settings()
        elif action == "call":
            app.call_pet()
        elif action == "pause":
            app.toggle_pause()
