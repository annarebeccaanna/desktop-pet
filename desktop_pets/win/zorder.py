"""Z-Reihenfolge: Fenster ganz nach vorn (topmost) oder „auf den Desktop“.

„Auf den Desktop“ heißt: hinter allen normalen Fenstern, aber *über* dem Desktop
selbst. ``HWND_BOTTOM`` wäre zu tief – ganz unten liegt unter Windows 10/11 der
Desktop (``Progman``/``WorkerW``), und das Fenster verschwände hinter dem
Hintergrundbild. Deshalb wird das Fenster direkt über dem obersten
Desktop-Fenster einsortiert. Nach „Desktop anzeigen“ (Win+D) liegt der Desktop
oben – dann kommt das Fenster wieder darüber und bleibt sichtbar.
"""

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

DESKTOP_CLASSES = {"Progman", "WorkerW"}


def desktop_insert_after(zorder: list[tuple[int, str]], own: int) -> int | None:
    """Nach welchem Fenster ``own`` einsortiert werden muss, um direkt über dem Desktop zu liegen.

    ``zorder``: sichtbare Top-Level-Fenster als (hwnd, Klassenname), oberstes zuerst.
    Gibt None zurück, wenn ``own`` schon richtig liegt; ``HWND_TOP``, wenn über dem
    Desktop nichts anderes liegt; ``HWND_BOTTOM`` als Rückfall ohne erkennbaren Desktop.
    """
    others = [(h, c) for h, c in zorder]
    desk = next((i for i, (_h, c) in enumerate(others) if c in DESKTOP_CLASSES), None)
    if desk is None:
        return HWND_BOTTOM
    above = [h for h, _c in others[:desk]]
    if above and above[-1] == own:
        return None
    above = [h for h in above if h != own]
    if not above:
        return HWND_TOP
    return above[-1]


def _user32():
    import ctypes

    return ctypes.WinDLL("user32", use_last_error=True)


def _set_pos(hwnd: int, after: int) -> bool:
    if not IS_WINDOWS or not hwnd:
        return False
    import ctypes

    return bool(_user32().SetWindowPos(ctypes.c_void_p(hwnd), ctypes.c_void_p(after), 0, 0, 0, 0, _FLAGS))


def set_topmost(hwnd: int, topmost: bool) -> bool:
    return _set_pos(hwnd, HWND_TOPMOST if topmost else HWND_NOTOPMOST)


def _visible_zorder() -> list[tuple[int, str]]:
    import ctypes
    from ctypes import wintypes

    user32 = _user32()
    out: list[tuple[int, str]] = []
    buf = ctypes.create_unicode_buffer(64)

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(raw, _lp):
        hwnd = ctypes.c_void_p(raw)
        if user32.IsWindowVisible(hwnd):
            user32.GetClassNameW(hwnd, buf, 64)
            out.append((int(raw or 0), buf.value))
        return True

    user32.EnumWindows(cb, 0)
    return out


def send_to_desktop(hwnd: int) -> bool:
    """Hinter alle normalen Fenster, aber über den Desktop (wie ein Desktop-Icon)."""
    if not IS_WINDOWS or not hwnd:
        return False
    _set_pos(hwnd, HWND_NOTOPMOST)
    after = desktop_insert_after(_visible_zorder(), hwnd)
    if after is None:
        return True
    return _set_pos(hwnd, after)
