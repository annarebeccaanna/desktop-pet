"""Globale Hotkeys über Win32 ``RegisterHotKey`` (keine Admin-Rechte nötig).

``parse_hotkey`` ist reine Logik und testbar. Die Registrierung funktioniert nur
unter Windows; anderswo meldet ``register`` False und die App läuft ohne.
"""

from __future__ import annotations

from typing import Callable

from ..core.log import get_logger
from . import IS_WINDOWS

log = get_logger("win.hotkeys")

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

_MODIFIERS = {
    "ctrl": MOD_CONTROL, "strg": MOD_CONTROL, "control": MOD_CONTROL,
    "alt": MOD_ALT, "shift": MOD_SHIFT, "umschalt": MOD_SHIFT,
    "win": MOD_WIN, "meta": MOD_WIN,
}
_SPECIAL_KEYS = {
    "space": 0x20, "leertaste": 0x20, "enter": 0x0D, "return": 0x0D, "tab": 0x09,
    "esc": 0x1B, "escape": 0x1B, "pause": 0x13, "home": 0x24, "pos1": 0x24, "end": 0x23, "ende": 0x23,
    "pgup": 0x21, "pageup": 0x21, "pgdown": 0x22, "pagedown": 0x22, "insert": 0x2D, "einfg": 0x2D,
    "delete": 0x2E, "del": 0x2E, "entf": 0x2E, "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
}


class HotkeyError(ValueError):
    pass


def parse_hotkey(text: str) -> tuple[int, int]:
    """'Strg + Alt + P' → (MOD_CONTROL|MOD_ALT, VK_P). Mindestens ein Modifikator ist Pflicht."""
    parts = [p.strip() for p in text.replace("-", "+").split("+") if p.strip()]
    if not parts:
        raise HotkeyError("Leerer Hotkey")
    mods = 0
    key = None
    for part in parts:
        low = part.lower()
        if low in _MODIFIERS:
            mods |= _MODIFIERS[low]
        elif key is None:
            key = low
        else:
            raise HotkeyError(f"Mehr als eine Taste in {text!r}")
    if key is None:
        raise HotkeyError(f"Taste fehlt in {text!r}")
    if mods == 0:
        raise HotkeyError("Mindestens Strg, Alt, Umschalt oder Win nötig")
    if len(key) == 1 and (key.isalpha() or key.isdigit()):
        vk = ord(key.upper())
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    elif key in _SPECIAL_KEYS:
        vk = _SPECIAL_KEYS[key]
    else:
        raise HotkeyError(f"Unbekannte Taste {key!r}")
    return mods, vk


def format_hotkey(text: str) -> str:
    """Normalisierte deutsche Anzeige: 'ctrl+alt+p' → 'Strg + Alt + P'."""
    names = {MOD_CONTROL: "Strg", MOD_ALT: "Alt", MOD_SHIFT: "Umschalt", MOD_WIN: "Win"}
    mods, _vk = parse_hotkey(text)
    key = [p.strip() for p in text.replace("-", "+").split("+") if p.strip().lower() not in _MODIFIERS][0]
    order = [MOD_CONTROL, MOD_ALT, MOD_SHIFT, MOD_WIN]
    return " + ".join([names[m] for m in order if mods & m] + [key.upper() if len(key) == 1 else key.capitalize()])


def to_settings(text: str) -> str:
    """Speicherform: 'Strg + Alt + P' → 'Ctrl+Alt+P'."""
    names = {MOD_CONTROL: "Ctrl", MOD_ALT: "Alt", MOD_SHIFT: "Shift", MOD_WIN: "Win"}
    mods, _vk = parse_hotkey(text)
    key = [p.strip() for p in text.replace("-", "+").split("+") if p.strip().lower() not in _MODIFIERS][0]
    order = [MOD_CONTROL, MOD_ALT, MOD_SHIFT, MOD_WIN]
    return "+".join([names[m] for m in order if mods & m] + [key.upper() if len(key) == 1 else key.capitalize()])


if IS_WINDOWS:
    from PySide6.QtCore import QAbstractNativeEventFilter, QTimer

    class _Filter(QAbstractNativeEventFilter):
        def __init__(self, manager: "HotkeyManager") -> None:
            super().__init__()
            self._manager = manager

        def nativeEventFilter(self, event_type, message):  # noqa: N802 (Qt-Name)
            from ctypes import wintypes

            try:
                msg = wintypes.MSG.from_address(int(message))
            except (TypeError, ValueError):
                return False, 0
            if msg.message == WM_HOTKEY:
                hk_id = int(msg.wParam)
                # Nicht im nativen Filter arbeiten – in die Event-Schleife verschieben
                QTimer.singleShot(0, lambda: self._manager._fire(hk_id))
            return False, 0
else:
    _Filter = None  # type: ignore[assignment,misc]


class HotkeyManager:
    def __init__(self, app=None) -> None:
        self._app = app
        self._callbacks: dict[int, Callable[[], None]] = {}
        self._names: dict[str, int] = {}
        self._next_id = 0xB000
        self._filter = None
        if IS_WINDOWS and app is not None:
            self._filter = _Filter(self)
            app.installNativeEventFilter(self._filter)

    @property
    def available(self) -> bool:
        return self._filter is not None

    def register(self, name: str, combo: str, callback: Callable[[], None]) -> bool:
        self.unregister(name)
        try:
            mods, vk = parse_hotkey(combo)
        except HotkeyError as exc:
            log.warning("Hotkey %s ungültig: %s", name, exc)
            return False
        if not self.available:
            log.info("Globale Hotkeys nur unter Windows (%s = %s nicht registriert)", name, combo)
            return False
        import ctypes

        hk_id = self._next_id
        self._next_id += 1
        if not ctypes.windll.user32.RegisterHotKey(None, hk_id, mods | MOD_NOREPEAT, vk):
            log.warning("Hotkey %s (%s) ist schon belegt", name, combo)
            return False
        self._callbacks[hk_id] = callback
        self._names[name] = hk_id
        return True

    def unregister(self, name: str) -> None:
        hk_id = self._names.pop(name, None)
        if hk_id is None:
            return
        self._callbacks.pop(hk_id, None)
        if IS_WINDOWS:
            import ctypes

            ctypes.windll.user32.UnregisterHotKey(None, hk_id)

    def unregister_all(self) -> None:
        for name in list(self._names):
            self.unregister(name)

    def _fire(self, hk_id: int) -> None:
        cb = self._callbacks.get(hk_id)
        if cb is None:
            return
        try:
            cb()
        except Exception:  # noqa: BLE001
            log.exception("Fehler im Hotkey-Handler")
