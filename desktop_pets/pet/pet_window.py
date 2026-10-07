"""Transparentes, rahmenloses Fenster, in dem das Tier gezeichnet wird.

* Nur Pixel des Tiers sind anklickbar, transparente Bereiche lassen jeden Klick
  zum Fenster darunter durch (Windows: von selbst bei durchscheinenden Fenstern;
  andere Systeme: ``setMask`` aus dem aktuellen Frame).
* Kein Taskleisteneintrag (``Qt.Tool``), stiehlt nie den Fokus.
* Im Pause-Modus liegt das Fenster hinter allen Fenstern, aber über dem Desktop.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QPointF, QRect, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPixmap, QRegion
from PySide6.QtWidgets import QWidget

from ..win import IS_WINDOWS, zorder
from .sprites import Frame

TOP_PAD_FACTOR = 1.0     # Platz über dem Tier für Herzchen/Zzz (in Framehöhen)
DRAG_THRESHOLD = 4


@dataclass
class Particle:
    pixmap: QPixmap
    x: float          # relativ zur Fußmitte
    y: float          # relativ zur Oberkante des Sprites (negativ = darüber)
    vx: float
    vy: float
    life: float
    age: float = 0.0


class _Base(QWidget):
    """Gemeinsame Fenster-Eigenschaften für Tier, Körbchen und Napf."""

    def __init__(self, topmost: bool) -> None:
        flags = Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint
        if topmost:
            flags |= Qt.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self._pin_bottom = not topmost
        self._topmost = topmost

    def set_pinned_bottom(self, bottom: bool) -> None:
        """Auf den Desktop legen (hinter alle Fenster, über das Hintergrundbild) oder wieder nach vorn."""
        self._pin_bottom = bottom
        if IS_WINDOWS:
            hwnd = int(self.winId())
            if bottom:
                zorder.send_to_desktop(hwnd)
            else:
                zorder.set_topmost(hwnd, self._topmost)
        else:
            # Andere Systeme: Flags umstellen (erzeugt das native Fenster neu)
            visible = self.isVisible()
            self.setWindowFlag(Qt.WindowStaysOnTopHint, not bottom and self._topmost)
            self.setWindowFlag(Qt.WindowStaysOnBottomHint, bottom)
            if visible:
                self.show()
            if bottom:
                self.lower()

    @property
    def pinned_bottom(self) -> bool:
        return self._pin_bottom


def apply_click_mask(widget: QWidget, region: QRegion) -> None:
    """Klick-Durchlässigkeit außerhalb der Grafik.

    Unter Windows sind transparente Pixel eines durchscheinenden Fensters (Layered
    Window) ohnehin durchlässig – dort ist keine Maske nötig. Andere Systeme brauchen sie.
    """
    if IS_WINDOWS:
        return
    widget.setMask(region)


class PetWindow(_Base):
    clicked = Signal()
    doubleClicked = Signal()
    rightClicked = Signal(QPoint)
    dragStarted = Signal()
    dragMoved = Signal(QPoint)      # globale Position der Fußmitte
    dragEnded = Signal()
    stroked = Signal(float)         # Mausweg über dem Tier (Streicheln), in px
    shown = Signal()

    def __init__(self) -> None:
        super().__init__(topmost=True)
        self.setMouseTracking(True)
        self.setWindowTitle("Desktop Pets – Tier")
        self._frame: Frame | None = None
        self._facing = 1
        self._frame_w = 32
        self._frame_h = 32
        self._pad = 32
        self._particles: list[Particle] = []
        self._press_pos: QPoint | None = None
        self._grab_offset = QPoint()
        self._dragging = False
        self._last_hover: QPointF | None = None
        self._mask_key = None
        self.occupied = True       # False: Tier liegt gerade im Körbchen-Fenster

    # ---------- Geometrie ----------
    def set_frame_size(self, w: int, h: int) -> None:
        self._frame_w, self._frame_h = w, h
        self._pad = int(h * TOP_PAD_FACTOR)
        self.setFixedSize(max(w, int(w * 1.5)), h + self._pad)
        self._mask_key = None

    @property
    def frame_size(self) -> tuple[int, int]:
        return self._frame_w, self._frame_h

    def place_feet(self, x: float, y: float) -> None:
        """Fußmitte des Tiers auf (x, y) setzen (globale logische Koordinaten)."""
        self.move(int(round(x - self.width() / 2)), int(round(y - self.height())))

    def head_anchor(self) -> QPoint:
        """Wohin Sprechblasen zeigen: knapp über dem Kopf."""
        g = self.geometry()
        return QPoint(g.center().x(), g.top() + self._pad + 2)

    def sprite_rect(self) -> QRect:
        x = (self.width() - self._frame_w) // 2
        return QRect(x, self._pad, self._frame_w, self._frame_h)

    # ---------- Inhalt ----------
    def set_frame(self, frame: Frame, facing: int) -> None:
        changed = frame is not self._frame or facing != self._facing
        self._frame, self._facing = frame, facing
        if changed:
            self._update_mask()
            self.update()

    def add_particle(self, pixmap: QPixmap, count: int = 1, life: float = 1.4) -> None:
        for _ in range(count):
            self._particles.append(Particle(
                pixmap, x=random.uniform(-self._frame_w * 0.35, self._frame_w * 0.35),
                y=random.uniform(-4, self._frame_h * 0.25), vx=random.uniform(-10, 10),
                vy=random.uniform(-45, -30), life=life * random.uniform(0.8, 1.2)))
        self._mask_key = None

    @property
    def has_particles(self) -> bool:
        return bool(self._particles)

    def tick_particles(self, dt: float) -> None:
        if not self._particles:
            return
        for p in self._particles:
            p.age += dt
            p.x += p.vx * dt
            p.y += p.vy * dt
        self._particles = [p for p in self._particles if p.age < p.life and p.y > -self._pad]
        self._mask_key = None
        self._update_mask()
        self.update()

    def _particle_rect(self, p: Particle) -> QRect:
        cx = self.width() / 2 + p.x
        return QRect(int(cx - p.pixmap.width() / 2), int(self._pad + p.y - p.pixmap.height()),
                     p.pixmap.width(), p.pixmap.height())

    def _update_mask(self) -> None:
        if self._frame is None or IS_WINDOWS:
            return
        key = (id(self._frame), self._facing, len(self._particles))
        if key == self._mask_key and not self._particles:
            return
        self._mask_key = key
        region = QRegion(self._frame.mask(self._facing))
        region.translate(self.sprite_rect().topLeft())
        for p in self._particles:
            region = region.united(QRegion(self._particle_rect(p)))
        if region.isEmpty():
            region = QRegion(0, 0, 1, 1)
        apply_click_mask(self, region)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        if self._frame is not None:
            p.drawPixmap(self.sprite_rect().topLeft(), self._frame.pixmap(self._facing))
        for part in self._particles:
            fade = max(0.0, 1.0 - part.age / part.life)
            p.setOpacity(min(1.0, fade * 1.6))
            p.drawPixmap(self._particle_rect(part).topLeft(), part.pixmap)
        p.setOpacity(1.0)

    # ---------- Maus ----------
    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() == Qt.LeftButton:
            self._press_pos = e.globalPosition().toPoint()
            feet = QPoint(self.x() + self.width() // 2, self.y() + self.height())
            self._grab_offset = feet - self._press_pos
            self._dragging = False
        elif e.button() == Qt.RightButton:
            self.rightClicked.emit(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        pos = e.globalPosition()
        if self._press_pos is not None and e.buttons() & Qt.LeftButton:
            if not self._dragging and (pos.toPoint() - self._press_pos).manhattanLength() > DRAG_THRESHOLD:
                self._dragging = True
                self.setCursor(Qt.ClosedHandCursor)
                self.dragStarted.emit()
            if self._dragging:
                self.dragMoved.emit(pos.toPoint() + self._grab_offset)
            return
        # Streicheln: Mausbewegung ohne gedrückte Taste über dem Tier
        if self._last_hover is not None:
            d = pos - self._last_hover
            dist = abs(d.x()) + abs(d.y())
            if 0 < dist < 80:
                self.stroked.emit(dist)
        self._last_hover = pos

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() != Qt.LeftButton:
            return
        if self._dragging:
            self._dragging = False
            self.unsetCursor()
            self.dragEnded.emit()
        elif self._press_pos is not None:
            self.clicked.emit()
        self._press_pos = None

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() == Qt.LeftButton:
            self.doubleClicked.emit()

    def leaveEvent(self, e) -> None:  # noqa: N802
        self._last_hover = None
        super().leaveEvent(e)

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        self.shown.emit()


class PropWindow(_Base):
    """Körbchen oder Napf: Grafik auf dem Desktop, klick-durchlässig außerhalb der Grafik.

    Das Körbchen liegt immer hinter allen Fenstern (wie ein Desktop-Icon). Liegt
    das Tier im Pause-Modus darin, zeichnet dieses Fenster das schlafende Tier mit
    – so bleibt alles in einem einzigen Fenster ganz unten.
    """

    clicked = Signal()
    doubleClicked = Signal()
    rightClicked = Signal(QPoint)
    moved = Signal(QPoint)          # neue Mitte unten (globale Koordinaten)
    shown = Signal()

    def __init__(self, bottom: bool = True, draggable: bool = True) -> None:
        super().__init__(topmost=not bottom)
        self.setWindowTitle("Desktop Pets – Körbchen")
        self._pixmap = QPixmap()
        self._overlay: QPixmap | None = None     # z. B. Futter im Napf
        self._occupant: QPixmap | None = None    # schlafendes Tier im Körbchen
        self._draggable = draggable
        self._press: QPoint | None = None
        self._grab = QPoint()
        self._dragging = False
        self.move_mode = False

    def set_pixmap(self, pixmap: QPixmap, overlay: QPixmap | None = None) -> None:
        self._pixmap = pixmap
        self._overlay = overlay
        self._relayout()

    def set_overlay(self, overlay: QPixmap | None) -> None:
        self._overlay = overlay
        self._relayout()

    def set_occupant(self, pixmap: QPixmap | None) -> None:
        """Schlafendes Tier im Körbchen zeichnen (None = leer)."""
        if pixmap is self._occupant:
            return
        self._occupant = pixmap
        self._relayout()

    @property
    def has_occupant(self) -> bool:
        return self._occupant is not None

    def _sink(self) -> int:
        """Wie tief die Füße des Tiers unter der Oberkante des Körbchens liegen."""
        return int(self._pixmap.height() * 0.75)

    def _relayout(self) -> None:
        bottom_center = self.bottom_center()
        pw, ph = self._pixmap.width(), self._pixmap.height()
        w, extra = pw, 0
        if self._occupant is not None:
            w = max(w, self._occupant.width())
            extra = max(extra, self._occupant.height() - self._sink())
        if self._overlay is not None:
            w = max(w, self._overlay.width())
            extra = max(extra, self._overlay.height() // 2)
        self.setFixedSize(max(1, w), max(1, ph + extra))
        if self.isVisible():
            self.place_bottom_center(bottom_center)
        self._update_mask()
        self.update()

    def place_bottom_center(self, p: QPoint) -> None:
        self.move(p.x() - self.width() // 2, p.y() - self.height())

    def bottom_center(self) -> QPoint:
        return QPoint(self.x() + self.width() // 2, self.y() + self.height())

    def _layout_rects(self) -> tuple[QRect, QRect | None, QRect | None]:
        w, h = self.width(), self.height()
        base = QRect((w - self._pixmap.width()) // 2, h - self._pixmap.height(),
                     self._pixmap.width(), self._pixmap.height())
        occ = None
        if self._occupant is not None:
            occ = QRect((w - self._occupant.width()) // 2, base.top() + self._sink() - self._occupant.height(),
                        self._occupant.width(), self._occupant.height())
        ov = None
        if self._overlay is not None:
            ov = QRect((w - self._overlay.width()) // 2, base.top() - self._overlay.height() // 2,
                       self._overlay.width(), self._overlay.height())
        return base, occ, ov

    def _update_mask(self) -> None:
        if self._pixmap.isNull() or IS_WINDOWS:
            return
        base, occ, ov = self._layout_rects()
        region = QRegion(self._pixmap.mask())
        region.translate(base.topLeft())
        for pm, rect in ((self._occupant, occ), (self._overlay, ov)):
            if pm is not None and rect is not None:
                r = QRegion(pm.mask())
                r.translate(rect.topLeft())
                region = region.united(r)
        apply_click_mask(self, region)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        base, occ, ov = self._layout_rects()
        p.drawPixmap(base.topLeft(), self._pixmap)
        if self._occupant is not None and occ is not None:
            # Tier hinein, dann den vorderen Rand darüber: es liegt „drin“
            p.drawPixmap(occ.topLeft(), self._occupant)
            half = self._pixmap.height() // 2
            p.drawPixmap(base.left(), base.top() + half,
                         self._pixmap.copy(0, half, self._pixmap.width(), self._pixmap.height() - half))
        if self._overlay is not None and ov is not None:
            p.drawPixmap(ov.topLeft(), self._overlay)

    # ---------- Maus ----------
    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() == Qt.LeftButton:
            if self.move_mode:
                self.move_mode = False
                self.releaseMouse()
                self.unsetCursor()
                self.moved.emit(self.bottom_center())
                return
            self._press = e.globalPosition().toPoint()
            self._grab = self.bottom_center() - self._press
            self._dragging = False
        elif e.button() == Qt.RightButton:
            self.rightClicked.emit(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        pos = e.globalPosition().toPoint()
        if self.move_mode:
            self.place_bottom_center(pos + QPoint(0, self.height() // 2))
            return
        if not self._draggable or self._press is None or not (e.buttons() & Qt.LeftButton):
            return
        if not self._dragging and (pos - self._press).manhattanLength() > DRAG_THRESHOLD:
            self._dragging = True
            self.setCursor(Qt.ClosedHandCursor)
        if self._dragging:
            self.place_bottom_center(pos + self._grab)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() != Qt.LeftButton or self.move_mode:
            return
        if self._dragging:
            self._dragging = False
            self.unsetCursor()
            self.moved.emit(self.bottom_center())
        elif self._press is not None:
            self.clicked.emit()
        self._press = None

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() == Qt.LeftButton:
            self.doubleClicked.emit()

    def start_move_mode(self) -> None:
        """„Körbchen verschieben“: hängt am Mauszeiger bis zum nächsten Klick."""
        self.move_mode = True
        self.setCursor(Qt.SizeAllCursor)
        self.grabMouse()

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        self.shown.emit()
