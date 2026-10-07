"""Retro-Bausteine: Fenster mit eigener Titelleiste, Statusleiste, Pixel-Labels, Hinweis-Ballon.

Die Fenster zeichnen ihre Titelleiste selbst (blauer Verlauf, Glanzstreifen,
abgerundete obere Ecken, Minimieren/Schließen). So sehen sie auf Windows 10
und 11 gleich aus. Windows 11 rundet die Ecken nicht ab (DWM), Schatten kommt
ebenfalls vom DWM.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QMouseEvent, QPainter, QPainterPath, QPen, QPixmap, QRegion
from PySide6.QtWidgets import (
    QAbstractButton, QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from ..win import dwm
from . import theme as theme_mod

TITLE_H = 30
BORDER = 4
CORNER = 7


class _CaptionButton(QAbstractButton):
    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(21, 21)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip({"close": "Schließen", "min": "Minimieren"}[kind])

    def enterEvent(self, e) -> None:  # noqa: N802
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:  # noqa: N802
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _e) -> None:  # noqa: N802
        t = theme_mod.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRect(0, 0, self.width() - 1, self.height() - 1)
        hover = self.underMouse()
        if self.kind == "close":
            top, bottom = QColor("#F08A6E") if hover else QColor("#EC7C60"), t.color("close_dark")
            if hover:
                bottom = t.color("close")
        else:
            top, bottom = QColor("#7FB2FF") if hover else QColor("#5E9CFF"), QColor("#1D5FD6")
        grad = QLinearGradient(0, 0, 0, r.height())
        grad.setColorAt(0, top)
        grad.setColorAt(1, bottom)
        p.setBrush(grad)
        p.setPen(QPen(QColor("white"), 1))
        p.drawRoundedRect(r.adjusted(0, 0, 0, 0), 3, 3)
        p.setRenderHint(QPainter.Antialiasing, False)
        pen = QPen(QColor("white"), 2)
        p.setPen(pen)
        if self.kind == "close":
            p.drawLine(6, 6, 14, 14)
            p.drawLine(14, 6, 6, 14)
        else:
            p.fillRect(QRect(6, 13, 8, 3), QColor("white"))
        if self.isDown():
            p.fillRect(r, QColor(0, 0, 0, 40))


class TitleBar(QWidget):
    closeClicked = Signal()
    minimizeClicked = Signal()

    def __init__(self, title: str, icon: QPixmap | None = None, minimizable: bool = True,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(TITLE_H)
        self._title = title
        self._icon = icon
        self._active = True
        self._drag_from: QPoint | None = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 6, 4)
        lay.setSpacing(2)
        lay.addStretch(1)
        if minimizable:
            self.btn_min = _CaptionButton("min", self)
            self.btn_min.clicked.connect(self.minimizeClicked)
            lay.addWidget(self.btn_min)
        self.btn_close = _CaptionButton("close", self)
        self.btn_close.clicked.connect(self.closeClicked)
        lay.addWidget(self.btn_close)

    def set_title(self, title: str) -> None:
        self._title = title
        self.update()

    def set_icon(self, icon: QPixmap | None) -> None:
        self._icon = icon
        self.update()

    def set_active(self, active: bool) -> None:
        self._active = active
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        t = theme_mod.current()
        p = QPainter(self)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, 0, h)
        if self._active:
            grad.setColorAt(0.0, t.color("title_gloss"))
            grad.setColorAt(0.12, t.color("title_to"))
            grad.setColorAt(0.45, t.color("title_from"))
            grad.setColorAt(0.85, t.color("title_from"))
            grad.setColorAt(1.0, t.color("title_to"))
        else:
            grad.setColorAt(0.0, t.color("title_inactive_to"))
            grad.setColorAt(1.0, t.color("title_inactive_from"))
        p.fillRect(self.rect(), grad)
        # heller Glanzstreifen oben
        p.fillRect(QRect(0, 1, w, 1), QColor(255, 255, 255, 90))
        x = 8
        if self._icon is not None and not self._icon.isNull():
            p.drawPixmap(QRect(x, (h - 16) // 2, 16, 16), self._icon)
            x += 22
        font = t.ui_font(9.5, bold=True)
        p.setFont(font)
        # leichter Schatten wie bei XP
        p.setPen(QColor(10, 24, 131, 160))
        p.drawText(QRect(x + 1, 1, w - x - 60, h), Qt.AlignVCenter | Qt.AlignLeft, self._title)
        p.setPen(t.color("title_text"))
        p.drawText(QRect(x, 0, w - x - 60, h), Qt.AlignVCenter | Qt.AlignLeft, self._title)

    # Verschieben per Ziehen an der Titelleiste
    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() == Qt.LeftButton:
            win = self.window().windowHandle()
            if win is not None and win.startSystemMove():
                return
            self._drag_from = e.globalPosition().toPoint() - self.window().frameGeometry().topLeft()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if self._drag_from is not None and e.buttons() & Qt.LeftButton:
            self.window().move(e.globalPosition().toPoint() - self._drag_from)

    def mouseReleaseEvent(self, _e) -> None:  # noqa: N802
        self._drag_from = None


def pixel_label(text: str, color: str | None = None, size_px: int = 8, parent: QWidget | None = None) -> QLabel:
    t = theme_mod.current()
    lab = QLabel(text.upper(), parent)
    lab.setFont(t.pixel_font(size_px))
    lab.setObjectName("pixel")
    if color:
        lab.setStyleSheet(f"color: {t.colors.get(color, color)}; background: transparent;")
    return lab


class StatusBar(QFrame):
    """Statusleiste am unteren Rand mit Feldern in Pixelschrift."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusbar")
        self.setFixedHeight(22)
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(8, 2, 8, 2)
        self._lay.setSpacing(8)
        self._labels: list[QLabel] = []

    def set_fields(self, fields: list[str]) -> None:
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._labels = []
        for i, text in enumerate(fields):
            if i:
                sep = QFrame(self)
                sep.setFrameShape(QFrame.VLine)
                sep.setStyleSheet("color: #ACA899;")
                self._lay.addWidget(sep)
            lab = pixel_label(text, parent=self)
            self._labels.append(lab)
            self._lay.addWidget(lab)
        self._lay.addStretch(1)


class InfoBalloon(QFrame):
    """Gelber Hinweis-Kasten (wie die Ballon-Tipps)."""

    def __init__(self, html: str, icon: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("balloon")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(8)
        if icon:
            lay.addWidget(InfoIcon(self), 0, Qt.AlignTop)
        self.label = QLabel(html, self)
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.RichText)
        self.label.setStyleSheet("background: transparent;")
        lay.addWidget(self.label, 1)


class InfoIcon(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(16, 16)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        grad = QLinearGradient(0, 0, 0, 16)
        grad.setColorAt(0, QColor("#5A9BFF"))
        grad.setColorAt(1, QColor("#1D4FC9"))
        p.setBrush(grad)
        p.setPen(QPen(QColor("#163B91"), 1))
        p.drawEllipse(QRect(0, 0, 15, 15))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("white"))
        p.drawRect(QRect(7, 6, 2, 6))
        p.drawRect(QRect(7, 3, 2, 2))


class RetroWindow(QWidget):
    """Rahmenloses Fenster mit selbst gezeichneter XP-Titelleiste und blauem Rahmen."""

    def __init__(self, title: str, icon: QPixmap | None = None, minimizable: bool = True,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint)
        self.setObjectName("RetroWindow")
        self.setWindowTitle(title)
        if icon is not None:
            from PySide6.QtGui import QIcon

            self.setWindowIcon(QIcon(icon))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(BORDER, 0, BORDER, BORDER)
        outer.setSpacing(0)
        self.title_bar = TitleBar(title, icon, minimizable, self)
        self.title_bar.closeClicked.connect(self.close)
        self.title_bar.minimizeClicked.connect(self.showMinimized)
        outer.addWidget(self.title_bar)
        self.body = QWidget(self)
        self.body.setObjectName("RetroBody")
        self.body.setAttribute(Qt.WA_StyledBackground, True)
        self.body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        outer.addWidget(self.body, 1)
        self.status_bar: StatusBar | None = None

    def add_status_bar(self) -> StatusBar:
        self.status_bar = StatusBar(self)
        self.layout().addWidget(self.status_bar)
        return self.status_bar

    def changeEvent(self, e) -> None:  # noqa: N802
        if e.type() == e.Type.ActivationChange:
            self.title_bar.set_active(self.isActiveWindow())
        super().changeEvent(e)

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        dwm.apply_retro_frame(int(self.winId()))
        self._update_mask()

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        self._update_mask()

    def _update_mask(self) -> None:
        """Obere Ecken pixelig abrunden (wie früher – ohne Glättung)."""
        w, h = self.width(), self.height()
        region = QRegion(0, CORNER, w, h - CORNER)
        steps = [5, 3, 2, 1, 1, 0, 0]   # Einrückung je Pixelzeile
        for y, inset in enumerate(steps):
            region = region.united(QRegion(inset, y, w - 2 * inset, 1))
        self.setMask(region)

    def paintEvent(self, _e) -> None:  # noqa: N802
        t = theme_mod.current()
        p = QPainter(self)
        w, h = self.width(), self.height()
        active = self.isActiveWindow()
        frame_from = t.color("title_from" if active else "title_inactive_from")
        frame_to = t.color("frame" if active else "title_inactive_to")
        grad = QLinearGradient(0, 0, BORDER, 0)
        grad.setColorAt(0, frame_to)
        grad.setColorAt(1, frame_from)
        p.fillRect(QRect(0, 0, BORDER, h), grad)
        grad2 = QLinearGradient(w - BORDER, 0, w, 0)
        grad2.setColorAt(0, frame_from)
        grad2.setColorAt(1, frame_to)
        p.fillRect(QRect(w - BORDER, 0, BORDER, h), grad2)
        grad3 = QLinearGradient(0, h - BORDER, 0, h)
        grad3.setColorAt(0, frame_from)
        grad3.setColorAt(1, frame_to)
        p.fillRect(QRect(0, h - BORDER, w, BORDER), grad3)


def sunken_panel(parent: QWidget | None = None) -> QFrame:
    f = QFrame(parent)
    f.setObjectName("sunken")
    return f


def balloon_path(rect: QRect, tail_at: QPoint | None, radius: int = 7) -> QPainterPath:
    """Sprechblasen-Umriss mit Schwanz zu ``tail_at`` (außerhalb von ``rect``)."""
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    if tail_at is not None:
        cx = min(max(tail_at.x(), rect.left() + 18), rect.right() - 18)
        base_y = rect.bottom() if tail_at.y() > rect.bottom() else rect.top()
        tail = QPainterPath()
        tail.moveTo(cx - 10, base_y)
        tail.lineTo(tail_at.x(), tail_at.y())
        tail.lineTo(cx + 4, base_y)
        tail.closeSubpath()
        path = path.united(tail)
    return path


def size_hint_at_least(widget: QWidget, w: int, h: int) -> QSize:
    s = widget.sizeHint()
    return QSize(max(s.width(), w), max(s.height(), h))
