"""Einstellungen: Laden/Speichern als JSON, Standardwerte, Migration.

Zugriff über Punkt-Schlüssel, z. B. ``settings.get("pause.exclude_from_capture")``.
API-Keys landen nie hier (siehe Abschnitt 9 der Spezifikation) – Schlüssel, die
danach aussehen, werden abgewiesen.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from .events import SETTINGS_CHANGED, EventBus
from .log import get_logger

log = get_logger("settings")

SCHEMA_VERSION = 2

DEFAULTS: dict[str, Any] = {
    "version": SCHEMA_VERSION,
    "pet": {
        "type": "cat",
        "size": 2,            # Benutzer-Größe 1×/2×/3×
        "names": {},          # pet_id -> eigener Name
        "colors": {},         # pet_id -> {"primary": "#rrggbb", "secondary": "#rrggbb"}
        "flip": False,        # Startblickrichtung gespiegelt
    },
    "features": {},           # feature_id -> bool (nur Abweichungen vom Default)
    "feature_options": {},    # feature_id -> {option: wert}
    "pause": {
        "exclude_from_capture": True,   # im Pause-Modus unsichtbar für Aufnahmen
        "always_exclude": False,        # auch im Normalmodus
        "auto_detect": False,           # experimentell (Phase 4)
    },
    "hotkeys": {
        "toggle_pause": "Ctrl+Alt+P",
        "toggle_visible": "Ctrl+Alt+H",
        "pomodoro": "Ctrl+Alt+T",
    },
    "general": {
        "autostart": False,
        "volume": 70,
        "muted": False,
        "language": "de",
    },
    "theme": "retro_xp",
    "bed": {
        "positions": {},      # Bildschirmname -> [x, y] (logische Koordinaten)
        "hidden": False,
    },
    "state": {},              # Gedächtnis (memory): Bedürfnisse, letzte Position
}

_FORBIDDEN_KEY_PARTS = ("api_key", "apikey", "secret", "token", "password")


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _migrate_1_to_2(data: dict) -> dict:
    # v1 hatte den Pause-Hotkey unter "pause.hotkey" und den Namen unter "pet.name".
    pause = data.get("pause", {})
    if "hotkey" in pause:
        data.setdefault("hotkeys", {})["toggle_pause"] = pause.pop("hotkey")
    pet = data.get("pet", {})
    if "name" in pet:
        pet.setdefault("names", {})[pet.get("type", "cat")] = pet.pop("name")
    return data


MIGRATIONS: dict[int, Callable[[dict], dict]] = {1: _migrate_1_to_2}


def migrate(data: dict) -> dict:
    version = int(data.get("version", 1))
    while version < SCHEMA_VERSION:
        step = MIGRATIONS.get(version)
        if step is not None:
            data = step(data)
        version += 1
    data["version"] = SCHEMA_VERSION
    return data


class Settings:
    def __init__(self, path: Path | None, bus: EventBus | None = None) -> None:
        self.path = path
        self.bus = bus
        self._data: dict[str, Any] = copy.deepcopy(DEFAULTS)

    # ---------- Laden / Speichern ----------
    def load(self) -> "Settings":
        if self.path is None or not self.path.exists():
            return self
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Wurzel ist kein Objekt")
        except (OSError, ValueError) as exc:
            log.warning("Einstellungen unlesbar (%s) – Standardwerte werden genutzt", exc)
            backup = self.path.with_suffix(".json.bak")
            try:
                self.path.replace(backup)
            except OSError:
                pass
            return self
        self._data = _deep_merge(DEFAULTS, migrate(raw))
        return self

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="settings-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            log.exception("Einstellungen konnten nicht gespeichert werden")
            try:
                os.unlink(tmp)
            except OSError:
                pass

    # ---------- Zugriff ----------
    def get(self, key: str, default: Any = None) -> Any:
        node: Any = self._data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return copy.deepcopy(node)

    def set(self, key: str, value: Any, save: bool = True) -> None:
        lowered = key.lower()
        if any(part in lowered for part in _FORBIDDEN_KEY_PARTS):
            raise ValueError(f"Geheimnisse gehören nicht in settings.json: {key!r}")
        parts = key.split(".")
        node = self._data
        for part in parts[:-1]:
            child = node.get(part)
            if not isinstance(child, dict):
                child = {}
                node[part] = child
            node = child
        if node.get(parts[-1]) == value:
            return
        node[parts[-1]] = copy.deepcopy(value)
        if save:
            self.save()
        if self.bus is not None:
            self.bus.publish(SETTINGS_CHANGED, key=key, value=value)

    # Komfort für Feature-Schalter und -Optionen
    def feature_enabled(self, feature_id: str, default: bool) -> bool:
        return bool(self._data.get("features", {}).get(feature_id, default))

    def set_feature_enabled(self, feature_id: str, enabled: bool) -> None:
        self.set(f"features.{feature_id}", bool(enabled))

    def feature_option(self, feature_id: str, option: str, default: Any) -> Any:
        return self._data.get("feature_options", {}).get(feature_id, {}).get(option, default)

    def set_feature_option(self, feature_id: str, option: str, value: Any) -> None:
        self.set(f"feature_options.{feature_id}.{option}", value)

    # Schnappschuss für „Abbrechen“ im Einstellungsdialog
    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)

    def restore(self, data: dict[str, Any]) -> None:
        self._data = copy.deepcopy(data)
        self.save()
        if self.bus is not None:
            self.bus.publish(SETTINGS_CHANGED, key="*", value=None)

    def reset(self) -> None:
        keep_state = self._data.get("state", {})
        self._data = copy.deepcopy(DEFAULTS)
        self._data["state"] = keep_state
        self.save()
        if self.bus is not None:
            self.bus.publish(SETTINGS_CHANGED, key="*", value=None)

    @property
    def data(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)
