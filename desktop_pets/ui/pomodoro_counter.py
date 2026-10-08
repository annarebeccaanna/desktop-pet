"""Kleiner Pixelzähler für Pomodoro: Restzeit + grüner Block-Fortschrittsbalken.

Liegt anfangs unten rechts in der Ecke (über der Taskleiste), lässt sich mit der
Maus wegziehen – die Position wird gemerkt. Klick in „Geschafft!“ startet die
Pause, Rechtsklick öffnet ein kleines Menü.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from ..core import paths
from . import theme as theme_mod

W, H = 128, 44
MARGIN = 12
DRAG_THRESHOLD = 4


class PomodoroCounter(QWidget):
    moved = Signal(int, int)        # neue linke obere Ecke
    clicked = Signal()
    rightClicked = Signal(QPoint)
    shown = Signal()

    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowTitle("Desktop Pets – Pomodoro")
        self.setFixedSize(W, H)
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("Pomodoro – ziehen zum Verschieben, Rechtsklick für Optionen")
        self._time = "55:00"
        self._label = "Arbeit"
        self._progress = 0.0
        self._resting = False
        self._press: QPoint | None = None
        self._grab = QPoint()
        self._dragging = False
        self._tomato = QPixmap(str(paths.assets_dir() / "tomato.png"))

    # ---------- Inhalt ----------
    def set_state(self, time_text: str, label: str, progress: float, resting: bool) -> None:
        changed = (time_text, label, round(progress, 3), resting) != (
            self._time, self._label, round(self._progress, 3), self._resting)
        self._time, self._label, self._progress, self._resting = time_text, label, progress, resting
        if changed:
            self.update()

    def place(self, saved: list | None) -> None:
        """Gespeicherte Position (falls noch auf einem Bildschirm), sonst unten rechts."""
        if saved and len(saved) == 2:
            pos = QPoint(int(saved[0]), int(saved[1]))
            if QGuiApplication.screenAt(pos + QPoint(W // 2, H // 2)) is not None:
                self.move(pos)
                return
        g = QGuiApplication.primaryScreen().availableGeometry()
        self.move(g.right() - W - MARGIN, g.bottom() - H - MARGIN)

    # ---------- Zeichnen ----------
    def paintEvent(self, _e) -> None:  # noqa: N802
        t = theme_mod.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        body = QRect(0, 0, W - 1, H - 1)
        p.setBrush(t.color("dialog_bg"))
        p.setPen(QPen(t.color("button_border"), 1))
        p.drawRoundedRect(body, 5, 5)
        p.setRenderHint(QPainter.Antialiasing, False)
        # Glanzlinie oben
        p.setPen(QColor(255, 255, 255, 200))
        p.drawLine(4, 1, W - 5, 1)
        if not self._tomato.isNull():
            p.drawPixmap(QRect(7, 8, self._tomato.width() * 2, self._tomato.height() * 2), self._tomato)
        p.setFont(t.pixel_font(16))
        p.setPen(t.color("pixel_blue"))
        p.drawText(QRect(32, 4, W - 38, 20), Qt.AlignLeft | Qt.AlignVCenter, self._time)
        p.setFont(t.pixel_font(8))
        p.setPen(t.color("pixel_green") if self._resting else t.color("text_muted"))
        p.drawText(QRect(32, 22, W - 38, 9), Qt.AlignLeft | Qt.AlignVCenter, self._label.upper())
        # Fortschrittsbalken aus grünen Blöcken (wie früher)
        bar = QRect(7, H - 11, W - 15, 7)
        p.setPen(QPen(QColor("#7F9DB9"), 1))
        p.setBrush(QColor("white"))
        p.drawRect(bar)
        blocks = (bar.width() - 2) // 6
        filled = int(round(blocks * max(0.0, min(1.0, self._progress))))
        green = QColor("#3C9A2E") if not self._resting else QColor("#57B847")
        for i in range(filled):
            p.fillRect(bar.left() + 2 + i * 6, bar.top() + 2, 4, bar.height() - 3, green)

    # ---------- Maus: ziehen, klicken ----------
    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() == Qt.LeftButton:
            self._press = e.globalPosition().toPoint()
            self._grab = self._press - self.pos()
            self._dragging = False
        elif e.button() == Qt.RightButton:
            self.rightClicked.emit(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if self._press is None or not (e.buttons() & Qt.LeftButton):
            return
        pos = e.globalPosition().toPoint()
        if not self._dragging and (pos - self._press).manhattanLength() > DRAG_THRESHOLD:
            self._dragging = True
            self.setCursor(Qt.ClosedHandCursor)
        if self._dragging:
            self.move(pos - self._grab)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() != Qt.LeftButton:
            return
        if self._dragging:
            self._dragging = False
            self.setCursor(Qt.OpenHandCursor)
            self.moved.emit(self.x(), self.y())
        elif self._press is not None:
            self.clicked.emit()
        self._press = None

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        self.shown.emit()
