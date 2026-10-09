"""Diktieren: Sprechen → Text dort einfügen, wo man gerade schreibt.

* Start/Stopp: ``Strg + Alt + D`` (änderbar) oder Copilot-Taste mit Aktion „Diktieren“.
* Das Tier hört zu; was es versteht, steht live in seiner Sprechblase. Ist man kurz
  still, ist das Diktat fertig (oder Kürzel nochmal drücken).
* Hat ein Eingabefeld den Fokus (dort, wo man hineingeklickt hat), wird der Text
  eingefügt – sonst landet er in der Zwischenablage und das Tier sagt Bescheid.
* Erkennung ohne Fenster über die Windows-Spracherkennung (win/speech.py). Geht das
  nicht, springt die Windows-Spracheingabe (Win + H) ein – sie schreibt selbst ins Feld.
* Kein API-Key nötig, nichts verlässt den Rechner außer über Windows selbst.
"""

from __future__ import annotations

from PySide6.QtCore import QMimeData, QObject, QTimer, Signal

from ..core.log import get_logger
from ..pet.brain import State
from ..win import input as win_input
from ..win import speech, textinsert
from . import punctuation
from .base import Feature, MenuAction, Option, register

log = get_logger("dictation")

RESTORE_AFTER_MS = 700        # alte Zwischenablage zurück, nachdem eingefügt wurde
WAIT_KEYS_MS = 1500           # so lange warten, bis Strg/Alt/… losgelassen sind


class _Bridge(QObject):
    partial = Signal(str)
    final = Signal(str)
    error = Signal(str)


def _copy_mime(mime: QMimeData | None) -> QMimeData | None:
    if mime is None:
        return None
    copy = QMimeData()
    for fmt in mime.formats():
        copy.setData(fmt, mime.data(fmt))
    return copy


@register
class Dictation(Feature):
    id = "dictation"
    name = "Diktieren"
    description = "Sprechen statt tippen: fügt ein, wo du schreibst (Strg+Alt+D)"
    category = "work"
    default_enabled = True
    allowed_in_pause = True          # auch im Termin nutzbar – dann ohne Sprechblase
    pause_label = "still"
    order = 15
    options = [
        Option("punctuation", "Gesprochene Satzzeichen („Punkt“, „Komma“, „neue Zeile“ …)", True, kind="bool"),
    ]

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self._bridge = _Bridge()
        self._bridge.partial.connect(self._on_partial)
        self._bridge.final.connect(self._on_final)
        self._bridge.error.connect(self._on_error)
        self.listener = speech.Dictation(self._bridge.partial.emit, self._bridge.final.emit,
                                         self._bridge.error.emit)
        self.listening = False
        # in Tests ersetzbar
        self.focus_info = textinsert.focus_info
        self.paste = textinsert.paste
        self.speech_available = speech.available
        self.last_result = ""                  # "inserted", "clipboard", "winh", "nothing", …

    # ------------------------------------------------------------------ #
    def hotkeys(self) -> list:
        return [("dictate", self.toggle)]

    def menu_actions(self, where: str) -> list[MenuAction]:
        if where != "tray":
            return []
        label = "Diktat beenden" if self.listening else "Diktieren"
        return [MenuAction(label, self.toggle, order=47, shortcut=self._shortcut())]

    def _shortcut(self) -> str:
        from ..win import hotkeys as hk

        try:
            return hk.format_hotkey(self.ctx.settings.get("hotkeys.dictate") or "")
        except hk.HotkeyError:
            return ""

    def disable(self) -> None:
        self.cancel()

    # ------------------------------------------------------------------ #
    def toggle(self) -> None:
        if self.listening:
            self.listener.finish()             # jetzt fertig – Bisheriges wird eingefügt
        else:
            self.start()

    def start(self) -> None:
        app = self.ctx.app
        if app is None or not self.enabled:
            return
        if not self.speech_available():
            self._fallback_winh("Ich nehme die Windows-Spracheingabe.")
            return
        self.listening = True
        self.last_result = ""
        if not self.ctx.modes.paused and not app.pet_hidden:
            app.brain.task = None
            app.brain.set_state(State.SIT, 60)  # hinsetzen und zuhören
        self._say("🎤 Ich höre zu …", 0)
        self.listener.start()

    def cancel(self) -> None:
        if self.listening:
            self.listener.cancel()
            self.listening = False
            self._dismiss()

    # ---------- Rückmeldungen der Spracherkennung ----------
    def _on_partial(self, text: str) -> None:
        if self.listening:
            if self.option("punctuation"):
                text = punctuation.apply(text)
            self._say(f"🎤 {text} …", 0)

    def _on_final(self, text: str) -> None:
        if not self.listening:
            return
        self.listening = False
        if self.option("punctuation"):
            text = punctuation.apply(text)
        self._wait_for_keys(text, WAIT_KEYS_MS)

    def _on_error(self, reason: str) -> None:
        if not self.listening:
            return
        self.listening = False
        if reason in (speech.PRIVACY, speech.LANGUAGE, speech.FAILED):
            hint = {
                speech.PRIVACY: "Für Diktieren ohne Fenster bitte in Windows „Online-Spracherkennung“ "
                                "einschalten. Jetzt nehme ich die Windows-Spracheingabe.",
                speech.LANGUAGE: "Die Windows-Spracherkennung kennt deine Sprache nicht – ich nehme Win + H.",
            }.get(reason, "Das hat nicht geklappt – ich nehme die Windows-Spracheingabe.")
            self._fallback_winh(hint)
        elif reason == speech.MICROPHONE:
            self.last_result = "microphone"
            self._say("Ich finde kein Mikrofon (oder darf es nicht benutzen).", 8)
        else:
            self.last_result = "nothing"
            self._say("Ich habe nichts gehört.", 4)

    # ---------- Einfügen ----------
    def _wait_for_keys(self, text: str, left_ms: int) -> None:
        """Erst einfügen, wenn keine Taste mehr gedrückt ist – sonst wird aus Strg + V etwas anderes."""
        if win_input.modifiers_down() and left_ms > 0:
            QTimer.singleShot(50, lambda: self._wait_for_keys(text, left_ms - 50))
            return
        self.deliver(text)

    def deliver(self, text: str) -> None:
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        action, sure = textinsert.decide(self.focus_info())
        log.info("Diktat fertig (%d Zeichen) → %s%s", len(text), action, " (sicher)" if sure else "")
        if action == textinsert.INSERT:
            previous = _copy_mime(clipboard.mimeData()) if sure else None
            clipboard.setText(text)
            self.paste()
            if previous is not None:
                QTimer.singleShot(RESTORE_AFTER_MS, lambda: clipboard.setMimeData(previous))
            self.last_result = "inserted"
            self._dismiss()
            app = self.ctx.app
            if app is not None and not self.ctx.modes.paused and not app.pet_hidden:
                app.hearts(1)
            return
        clipboard.setText(text)
        self.last_result = "clipboard"
        # Nirgends zum Hineinschreiben → das Tier sagt Bescheid
        shown = text if len(text) <= 300 else text[:300].rstrip() + " …"
        self._say(f"„{shown}“\n\nIch habe es in die Zwischenablage gelegt – mit Strg + V einfügen.", 12,
                  tray_too=True)

    def _fallback_winh(self, hint: str) -> None:
        self.last_result = "winh"
        self._say(hint, 6)
        win_input.start_dictation()

    # ---------- Sprechblase ----------
    def _say(self, text: str, timeout: float, tray_too: bool = False) -> None:
        app = self.ctx.app
        if app is None:
            return
        if self.ctx.modes.paused:
            if tray_too:                       # im Pause-Modus keine Blase – aber Bescheid geben
                app.tray.tray.showMessage("Diktat", "In der Zwischenablage – mit Strg + V einfügen.")
            return
        app.say(app.pet_name, text, timeout)

    def _dismiss(self) -> None:
        app = self.ctx.app
        if app is not None:
            app.bubble.dismiss()
