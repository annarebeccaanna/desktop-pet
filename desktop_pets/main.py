"""Einstieg: startet App, Tray und Hotkeys.

    python -m desktop_pets
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication

    from . import APP_NAME, __version__
    from .core.log import setup_logging

    log = setup_logging()
    # Per-Monitor-DPI ist in Qt 6 Standard. PassThrough = echte Windows-Skalierung (125 %, 150 % …):
    # Dialoge haben die richtige Größe; die Pixel-Art ist bei 100/200 % exakt scharf, bei
    # Zwischenstufen je nach Tiergröße minimal ungleichmäßig (bewusst so belassen).
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("DesktopPets")
    app.setQuitOnLastWindowClosed(False)

    from .core.app import PetApp

    try:
        pet_app = PetApp(app)
        pet_app.start()
    except Exception:
        log.exception("Start fehlgeschlagen")
        raise
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
