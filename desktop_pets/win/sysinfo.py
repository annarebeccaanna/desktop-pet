"""CPU-Auslastung und Akkustand über die Windows-API (ohne Zusatzpakete).
Auf anderen Systemen: None (die Funktion „Systemlast“ macht dann einfach nichts)."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass

from . import IS_WINDOWS


class CpuSampler:
    """Auslastung seit dem letzten Aufruf (0–100) aus ``GetSystemTimes``."""

    def __init__(self) -> None:
        self._last: tuple[int, int, int] | None = None

    def sample(self) -> float | None:
        if not IS_WINDOWS:
            return None
        from ctypes import wintypes

        idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
        if not ctypes.WinDLL("kernel32").GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel),
                                                       ctypes.byref(user)):
            return None

        def val(ft) -> int:
            return (ft.dwHighDateTime << 32) | ft.dwLowDateTime

        now = (val(idle), val(kernel), val(user))
        last, self._last = self._last, now
        if last is None:
            return None
        d_idle, d_kernel, d_user = (now[i] - last[i] for i in range(3))
        total = d_kernel + d_user                  # Kernel-Zeit enthält die Leerlaufzeit
        if total <= 0:
            return None
        return max(0.0, min(100.0, 100.0 * (total - d_idle) / total))


@dataclass
class Battery:
    percent: int
    plugged: bool


def battery() -> Battery | None:
    """None = kein Akku (Desktop-PC) oder unbekannt."""
    if not IS_WINDOWS:
        return None

    class SYSTEM_POWER_STATUS(ctypes.Structure):
        _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                    ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                    ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]

    status = SYSTEM_POWER_STATUS()
    if not ctypes.WinDLL("kernel32").GetSystemPowerStatus(ctypes.byref(status)):
        return None
    if status.BatteryFlag == 128 or status.BatteryFlag == 255 or status.BatteryLifePercent == 255:
        return None                                # kein Akku / unbekannt
    return Battery(percent=int(status.BatteryLifePercent), plugged=status.ACLineStatus == 1)
