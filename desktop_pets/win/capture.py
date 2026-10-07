"""Capture-Ausschluss: Fenster für Bildschirmaufnahmen/Freigaben unsichtbar machen.

``SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)`` – ab Windows 10 2004
(Build 19041). Auf älteren Systemen ist die Option nicht verfügbar.
"""

from __future__ import annotations

from ..core.log import get_logger
from . import IS_WINDOWS, windows_build

log = get_logger("win.capture")

WDA_NONE = 0x00
WDA_EXCLUDEFROMCAPTURE = 0x11
MIN_BUILD = 19041


def is_supported() -> bool:
    return IS_WINDOWS and windows_build() >= MIN_BUILD


def set_excluded(hwnd: int, excluded: bool) -> bool:
    """True bei Erfolg. Auf nicht unterstützten Systemen immer False."""
    if not is_supported() or not hwnd:
        return False
    import ctypes

    user32 = ctypes.windll.user32
    ok = bool(user32.SetWindowDisplayAffinity(ctypes.c_void_p(hwnd), WDA_EXCLUDEFROMCAPTURE if excluded else WDA_NONE))
    if not ok:
        log.warning("SetWindowDisplayAffinity fehlgeschlagen (Fehler %s)", ctypes.GetLastError())
    return ok
