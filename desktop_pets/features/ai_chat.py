"""KI-Chat (Phase 5): Mit dem Tier chatten – über einen eigenen API-Key.

* Öffnen: Copilot-Taste (Aktion „KI-Chat öffnen“) oder ``Strg + Alt + K``.
  Spracheingabe: Alt + Copilot oder ``Strg + Alt + Umschalt + K``.
* Eine Eingabe-Sprechblase geht vom Tier aus; die Antwort kommt als Sprechblase.
* Anbieter, Key, Modell und Persönlichkeit: Einstellungen → Tab „KI“.
* Datenschutz: Es geht nur der Chattext hinaus (nie Fenstertitel, nie Screenshots).
  Der Chat wird nicht gespeichert und nicht protokolliert. Im Pause-Modus ist er aus.
* Ohne hinterlegten Key bleibt der Schalter ausgegraut.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from ..core.log import get_logger
from ..core.modes import Mode
from ..pet.brain import State
from .ai.chat import Conversation, system_prompt
from .ai.keys import KeyStore
from .ai.providers import KEY_OPTIONAL, PROVIDERS, AIError, make_provider
from .base import Feature, MenuAction, register

if TYPE_CHECKING:  # pragma: no cover
    from ..ui.chat_input import ChatInput

log = get_logger("ai_chat")

MAX_SHOWN = 700          # Zeichen in der Sprechblase; alles über „Kopieren“


class _Bridge(QObject):
    """Arbeits-Thread → GUI-Thread."""

    done = Signal(int, object, object)      # Anfrage-Nr., Antwort, Fehlertext


@register
class AIChat(Feature):
    id = "ai_chat"
    name = "KI-Chat"
    description = "Chatten über eigenen API-Key (Copilot-Taste oder Strg+Alt+K)"
    category = "social"
    default_enabled = False
    allowed_in_pause = False
    pause_label = "immer aus"
    order = 20

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.keys = KeyStore()
        self.conversation = Conversation()
        self.input: ChatInput | None = None
        self.provider_factory = make_provider        # in Tests ersetzbar
        self.busy = False
        self._request = 0
        self._last_answer = ""
        self._bridge = _Bridge()
        self._bridge.done.connect(self._on_done)

    # ------------------------------------------------------------------ #
    # Anbieter und Key
    # ------------------------------------------------------------------ #
    @property
    def provider_id(self) -> str:
        pid = self.ctx.settings.get("ai.provider") or ""
        return pid if pid in PROVIDERS else ""

    def model_for(self, pid: str) -> str:
        info = PROVIDERS.get(pid)
        return self.ctx.settings.get(f"ai.models.{pid}") or (info.default_model if info else "")

    def base_url_for(self, pid: str) -> str:
        info = PROVIDERS.get(pid)
        return self.ctx.settings.get(f"ai.base_urls.{pid}") or (info.base_url if info else "")

    def is_ready(self, pid: str | None = None) -> bool:
        pid = pid if pid is not None else self.provider_id
        if not pid:
            return False
        if pid in KEY_OPTIONAL:
            return bool(self.base_url_for(pid))
        return self.keys.has(pid)

    @property
    def available(self) -> bool:            # ohne Key ausgegraut
        return self.is_ready()

    def make(self, pid: str | None = None):
        pid = pid or self.provider_id
        return self.provider_factory(pid, self.keys.get(pid), model=self.model_for(pid),
                                     base_url=self.base_url_for(pid))

    def personality(self) -> str:
        app = self.ctx.app
        if app is None:
            return ""
        own = self.ctx.settings.get(f"ai.personality.{app.pack.id}")
        return own if own is not None else app.pack.prompt

    # ------------------------------------------------------------------ #
    # Lebenszyklus
    # ------------------------------------------------------------------ #
    def _ensure_input(self) -> "ChatInput":
        if self.input is None:
            from ..ui.chat_input import ChatInput

            self.input = ChatInput()
            self.input.submitted.connect(self.send)
        return self.input

    @property
    def windows(self) -> list:
        return [self.input] if self.input is not None else []

    def enable(self) -> None:
        # Beim ersten Einschalten übernimmt die Copilot-Taste den Chat – vorher war
        # „Einstellungen öffnen“ nur deshalb Standard, weil es noch keinen Chat gab.
        settings = self.ctx.settings
        if not settings.get("ai.copilot_switched"):
            settings.set("ai.copilot_switched", True)
            if settings.get("general.copilot_action", "settings") == "settings":
                settings.set("general.copilot_action", "ai_chat")

    def disable(self) -> None:
        self._request += 1          # laufende Antworten verwerfen
        self.busy = False
        if self.input is not None:
            self.input.close_input()

    def on_mode_changed(self, mode: Mode) -> None:
        if mode == Mode.PAUSE:
            self.disable()

    def tick(self, dt: float) -> None:  # noqa: ARG002
        app = self.ctx.app
        if app is not None and self.input is not None and self.input.isVisible():
            self.input.follow(app.pet_window.head_anchor())

    def hotkeys(self) -> list:
        return [("ai_chat", lambda: self.open_input(voice=False)),
                ("ai_voice", lambda: self.open_input(voice=True))]

    def menu_actions(self, where: str) -> list[MenuAction]:
        if where not in ("tray", "pet") or self.ctx.modes.paused:
            return []
        return [MenuAction("Mit dem Tier chatten …", lambda: self.open_input(voice=False), order=48,
                           shortcut=self._shortcut())]

    def _shortcut(self) -> str:
        from ..win import hotkeys as hk

        try:
            return hk.format_hotkey(self.ctx.settings.get("hotkeys.ai_chat") or "")
        except hk.HotkeyError:
            return ""

    # ------------------------------------------------------------------ #
    # Chat
    # ------------------------------------------------------------------ #
    def open_input(self, voice: bool = False) -> None:
        app = self.ctx.app
        if app is None:
            return
        if self.ctx.modes.paused:
            app.tray.tray.showMessage("KI-Chat", "Im Pause-Modus ist der KI-Chat aus.")
            return
        if not self.enabled:
            text = ("Der KI-Chat ist aus. Schalte ihn unter Einstellungen → KI ein."
                    if self.is_ready() else "Für den Chat brauche ich erst einen API-Key – Einstellungen → KI.")
            app.say(app.pet_name, text, 10, buttons=[("Einstellungen", lambda: app.open_settings("KI"), True)])
            return
        if self.busy:
            app.say(app.pet_name, "Moment, ich überlege noch …", 4)
            return
        if app.pet_hidden:
            app.tray.tray.showMessage("KI-Chat", "Das Tier ist ausgeblendet (Strg + Alt + H blendet es ein).")
            return
        bed = app.features.get("bed")
        if app.in_bed and bed is not None:
            bed.wake_pet()
        app.bubble.dismiss()
        app.brain.task = None
        app.brain.target_x = None
        app.brain.set_state(State.SIT, 60)       # hinsetzen und zuhören
        self._ensure_input().open(f"Frag {app.pet_name}", app.pet_window.head_anchor(), voice=voice)

    def send(self, text: str) -> None:
        app = self.ctx.app
        if app is None or not self.active or not text.strip():
            return
        pid = self.provider_id
        try:
            provider = self.make(pid)
        except AIError as exc:
            self._show_error(str(exc))
            return
        messages = self.conversation.prepare(text.strip(), time.monotonic())
        system = system_prompt(app.pet_name, self.personality())
        self._request += 1
        number = self._request
        self.busy = True
        app.brain.set_state(State.SIT, 90)
        app.say(app.pet_name, "Hmm … ich überlege.", 0)
        log.info("Anfrage an %s (%s), %d Zeichen", pid, provider.model, len(text))

        def work() -> None:
            try:
                answer = provider.chat(system, messages)
                self._bridge.done.emit(number, answer, None)
            except AIError as exc:
                self._bridge.done.emit(number, None, str(exc))
            except Exception as exc:  # noqa: BLE001 – nie den Arbeits-Thread sterben lassen
                log.warning("KI-Anfrage fehlgeschlagen: %s", type(exc).__name__)
                self._bridge.done.emit(number, None, provider.scrub(f"Unerwarteter Fehler: {exc}"))

        threading.Thread(target=work, name="ai-chat", daemon=True).start()

    def _on_done(self, number: int, answer, error) -> None:
        if number != self._request:
            return                              # veraltet (Pause, abgeschaltet …)
        self.busy = False
        app = self.ctx.app
        if app is None or not self.active:
            return
        if error:
            self.conversation.failed()
            self._show_error(error)
            return
        answer = (answer or "").strip() or "…"
        self.conversation.answered(answer)
        self._last_answer = answer
        shown = answer if len(answer) <= MAX_SHOWN else answer[:MAX_SHOWN].rstrip() + " … (Kopieren für alles)"
        app.brain.set_state(State.SIT, 8)
        app.say(app.pet_name, shown, min(90.0, 10 + len(shown) / 15), wide=True, buttons=[
            ("Antworten", lambda: self.open_input(voice=False), True),
            ("Kopieren", self.copy_answer, False),
        ])
        app.sound.play(app.pack.sounds.get("call"), app.pack.path)

    def _show_error(self, error: str) -> None:
        app = self.ctx.app
        if app is None:
            return
        app.say(app.pet_name, f"Hoppla: {error}", 12,
                buttons=[("Einstellungen", lambda: app.open_settings("KI"), False)])

    def copy_answer(self) -> None:
        from PySide6.QtGui import QGuiApplication

        QGuiApplication.clipboard().setText(self._last_answer)

    def forget(self) -> None:
        self.conversation.reset()
