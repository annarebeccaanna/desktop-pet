"""Erzeugt die Pixel-Art der Start-Tiere (eigene Grafiken, per Skript gezeichnet).

Aufruf:  python tools/make_sprites.py [--preview ORDNER]

Pro Tier entstehen in ``desktop_pets/pets/<id>/``:
  sprites.png  – Sprite-Sheet (eine Zeile pro Animation, 16×16 je Frame)
  icon.png     – 16×16 Kopf für Tray/Listen
  bed.png      – Körbchen / Kissen / Nest / Glas
  bowl.png     – Napf (leer)
  food.png     – Futter (Fisch, Knochen, Paprika, Wurm)
  pet.json     – Metadaten (nur, wenn noch nicht vorhanden oder --force)

Zusätzlich ``desktop_pets/assets/`` mit gemeinsamen Grafiken (Herz, Zzz, Standard-Napf).

Benötigt Pillow (nur zum Erzeugen, nicht zur Laufzeit).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PETS_DIR = ROOT / "desktop_pets" / "pets"
ASSETS_DIR = ROOT / "desktop_pets" / "assets"

S = 16  # Frame-Größe

# --------------------------------------------------------------------------- #
# Hilfen
# --------------------------------------------------------------------------- #

Grid = list[str]


def sym(left_halves: list[str]) -> Grid:
    """Spiegelt 8 Zeichen breite linke Hälften zu 16 Zeichen."""
    out = []
    for row in left_halves:
        assert len(row) == 8, (row, len(row))
        out.append(row + row[::-1])
    return out


def check(grid: Grid, name: str) -> Grid:
    assert len(grid) == S, f"{name}: {len(grid)} Zeilen"
    for i, row in enumerate(grid):
        assert len(row) == S, f"{name} Zeile {i}: {len(row)} Zeichen: {row!r}"
    return grid


def put(grid: Grid, r: int, c: int, ch: str) -> Grid:
    g = list(grid)
    if 0 <= r < S and 0 <= c < S:
        row = g[r]
        g[r] = row[:c] + ch + row[c + 1:]
    return g


def shift(grid: Grid, dx: int = 0, dy: int = 0) -> Grid:
    empty = "." * S
    rows = list(grid)
    if dy > 0:
        rows = [empty] * dy + rows[:-dy]
    elif dy < 0:
        rows = rows[-dy:] + [empty] * (-dy)
    out = []
    for row in rows:
        if dx > 0:
            row = "." * dx + row[:-dx]
        elif dx < 0:
            row = row[-dx:] + "." * (-dx)
        out.append(row)
    return out


def compose(top: Grid, bottom: Grid) -> Grid:
    return list(top) + list(bottom)


def eyes(grid: Grid) -> list[tuple[int, int]]:
    return [(r, c) for r, row in enumerate(grid) for c, ch in enumerate(row) if ch == "E"]


def face_color_at(grid: Grid, r: int, c: int) -> str:
    """Farbe neben dem Auge (für geschlossene Augen)."""
    for dc in (-1, 1, -2, 2):
        cc = c + dc
        if 0 <= cc < S and grid[r][cc] not in "EKW.":
            return grid[r][cc]
    return "O"


def expr(grid: Grid, kind: str) -> Grid:
    """Gesichtsausdruck über die mit E markierten Augenpixel."""
    pts = eyes(grid)
    if not pts:
        return grid
    by_col: dict[int, list[int]] = {}
    for r, c in pts:
        by_col.setdefault(c, []).append(r)
    g = list(grid)
    center = 7.5
    for c, rs in by_col.items():
        rs.sort()
        top, bottom = rs[0], rs[-1]
        base = face_color_at(grid, top, c)
        if kind == "open":
            for r in rs:
                g = put(g, r, c, "K")
        elif kind == "closed":
            for r in rs:
                g = put(g, r, c, base)
            g = put(g, bottom, c, "K")
        elif kind == "happy":
            for r in rs:
                g = put(g, r, c, base)
            g = put(g, top, c, "K")
            inner = c + (1 if c < center else -1)
            outer = c - (1 if c < center else -1)
            g = put(g, bottom, inner, "K") if grid[bottom][inner] not in "EP" else g
            g = put(g, bottom, outer, "K") if grid[bottom][outer] not in "EP" else g
        elif kind == "angry":
            for r in rs:
                g = put(g, r, c, "K")
            inner = c + (1 if c < center else -1)
            g = put(g, top - 1, inner, "K")
            g = put(g, top, inner, "K") if grid[top][inner] not in "EP" else g
        elif kind == "look":
            # Pupillen nach rechts (Laufrichtung; links = gespiegelt)
            for r in rs:
                g = put(g, r, c, "K")
            g = put(g, top, c, "W")
        elif kind == "wide":
            for r in rs:
                g = put(g, r, c, "K")
            g = put(g, top, c, "W")
            g = put(g, bottom, c, "W")
    return g


def finish(grid: Grid) -> Grid:
    """Restliche E-Marker zu schwarzen Augen machen."""
    return [row.replace("E", "K") for row in grid]


# --------------------------------------------------------------------------- #
# Tiere
# --------------------------------------------------------------------------- #
# Zeichen: . transparent  K Outline  O Hauptfarbe  D dunkle Hauptfarbe
#          C Zweitfarbe   P Akzent (Nase/Ohren/Kiemen)  A Akzent 2
#          W weiß  E Auge  T Zunge/Rot

CAT = {
    "colors": {"O": "#E89C3C", "D": "#B8732A", "C": "#FDF0D2", "P": "#F08CB4", "A": "#F08CB4",
               "W": "#FFFFFF", "K": "#000000", "T": "#E0503A"},
    "head": sym([
        "........",
        "..K.....",
        "..KK....",
        "..KPK...",
        "..KPPKKK",
        ".KOOOOOO",
        ".KOOEOOO",
        ".KOOEOOO",
        "KOCOOOOP",
        ".KOOOOOK",
    ]),
    "body_sit": sym([
        "..KKOOOO",
        "..KOCCCC",
        ".KOOCCCC",
        ".KOOCCCC",
        ".KOKOCCC",
        "..KKKKKK",
    ]),
    "body_walk_a": [
        "..KKOOOOOOOOKK..",
        "..KOCCCCCCCCOK..",
        ".KOOCCCCCCCCOOK.",
        ".KOKKKKKKKKKKOK.",
        ".KOK........KOK.",
        ".KKK........KKK.",
    ],
    "body_walk_b": [
        "..KKOOOOOOOOKK..",
        "..KOCCCCCCCCOK..",
        ".KOOCCCCCCCCOOK.",
        ".KKKOKKKKKKOKKK.",
        "...KOK....KOK...",
        "...KKK....KKK...",
    ],
    "lie": [
        "................",
        "................",
        "................",
        "................",
        "................",
        "..K....K........",
        "..KK..KK........",
        ".KPPKKPPK.......",
        ".KOOOOOOK.KKKK..",
        "KOOOOOOOOKOOOOK.",
        "KOKKOOKKOOOOOOOK",
        "KCOOPPOOCOOOOOOK",
        ".KCCOOCCOOOOOKOK",
        ".KOCCCCOOOOOKKOK",
        ".KOKKKKOKKKKOOK.",
        "..KK..KK...KKK..",
    ],
}

DOG = {
    "colors": {"O": "#C68642", "D": "#6B3E1E", "C": "#FFFFFF", "P": "#E0503A", "A": "#6B3E1E",
               "W": "#FFFFFF", "K": "#000000", "T": "#E0503A"},
    "head": sym([
        "........",
        "....KKKK",
        "...KOOOO",
        ".KKOOOOO",
        "KDDKOOOO",
        "KDDKOEOO",
        "KDDKOEOO",
        "KDDKCCCK",
        ".KKKCCKT",
        "...KCCCT",
    ]),
    "body_sit": sym([
        "...KKOOO",
        "...KOCCC",
        "..KOOCCC",
        "..KOOCCC",
        "..KOKOOC",
        "...KKKKK",
    ]),
    "body_walk_a": [
        "...KKOOOOOOKK...",
        "...KOCCCCCCOK...",
        "..KOOCCCCCCOOK..",
        "..KOKKKKKKKKOK..",
        "..KOK......KOK..",
        "..KKK......KKK..",
    ],
    "body_walk_b": [
        "...KKOOOOOOKK...",
        "...KOCCCCCCOK...",
        "..KOOCCCCCCOOK..",
        "..KKKOKKKKOKKK..",
        "....KOK..KOK....",
        "....KKK..KKK....",
    ],
    "lie": [
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "...KKKKK........",
        "..KOOOOOK.......",
        ".KDKOOOOOKKKKKK.",
        "KDDKOKOKOOOOOOOK",
        "KDDKOOOOOOOOOOOK",
        "KDDKCCCKOOOOOOOK",
        ".KKCCKCCKOOOOKOK",
        "..KCCCCOOOOOKKOK",
        "..KKKKKKKKKKKKK.",
        "................",
    ],
}

DRAGON = {
    "colors": {"O": "#3A9A2E", "D": "#26701E", "C": "#F5D547", "P": "#90D070", "A": "#F5A623",
               "W": "#FFFFFF", "K": "#000000", "T": "#E0503A"},
    "head": sym([
        "...P....",
        "...KP...",
        "....KKKK",
        "...KOOOO",
        "..KOOOOO",
        "..KOAEOO",
        "..KOOEOO",
        "..KOOOOO",
        "..KOOOOK",
        "...KKOOO",
    ]),
    "body_sit": sym([
        "KPK.KOOO",
        "KPPKOCCC",
        "KPPKOCCC",
        ".KPKOCCC",
        "..KOOOOC",
        "..KKKKKK",
    ]),
    "body_walk_a": [
        "KPK.KOOOOOOK.KPK",
        "KPPKOCCCCCCOKPPK",
        ".KPKOCCCCCCOKPK.",
        "..KOKKKKKKKKOK..",
        "..KOK......KOK..",
        "..KKK......KKK..",
    ],
    "body_walk_b": [
        ".KPKKOOOOOOKKPK.",
        "KPPKOCCCCCCOKPPK",
        "KPPKOCCCCCCOKPPK",
        ".KKKOKKKKKKOKKK.",
        "....KOK..KOK....",
        "....KKK..KKK....",
    ],
    "lie": [
        "................",
        "................",
        "................",
        "................",
        "..P..P..........",
        "..KP.KP.........",
        "..KKKKKK..KPK...",
        ".KOOOOOOK.KPPK..",
        "KOOOOOOOOKKOPK..",
        "KOKKOOKKOOOOOOK.",
        "KOOOOOOOOOOOOOOK",
        ".KOOKKOOOCCCCOOK",
        "..KOOOOOCCCCCOKK",
        "..KOOOOOOOOOOOK.",
        "..KKKOKKKKKOKKOK",
        "....KK.....KKKKK",
    ],
}

AXOLOTL = {
    "colors": {"O": "#F5A3C7", "D": "#D97AA6", "C": "#FFE0EC", "P": "#E0503A", "A": "#E0503A",
               "W": "#FFFFFF", "K": "#000000", "T": "#E0503A"},
    "head": sym([
        "........",
        "P.P.....",
        ".PKKKKKK",
        "PPKOOOOO",
        ".KOOOOOO",
        "PKOOEOOO",
        "PKOOEOOO",
        ".KOOOOOO",
        "..KOOKKK",
        "...KOOOO",
    ]),
    "body_sit": sym([
        "...KOOOC",
        "..KOOCCC",
        "..KOOCCC",
        "..KOOOCC",
        "..KOKOOO",
        "...KKKKK",
    ]),
    "body_walk_a": [
        "...KOOOOOOOOK...",
        "..KOOCCCCCCOOKK.",
        "..KOOCCCCCCOOOOK",
        "..KOKKKKKKKKOKKK",
        "..KOK......KOK..",
        "..KKK......KKK..",
    ],
    "body_walk_b": [
        "...KOOOOOOOOK...",
        "..KOOCCCCCCOOKK.",
        "..KOOCCCCCCOOOOK",
        "..KKKOKKKKOKKKKK",
        "....KOK..KOK....",
        "....KKK..KKK....",
    ],
    "lie": [
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "P.P.............",
        ".PKKKKKK........",
        "PPKOOOOOK.......",
        ".KOOOOOOOKKKKK..",
        "PKOKOOKOOOOOOOKK",
        "PKOOOOOOOOOOOOOK",
        ".KOOKKOOCCCCCOOK",
        "..KOOOOCCCCCCOKK",
        "..KKKOKKKKKOKKK.",
        "....KK.....KK...",
    ],
}

PETS = {
    "cat": {
        "art": CAT, "name": "Katze", "default_name": "Mieze", "food": "Fisch", "bed_name": "Körbchen",
        "personality": {"playfulness": 0.7, "laziness": 0.6},
        "sounds": {"happy": "purr.wav", "angry": "hiss.wav", "call": "meow.wav", "eat": "munch.wav"},
        "prompt": "Du bist eine verspielte, leicht eigensinnige Hauskatze. Antworte kurz, gern mit Miau.",
    },
    "dog": {
        "art": DOG, "name": "Hund", "default_name": "Bello", "food": "Knochen", "bed_name": "Hundekissen",
        "personality": {"playfulness": 0.85, "laziness": 0.35},
        "sounds": {"happy": "pant.wav", "angry": "growl.wav", "call": "woof.wav", "eat": "munch.wav"},
        "prompt": "Du bist ein begeisterter, treuer Hund. Antworte kurz und freudig, gern mit Wuff.",
    },
    "dragon": {
        "art": DRAGON, "name": "Drache", "default_name": "Funki", "food": "Paprika", "bed_name": "Nest",
        "personality": {"playfulness": 0.6, "laziness": 0.5},
        "sounds": {"happy": "chirp.wav", "angry": "roar.wav", "call": "chirp.wav", "eat": "munch.wav"},
        "prompt": "Du bist ein kleiner, stolzer Drache, der gern Feuer spucken würde. Antworte kurz.",
    },
    "axolotl": {
        "art": AXOLOTL, "name": "Axolotl", "default_name": "Lotti", "food": "Wurm", "bed_name": "Glas",
        "personality": {"playfulness": 0.45, "laziness": 0.75},
        "sounds": {"happy": "blub.wav", "angry": "blub.wav", "call": "blub.wav", "eat": "munch.wav"},
        "prompt": "Du bist ein entspanntes, immer lächelndes Axolotl. Antworte kurz und gelassen.",
    },
}

# Reihenfolge = Zeilen im Sprite-Sheet
ANIMATIONS = [
    ("idle", 4, 4), ("walk", 6, 10), ("run", 6, 14), ("sit", 2, 2), ("sleep", 2, 1),
    ("groom", 6, 6), ("jump", 4, 10), ("fall", 2, 8), ("happy", 4, 8), ("angry", 4, 10),
    ("eat", 4, 6),
]
COLS = max(n for _, n, _ in ANIMATIONS)


def frames_for(art: dict) -> dict[str, list[Grid]]:
    head = art["head"]
    sit = check(compose(head, art["body_sit"]), "sit")
    walk_a = check(compose(head, art["body_walk_a"]), "walk_a")
    walk_b = check(compose(head, art["body_walk_b"]), "walk_b")
    lie = check(art["lie"], "lie")

    open_sit = expr(sit, "open")
    blink = expr(sit, "closed")
    look_a = expr(walk_a, "look")
    look_b = expr(walk_b, "look")
    happy = expr(sit, "happy")
    angry = expr(sit, "angry")
    closed_sit = expr(sit, "closed")

    # Putzen: Augen zu, Pfote (Zweitfarbe) am Mund, Kopf leicht geneigt
    paw = put(put(closed_sit, 10, 5, "C"), 9, 5, "C")
    paw = put(paw, 11, 5, "K")
    lick = put(closed_sit, 10, 8, "T")

    eat_a = shift(closed_sit, 0, 1)
    eat_b = put(shift(closed_sit, 0, 2), 11, 7, "T")

    zz = lie
    for r, c in ((1, 11), (1, 12), (1, 13), (2, 12), (3, 11), (3, 12), (3, 13)):
        zz = put(zz, r, c, "K")
    small_z = put(put(put(lie, 3, 12, "K"), 3, 13, "K"), 4, 12, "K")

    frames = {
        "idle": [open_sit, open_sit, blink, open_sit],
        "walk": [look_a, shift(look_a, 0, -1), look_a, look_b, shift(look_b, 0, -1), look_b],
        "run": [shift(look_a, 0, -1), look_a, shift(look_b, 0, -2), shift(look_b, 0, -1), look_a,
                shift(look_b, 0, -1)],
        "sit": [open_sit, blink],
        "sleep": [zz, small_z],
        "groom": [closed_sit, lick, closed_sit, paw, shift(paw, 0, 1), closed_sit],
        "jump": [shift(expr(walk_b, "look"), 0, -1), shift(look_a, 0, -1), look_a, look_b],
        "fall": [expr(walk_a, "wide"), shift(expr(walk_b, "wide"), 0, -1)],
        "happy": [happy, shift(happy, 0, -1), shift(happy, 0, -2), shift(happy, 0, -1)],
        "angry": [angry, shift(angry, 1, 0), angry, shift(angry, -1, 0)],
        "eat": [eat_a, eat_b, eat_a, eat_b],
    }
    return {k: [finish(f) for f in v] for k, v in frames.items()}


def render(grid: Grid, colors: dict[str, str]) -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    px = img.load()
    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch == ".":
                continue
            col = colors.get(ch, "#FF00FF")
            px[c, r] = tuple(int(col[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
    return img


def build_sheet(art: dict) -> Image.Image:
    frames = frames_for(art)
    sheet = Image.new("RGBA", (COLS * S, len(ANIMATIONS) * S), (0, 0, 0, 0))
    for row, (name, count, _fps) in enumerate(ANIMATIONS):
        fl = frames[name]
        assert len(fl) == count, (name, len(fl), count)
        for col, grid in enumerate(fl):
            sheet.paste(render(grid, art["colors"]), (col * S, row * S))
    return sheet


def build_icon(art: dict) -> Image.Image:
    head = finish(expr(compose(art["head"], art["body_sit"]), "open"))
    img = render(head, art["colors"]).crop((0, 0, S, 11))
    icon = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    icon.paste(img, (0, 3))
    return icon


# --------------------------------------------------------------------------- #
# Körbchen, Napf, Futter
# --------------------------------------------------------------------------- #

BED_ART = {
    "cat": ([  # geflochtener Korb mit Kissen
        "........................",
        "........................",
        "........................",
        "........................",
        "........................",
        ".KKKKKKKKKKKKKKKKKKKKKK.",
        "KBBbBBbBBbBBbBBbBBbBBbBK",
        "KbRRRRRRRRRRRRRRRRRRRRbK",
        "KBRRRRRRRRRRRRRRRRRRRRBK",
        "KbBBbBBbBBbBBbBBbBBbBBbK",
        "KBbBBbBBbBBbBBbBBbBBbBBK",
        ".KbBBbBBbBBbBBbBBbBBbBK.",
        "..KKKKKKKKKKKKKKKKKKKK..",
    ], {"B": "#C08040", "b": "#8A5A2B", "R": "#D94A4A", "K": "#000000"}),
    "dog": ([  # Hundekissen
        "........................",
        "........................",
        "........................",
        "........................",
        "...KKKKKKKKKKKKKKKKKK...",
        "..KBBBBBBBBBBBBBBBBBBK..",
        ".KBbbbbbbbbbbbbbbbbbbBK.",
        "KBbRRRRRRRRRRRRRRRRRRbBK",
        "KBbRRRRRRRRRRRRRRRRRRbBK",
        "KBBbbbbbbbbbbbbbbbbbbBBK",
        "KBBBBBBBBBBBBBBBBBBBBBBK",
        ".KBBBBBBBBBBBBBBBBBBBBK.",
        "..KKKKKKKKKKKKKKKKKKKK..",
    ], {"B": "#3D6FC4", "b": "#28509A", "R": "#8FB4EA", "K": "#000000"}),
    "dragon": ([  # Nest mit Ästen
        "........................",
        "........................",
        "........................",
        "........................",
        "........................",
        "..K.K..K..K.K..K..K.K...",
        ".KBKbKKBKKbKBKKbKKBKbK..",
        "KbBbBbBbBbBbBbBbBbBbBbK.",
        "KBYYYYYYYYYYYYYYYYYYYBbK",
        "KbBbBbBbBbBbBbBbBbBbBbBK",
        ".KBbBbBbBbBbBbBbBbBbBbK.",
        "..KKbKKKbKKKbKKKbKKKKK..",
        "...KK..KK...KK..KK......",
    ], {"B": "#8A5A2B", "b": "#5E3A18", "Y": "#F5D547", "K": "#000000"}),
    "axolotl": ([  # Glas mit Wasser
        "....KKKKKKKKKKKKKKKK....",
        "....KGGGGGGGGGGGGGGK....",
        "...KWWWWWWWWWWWWWWWWK...",
        "..KWLLLLLLLLLLLLLLLLWK..",
        ".KWLLLLLLLLLLLLLLLLLLWK.",
        ".KWLLLLLLLLLLLLLLLLLLWK.",
        "KWLLLLLLLLLLLLLLLLLLLLWK",
        "KWLLLLLLLLLLLLLLLLLLLLWK",
        "KWLLLLLLLLLLLLLLLLLLLLWK",
        "KWLLLLLSSSSLLLLLSSLLLLWK",
        ".KWLLSSSSSSSSSSSSSSLLWK.",
        "..KWWWWWWWWWWWWWWWWWWK..",
        "...KKKKKKKKKKKKKKKKKK...",
    ], {"G": "#9AD0E8", "W": "#D8F0FF", "L": "#7EC8F0", "S": "#E8D29A", "K": "#000000"}),
}

BOWL = ([
    "............",
    "............",
    ".KKKKKKKKKK.",
    "KWWWWWWWWWWK",
    "KRRRRRRRRRRK",
    ".KRRRRRRRRK.",
    "..KKKKKKKK..",
], {"W": "#FFFFFF", "R": "#E0503A", "K": "#000000"})

FOOD = {
    "cat": ([  # Fisch
        "........",
        "........",
        ".KKKK.K.",
        "KBBBWKBK",
        "KBKBBBK.",
        ".KKKK.K.",
        "........",
        "........",
    ], {"B": "#7EA6D8", "W": "#FFFFFF", "K": "#000000"}),
    "dog": ([  # Knochen
        "........",
        ".KK..KK.",
        "KWWKKWWK",
        ".KWWWWK.",
        "KWWKKWWK",
        ".KK..KK.",
        "........",
        "........",
    ], {"W": "#FFF6E0", "K": "#000000"}),
    "dragon": ([  # Paprika
        "....K...",
        "...KG...",
        ".KKKKKK.",
        "KRRRRRWK",
        "KRRRRRRK",
        "KRRRRRRK",
        ".KRRRRK.",
        "..KKKK..",
    ], {"R": "#E0503A", "G": "#3A9A2E", "W": "#FFFFFF", "K": "#000000"}),
    "axolotl": ([  # Wurm
        "........",
        "........",
        "..KKK...",
        ".KPPPK..",
        "KPK.KPK.",
        "KPK..KPK",
        ".K....K.",
        "........",
    ], {"P": "#E88A9A", "K": "#000000"}),
}

HEART = ([
    ".KK.KK.",
    "KRRKRRK",
    "KRWRRRK",
    ".KRRRK.",
    "..KRK..",
    "...K...",
], {"R": "#E2563A", "W": "#FFFFFF", "K": "#000000"})

ZZZ = ([
    "KKKK",
    "..K.",
    ".K..",
    "KKKK",
], {"K": "#1A3A8A"})


def render_art(rows: list[str], colors: dict[str, str]) -> Image.Image:
    w, h = len(rows[0]), len(rows)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for r, row in enumerate(rows):
        assert len(row) == w, (row, len(row), w)
        for c, ch in enumerate(row):
            if ch != ".":
                col = colors[ch]
                px[c, r] = tuple(int(col[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
    return img


CHECK = [
    ".............",
    ".............",
    ".............",
    ".........G...",
    "........GG...",
    "..G....GGG...",
    "..GG..GGG....",
    "..GGGGGG.....",
    "...GGGG......",
    "....GG.......",
    ".............",
    ".............",
    ".............",
]
MENU_CHECK = [
    ".......",
    "......K",
    ".....KK",
    "K...KK.",
    "KK.KK..",
    ".KKK...",
    "..K....",
]
ARROW = [
    "K....",
    "KK...",
    "KKK..",
    "KKKK.",
    "KKK..",
    "KK...",
    "K....",
]


def build_ui_assets() -> None:
    ui = ASSETS_DIR / "ui"
    ui.mkdir(parents=True, exist_ok=True)
    render_art(CHECK, {"G": "#21A121"}).save(ui / "check.png")
    render_art(MENU_CHECK, {"K": "#000000"}).save(ui / "menu_check.png")
    render_art(MENU_CHECK, {"K": "#FFFFFF"}).save(ui / "menu_check_white.png")
    render_art(ARROW, {"K": "#000000"}).save(ui / "arrow.png")


def pet_json(pet_id: str, meta: dict) -> dict:
    art = meta["art"]
    return {
        "id": pet_id,
        "name": meta["name"],
        "order": list(PETS).index(pet_id) + 1,
        "default_name": meta["default_name"],
        "sprite_size": [S, S],
        "scale": 2,
        "food": meta["food"],
        "bed_name": meta["bed_name"],
        "palette": {
            "primary": art["colors"]["O"],
            "primary_dark": art["colors"]["D"],
            "secondary": art["colors"]["C"],
        },
        "sounds": meta["sounds"],
        "personality": meta["personality"],
        "prompt": meta["prompt"],
        "animations": {
            name: {"row": i, "frames": n, "fps": fps, **({"loop": False} if name == "jump" else {})}
            for i, (name, n, fps) in enumerate(ANIMATIONS)
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preview", type=Path, help="Zusätzlich vergrößerte Vorschaubilder hierhin schreiben")
    ap.add_argument("--force", action="store_true", help="pet.json überschreiben")
    args = ap.parse_args()

    for pet_id, meta in PETS.items():
        folder = PETS_DIR / pet_id
        folder.mkdir(parents=True, exist_ok=True)
        art = meta["art"]
        sheet = build_sheet(art)
        sheet.save(folder / "sprites.png")
        build_icon(art).save(folder / "icon.png")
        bed_rows, bed_colors = BED_ART[pet_id]
        render_art(bed_rows, bed_colors).save(folder / "bed.png")
        render_art(*FOOD[pet_id]).save(folder / "food.png")
        render_art(*BOWL).save(folder / "bowl.png")
        meta_file = folder / "pet.json"
        if args.force or not meta_file.exists():
            meta_file.write_text(json.dumps(pet_json(pet_id, meta), indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
        if args.preview:
            args.preview.mkdir(parents=True, exist_ok=True)
            sheet.resize((sheet.width * 8, sheet.height * 8), Image.NEAREST).save(args.preview / f"{pet_id}.png")
        print(f"{pet_id}: {sheet.width}×{sheet.height} px")

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    render_art(*HEART).save(ASSETS_DIR / "heart.png")
    render_art(*ZZZ).save(ASSETS_DIR / "zzz.png")
    render_art(*BOWL).save(ASSETS_DIR / "bowl.png")
    render_art(*FOOD["cat"]).save(ASSETS_DIR / "food.png")
    render_art(*BED_ART["cat"]).save(ASSETS_DIR / "bed.png")
    build_ui_assets()
    # Programm-Icon (.ico) aus dem Katzenkopf für die .exe
    cat_icon = build_icon(CAT)
    sizes = [16, 32, 48, 64, 128, 256]
    big = cat_icon.resize((256, 256), Image.NEAREST)
    big.save(ASSETS_DIR / "app.ico", sizes=[(n, n) for n in sizes])


if __name__ == "__main__":
    main()
