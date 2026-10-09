"""Copilot-Taste abfangen (sendet Win + Umschalt + F23).

``RegisterHotKey`` reicht hier nicht: Windows hat die Kombination selbst belegt.
Deshalb ein Low-Level-Tastatur-Hook (wie PowerToys), der *nur* F23 bei gedrückter
Win- und Umschalt-Taste schluckt – alle anderen Tasten laufen unberührt durch.

* Läuft in einem eigenen Thread mit eigener Nachrichtenschleife: Selbst wenn die
  App kurz beschäftigt ist, hakt die Tastatur nie.
* Beim Loslassen der Win-Taste würde Windows sonst das Startmenü öffnen. Darum
  wird beim Abfangen ein unbelegter Dummy-Tastendruck eingeschoben (wie PowerToys).

``ComboMatcher`` ist reine Logik und testbar; der Hook selbst nur unter Windows.
"""

from __future__ import annotations

import threading
from typing import Callable

from ..core.log import get_logger
from . import IS_WINDOWS

log = get_logger("win.keyhook")

VK_F23 = 0x86
VK_WIN = {0x5B, 0x5C}                 # linke/rechte Windows-Taste
VK_SHIFT = {0x10, 0xA0, 0xA1}
VK_ALT = {0x12, 0xA4, 0xA5}           # Alt + Copilot = Spracheingabe
VK_CTRL = {0x11, 0xA2, 0xA3}          # Strg + Copilot = sachliche Anfrage
VK_DUMMY = 0xE8                       # unbelegt – unterdrückt das Startmenü


class ComboMatcher:
    """Erkennt Win + Umschalt + <Taste> aus einzelnen Tastenereignissen."""

    def __init__(self, key: int = VK_F23) -> None:
        self.key = key
        self.pressed: set[int] = set()
        self.swallowing = False
        self.alt = False                      # war Alt beim letzten Auslösen gedrückt?
        self.ctrl = False                     # … und Strg?

    def reset(self) -> None:
        self.pressed.clear()
        self.swallowing = False

    def on_key(self, vk: int, down: bool, injected: bool = False) -> tuple[bool, bool]:
        """Gibt (schlucken, auslösen) zurück."""
        if injected:
            return False, False           # eigene/fremde künstliche Tasten nie anfassen
        if vk in VK_WIN or vk in VK_SHIFT or vk in VK_ALT or vk in VK_CTRL:
            if down:
                self.pressed.add(vk)
            else:
                self.pressed.discard(vk)
            return False, False
        if vk != self.key:
            return False, False
        if down:
            held = bool(self.pressed & VK_WIN) and bool(self.pressed & VK_SHIFT)
            if held or self.swallowing:
                fire = not self.swallowing      # Tastenwiederholung löst nicht erneut aus
                if fire:
                    self.alt = bool(self.pressed & VK_ALT)
                    self.ctrl = bool(self.pressed & VK_CTRL)
                self.swallowing = True
                return True, fire
            return False, False
        if self.swallowing:
            self.swallowing = False
            return True, False
        return False, False


class CopilotKeyHook:
    """Fängt die Copilot-Taste ab, solange gestartet. ``on_fire(alt, ctrl)`` läuft im Hook-Thread –
    der Aufrufer muss selbst in den GUI-Thread wechseln (z. B. per Qt-Signal)."""

    def __init__(self, on_fire: Callable[[bool, bool], None]) -> None:
        self.on_fire = on_fire
        self.matcher = ComboMatcher()
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._started = threading.Event()
        self._ok = False

    @property
    def available(self) -> bool:
        return IS_WINDOWS

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and self._ok

    def start(self) -> bool:
        if not IS_WINDOWS or self.running:
            return self.running
        self.matcher.reset()
        self._started.clear()
        self._thread = threading.Thread(target=self._run, name="copilot-key-hook", daemon=True)
        self._thread.start()
        self._started.wait(2.0)
        return self._ok

    def stop(self) -> None:
        if not IS_WINDOWS or self._thread is None:
            return
        import ctypes

        WM_QUIT = 0x0012
        ctypes.WinDLL("user32").PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        self._thread.join(2.0)
        self._thread = None
        self._ok = False

    # ---------- Windows ----------
    def _run(self) -> None:  # pragma: no cover – nur unter Windows
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        WH_KEYBOARD_LL = 13
        WM_KEYDOWN, WM_SYSKEYDOWN = 0x0100, 0x0104
        LLKHF_INJECTED = 0x10
        KEYEVENTF_KEYUP = 0x0002

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

        HOOKPROC = ctypes.WINFUNCTYPE(wintypes.LPARAM, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user32.CallNextHookEx.restype = wintypes.LPARAM
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE

        def proc(n_code, w_param, l_param):
            try:
                if n_code == 0:
                    kb = KBDLLHOOKSTRUCT.from_address(l_param)
                    down = w_param in (WM_KEYDOWN, WM_SYSKEYDOWN)
                    swallow, fire = self.matcher.on_key(kb.vkCode, down, bool(kb.flags & LLKHF_INJECTED))
                    if fire:
                        # Dummy-Taste, damit beim Loslassen von Win kein Startmenü aufgeht
                        user32.keybd_event(VK_DUMMY, 0, 0, 0)
                        user32.keybd_event(VK_DUMMY, 0, KEYEVENTF_KEYUP, 0)
                        try:
                            self.on_fire(self.matcher.alt, self.matcher.ctrl)
                        except Exception:  # noqa: BLE001
                            log.exception("Fehler in der Copilot-Tasten-Aktion")
                    if swallow:
                        return 1
            except Exception:  # noqa: BLE001 – der Hook darf die Tastatur nie blockieren
                log.exception("Fehler im Tastatur-Hook")
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        callback = HOOKPROC(proc)            # Referenz halten, sonst räumt Python sie weg
        self._thread_id = kernel32.GetCurrentThreadId()
        hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, callback, kernel32.GetModuleHandleW(None), 0)
        self._ok = bool(hook)
        if not hook:
            log.warning("Tastatur-Hook konnte nicht gesetzt werden (Fehler %s)", ctypes.get_last_error())
        self._started.set()
        if not hook:
            return
        log.info("Copilot-Taste wird abgefangen")
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        user32.UnhookWindowsHookEx(hook)
        log.info("Copilot-Taste wieder frei")
