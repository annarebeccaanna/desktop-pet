"""Plattformen für die Physik: Boden je Bildschirm + (optional) sichtbare Fensteroberkanten."""

from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtGui import QGuiApplication

from ..pet.physics import Platform
from ..win.windows_enum import WinRect, list_windows, visible_top_edges


def screen_grounds() -> list[Platform]:
    out = []
    for s in QGuiApplication.screens():
        g = s.availableGeometry()
        out.append(Platform(f"screen:{s.name()}", g.left(), g.left() + g.width(), g.top() + g.height(), solid=True))
    return out


def to_logical(w: WinRect) -> WinRect:
    """Physische Pixel (Win32) → logische Qt-Koordinaten (pro Bildschirm skaliert).

    Qt behält den Ursprung jedes Bildschirms bei und teilt nur die Ausdehnung durch
    dessen Skalierung: logisch = Ursprung + (physisch − Ursprung) / Faktor.
    """
    cx, cy = (w.left + w.right) / 2, w.top
    for s in QGuiApplication.screens():
        g = s.geometry()
        dpr = s.devicePixelRatio()
        if g.left() <= cx < g.left() + g.width() * dpr and g.top() <= cy < g.top() + g.height() * dpr:
            ox, oy = g.left(), g.top()

            def conv(v: float, o: float) -> int:
                return int(round(o + (v - o) / dpr))

            return WinRect(w.hwnd, conv(w.left, ox), conv(w.top, oy), conv(w.right, ox), conv(w.bottom, oy), w.title)
    return w


def window_edges(pet_height: float) -> list[Platform]:
    """Sichtbare Fensteroberkanten mit genug Platz darüber für das Tier."""
    out = []
    rects = [to_logical(w) for w in list_windows()]
    for e in visible_top_edges(rects):
        screen = QGuiApplication.screenAt(QPoint(int((e.left + e.right) / 2), int(e.y)))
        if screen is None:
            continue
        g = screen.availableGeometry()
        if e.y - pet_height < g.top() or e.y > g.bottom() - 20:
            continue
        out.append(Platform(e.id, e.left, e.right, e.y))
    return out
