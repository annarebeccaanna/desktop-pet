"""Kurze 8-Bit-Sounds mit globaler Lautstärke und Stummschalter.

Im Pause-Modus gibt es keine Sounds. Fehlt ein Audio-Backend, bleibt es still.
"""

from __future__ import annotations

from pathlib import Path

from . import paths
from .log import get_logger

log = get_logger("sound")


class SoundPlayer:
    def __init__(self) -> None:
        self._effects: dict[str, object] = {}
        self.volume = 70
        self.muted = False
        self.blocked = False      # True im Pause-Modus
        self._available = True
        try:
            from PySide6.QtMultimedia import QSoundEffect  # noqa: F401
        except Exception:  # noqa: BLE001
            log.info("QtMultimedia nicht verfügbar – Sounds sind aus")
            self._available = False

    def configure(self, volume: int, muted: bool) -> None:
        self.volume = max(0, min(100, int(volume)))
        self.muted = bool(muted)

    def play(self, filename: str | None, pack_dir: Path | None = None) -> None:
        if not filename or not self._available or self.muted or self.blocked or self.volume <= 0:
            return
        path = None
        if pack_dir is not None and (pack_dir / filename).exists():
            path = pack_dir / filename
        elif (paths.assets_dir() / "sounds" / filename).exists():
            path = paths.assets_dir() / "sounds" / filename
        if path is None:
            return
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QSoundEffect

            effect = self._effects.get(str(path))
            if effect is None:
                effect = QSoundEffect()
                effect.setSource(QUrl.fromLocalFile(str(path)))
                self._effects[str(path)] = effect
            effect.setVolume(self.volume / 100.0 * 0.6)
            effect.play()
        except Exception:  # noqa: BLE001
            log.exception("Sound %s konnte nicht abgespielt werden", filename)
            self._available = False
