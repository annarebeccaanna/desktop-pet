"""Eingabe-Sprechblase für den KI-Chat – geht vom Tier aus.

* Enter schickt die Frage ab, Esc schließt.
* Spracheingabe (Alt + Copilot): Die Blase holt sich den Fokus und startet die
  Windows-Spracheingabe (Win + H), die direkt ins Feld schreibt. Sobald eine Weile
  nichts Neues mehr dazukommt, wird automatisch abgeschickt (Enter = sofort).

Anders als die normale Sprechblase nimmt dieses Fenster den Tastaturfokus an.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QTimer, Qt, Signal
from PySide6.QtGui import QKeyEvent, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from ..win import input as win_input
from . import theme as theme_mod
from .retro import balloon_path, pixel_label
from .speech_bubble import PAD, TAIL, _CloseX, bubble_position

VOICE_SEND_AFTER = 2.5      # s ohne neue Wörter → automatisch abschicken
VOICE_WAIT_KEYS = 2.0       # s: so lange auf das Loslassen von Alt/Win/Umschalt warten


class _Line(QLineEdit):
    escape = Signal()

    def keyPressEvent(self, e: QKeyEvent) -> None:  # noqa: N802
        if e.key() == Qt.Key_Escape:
            self.escape.emit()
            return
        super().keyPressEvent(e)


class ChatInput(QWidget):
    submitted = Signal(str)
    closed = Signal()

    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("Desktop Pets – KI-Chat")
        self._tail_local: QPoint | None = None
        self.voice = False
        self._waited = 0.0

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
        outer.addWidget(self.line)
        self.hint = QLabel("", self)
        self.hint.setObjectName("muted")
        self.hint.setFont(t.ui_font(8))
        self.hint.setStyleSheet("background: transparent;")
        self.hint.setWordWrap(True)
        self.hint.setMaximumWidth(300)
        outer.addWidget(self.hint)

        self._send_timer = QTimer(self)
        self._send_timer.setSingleShot(True)
        self._send_timer.timeout.connect(self._submit)
        self._keys_timer = QTimer(self)
        self._keys_timer.setInterval(50)
        self._keys_timer.timeout.connect(self._wait_for_keys)

    # ---------- öffentlich ----------
    def open(self, title: str, anchor: QPoint, voice: bool = False) -> None:
        self.voice = voice and win_input.voice_supported()
        self.title.setText(title.upper())
        self.line.clear()
        if self.voice:
            self.line.setPlaceholderText("Sprich jetzt …")
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
        if self.voice:
            self._waited = 0.0
            self._keys_timer.start()

    def follow(self, anchor: QPoint) -> None:
        x, y = bubble_position(anchor, self.width(), self.height())
        self.move(x, y)
        self._tail_local = QPoint(anchor.x() - x, anchor.y() - y)
        self.update()

    def close_input(self) -> None:
        self._send_timer.stop()
        self._keys_timer.stop()
        if self.isVisible():
            self.hide()
            self.closed.emit()

    # ---------- intern ----------
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
        if self.voice and text.strip():
            self._send_timer.start(int(VOICE_SEND_AFTER * 1000))

    def _submit(self) -> None:
        self._send_timer.stop()
        text = self.line.text().strip()
        if not text:
            return
        self.close_input()
        self.submitted.emit(text)

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
