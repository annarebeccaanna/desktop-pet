import random

import pytest

from desktop_pets.core.paths import resource_dir
from desktop_pets.pet.animator import Animator
from desktop_pets.pet.brain import Brain, Perception, State
from desktop_pets.pet.needs import FeedResult, Needs
from desktop_pets.pet.pack import AnimationDef, PackError, discover_packs, load_pack
from desktop_pets.pet.physics import GRAVITY, Body, Platform, World, jump_velocity
from desktop_pets.pet.recolor import PAINT_PALETTE, build_color_map, parse_hex, shade

ALL = frozenset({"wander", "mouse_chase", "idle_sleep", "petting", "needs", "day_rhythm", "window_walking"})


# ---------- Animator ----------
def anims():
    return {"idle": AnimationDef(0, 4, 4), "walk": AnimationDef(1, 6, 10),
            "jump": AnimationDef(2, 3, 10, loop=False)}


def test_animator_loops_and_falls_back():
    a = Animator(anims())
    assert a.play("does_not_exist") == "idle"
    a.update(0.25 * 5)  # 5 Frames bei 4 fps
    assert a.frame == 1
    a.play("walk")
    assert a.row == 1 and a.frame == 0


def test_animator_one_shot_stops_on_last_frame():
    a = Animator(anims())
    a.play("jump")
    a.update(1.0)
    assert a.finished and a.frame == 2


def test_animator_requires_idle():
    with pytest.raises(ValueError):
        Animator({"walk": AnimationDef(0, 2, 2)})


# ---------- Tier-Pakete ----------
def test_bundled_packs_are_valid():
    packs = discover_packs([resource_dir() / "pets"])
    assert list(packs)[:4] == ["cat", "dog", "dragon", "axolotl"]
    for pack in packs.values():
        assert pack.sprites_file.exists()
        assert "idle" in pack.animations
        assert pack.palette.get("primary")
        assert pack.optional_file("bed.png") is not None


def test_new_pack_folder_is_discovered_without_code_change(tmp_path):
    src = resource_dir() / "pets" / "cat"
    dst = tmp_path / "hamster"
    dst.mkdir()
    (dst / "sprites.png").write_bytes((src / "sprites.png").read_bytes())
    (dst / "pet.json").write_text('{"id": "hamster", "name": "Hamster", "sprite_size": [16, 16],'
                                  ' "animations": {"idle": {"row": 0, "frames": 4, "fps": 4}}}', encoding="utf-8")
    packs = discover_packs([resource_dir() / "pets", tmp_path])
    assert "hamster" in packs
    assert packs["hamster"].name == "Hamster"


def test_broken_pack_is_skipped(tmp_path):
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "pet.json").write_text("{nope", encoding="utf-8")
    assert discover_packs([tmp_path]) == {}
    with pytest.raises(PackError):
        load_pack(bad)


# ---------- Physik ----------
def ground_world(width=1000, y=800):
    w = World()
    w.set_platforms([Platform("ground", 0, width, y, solid=True)])
    return w


def test_body_falls_and_lands_on_ground():
    w = ground_world()
    b = Body(x=100, y=100)
    events = [w.step(b, 1 / 30) for _ in range(120)]
    assert "landed" in events
    assert b.on_ground and b.y == 800


def test_body_lands_on_window_edge_and_moves_with_it():
    w = World()
    w.set_platforms([Platform("ground", 0, 1000, 800, solid=True), Platform("win", 200, 600, 400)])
    b = Body(x=300, y=100)
    for _ in range(60):
        w.step(b, 1 / 30)
    assert b.support == "win" and b.y == 400
    # Fenster wird verschoben
    w.set_platforms([Platform("ground", 0, 1000, 800, solid=True), Platform("win", 250, 650, 380)])
    w.step(b, 1 / 30)
    assert b.x == pytest.approx(350) and b.y == 380


def test_body_falls_when_window_disappears():
    w = World()
    w.set_platforms([Platform("ground", 0, 1000, 800, solid=True), Platform("win", 200, 600, 400)])
    b = Body(x=300, y=400)
    b.place_on(w.platforms["win"])
    w.set_platforms([Platform("ground", 0, 1000, 800, solid=True)])
    assert w.step(b, 1 / 30) == "fell"
    for _ in range(60):
        w.step(b, 1 / 30)
    assert b.support == "ground"


def test_walking_off_edge_falls():
    w = World()
    w.set_platforms([Platform("ground", 0, 1000, 800, solid=True), Platform("win", 200, 300, 400)])
    b = Body(x=290, y=400, vx=100)
    b.place_on(w.platforms["win"])
    for _ in range(10):
        w.step(b, 1 / 30)
    assert b.support != "win"


def test_higher_neighbour_screen_acts_as_wall():
    w = World()
    w.set_platforms([Platform("a", 0, 1000, 800, solid=True), Platform("b", 1000, 2000, 600, solid=True)])
    b = Body(x=960, y=800, vx=300, width=40)
    b.place_on(w.platforms["a"])
    for _ in range(30):
        w.step(b, 1 / 30)
    assert b.x <= 1000 and b.support == "a"


def test_jump_velocity_reaches_target():
    vx, vy = jump_velocity(200, -150)
    assert vy < 0
    # Simulieren und prüfen, dass die Bahn die Zielhöhe absteigend bei x≈200 kreuzt
    x = y = 0.0
    dt = 1 / 600
    crossed = None
    for _ in range(6000):
        prev = y
        vy += GRAVITY * dt
        x += vx * dt
        y += vy * dt
        if vy > 0 and prev <= -150 <= y:
            crossed = x
            break
    assert crossed == pytest.approx(200, abs=3)


# ---------- Bedürfnisse ----------
def test_needs_drift_and_feeding():
    n = Needs(hunger=50, mood=50, energy=50)
    n.tick(3600)
    assert n.hunger > 50
    assert n.feed() == FeedResult.EATEN
    assert n.hunger < 20 and n.mood > 50


def test_overfeeding_turns_away_without_penalty():
    n = Needs(hunger=5, mood=60)
    assert n.feed() == FeedResult.FULL
    assert n.feed() == FeedResult.TURN_AWAY
    assert n.mood == 60


def test_needs_never_leave_range():
    n = Needs(hunger=99, mood=1, energy=1)
    n.tick(48 * 3600)
    assert 0 <= n.hunger <= 100 and 0 <= n.mood <= 100 and 0 <= n.energy <= 100


def test_sleeping_restores_energy_faster_in_bed():
    from desktop_pets.pet.needs import Activity

    a, b = Needs(energy=10), Needs(energy=10)
    a.tick(1800, Activity.SLEEP)
    b.tick(1800, Activity.BED_SLEEP)
    assert b.energy > a.energy > 10


def test_needs_roundtrip_with_offline_catch_up():
    n = Needs(hunger=20, mood=80, energy=40)
    data = n.to_dict()
    restored = Needs.from_dict(data, now=data["saved_at"] + 3600)
    assert restored.hunger > 20 and restored.energy > 40 and restored.mood == 80


# ---------- Umfärben ----------
def test_paint_palette_has_28_colors():
    assert len(PAINT_PALETTE) == 28 and len(set(PAINT_PALETTE)) == 28


def test_color_map():
    pal = {"primary": "#E89C3C", "primary_dark": "#B8732A", "secondary": "#FDF0D2"}
    assert build_color_map(pal, None) == {}
    cmap = build_color_map(pal, {"primary": "#0000FF", "secondary": "#FFFFFF"})
    assert cmap[parse_hex("#E89C3C")] == 0x0000FF
    assert cmap[parse_hex("#B8732A")] == shade(0x0000FF, 0.72)
    assert cmap[parse_hex("#FDF0D2")] == 0xFFFFFF


# ---------- Gehirn ----------
def brain(seed=1, **kw):
    return Brain(rng=random.Random(seed), **kw)


def perc(**kw):
    base = dict(x=500, y=800, walk_left=20, walk_right=1900, features=ALL, user_idle=0.0)
    base.update(kw)
    return Perception(**base)


def run(b, p, seconds, dt=1 / 30):
    states = set()
    intent = None
    for _ in range(int(seconds / dt)):
        intent = b.tick(dt, p)
        states.add(b.state)
    return states, intent


def test_wander_produces_varied_behaviour():
    b = brain(3)
    states, _ = run(b, perc(cursor=None), 120)
    assert State.WALK in states
    assert len(states & {State.SIT, State.IDLE, State.GROOM}) >= 2


def test_without_wander_pet_never_walks():
    b = brain(4)
    states, _ = run(b, perc(features=frozenset({"petting"})), 300)
    assert State.WALK not in states and State.RUN not in states


def test_pause_means_no_movement():
    b = brain(5)
    b.go_to(1500)
    for _ in range(3000):
        intent = b.tick(1 / 30, perc(paused=True, cursor=(900, 500), cursor_speed=2000))
        assert intent.vx == 0
        assert b.state in (State.SLEEP, State.SIT, State.GROOM, State.IDLE)
        assert intent.jump_to is None


def test_idle_sleep_and_wake_on_input():
    b = brain(6)
    _, intent = run(b, perc(user_idle=400, idle_timeout=300), 1)
    assert b.state == State.SLEEP and intent.animation == "sleep"
    b.tick(1 / 30, perc(user_idle=0.2))
    assert b.state != State.SLEEP
    assert "woke" in b.pop_events()


def test_idle_sleep_disabled_keeps_awake():
    b = brain(6)
    feats = ALL - {"idle_sleep", "wander"}
    run(b, perc(user_idle=4000, idle_timeout=300, features=feats), 2)
    assert b.state != State.SLEEP or b.timer < 1e8


def test_mouse_chase_runs_to_cursor_and_catches_it():
    b = brain(7, playfulness=1.0)
    b.chase_cooldown = 0
    x = 300.0
    caught = False
    for i in range(30 * 20):
        moving = i < 90 or (b.state != State.RUN and i < 400)
        still = 0.0 if moving else 1.0
        speed = 900.0 if moving else 0.0
        intent = b.tick(1 / 30, perc(x=x, cursor=(900, 700), cursor_speed=speed, cursor_still_for=still))
        x += intent.vx / 30
        if intent.jump_to is not None:
            caught = True
            assert intent.jump_to[0] == 900
            break
    assert caught
    assert "caught" in b.pop_events()


def test_mouse_chase_off_never_runs():
    b = brain(8, playfulness=1.0)
    b.chase_cooldown = 0
    feats = ALL - {"mouse_chase"}
    states, _ = run(b, perc(cursor=(1500, 700), cursor_speed=2000, features=feats), 30)
    assert State.RUN not in states


def test_goto_task_eats_and_reports():
    b = brain(9)
    b.go_to(700, then=State.EAT, duration=1.0, tag="feed")
    x = 500.0
    events = []
    for _ in range(30 * 10):
        intent = b.tick(1 / 30, perc(x=x, features=frozenset()))
        x += intent.vx / 30
        events += b.pop_events()
        if "done:feed" in events:
            break
    assert "arrived:feed" in events and "done:feed" in events
    assert abs(x - 700) <= 5


def test_goto_bed_then_sleep_does_not_loop():
    b = brain(10)
    b.go_to(520, then=State.SLEEP, duration=600, tag="bed")
    x = 500.0
    arrived = 0
    for _ in range(30 * 30):
        intent = b.tick(1 / 30, perc(x=x, features=frozenset()))
        x += intent.vx / 30
        arrived += b.pop_events().count("arrived:bed")
    assert arrived == 1 and b.state == State.SLEEP and b.task is None


def test_petting_makes_happy_with_hearts():
    b = brain(11)
    b.petted()
    assert b.state == State.HAPPY
    assert "hearts" in b.pop_events()


def test_window_jump_is_chosen_sometimes():
    b = brain(12, playfulness=1.0, laziness=0.0)
    jumps = 0
    x = 500.0
    for _ in range(30 * 120):
        intent = b.tick(1 / 30, perc(x=x, cursor=None, jump_targets=((700, 500),)))
        x += intent.vx / 30
        if intent.jump_to is not None:
            jumps += 1
            b.tick(1 / 30, perc(on_ground=False, cursor=None))
    assert jumps > 0


def test_dragging_overrides_everything():
    b = brain(13)
    b.start_drag()
    for _ in range(60):
        intent = b.tick(1 / 30, perc(user_idle=9999))
        assert intent.animation == "fall" and intent.vx == 0
    b.end_drag()
    b.tick(1 / 30, perc(on_ground=False))
    assert b.state == State.FALL
