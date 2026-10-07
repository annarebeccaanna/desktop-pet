"""Sichtbare Fenster und ihre Oberkanten (für ``window_walking``).

* ``EnumWindows`` liefert die Fenster von oben nach unten (Z-Reihenfolge).
* ``DwmGetWindowAttribute(DWMWA_EXTENDED_FRAME_BOUNDS)`` gibt die sichtbaren
  Kanten ohne unsichtbare Schattenränder.
* Minimierte, unsichtbare, „verhüllte“ (cloaked) und eigene Fenster werden ignoriert.

``visible_top_edges`` ist reine Logik: Sie schneidet von jeder Oberkante die
Stücke weg, die von weiter oben liegenden Fenstern verdeckt sind.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from . import IS_WINDOWS


@dataclass(frozen=True)
class WinRect:
    hwnd: int
    left: int
    top: int
    right: int
    bottom: int
    title: str = ""

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


@dataclass(frozen=True)
class Edge:
    id: str
    left: float
    right: float
    y: float


def _subtract(segments: list[tuple[float, float]], cut: tuple[float, float]) -> list[tuple[float, float]]:
    out = []
    c0, c1 = cut
    for s0, s1 in segments:
        if c1 <= s0 or c0 >= s1:
            out.append((s0, s1))
            continue
        if c0 > s0:
            out.append((s0, c0))
        if c1 < s1:
            out.append((c1, s1))
    return out


def visible_top_edges(windows: list[WinRect], min_width: float = 40) -> list[Edge]:
    """``windows`` in Z-Reihenfolge (oberstes zuerst)."""
    edges: list[Edge] = []
    for i, w in enumerate(windows):
        segs = [(float(w.left), float(w.right))]
        y = w.top
        for above in windows[:i]:
            # Verdeckt, wenn die Kante (und etwas Platz darüber für das Tier) im oberen Fenster liegt
            if above.top - 1 <= y <= above.bottom:
                segs = _subtract(segs, (above.left, above.right))
                if not segs:
                    break
        for j, (s0, s1) in enumerate(segs):
            if s1 - s0 >= min_width:
                edges.append(Edge(f"win:{w.hwnd}:{j}", s0, s1, float(y)))
    return edges


_IGNORED_CLASSES = {"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW", "Windows.UI.Core.CoreWindow"}


def list_windows(min_w: int = 120, min_h: int = 60) -> list[WinRect]:
    """Sichtbare Top-Level-Fenster in physischen Pixeln (oberstes zuerst)."""
    if not IS_WINDOWS:
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    dwm = ctypes.windll.dwmapi
    own_pid = os.getpid()
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_NOACTIVATE = 0x08000000
    DWMWA_EXTENDED_FRAME_BOUNDS = 9
    DWMWA_CLOAKED = 14

    result: list[WinRect] = []
    buf = ctypes.create_unicode_buffer(256)

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == own_pid:
            return True
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if ex & (WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE):
            return True
        cloaked = ctypes.c_int(0)
        dwm.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
        if cloaked.value:
            return True
        user32.GetClassNameW(hwnd, buf, 256)
        if buf.value in _IGNORED_CLASSES:
            return True
        user32.GetWindowTextW(hwnd, buf, 256)
        title = buf.value
        if not title:
            return True
        rect = wintypes.RECT()
        if dwm.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect)) != 0:
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return True
        w = WinRect(int(hwnd or 0), rect.left, rect.top, rect.right, rect.bottom, title)
        if w.width >= min_w and w.height >= min_h:
            result.append(w)
        return True

    user32.EnumWindows(callback, 0)
    return result


def foreground_is_fullscreen(screen_rects: list[tuple[int, int, int, int]]) -> bool:
    """Phase 4: Vollbild-Anwendung im Vordergrund (Spiel, Präsentation)?"""
    if not IS_WINDOWS:
        return False
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    buf = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hwnd, buf, 64)
    if buf.value in _IGNORED_CLASSES:
        return False
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False
    return any(rect.left <= l and rect.top <= t and rect.right >= r and rect.bottom >= b
               for l, t, r, b in screen_rects)
