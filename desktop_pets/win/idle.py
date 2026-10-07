"""Leerlauf-Erkennung: Sekunden seit der letzten Tastatur-/Mauseingabe.

Windows: ``GetLastInputInfo``. Andere Systeme: Näherung über Mausbewegung
(:class:`CursorIdleTracker`), damit die App auch dort sinnvoll läuft.
"""

from __future__ import annotations

import time
from typing import Callable

from . import IS_WINDOWS


def system_idle_seconds() -> float | None:
    """None, wenn das System keine Auskunft gibt."""
    if not IS_WINDOWS:
        return None
    import ctypes
    from ctypes import wintypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return None
    now = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
    return ((now - info.dwTime) & 0xFFFFFFFF) / 1000.0


class CursorIdleTracker:
    """Fallback: misst nur Mausbewegung (Tastatur ist ohne Systemhooks nicht sichtbar)."""

    def __init__(self, cursor_pos: Callable[[], tuple[int, int]], clock: Callable[[], float] = time.monotonic) -> None:
        self._cursor_pos = cursor_pos
        self._clock = clock
        self._last_pos = cursor_pos()
        self._last_input = clock()

    def poke(self) -> None:
        self._last_input = self._clock()

    def idle_seconds(self) -> float:
        pos = self._cursor_pos()
        if pos != self._last_pos:
            self._last_pos = pos
            self._last_input = self._clock()
        return self._clock() - self._last_input


class IdleMonitor:
    def __init__(self, cursor_pos: Callable[[], tuple[int, int]]) -> None:
        self._fallback = CursorIdleTracker(cursor_pos)

    def idle_seconds(self) -> float:
        value = system_idle_seconds()
        if value is None:
            return self._fallback.idle_seconds()
        return value
