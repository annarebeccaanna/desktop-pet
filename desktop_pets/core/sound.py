"""Kurze 8-Bit-Sounds mit globaler Lautstärke.

Zwei Arten, getrennt abschaltbar:
* ``"pet"``    – Geräusche des Tiers (Miau, Schnurren, Bellen, Mampf …)
* ``"notice"`` – Hinweistöne (z. B. Pomodoro-„Pling“)

Im Pause-Modus gibt es gar keine Sounds. Fehlt ein Audio-Backend, bleibt es still.
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
        self.pet_sounds = True
        self.notice_sounds = True
        self.blocked = False      # True im Pause-Modus
        self._available = True
        try:
            from PySide6.QtMultimedia import QSoundEffect  # noqa: F401
        except Exception:  # noqa: BLE001
            log.info("QtMultimedia nicht verfügbar – Sounds sind aus")
            self._available = False

    def configure(self, volume: int, pet_sounds: bool = True, notice_sounds: bool = True) -> None:
        self.volume = max(0, min(100, int(volume)))
        self.pet_sounds = bool(pet_sounds)
        self.notice_sounds = bool(notice_sounds)

    def allowed(self, kind: str = "pet") -> bool:
        if self.blocked or self.volume <= 0:
            return False
        return self.notice_sounds if kind == "notice" else self.pet_sounds

    def play(self, filename: str | None, pack_dir: Path | None = None, kind: str = "pet",
             force: bool = False) -> None:
        """``force``: auch abspielen, wenn diese Art ausgeschaltet ist (Probe-Knopf) – nie im Pause-Modus."""
        if not filename or not self._available:
            return
        if not (self.allowed(kind) or (force and not self.blocked and self.volume > 0)):
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
