"""Wandelt die Text-Sprites (art/*.txt) in die Grafiken um, die die App lädt.

Aufruf:  python tools/make_sprites.py            (alle Tiere + gemeinsame Grafiken)
         python tools/make_sprites.py cat        (nur ein Tier)
         python tools/make_sprites.py --preview vorschau/   (zusätzlich vergrößerte Bögen)

Pro Tier mit ``pets/<id>/art/``:
  sprites.png  – eine Zeile pro Animation, ein Feld pro Bild
  icon.png     – 16×16-Kopf aus dem ersten idle-Bild (Tray, Listen)
  bed.png / food.png / bowl.png – aus bed.txt / food.txt / bowl.txt, falls vorhanden
  pet.json     – „animations“ (Zeile, Bilder, Dauern) und „palette“ werden aktualisiert,
                 alles andere (Name, Futter, Persönlichkeit …) bleibt wie es ist.

Gemeinsame Grafiken: ``desktop_pets/assets/art/**.txt`` → ``desktop_pets/assets/**.png``
plus ``app.ico`` aus dem Katzenkopf.

Das Format der Textdateien steht in ``desktop_pets/pet/textsprites.py``.
Benötigt Pillow (nur zum Erzeugen, nicht zur Laufzeit).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from desktop_pets.pet.textsprites import Art, TextImage, load_art, load_image, pixel  # noqa: E402

PETS_DIR = ROOT / "desktop_pets" / "pets"
ASSETS_DIR = ROOT / "desktop_pets" / "assets"
ICON_ROWS = 11


def grid_image(rows: list[str], colors) -> Image.Image:
    w, h = len(rows[0]), len(rows)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            px[c, r] = pixel(colors, ch)
    return img


def build_sheet(art: Art) -> Image.Image:
    w, h = art.animations[0].size
    cols = max(len(a.frames) for a in art.animations)
    sheet = Image.new("RGBA", (cols * w, len(art.animations) * h), (0, 0, 0, 0))
    for row, anim in enumerate(art.animations):
        for col, frame in enumerate(anim.frames):
            sheet.paste(grid_image(frame, art.colors), (col * w, row * h))
    return sheet


def build_icon(art: Art) -> Image.Image:
    w, h = art.animations[0].size
    head = grid_image(art.animations[0].frames[0], art.colors).crop((0, 0, w, min(h, ICON_ROWS)))
    icon = Image.new("RGBA", (w, w), (0, 0, 0, 0))
    icon.paste(head, (0, (w - head.height) // 2))
    return icon


def animation_meta(art: Art) -> dict:
    out = {}
    for row, anim in enumerate(art.animations):
        entry: dict = {"row": row, "frames": len(anim.frames)}
        if anim.durations:
            entry["durations"] = anim.durations
            entry["fps"] = round(1000 / (sum(anim.durations) / len(anim.durations)), 2)
        else:
            entry["fps"] = anim.fps or 4
        if not anim.loop:
            entry["loop"] = False
        out[anim.name] = entry
    return out


def build_pet(folder: Path, preview: Path | None) -> None:
    art = load_art(folder / "art")
    sheet = build_sheet(art)
    sheet.save(folder / "sprites.png")
    build_icon(art).save(folder / "icon.png")
    for name, image in art.images.items():
        grid_image(image.rows, image.colors).save(folder / f"{name}.png")

    meta_file = folder / "pet.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {
        "id": folder.name, "name": folder.name.capitalize(), "scale": 2,
    }
    w, h = art.animations[0].size
    meta["sprite_size"] = [w, h]
    meta["animations"] = animation_meta(art)
    if art.roles:
        meta["palette"] = art.roles
    meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if preview is not None:
        preview.mkdir(parents=True, exist_ok=True)
        sheet.resize((sheet.width * 8, sheet.height * 8), Image.NEAREST).save(preview / f"{folder.name}.png")
    print(f"{folder.name}: {len(art.animations)} Animationen, Bogen {sheet.width}×{sheet.height} px")


def build_shared() -> None:
    src = ASSETS_DIR / "art"
    for txt in sorted(src.rglob("*.txt")):
        image: TextImage = load_image(txt)
        target = ASSETS_DIR / txt.relative_to(src).with_suffix(".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        grid_image(image.rows, image.colors).save(target)
    cat = PETS_DIR / "cat" / "icon.png"
    if cat.exists():
        big = Image.open(cat).resize((256, 256), Image.NEAREST)
        big.save(ASSETS_DIR / "app.ico", sizes=[(n, n) for n in (16, 32, 48, 64, 128, 256)])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pets", nargs="*", help="nur diese Tiere (Ordnernamen)")
    ap.add_argument("--preview", type=Path, help="vergrößerte Sprite-Bögen hierhin schreiben")
    args = ap.parse_args()
    folders = [PETS_DIR / p for p in args.pets] if args.pets else sorted(
        p for p in PETS_DIR.iterdir() if (p / "art").is_dir())
    for folder in folders:
        build_pet(folder, args.preview)
    build_shared()


if __name__ == "__main__":
    main()
