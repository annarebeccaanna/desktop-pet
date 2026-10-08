"""Tier-Pakete: ``pets/<id>/pet.json`` + ``sprites.png`` (+ optional bed/bowl/food.png).

Ein neuer Ordner mit diesen Dateien erscheint ohne Codeänderung in der Auswahl.
Kein Qt-Import hier – die Logik bleibt testbar.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ..core.log import get_logger

log = get_logger("pack")

ANIMATION_NAMES = (
    "idle", "move", "move_fast", "sit", "sleep", "groom", "jump", "fall", "happy", "angry", "eat",
    "sit_down", "stand_up", "land", "wake", "yawn", "fidget", "special",
)
# Ältere Tier-Pakete nennen die Fortbewegung noch „walk“/„run“ – sie funktionieren weiter.
ALIASES = {"move": "walk", "move_fast": "run"}


@dataclass(frozen=True)
class AnimationDef:
    row: int
    frames: int
    fps: float
    loop: bool = True
    durations: tuple[float, ...] | None = None   # Sekunden je Bild (überschreibt fps)

    def frame_time(self, index: int) -> float:
        if self.durations:
            return max(0.01, self.durations[index % len(self.durations)])
        return 1.0 / self.fps


@dataclass
class PetPack:
    id: str
    name: str
    path: Path
    sprite_size: tuple[int, int]
    scale: int
    animations: dict[str, AnimationDef]
    sounds: dict[str, str] = field(default_factory=dict)
    personality: dict[str, float] = field(default_factory=dict)
    food: str = "Futter"
    bed_name: str = "Körbchen"
    palette: dict[str, str] = field(default_factory=dict)   # "primary"/"secondary" -> #rrggbb
    default_name: str = ""
    prompt: str = ""
    order: int = 100

    @property
    def sprites_file(self) -> Path:
        return self.path / "sprites.png"

    def optional_file(self, name: str) -> Path | None:
        candidate = self.path / name
        return candidate if candidate.exists() else None

    def trait(self, name: str, default: float = 0.5) -> float:
        try:
            return max(0.0, min(1.0, float(self.personality.get(name, default))))
        except (TypeError, ValueError):
            return default


class PackError(ValueError):
    pass


def _parse_animations(raw: Any) -> dict[str, AnimationDef]:
    if not isinstance(raw, dict) or not raw:
        raise PackError("'animations' fehlt oder ist leer")
    out: dict[str, AnimationDef] = {}
    for name, spec in raw.items():
        try:
            frames = max(1, int(spec.get("frames", 1)))
            durations = spec.get("durations")
            if durations is not None:
                durations = tuple(max(1, float(ms)) / 1000.0 for ms in durations)
                if len(durations) != frames:
                    raise PackError(f"Animation {name!r}: {frames} Bilder, aber {len(durations)} Dauern")
            out[name] = AnimationDef(
                row=int(spec["row"]),
                frames=frames,
                fps=max(0.1, float(spec.get("fps", 4))),
                loop=bool(spec.get("loop", True)),
                durations=durations,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PackError(f"Animation {name!r} ungültig: {exc}") from exc
    if "idle" not in out:
        raise PackError("Animation 'idle' ist Pflicht (Rückfall für alle anderen)")
    for new, old in ALIASES.items():
        if new not in out and old in out:
            out[new] = out[old]
    if "move_fast" not in out and "move" in out:
        out["move_fast"] = out["move"]
    return out


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_pack(folder: Path) -> PetPack:
    meta_file = folder / "pet.json"
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PackError(f"{meta_file}: {exc}") from exc
    if not (folder / "sprites.png").exists():
        raise PackError(f"{folder}: sprites.png fehlt")
    size = meta.get("sprite_size", [32, 32])
    try:
        sprite_size = (int(size[0]), int(size[1]))
        scale = max(1, int(meta.get("scale", 1)))
    except (TypeError, ValueError, IndexError) as exc:
        raise PackError(f"{meta_file}: sprite_size/scale ungültig") from exc
    pet_id = str(meta.get("id") or folder.name)
    return PetPack(
        id=pet_id,
        name=str(meta.get("name", pet_id)),
        path=folder,
        sprite_size=sprite_size,
        scale=scale,
        animations=_parse_animations(meta.get("animations")),
        sounds=dict(meta.get("sounds", {})),
        personality=dict(meta.get("personality", {})),
        food=str(meta.get("food", "Futter")),
        bed_name=str(meta.get("bed_name", "Körbchen")),
        palette=dict(meta.get("palette", {})),
        default_name=str(meta.get("default_name", meta.get("name", pet_id))),
        prompt=str(meta.get("prompt", "")),
        order=_int(meta.get("order"), 100),
    )


def discover_packs(dirs: Iterable[Path]) -> dict[str, PetPack]:
    """Findet alle gültigen Pakete. Spätere Ordner überschreiben frühere (Benutzer > mitgeliefert)."""
    packs: dict[str, PetPack] = {}
    for base in dirs:
        if not base.is_dir():
            continue
        for folder in sorted(p for p in base.iterdir() if p.is_dir()):
            if not (folder / "pet.json").exists():
                continue
            try:
                pack = load_pack(folder)
            except PackError as exc:
                log.warning("Tier-Paket übersprungen: %s", exc)
                continue
            packs[pack.id] = pack
    return dict(sorted(packs.items(), key=lambda kv: (kv[1].order, kv[1].name.lower())))
