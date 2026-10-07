"""Dateipfade: Benutzerdaten (%APPDATA%) und mitgelieferte Ressourcen."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "DesktopPets"


def resource_dir() -> Path:
    """Ordner des Pakets `desktop_pets` (auch innerhalb einer PyInstaller-.exe)."""
    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base:
        return Path(frozen_base) / "desktop_pets"
    return Path(__file__).resolve().parent.parent


def user_data_dir() -> Path:
    """%APPDATA%\\DesktopPets unter Windows, ~/.config/DesktopPets sonst.

    Mit der Umgebungsvariable DESKTOP_PETS_HOME lässt sich der Ordner umlenken
    (praktisch für Tests und portable Installationen).
    """
    override = os.environ.get("DESKTOP_PETS_HOME")
    if override:
        base = Path(override)
    elif sys.platform == "win32" and os.environ.get("APPDATA"):
        base = Path(os.environ["APPDATA"]) / APP_DIR_NAME
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_DIR_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def settings_file() -> Path:
    return user_data_dir() / "settings.json"


def log_file() -> Path:
    return user_data_dir() / "log.txt"


def pets_dirs() -> list[Path]:
    """Mitgelieferte Tier-Pakete plus eigene Pakete im Benutzerordner."""
    user_pets = user_data_dir() / "pets"
    user_pets.mkdir(exist_ok=True)
    return [resource_dir() / "pets", user_pets]


def themes_dir() -> Path:
    return resource_dir() / "themes"


def assets_dir() -> Path:
    return resource_dir() / "assets"
