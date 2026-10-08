"""Bilddauern, Übergänge (Choreografie) und Text-Sprites."""

import random

import pytest

from desktop_pets.core.paths import resource_dir
from desktop_pets.pet.animator import Animator
from desktop_pets.pet.choreo import Choreographer
from desktop_pets.pet.pack import AnimationDef, discover_packs
from desktop_pets.pet.textsprites import ORDER, ArtError, load_art, parse_file


def full_set():
    one = lambda row, n=2, loop=True: AnimationDef(row, n, 8, loop)   # noqa: E731
    return {
        "idle": one(0), "walk": one(1, 4), "run": one(2, 4), "sit": one(3), "sleep": one(4),
        "jump": one(5, 2, False), "fall": one(6), "sit_down": one(7, 2, False), "stand_up": one(8, 2, False),
        "land": one(9, 2, False), "wake": one(10, 2, False), "fidget": one(11, 2, False),
        "yawn": one(12, 2, False), "special": one(13, 2, False),
    }


def run(ch, wanted, seconds, dt=1 / 30, **kw):
    seen = []
    for _ in range(int(seconds / dt)):
        ch.update(wanted, dt, **kw)
        if not seen or seen[-1] != ch.animator.name:
            seen.append(ch.animator.name)
    return seen


# ---------- Bilddauern ----------
def test_per_frame_durations():
    a = Animator({"idle": AnimationDef(0, 2, 4, durations=(2.0, 0.1))})
    a.update(1.9)
    assert a.frame == 0          # Augen lange offen
    a.update(0.15)
    assert a.frame == 1          # kurz blinzeln
    a.update(0.1)
    assert a.frame == 0


def test_single_frame_one_shot_finishes():
    a = Animator({"idle": AnimationDef(0, 1, 4), "pose": AnimationDef(1, 1, 4, loop=False, durations=(0.3,))})
    a.play("pose")
    a.update(0.2)
    assert not a.finished
    a.update(0.2)
    assert a.finished


# ---------- Choreografie ----------
def test_walk_to_sit_plays_sit_down():
    ch = Choreographer(Animator(full_set()), random.Random(1))
    run(ch, "walk", 1)
    seen = run(ch, "sit", 1)
    assert seen[:2] == ["sit_down", "sit"]


def test_sit_to_walk_plays_stand_up_and_blocks_movement():
    ch = Choreographer(Animator(full_set()), random.Random(1))
    run(ch, "sit", 1)
    ch.update("walk", 1 / 30)
    assert ch.animator.name == "stand_up" and ch.blocking
    seen = run(ch, "walk", 1)
    assert seen[-1] == "walk" and not ch.blocking


def test_landing_and_waking_transitions():
    ch = Choreographer(Animator(full_set()), random.Random(1))
    run(ch, "fall", 0.5)
    assert run(ch, "walk", 1)[:2] == ["land", "walk"]
    run(ch, "sleep", 1)
    assert run(ch, "walk", 1)[:3] == ["wake", "stand_up", "walk"]


def test_jumping_interrupts_a_transition_immediately():
    ch = Choreographer(Animator(full_set()), random.Random(1))
    run(ch, "sit", 1)
    ch.update("walk", 1 / 30)
    assert ch.animator.name == "stand_up"
    ch.update("jump", 1 / 30)
    assert ch.animator.name == "jump"


def test_idle_extras_appear_and_stop_when_moving():
    ch = Choreographer(Animator(full_set()), random.Random(2))
    seen = run(ch, "idle", 60)
    assert {"fidget", "yawn", "special"} & set(seen)
    assert seen[-1] in ("idle", "fidget", "yawn", "special")
    # mitten im Zwischenbild losgehen → abbrechen, aufstehen, laufen
    for _ in range(3000):
        ch.update("idle", 1 / 30)
        if ch.transient in ("fidget", "yawn", "special"):
            break
    assert run(ch, "walk", 1)[:2] == ["stand_up", "walk"]


def test_quiet_extras_in_pause_and_no_extras_while_walking():
    ch = Choreographer(Animator(full_set()), random.Random(3))
    seen = run(ch, "idle", 120, quiet=True)
    assert "special" not in seen
    ch2 = Choreographer(Animator(full_set()), random.Random(3))
    seen2 = run(ch2, "walk", 120)
    assert not {"fidget", "yawn", "special"} & set(seen2)


def test_missing_transitions_are_skipped():
    minimal = {"idle": AnimationDef(0, 2, 4), "walk": AnimationDef(1, 2, 4), "sit": AnimationDef(2, 2, 4)}
    ch = Choreographer(Animator(minimal), random.Random(1))
    run(ch, "walk", 1)
    assert run(ch, "sit", 1) == ["sit"]


# ---------- Text-Sprites ----------
PETS = ["cat", "dog", "dragon", "axolotl"]


@pytest.mark.parametrize("pid", PETS)
def test_every_pet_has_all_animations_as_text(pid):
    art = load_art(resource_dir() / "pets" / pid / "art")
    assert [a.name for a in art.animations] == ORDER
    assert art.roles.get("primary") and art.roles.get("secondary")
    assert {"bed", "food"} <= set(art.images)
    # Laufen/Rennen: Seitenansicht ⇒ asymmetrisch (Spiegeln zeigt die andere Richtung)
    walk = art.animation("walk").frames[0]
    assert walk != [row[::-1] for row in walk]


@pytest.mark.parametrize("pid", PETS)
def test_sprites_png_matches_text_files(pid):
    """Wer eine .txt ändert, muss ``python tools/make_sprites.py`` laufen lassen – sonst schlägt das hier fehl."""
    QtGui = pytest.importorskip("PySide6.QtGui")
    folder = resource_dir() / "pets" / pid
    art = load_art(folder / "art")
    sheet = QtGui.QImage(str(folder / "sprites.png")).convertToFormat(QtGui.QImage.Format_ARGB32)
    pack = discover_packs([resource_dir() / "pets"])[pid]
    w, h = art.animations[0].size
    for anim in art.animations:
        meta = pack.animations[anim.name]
        assert meta.frames == len(anim.frames)
        if anim.durations:
            assert [round(d * 1000) for d in meta.durations] == anim.durations
        for col, frame in enumerate(anim.frames):
            for r, row in enumerate(frame):
                for c, ch in enumerate(row):
                    want = art.colors.get(ch)
                    got = sheet.pixelColor(col * w + c, meta.row * h + r)
                    if want is None:
                        assert got.alpha() == 0, (anim.name, col, r, c)
                    else:
                        assert (got.red(), got.green(), got.blue(), got.alpha()) == want, (anim.name, col, r, c)


def test_text_format_errors_are_clear(tmp_path):
    bad = tmp_path / "walk.txt"
    bad.write_text("@durations 100\n\n..X.\n....\n", encoding="utf-8")
    with pytest.raises(ArtError, match="unbekanntes Zeichen"):
        parse_file(bad, {".": None})
    bad.write_text("\n....\n....\n\n...\n...\n", encoding="utf-8")
    with pytest.raises(ArtError, match="Größe"):
        parse_file(bad, {".": None})


def test_palette_comments_keep_hex_colors(tmp_path):
    from desktop_pets.pet.textsprites import parse_palette

    pal = tmp_path / "palette.txt"
    pal.write_text("# Farben\n.  transparent\nO  #E89C3C  primary    # Fell\nK #000000\n", encoding="utf-8")
    colors, roles = parse_palette(pal)
    assert colors["O"] == (0xE8, 0x9C, 0x3C, 255) and colors["."] is None
    assert roles == {"primary": "#E89C3C"}
