"""Sprechblasen über dem Tier (gelber Ballon, Titel in Pixelschrift, Schließen-X).

Ein eigenes, rahmenloses Fenster, das nie den Fokus stiehlt. Im Pause-Modus
zeigt die App keine Blasen (Meldungen werden gesammelt, siehe core/modes.py).
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPoint, QRect, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import theme as theme_mod
from .retro import balloon_path, pixel_label

TAIL = 18
PAD = 2


class _CloseX(QPushButton):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(15, 15)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Schließen")
        self.setStyleSheet("QPushButton { min-width: 0; min-height: 0; padding: 0; border: 1px solid #808080;"
                           " border-radius: 2px; background: white; }"
                           "QPushButton:hover { border: 1px solid #F8B33A; padding: 0; }")

    def paintEvent(self, e) -> None:  # noqa: N802
        super().paintEvent(e)
        p = QPainter(self)
        p.setPen(QPen(QColor("black"), 1))
        p.drawLine(4, 4, 10, 10)
        p.drawLine(10, 4, 4, 10)
        p.drawLine(5, 4, 11, 10)
        p.drawLine(11, 4, 5, 10)


def bubble_position(anchor: QPoint, w: int, h: int) -> tuple[int, int]:
    """Blase links vom Tier, Schwanz rechts unten – oder rechts, wenn links kein Platz ist."""
    screen = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
    geo = screen.availableGeometry()
    x = anchor.x() - w + 40
    if x < geo.left() + 4:
        x = anchor.x() - 40
    x = max(geo.left() + 4, min(x, geo.right() - w - 4))
    y = max(geo.top() + 4, anchor.y() - h)
    return x, y


class SpeechBubble(QWidget):
    closed = Signal()

    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._anchor = QPoint(0, 0)
        self._tail_local: QPoint | None = None
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.dismiss)

        t = theme_mod.current()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10 + TAIL)
        outer.setSpacing(5)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.title = pixel_label("", color="pixel_blue", parent=self)
        head.addWidget(self.title, 1)
        self.btn_close = _CloseX(self)
        self.btn_close.clicked.connect(self.dismiss)
        head.addWidget(self.btn_close, 0, Qt.AlignTop)
        outer.addLayout(head)
        self.text = QLabel("", self)
        self.text.setWordWrap(True)
        self.text.setFont(t.ui_font(9))
        self.text.setStyleSheet("background: transparent;")
        self.text.setMaximumWidth(260)
        outer.addWidget(self.text)
        self.buttons = QHBoxLayout()
        self.buttons.setSpacing(6)
        outer.addLayout(self.buttons)
        self._outer = outer

    # ---------- öffentlich ----------
    def show_message(self, title: str, text: str, anchor: QPoint, timeout_s: float = 7.0,
                     buttons: list[tuple[str, Callable[[], None], bool]] | None = None,
                     wide: bool = False) -> None:
        """``wide``: breiter und markierbar – z. B. für Antworten aus dem KI-Chat."""
        if wide:
            # Lange Antworten: so breit wie nötig (bis 380 px), damit die Blase nicht zum Turm wird
            natural = self.text.fontMetrics().horizontalAdvance(text) + 8
            self.text.setFixedWidth(max(220, min(380, natural)))
        else:
            self.text.setMinimumWidth(0)
            self.text.setMaximumWidth(260)
        self.text.setTextInteractionFlags(Qt.TextSelectableByMouse if wide else Qt.NoTextInteraction)
        self.text.setTextFormat(Qt.PlainText if wide else Qt.AutoText)
        self.title.setText(title.upper())
        self.title.setVisible(bool(title))
        self.text.setText(text)
        self.text.setVisible(bool(text))
        while self.buttons.count():
            item = self.buttons.takeAt(0)
            if item.widget():
                item.widget().hide()            # sofort weg, nicht erst beim Aufräumen
                item.widget().deleteLater()
        for label, cb, primary in buttons or []:
            btn = QPushButton(label, self)
            if primary:
                btn.setObjectName("primary")
            btn.setFocusPolicy(Qt.NoFocus)
            btn.clicked.connect(lambda _=False, c=cb: (self.dismiss(), c()))
            self.buttons.addWidget(btn)
            btn.show()          # sofort sichtbar, damit adjustSize() die volle Breite kennt
        if buttons:
            self.buttons.addStretch(1)
        self.adjustSize()
        self.follow(anchor)
        self.show()
        self.raise_()
        if timeout_s > 0:
            self._hide_timer.start(int(timeout_s * 1000))
        else:
            self._hide_timer.stop()

    def follow(self, anchor: QPoint) -> None:
        """Positioniert die Blase so, dass der Schwanz auf ``anchor`` (Kopf des Tiers) zeigt."""
        self._anchor = anchor
        x, y = bubble_position(anchor, self.width(), self.height())
        self.move(x, y)
        self._tail_local = QPoint(anchor.x() - x, anchor.y() - y)
        self.update()

    def dismiss(self) -> None:
        self._hide_timer.stop()
        if self.isVisible():
            self.hide()
            self.closed.emit()

    # ---------- Zeichnen ----------
    def paintEvent(self, _e) -> None:  # noqa: N802
        t = theme_mod.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        body = QRect(PAD, PAD, self.width() - 2 * PAD - 1, self.height() - TAIL - PAD - 1)
        tail = self._tail_local
        if tail is not None:
            tail = QPoint(min(max(tail.x(), body.left() + 6), body.right() - 6), self.height() - 2)
        path = balloon_path(body, tail)
        p.setBrush(t.color("balloon"))
        p.setPen(QPen(t.color("balloon_border"), 1))
        p.drawPath(path)
