"""Autostart mit Windows über HKCU\\...\\Run (keine Admin-Rechte nötig)."""

from __future__ import annotations

import sys

from . import IS_WINDOWS

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE = "DesktopPets"


def command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe = sys.executable.replace("python.exe", "pythonw.exe")
    return f'"{exe}" -m desktop_pets'


def is_supported() -> bool:
    return IS_WINDOWS


def is_enabled() -> bool:
    if not IS_WINDOWS:
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE)
            return True
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    if not IS_WINDOWS:
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE, 0, winreg.REG_SZ, command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False
