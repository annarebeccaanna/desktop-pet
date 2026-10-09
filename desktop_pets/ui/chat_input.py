"""Eingabe-Sprechblase für den KI-Chat – geht vom Tier aus.

* Enter schickt die Frage ab, Esc schließt.
* Spracheingabe (Alt + Copilot):
  - Standard „ohne Fenster“: Die Windows-Spracherkennung hört im Hintergrund zu
    (win/speech.py), das Gesagte erscheint live im Feld und geht ab, sobald man
    kurz nichts mehr sagt.
  - Rückfall oder auf Wunsch: Windows-Spracheingabe (Win + H, mit ihrem Fenster),
    die ins Feld schreibt; nach 2,5 s ohne neue Wörter wird abgeschickt.
  Enter = sofort senden, Esc = abbrechen, 🎤 = nochmal sprechen.

Anders als die normale Sprechblase nimmt dieses Fenster den Tastaturfokus an.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QTimer, Qt, Signal
from PySide6.QtGui import QKeyEvent, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ..win import input as win_input
from ..win import speech
from . import theme as theme_mod
from .retro import balloon_path, pixel_label
from .speech_bubble import PAD, TAIL, _CloseX, bubble_position

VOICE_SEND_AFTER = 2.5      # s ohne neue Wörter → automatisch abschicken
VOICE_WAIT_KEYS = 2.0       # s: so lange auf das Loslassen von Alt/Win/Umschalt warten


class _Line(QLineEdit):
    escape = Signal()
    typed = Signal()                  # Mensch tippt selbst → Zuhören beenden

    def keyPressEvent(self, e: QKeyEvent) -> None:  # noqa: N802
        if e.key() == Qt.Key_Escape:
            self.escape.emit()
            return
        if e.key() not in (Qt.Key_Return, Qt.Key_Enter):
            self.typed.emit()
        super().keyPressEvent(e)


SPEECH_HINTS = {
    speech.PRIVACY: "Für die Spracheingabe ohne Fenster in Windows „Online-Spracherkennung“ einschalten "
                    "(Einstellungen → Datenschutz → Spracherkennung). Solange nehme ich Win + H.",
    speech.LANGUAGE: "Die Windows-Spracherkennung kennt deine Sprache nicht – ich nehme Win + H.",
    speech.FAILED: "Die Spracherkennung ohne Fenster klappt gerade nicht – ich nehme Win + H.",
    speech.MICROPHONE: "Kein Mikrofon gefunden oder kein Zugriff (Windows → Datenschutz → Mikrofon).",
    speech.NOTHING: "Ich habe nichts gehört. 🎤 = nochmal sprechen, oder einfach tippen.",
}


class ChatInput(QWidget):
    submitted = Signal(str, bool)     # Text, sachlich?
    closed = Signal()
    _heard_partial = Signal(str)      # aus dem Spracherkennungs-Thread
    _heard_final = Signal(str)
    _heard_error = Signal(str)

    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("Desktop Pets – KI-Chat")
        self._tail_local: QPoint | None = None
        self.voice = False
        self.serious = False
        self._title = ""
        self.mode = ""                # "silent" (ohne Fenster), "winh" oder "" (tippen)
        self._waited = 0.0
        self._heard_partial.connect(self._on_partial)
        self._heard_final.connect(self._on_final)
        self._heard_error.connect(self._on_speech_error)
        self.dictation = speech.Dictation(self._heard_partial.emit, self._heard_final.emit,
                                          self._heard_error.emit)

        t = theme_mod.current()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10 + TAIL)
        outer.setSpacing(6)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.title = pixel_label("", color="pixel_blue", parent=self)
        head.addWidget(self.title, 1)
        self.btn_close = _CloseX(self)
        self.btn_close.clicked.connect(self.close_input)
        head.addWidget(self.btn_close, 0, Qt.AlignTop)
        outer.addLayout(head)
        self.line = _Line(self)
        self.line.setMinimumWidth(300)
        self.line.setFont(t.ui_font(9))
        self.line.setMaxLength(2000)
        self.line.returnPressed.connect(self._submit)
        self.line.escape.connect(self.close_input)
        self.line.textChanged.connect(self._on_text_changed)
        self.line.typed.connect(self._stop_listening)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self.line, 1)
        self.btn_mic = QPushButton("🎤", self)
        self.btn_mic.setToolTip("Nochmal sprechen")
        self.btn_mic.setFixedWidth(34)
        self.btn_mic.setFocusPolicy(Qt.NoFocus)
        self.btn_mic.clicked.connect(self._listen_again)
        row.addWidget(self.btn_mic)
        outer.addLayout(row)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self.btn_serious = QPushButton("Sachlich", self)
        self.btn_serious.setCheckable(True)
        self.btn_serious.setFocusPolicy(Qt.NoFocus)
        self.btn_serious.setToolTip("Sachliche Anfrage: ohne Tier-Rolle, ausführlichere Antwort\n"
                                    "(Strg + Copilot oder Strg + Alt + E)")
        self.btn_serious.setStyleSheet("QPushButton:checked { background: #FCE7B2; border: 1px solid #F8B33A;"
                                       " font-weight: bold; }")
        self.btn_serious.toggled.connect(self._set_serious)
        mode_row.addWidget(self.btn_serious)
        mode_row.addStretch(1)
        self.hint = QLabel("", self)
        self.hint.setObjectName("muted")
        self.hint.setFont(t.ui_font(8))
        self.hint.setStyleSheet("background: transparent;")
        self.hint.setWordWrap(True)
        self.hint.setMaximumWidth(300)
        outer.addWidget(self.hint)
        outer.addLayout(mode_row)

        self._send_timer = QTimer(self)
        self._send_timer.setSingleShot(True)
        self._send_timer.timeout.connect(self._submit)
        self._keys_timer = QTimer(self)
        self._keys_timer.setInterval(50)
        self._keys_timer.timeout.connect(self._wait_for_keys)

    # ---------- öffentlich ----------
    def open(self, title: str, anchor: QPoint, voice: bool = False, silent: bool = True,
             serious: bool = False) -> None:
        self.dictation.cancel()
        self._title = title
        self.btn_serious.blockSignals(True)
        self.btn_serious.setChecked(serious)
        self.btn_serious.blockSignals(False)
        self._set_serious(serious)
        self.voice = voice and win_input.voice_supported()
        self.mode = ("silent" if silent and speech.available() else "winh") if self.voice else ""
        self.btn_mic.setVisible(self.voice)
        self.line.clear()
        if self.voice:
            self.line.setPlaceholderText("Ich höre zu … sprich jetzt")
            self.hint.setText("Ich schicke es ab, sobald du fertig bist. Enter = sofort, Esc = abbrechen.")
        else:
            self.line.setPlaceholderText("Frag mich etwas …")
            note = "Enter = senden, Esc = schließen."
            if voice:
                note += " Spracheingabe gibt es nur unter Windows."
            self.hint.setText(note)
        self.adjustSize()
        self.follow(anchor)
        self.show()
        self.raise_()
        self.activateWindow()
        win_input.force_foreground(int(self.winId()))
        self.line.setFocus(Qt.OtherFocusReason)
        if self.mode == "silent":
            self.dictation.start()
        elif self.mode == "winh":
            self._start_winh()

    def follow(self, anchor: QPoint) -> None:
        x, y = bubble_position(anchor, self.width(), self.height())
        self.move(x, y)
        self._tail_local = QPoint(anchor.x() - x, anchor.y() - y)
        self.update()

    def close_input(self) -> None:
        self.dictation.cancel()
        self._send_timer.stop()
        self._keys_timer.stop()
        if self.isVisible():
            self.hide()
            self.closed.emit()

    # ---------- intern ----------
    def _set_serious(self, on: bool) -> None:
        self.serious = on
        self.btn_serious.setText("✓ Sachlich" if on else "Sachlich")
        self.title.setText(("Sachliche Frage" if on else getattr(self, "_title", "")).upper())
        self.update()

    def _start_winh(self) -> None:
        self.mode = "winh"
        self._waited = 0.0
        self._keys_timer.start()

    def _stop_listening(self) -> None:
        """Wer tippt, will nicht mehr sprechen."""
        if self.mode == "silent":
            self.dictation.cancel()
        self._send_timer.stop()
        self.mode = ""

    def _listen_again(self) -> None:
        self.line.clear()
        self.hint.setText("Ich höre zu … Enter = sofort senden, Esc = abbrechen.")
        if speech.available() and self.mode != "winh":
            self.mode = "silent"
            self.dictation.cancel()
            self.dictation.start()
        else:
            self._start_winh()

    def _on_partial(self, text: str) -> None:
        if self.isVisible() and self.mode == "silent":
            self.line.setText(text)

    def _on_final(self, text: str) -> None:
        if self.isVisible() and self.mode == "silent":
            self.line.setText(text)
            self._submit()

    def _on_speech_error(self, reason: str) -> None:
        if not self.isVisible() or self.mode != "silent":
            return
        self.hint.setText(SPEECH_HINTS.get(reason, SPEECH_HINTS[speech.FAILED]))
        if reason in (speech.PRIVACY, speech.LANGUAGE, speech.FAILED):
            self._start_winh()               # Rückfall: Windows-Spracheingabe mit Fenster
        else:
            self.mode = ""

    def _wait_for_keys(self) -> None:
        """Erst wenn Alt/Win/Umschalt los sind, Win + H schicken – sonst wird es eine andere Kombination."""
        self._waited += 0.05
        if win_input.modifiers_down() and self._waited < VOICE_WAIT_KEYS:
            return
        self._keys_timer.stop()
        win_input.force_foreground(int(self.winId()))
        self.line.setFocus(Qt.OtherFocusReason)
        win_input.start_dictation()

    def _on_text_changed(self, text: str) -> None:
        if self.mode == "winh" and text.strip():
            self._send_timer.start(int(VOICE_SEND_AFTER * 1000))

    def _submit(self) -> None:
        self.dictation.cancel()
        self._send_timer.stop()
        text = self.line.text().strip()
        if not text:
            return
        self.close_input()
        self.submitted.emit(text, self.serious)

    def paintEvent(self, _e) -> None:  # noqa: N802
        t = theme_mod.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        body = QRect(PAD, PAD, self.width() - 2 * PAD - 1, self.height() - TAIL - PAD - 1)
        tail = self._tail_local
        if tail is not None:
            tail = QPoint(min(max(tail.x(), body.left() + 6), body.right() - 6), self.height() - 2)
        p.setBrush(t.color("balloon"))
        p.setPen(QPen(t.color("balloon_border"), 1))
        p.drawPath(balloon_path(body, tail))
