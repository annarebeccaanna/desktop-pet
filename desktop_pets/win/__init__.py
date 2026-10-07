"""Windows-Anbindung über ctypes. Auf anderen Systemen sind alle Funktionen No-Ops,
damit sich die App (und die Tests) auch unter Linux/macOS starten lassen."""

import sys

IS_WINDOWS = sys.platform == "win32"


def windows_build() -> int:
    if not IS_WINDOWS:
        return 0
    try:
        return int(sys.getwindowsversion().build)
    except Exception:  # noqa: BLE001
        return 0
