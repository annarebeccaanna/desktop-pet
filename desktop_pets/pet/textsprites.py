"""Text-Sprites: Pixel-Art als Textdateien, die man direkt im Editor zeichnet.

Aufbau eines Tier-Ordners::

    pets/cat/art/
    ├── palette.txt     Zeichen → Farbe (+ Rolle für das Umfärben)
    ├── idle.txt        eine Datei je Animation
    ├── walk.txt
    ├── …
    ├── bed.txt         Einzelbilder (Körbchen, Futter)
    └── food.txt

Format einer Animation::

    # Kommentar
    @durations 130 130 130 130      Dauer je Bild in ms (alternativ: @fps 8)
    @loop false                     optional, Standard: Schleife

    ................                ein Bild = ein Block aus Zeilen,
    ....KK..........                Blöcke durch Leerzeilen getrennt
    …

Einzelbilder dürfen eigene Farben mitbringen: ``@color B #C08040``.
Seitenansichten blicken nach rechts – nach links spiegelt die App.

``tools/make_sprites.py`` wandelt alles in ``sprites.png`` & Co. um. Diese Datei
enthält nur das Einlesen (ohne Qt, ohne Pillow) und ist damit testbar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Reihenfolge der Zeilen im Sprite-Sheet (weitere Animationen werden alphabetisch angehängt)
ORDER = [
    "idle", "walk", "run", "sit", "sleep", "groom", "jump", "fall", "happy", "angry", "eat",
    "sit_down", "stand_up", "land", "wake", "yawn", "fidget", "special",
]
IMAGES = {"bed", "food", "bowl", "icon"}      # Einzelbilder, keine Animationen
TRANSPARENT = "."

RGBA = tuple[int, int, int, int]
_COMMENT = re.compile(r"\s#(\s|$)")


class ArtError(ValueError):
    pass


@dataclass
class TextAnim:
    name: str
    frames: list[list[str]]
    durations: list[int] | None = None   # ms je Bild
    fps: float | None = None
    loop: bool = True
    title: str = ""

    @property
    def size(self) -> tuple[int, int]:
        rows = self.frames[0]
        return len(rows[0]), len(rows)


@dataclass
class TextImage:
    name: str
    rows: list[str]
    colors: dict[str, RGBA | None]


@dataclass
class Art:
    animations: list[TextAnim]
    colors: dict[str, RGBA | None]
    roles: dict[str, str] = field(default_factory=dict)   # "primary" → "#E89C3C"
    images: dict[str, TextImage] = field(default_factory=dict)

    def animation(self, name: str) -> TextAnim | None:
        return next((a for a in self.animations if a.name == name), None)


def parse_color(text: str) -> RGBA | None:
    t = text.strip().lower()
    if t in ("transparent", "-", "none"):
        return None
    t = t.lstrip("#")
    if len(t) != 6:
        raise ArtError(f"Keine Farbe: {text!r}")
    return int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16), 255


def parse_palette(path: Path) -> tuple[dict[str, RGBA | None], dict[str, str]]:
    colors: dict[str, RGBA | None] = {TRANSPARENT: None}
    roles: dict[str, str] = {}
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = _strip_comment(raw)
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2 or len(parts[0]) != 1:
            raise ArtError(f"{path.name}:{n}: erwartet „Zeichen Farbe [Rolle]“")
        ch, col = parts[0], parts[1]
        colors[ch] = parse_color(col)
        if len(parts) >= 3 and colors[ch] is not None:
            roles[parts[2]] = col.upper() if col.startswith("#") else "#" + col.upper()
    return colors, roles


def _strip_comment(raw: str) -> str:
    """Kommentare: Zeile beginnt mit „#“ oder „ # …“ (mit Leerzeichen danach) – Farben wie #E89C3C bleiben."""
    line = raw.strip()
    if line.startswith("#"):
        return ""
    match = _COMMENT.search(line)
    return line[:match.start()].strip() if match else line


def parse_file(path: Path, colors: dict[str, RGBA | None]) -> tuple[dict[str, str], list[list[str]], dict]:
    """Liest Direktiven, Bilder und eigene Farben (@color) einer Datei."""
    directives: dict[str, str] = {}
    own = dict(colors)
    frames: list[list[str]] = []
    current: list[str] = []
    title = ""
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.rstrip()
        if line.startswith("#"):
            if not title:
                title = line.lstrip("# ").strip()
            continue
        if line.startswith("@"):
            key, _sp, value = line[1:].partition(" ")
            if key == "color":
                ch, _s, col = value.strip().partition(" ")
                if len(ch) != 1:
                    raise ArtError(f"{path.name}:{n}: @color braucht ein einzelnes Zeichen")
                own[ch] = parse_color(col)
            else:
                directives[key] = value.strip()
            continue
        if not line.strip():
            if current:
                frames.append(current)
                current = []
            continue
        current.append(line.strip())
    if current:
        frames.append(current)
    directives.setdefault("title", title)
    if not frames:
        raise ArtError(f"{path.name}: keine Bilder gefunden")
    w, h = len(frames[0][0]), len(frames[0])
    for i, fr in enumerate(frames, 1):
        if len(fr) != h or any(len(r) != w for r in fr):
            raise ArtError(f"{path.name}: Bild {i} hat nicht die Größe {w}×{h}")
        for r, row in enumerate(fr):
            for ch in row:
                if ch not in own:
                    raise ArtError(f"{path.name}: Bild {i}, Zeile {r + 1}: unbekanntes Zeichen {ch!r}")
    return directives, frames, own


def load_art(folder: Path) -> Art:
    pal = folder / "palette.txt"
    colors, roles = parse_palette(pal) if pal.exists() else ({TRANSPARENT: None}, {})
    anims: list[TextAnim] = []
    images: dict[str, TextImage] = {}
    files = {p.stem: p for p in folder.glob("*.txt") if p.stem != "palette"}
    order = [n for n in ORDER if n in files] + sorted(n for n in files if n not in ORDER and n not in IMAGES)
    for name in order:
        d, frames, _own = parse_file(files[name], colors)
        durations = [int(x) for x in d["durations"].split()] if d.get("durations") else None
        if durations is not None and len(durations) != len(frames):
            raise ArtError(f"{name}.txt: {len(frames)} Bilder, aber {len(durations)} Dauern")
        anims.append(TextAnim(
            name=name, frames=frames, durations=durations,
            fps=float(d["fps"]) if d.get("fps") else None,
            loop=d.get("loop", "true").lower() not in ("false", "nein", "0", "no"),
            title=d.get("title", ""),
        ))
    for name in IMAGES:
        if name in files:
            _d, frames, own = parse_file(files[name], colors)
            images[name] = TextImage(name, frames[0], own)
    if anims:
        sizes = {a.size for a in anims}
        if len(sizes) != 1:
            raise ArtError(f"{folder}: Animationen haben unterschiedliche Größen {sorted(sizes)}")
        if anims[0].name != "idle":
            raise ArtError(f"{folder}: idle.txt fehlt (Pflicht)")
    return Art(anims, colors, roles, images)


def load_image(path: Path) -> TextImage:
    _d, frames, own = parse_file(path, {TRANSPARENT: None})
    return TextImage(path.stem, frames[0], own)


def pixel(colors: dict[str, RGBA | None], ch: str) -> RGBA:
    c = colors.get(ch)
    return (0, 0, 0, 0) if c is None else c
