"""Pixel-Menü der Text-Werkzeuge – eine Sprechblase am Tier.

Seiten: Werkzeuge (Pixel-Knöpfe mit Icons) → „arbeitet …“ → Ergebnis mit
Ersetzen / Kopieren / Zurück. Alles in Pixelschrift mit harten schwarzen Kanten.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QIcon, QKeyEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QStackedWidget, QVBoxLayout,
    QWidget,
)

from ..core import paths
from ..features.ai.text_tools import CUSTOM, TOOLS
from . import theme as theme_mod
from .retro import balloon_path, pixel_label
from .speech_bubble import PAD, TAIL, _CloseX, bubble_position

PIXEL_BUTTON = (
    "QStackedWidget#toolPages, QWidget#toolPage { background: transparent; }"
    "QPushButton#pixelTool { background: #FFFFFF; color: #000000; border: 2px solid #000000;"
    " border-right-width: 3px; border-bottom-width: 3px; border-radius: 0; padding: 3px 6px; border-image: none;"
    " text-align: left; min-height: 20px; }"
    "QPushButton#pixelTool:hover { background: #FCE7B2; }"
    "QPushButton#pixelTool:pressed { background: #F8C33A; border-right-width: 2px; border-bottom-width: 2px; }"
    "QPushButton#pixelTool:disabled { color: #8A8A8A; border-color: #8A8A8A; }"
    "QPushButton#pixelPrimary { background: #3C9A2E; color: #FFFFFF; border: 2px solid #000000;"
    " border-right-width: 3px; border-bottom-width: 3px; border-radius: 0; padding: 3px 10px; min-height: 20px;"
    " border-image: none; }"
    "QPushButton#pixelPrimary:hover { background: #4CB23C; }"
    "QLineEdit#pixelField, QPlainTextEdit#pixelField { background: #FFFFFF; border: 2px solid #000000;"
    " border-radius: 0; padding: 2px 4px; }"
)


def pixel_icon(name: str, scale: int = 2) -> QIcon:
    pm = QPixmap(str(paths.assets_dir() / "tools" / f"{name}.png"))
    if pm.isNull():
        return QIcon()
    return QIcon(pm.scaled(pm.width() * scale, pm.height() * scale, Qt.IgnoreAspectRatio, Qt.FastTransformation))


class _Field(QLineEdit):
    escape = Signal()

    def keyPressEvent(self, e: QKeyEvent) -> None:  # noqa: N802
        if e.key() == Qt.Key_Escape:
            self.escape.emit()
            return
        super().keyPressEvent(e)


class TextToolsMenu(QWidget):
    tool_chosen = Signal(str, str)        # Werkzeug-ID, eigene Anweisung (nur bei „custom“)
    replace_clicked = Signal(str)
    copy_clicked = Signal(str)
    closed = Signal()

    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)    # das Programm mit dem markierten Text behält den Fokus
        self.setWindowTitle("Desktop Pets – Text-Werkzeuge")
        self.setStyleSheet(PIXEL_BUTTON)
        self._tail_local: QPoint | None = None
        self._replace_default = True
        t = theme_mod.current()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10 + TAIL)
        outer.setSpacing(6)
        head = QHBoxLayout()
        self.title = pixel_label("Text-Werkzeuge", color="pixel_blue", parent=self)
        head.addWidget(self.title, 1)
        close = _CloseX(self)
        close.clicked.connect(self.close_menu)
        head.addWidget(close, 0, Qt.AlignTop)
        outer.addLayout(head)
        self.pages = QStackedWidget(self)
        self.pages.setObjectName("toolPages")
        outer.addWidget(self.pages)

        # ---------- Seite 1: Werkzeuge ----------
        menu = QWidget()
        menu.setObjectName("toolPage")
        ml = QVBoxLayout(menu)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(6)
        self.preview = QLabel("", menu)
        self.preview.setObjectName("muted")
        self.preview.setFont(t.ui_font(8))
        self.preview.setWordWrap(True)
        self.preview.setMaximumWidth(330)
        ml.addWidget(self.preview)
        grid = QGridLayout()
        grid.setSpacing(5)
        self.tool_buttons: dict[str, QPushButton] = {}
        for i, tool in enumerate(TOOLS):
            btn = QPushButton(tool.label.upper(), menu)
            btn.setObjectName("pixelTool")
            btn.setFont(t.pixel_font(8))
            btn.setIcon(pixel_icon(tool.id))
            btn.setIconSize(QSize(20, 20))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.clicked.connect(lambda _=False, tid=tool.id: self.tool_chosen.emit(tid, ""))
            self.tool_buttons[tool.id] = btn
            grid.addWidget(btn, i // 2, i % 2)
        ml.addLayout(grid)
        custom = QHBoxLayout()
        custom.setSpacing(5)
        icon = QLabel(menu)
        icon.setPixmap(pixel_icon(CUSTOM.id).pixmap(20, 20))
        custom.addWidget(icon)
        self.custom = _Field(menu)
        self.custom.setObjectName("pixelField")
        self.custom.setPlaceholderText("Eigene Anweisung, z. B. „als Stichpunkte“")
        self.custom.returnPressed.connect(self._custom)
        self.custom.escape.connect(self.close_menu)
        custom.addWidget(self.custom, 1)
        go = QPushButton("LOS", menu)
        go.setObjectName("pixelTool")
        go.setFont(t.pixel_font(8))
        go.clicked.connect(self._custom)
        custom.addWidget(go)
        ml.addLayout(custom)
        self.pages.addWidget(menu)

        # ---------- Seite 2: arbeitet ----------
        work = QWidget()
        work.setObjectName("toolPage")
        wl = QVBoxLayout(work)
        wl.setContentsMargins(0, 8, 0, 8)
        self.working = pixel_label("Arbeite dran", parent=work)
        wl.addWidget(self.working, 0, Qt.AlignCenter)
        self.pages.addWidget(work)
        self._dots = 0
        self._dot_timer = QTimer(self)
        self._dot_timer.timeout.connect(self._tick_dots)

        # ---------- Seite 3: Ergebnis ----------
        res = QWidget()
        res.setObjectName("toolPage")
        rl = QVBoxLayout(res)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)
        self.result = QPlainTextEdit(res)
        self.result.setObjectName("pixelField")
        self.result.setReadOnly(False)                # kleine Korrekturen vor dem Einfügen erlaubt
        self.result.setFont(t.ui_font(9))
        self.result.setMinimumSize(330, 90)
        self.result.setMaximumHeight(240)
        rl.addWidget(self.result)
        buttons = QHBoxLayout()
        buttons.setSpacing(5)
        self.btn_primary = QPushButton("", res)
        self.btn_primary.setObjectName("pixelPrimary")
        self.btn_primary.setFont(t.pixel_font(8))
        self.btn_primary.clicked.connect(lambda: self._finish(self._replace_default))
        buttons.addWidget(self.btn_primary)
        self.btn_secondary = QPushButton("", res)
        self.btn_secondary.setObjectName("pixelTool")
        self.btn_secondary.setFont(t.pixel_font(8))
        self.btn_secondary.clicked.connect(lambda: self._finish(not self._replace_default))
        buttons.addWidget(self.btn_secondary)
        buttons.addStretch(1)
        back = QPushButton("ZURÜCK", res)
        back.setObjectName("pixelTool")
        back.setFont(t.pixel_font(8))
        back.clicked.connect(self.show_menu)
        buttons.addWidget(back)
        rl.addLayout(buttons)
        self.pages.addWidget(res)

    # ---------- öffentlich ----------
    def open(self, text: str, anchor: QPoint, can_replace: bool = True) -> None:
        preview = " ".join(text.split())
        if len(preview) > 90:
            preview = preview[:90].rstrip() + " …"
        self.preview.setText(f"„{preview}“  ({len(text)} Zeichen)")
        self.can_replace = can_replace
        self.custom.clear()
        self.show_menu()
        self.follow(anchor)
        self.show()
        self.raise_()

    def show_menu(self) -> None:
        self._dot_timer.stop()
        self.title.setText("TEXT-WERKZEUGE")
        self.pages.setCurrentIndex(0)
        self._resize()

    def show_working(self, label: str) -> None:
        self.title.setText(label.upper())
        self._dots = 0
        self._tick_dots()
        self._dot_timer.start(350)
        self.pages.setCurrentIndex(1)
        self._resize()

    def show_result(self, label: str, text: str, replace_default: bool) -> None:
        self._dot_timer.stop()
        self._replace_default = replace_default and getattr(self, "can_replace", True)
        self.title.setText(label.upper())
        self.result.setPlainText(text)
        self.btn_primary.setText("ERSETZEN" if self._replace_default else "KOPIEREN")
        self.btn_secondary.setText("KOPIEREN" if self._replace_default else "ERSETZEN")
        self.btn_secondary.setVisible(getattr(self, "can_replace", True))
        self.pages.setCurrentIndex(2)
        self._resize()

    def follow(self, anchor: QPoint) -> None:
        x, y = bubble_position(anchor, self.width(), self.height())
        self.move(x, y)
        self._tail_local = QPoint(anchor.x() - x, anchor.y() - y)
        self.update()

    def close_menu(self) -> None:
        self._dot_timer.stop()
        if self.isVisible():
            self.hide()
            self.closed.emit()

    # ---------- intern ----------
    def _resize(self) -> None:
        anchor = self._tail_local + self.pos() if self._tail_local is not None and self.isVisible() else None
        for i in range(self.pages.count()):
            page = self.pages.widget(i)
            page.setVisible(i == self.pages.currentIndex())
        self.pages.adjustSize()
        self.adjustSize()
        if anchor is not None:
            self.follow(anchor)

    def _tick_dots(self) -> None:
        self._dots = (self._dots + 1) % 4
        self.working.setText(("Arbeite dran" + "." * self._dots).upper())

    def _custom(self) -> None:
        text = self.custom.text().strip()
        if text:
            self.tool_chosen.emit(CUSTOM.id, text)

    def _finish(self, replace: bool) -> None:
        text = self.result.toPlainText()
        (self.replace_clicked if replace else self.copy_clicked).emit(text)

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
