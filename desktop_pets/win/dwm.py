"""DWM-Feinheiten für die Retro-Fenster: eckige Ecken (Windows 11) und Schatten."""

from __future__ import annotations

from . import IS_WINDOWS

DWMWA_NCRENDERING_POLICY = 2
DWMNCRP_ENABLED = 2
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_DONOTROUND = 1


def apply_retro_frame(hwnd: int, shadow: bool = True) -> None:
    if not IS_WINDOWS or not hwnd:
        return
    import ctypes
    from ctypes import wintypes

    try:
        dwm = ctypes.windll.dwmapi
    except OSError:
        return
    pref = ctypes.c_int(DWMWCP_DONOTROUND)
    # Unter Windows 10 schlägt das fehl (gibt es dort nicht) – das ist in Ordnung.
    dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(pref), ctypes.sizeof(pref))
    if shadow:
        policy = ctypes.c_int(DWMNCRP_ENABLED)
        dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), DWMWA_NCRENDERING_POLICY, ctypes.byref(policy), ctypes.sizeof(policy))

        class MARGINS(ctypes.Structure):
            _fields_ = [("l", ctypes.c_int), ("r", ctypes.c_int), ("t", ctypes.c_int), ("b", ctypes.c_int)]

        margins = MARGINS(1, 1, 1, 1)
        dwm.DwmExtendFrameIntoClientArea(wintypes.HWND(hwnd), ctypes.byref(margins))
