"""Text-Werkzeuge: markierten Text mit der KI bearbeiten – im Pixel-Menü am Tier.

* Text irgendwo markieren → ``Strg + Alt + M`` oder Copilot-Taste (wenn Text markiert ist).
* Das Tier holt den markierten Text (kurz Strg + C, die Zwischenablage bleibt wie sie war),
  zeigt seine Werkzeuge: Verbessern, Kürzer, Freundlicher, Förmlicher, Übersetzen,
  Zusammenfassen, Erklären oder eine eigene Anweisung.
* Ergebnis: **Ersetzen** (fügt an Stelle der Markierung ein) oder **Kopieren**.
* In Konsolen wird nie automatisch kopiert (dort hieße Strg + C „abbrechen“).
* Nutzt den Anbieter aus dem Tab KI; im Pause-Modus aus.
"""

from __future__ import annotations

import threading
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal

from ..core.log import get_logger
from ..pet.brain import State
from ..win import input as win_input
from ..win import textinsert
from .ai.providers import AIError
from .ai.text_tools import CUSTOM, MAX_CHARS, SYSTEM, build_request, clean_result, tool_by_id
from .base import Feature, register
from .dictation import RESTORE_AFTER_MS, _copy_mime

log = get_logger("text_tools")

COPY_WAIT_MS = 450            # so lange auf die Kopie warten
WAIT_KEYS_MS = 1200


class _Bridge(QObject):
    done = Signal(int, object, object)        # Auftrag-Nr., Ergebnis, Fehler


@register
class TextTools(Feature):
    id = "text_tools"
    name = "Text-Werkzeuge"
    description = "Markierten Text verbessern, kürzen, übersetzen … (Strg+Alt+M)"
    category = "work"
    default_enabled = True
    allowed_in_pause = False
    pause_label = "aus"
    order = 16

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.menu = None
        self.text = ""
        self.target = 0                       # Fenster mit dem markierten Text
        self.busy = False
        self._job = 0
        self._tool_label = ""
        self._replace_default = True
        self._bridge = _Bridge()
        self._bridge.done.connect(self._on_done)
        # in Tests ersetzbar
        self.foreground_window = textinsert.foreground_window
        self.foreground_process = textinsert.foreground_process
        self.clipboard_sequence = textinsert.clipboard_sequence
        self.send_copy = textinsert.send_copy
        self.focus_info = textinsert.focus_info
        self.paste = textinsert.paste
        self.bring_back = win_input.force_foreground

    # ------------------------------------------------------------------ #
    @property
    def windows(self) -> list:
        return [self.menu] if self.menu is not None else []

    def hotkeys(self) -> list:
        return [("text_tools", lambda: self.start())]

    def disable(self) -> None:
        self._job += 1
        self.busy = False
        if self.menu is not None:
            self.menu.close_menu()

    def on_mode_changed(self, mode) -> None:  # noqa: ARG002 – Pause → aus (active=False)
        if not self.active:
            self.disable()

    def tick(self, dt: float) -> None:  # noqa: ARG002
        app = self.ctx.app
        if app is not None and self.menu is not None and self.menu.isVisible():
            self.menu.follow(app.pet_window.head_anchor())

    def _ensure_menu(self):
        if self.menu is None:
            from ..ui.text_tools_menu import TextToolsMenu

            self.menu = TextToolsMenu()
            self.menu.tool_chosen.connect(self.run_tool)
            self.menu.replace_clicked.connect(self.replace)
            self.menu.copy_clicked.connect(self.copy)
        return self.menu

    # ------------------------------------------------------------------ #
    # 1. Markierten Text holen
    # ------------------------------------------------------------------ #
    def start(self, fallback: Callable[[], None] | None = None) -> None:
        """``fallback``: was passieren soll, wenn nichts markiert ist (z. B. Chat öffnen)."""
        app = self.ctx.app
        if app is None or not self.active or self.busy:
            return
        self.target = self.foreground_window()
        if self.foreground_process() in textinsert.TERMINALS:
            if fallback is not None:
                fallback()
            else:
                self._say("In Konsolen kopiere ich nicht selbst – dort hieße Strg + C „abbrechen“.", 6)
            return
        self._wait_keys(fallback, WAIT_KEYS_MS)

    def _wait_keys(self, fallback, left_ms: int) -> None:
        if win_input.modifiers_down() and left_ms > 0:
            QTimer.singleShot(40, lambda: self._wait_keys(fallback, left_ms - 40))
            return
        self._grab(fallback)

    def _grab(self, fallback) -> None:
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        before = self.clipboard_sequence()
        saved = _copy_mime(clipboard.mimeData())
        if not self.send_copy():                 # kopieren geht hier nicht (z. B. kein Windows)
            self._selected("", fallback)
            return

        def check(left_ms: int) -> None:
            if self.clipboard_sequence() == before and left_ms > 0:
                QTimer.singleShot(30, lambda: check(left_ms - 30))
                return
            changed = self.clipboard_sequence() != before
            text = clipboard.text() if changed else ""
            if changed and saved is not None:
                clipboard.setMimeData(saved)     # Zwischenablage wie vorher
            self._selected(text, fallback)

        check(COPY_WAIT_MS)

    def _selected(self, text: str, fallback) -> None:
        app = self.ctx.app
        if app is None:
            return
        if not text.strip():
            if fallback is not None:
                fallback()
            else:
                self._say("Markiere erst einen Text – dann helfe ich dir damit.", 5)
            return
        if len(text) > MAX_CHARS:
            self._say(f"Das ist mir zu lang ({len(text)} Zeichen, höchstens {MAX_CHARS}).", 6)
            return
        chat = app.features.get("ai_chat")
        if chat is None or not chat.is_ready():
            app.say(app.pet_name, "Für die Text-Werkzeuge brauche ich einen KI-Zugang – Einstellungen → KI.", 10,
                    buttons=[("Einstellungen", lambda: app.open_settings("KI"), True)])
            return
        self.text = text
        app.bubble.dismiss()
        if not app.pet_hidden:
            app.brain.task = None
            app.brain.set_state(State.SIT, 60)
        self._ensure_menu().open(text, app.pet_window.head_anchor())
        app.apply_capture()

    # ------------------------------------------------------------------ #
    # 2. Werkzeug anwenden
    # ------------------------------------------------------------------ #
    def run_tool(self, tool_id: str, custom: str = "") -> None:
        app = self.ctx.app
        chat = app.features.get("ai_chat") if app is not None else None
        if chat is None or not self.text:
            return
        tool = CUSTOM if tool_id == CUSTOM.id else tool_by_id(tool_id)
        if tool is None:
            return
        instruction = custom if tool is CUSTOM else tool.instruction
        self._tool_label = custom[:28] if tool is CUSTOM else tool.label
        self._replace_default = tool.replace
        try:
            provider = chat.make()
        except AIError as exc:
            self._say(f"Hoppla: {exc}", 10)
            return
        self._job += 1
        job = self._job
        self.busy = True
        self.menu.show_working(self._tool_label)
        messages = build_request(instruction, self.text)
        log.info("Text-Werkzeug %s (%d Zeichen)", tool.id, len(self.text))

        def work() -> None:
            try:
                self._bridge.done.emit(job, provider.chat(SYSTEM, messages, one_shot=True), None)
            except AIError as exc:
                self._bridge.done.emit(job, None, str(exc))
            except Exception as exc:  # noqa: BLE001
                log.warning("Text-Werkzeug fehlgeschlagen: %s", type(exc).__name__)
                self._bridge.done.emit(job, None, provider.scrub(f"Unerwarteter Fehler: {exc}"))

        threading.Thread(target=work, name="text-tools", daemon=True).start()

    def _on_done(self, job: int, answer, error) -> None:
        if job != self._job or self.menu is None:
            return
        self.busy = False
        if error:
            self.menu.show_menu()
            self._say(f"Hoppla: {error}", 10)
            return
        self.menu.show_result(self._tool_label, clean_result(answer or "", self.text), self._replace_default)

    # ------------------------------------------------------------------ #
    # 3. Ersetzen oder kopieren
    # ------------------------------------------------------------------ #
    def replace(self, text: str) -> None:
        self.menu.close_menu()
        self.bring_back(self.target)          # zurück ins Programm mit der Markierung
        QTimer.singleShot(150, lambda: self._insert(text))

    def _insert(self, text: str) -> None:
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        action, sure = textinsert.decide(self.focus_info())
        if action == textinsert.CLIPBOARD:
            clipboard.setText(text)
            self._say("Dort kann ich nicht hineinschreiben – das Ergebnis liegt in der Zwischenablage "
                      "(Strg + V).", 8)
            return
        previous = _copy_mime(clipboard.mimeData()) if sure else None
        clipboard.setText(text)
        self.paste()
        if previous is not None:
            QTimer.singleShot(RESTORE_AFTER_MS, lambda: clipboard.setMimeData(previous))
        else:
            self._say("Ersetzt – und zur Sicherheit auch in der Zwischenablage.", 4)
        app = self.ctx.app
        if app is not None and not app.pet_hidden:
            app.hearts(2)

    def copy(self, text: str) -> None:
        from PySide6.QtGui import QGuiApplication

        QGuiApplication.clipboard().setText(text)
        self.menu.close_menu()
        self._say("Kopiert – mit Strg + V einfügen.", 3)

    def _say(self, text: str, timeout: float) -> None:
        app = self.ctx.app
        if app is not None:
            app.say(app.pet_name, text, timeout)
