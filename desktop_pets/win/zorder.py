"""Z-Reihenfolge: Fenster ganz nach oben (topmost) oder ganz nach hinten."""

from __future__ import annotations

from . import IS_WINDOWS

HWND_TOP = 0
HWND_BOTTOM = 1
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_NOOWNERZORDER = 0x0200
_FLAGS = SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_NOOWNERZORDER


def _set_pos(hwnd: int, after: int) -> bool:
    if not IS_WINDOWS or not hwnd:
        return False
    import ctypes

    return bool(ctypes.windll.user32.SetWindowPos(ctypes.c_void_p(hwnd), ctypes.c_void_p(after), 0, 0, 0, 0, _FLAGS))


def set_topmost(hwnd: int, topmost: bool) -> bool:
    return _set_pos(hwnd, HWND_TOPMOST if topmost else HWND_NOTOPMOST)


def send_to_bottom(hwnd: int) -> bool:
    """Hinter alle anderen Fenster (wie ein Desktop-Icon)."""
    _set_pos(hwnd, HWND_NOTOPMOST)
    return _set_pos(hwnd, HWND_BOTTOM)


WM_WINDOWPOSCHANGING = 0x0046
SWP_NOZORDER = 0x0004


_WINDOWPOS = None


def _windowpos_type():
    global _WINDOWPOS
    if _WINDOWPOS is None:
        import ctypes
        from ctypes import wintypes

        class WINDOWPOS(ctypes.Structure):
            _fields_ = [("hwnd", wintypes.HWND), ("hwndInsertAfter", wintypes.HWND),
                        ("x", ctypes.c_int), ("y", ctypes.c_int), ("cx", ctypes.c_int), ("cy", ctypes.c_int),
                        ("flags", wintypes.UINT)]

        _WINDOWPOS = WINDOWPOS
    return _WINDOWPOS


def pin_bottom_in_native_event(message: int) -> None:
    """In ``nativeEvent`` aufrufen: hält das Fenster bei jeder Z-Änderung ganz unten.

    Setzt in ``WM_WINDOWPOSCHANGING`` das Ziel auf ``HWND_BOTTOM`` – so kommt das
    Fenster auch nach einem Klick nicht wieder nach vorn (wie ein Desktop-Icon).
    """
    if not IS_WINDOWS:
        return
    from ctypes import wintypes

    try:
        msg = wintypes.MSG.from_address(int(message))
    except (TypeError, ValueError):
        return
    if msg.message != WM_WINDOWPOSCHANGING or not msg.lParam:
        return
    pos = _windowpos_type().from_address(msg.lParam)
    if pos.flags & SWP_NOZORDER:
        return
    pos.hwndInsertAfter = HWND_BOTTOM
