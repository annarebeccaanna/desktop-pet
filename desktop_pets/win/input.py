"""Tastatur-Hilfen für den KI-Chat: Fenster in den Vordergrund holen und die
Windows-Spracheingabe (Win + H) starten. Auf anderen Systemen No-Ops."""

from __future__ import annotations

from ..core.log import get_logger
from . import IS_WINDOWS

log = get_logger("win.input")

VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12
VK_LWIN, VK_RWIN = 0x5B, 0x5C
VK_H = 0x48
KEYEVENTF_KEYUP = 0x0002
MODIFIERS = (VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN)


def voice_supported() -> bool:
    return IS_WINDOWS


def modifiers_down() -> bool:
    """Hält der Mensch noch Win/Umschalt/Strg/Alt gedrückt (z. B. von Alt + Copilot)?"""
    if not IS_WINDOWS:
        return False
    import ctypes

    user32 = ctypes.WinDLL("user32")
    return any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in MODIFIERS)


def start_dictation() -> bool:
    """Windows-Spracheingabe öffnen (wie Win + H). Sie schreibt in das Feld mit dem Fokus."""
    if not IS_WINDOWS:
        return False
    import ctypes

    user32 = ctypes.WinDLL("user32")
    user32.keybd_event(VK_LWIN, 0, 0, 0)
    user32.keybd_event(VK_H, 0, 0, 0)
    user32.keybd_event(VK_H, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
    log.info("Spracheingabe gestartet")
    return True


def force_foreground(hwnd: int) -> bool:
    """Eigenes Fenster wirklich nach vorn holen (Windows erlaubt das Hintergrund-Apps
    sonst nicht). Trick: kurz an den Eingabe-Thread des Vordergrundfensters anhängen."""
    if not IS_WINDOWS or not hwnd:
        return False
    import ctypes

    user32 = ctypes.WinDLL("user32")
    kernel32 = ctypes.WinDLL("kernel32")
    fg = user32.GetForegroundWindow()
    if fg == hwnd:
        return True
    fg_thread = user32.GetWindowThreadProcessId(fg, None)
    own_thread = kernel32.GetCurrentThreadId()
    attached = fg_thread and fg_thread != own_thread and user32.AttachThreadInput(own_thread, fg_thread, True)
    try:
        user32.BringWindowToTop(hwnd)
        ok = bool(user32.SetForegroundWindow(hwnd))
        user32.SetFocus(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(own_thread, fg_thread, False)
    return ok
