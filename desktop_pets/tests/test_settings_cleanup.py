"""Rückmeldungen nach 0.8.0: abhängige Funktionen, Vollbild-Schalter verlegt,
„Umfärben“ entfernt, Körbchen zuverlässiger, Absetzen auf Fenstern."""

import os
import random
from datetime import datetime

import pytest

from desktop_pets.core.settings import Settings, migrate
from desktop_pets.features.window_walking import MIN_STAY, WalkOffEdge
from desktop_pets.pet.brain import Brain, Perception, State
from desktop_pets.pet.physics import Body, Platform, World

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---------- reine Logik ----------
def test_migration_moves_fullscreen_switch_and_drops_recolor():
    data = migrate({"version": 3, "features": {"fullscreen_hide": False, "recolor": True, "wander": True}})
    assert data["pause"]["fullscreen_hide"] is False
    assert "fullscreen_hide" not in data["features"] and "recolor" not in data["features"]
    assert data["features"]["wander"] is True


def test_fullscreen_default_is_on(tmp_path):
    assert Settings(tmp_path / "s.json").load().get("pause.fullscreen_hide") is True


def test_drop_on_title_bar_lands_on_window_edge():
    world = World()
    world.set_platforms([Platform("screen", 0, 1920, 1040, solid=True), Platform("win", 400, 1200, 300)])
    body = Body(x=700, y=318, width=48)          # auf der Titelleiste losgelassen (18 px unter der Kante)
    assert world.catch_on_drop(body, tolerance=40) is not None
    assert body.support == "win" and body.y == 300
    for _ in range(60):                          # und bleibt dort stehen
        world.step(body, 1 / 30)
    assert body.support == "win"


def test_drop_far_below_edge_falls_down():
    world = World()
    world.set_platforms([Platform("screen", 0, 1920, 1040, solid=True), Platform("win", 400, 1200, 300)])
    body = Body(x=700, y=600, width=48)          # mitten im Fenster losgelassen
    assert world.catch_on_drop(body, tolerance=40) is None
    assert body.support is None


def _on_window(**kw):
    base = dict(x=700, y=300, walk_left=420, walk_right=1180, on_window=True, features=frozenset())
    base.update(kw)
    return Perception(**base)


def test_pet_stays_on_window_for_a_while():
    brain = Brain(rng=random.Random(1))
    brain.set_state(State.IDLE, 0)
    beh = WalkOffEdge()
    for _ in range(int((MIN_STAY - 1) * 10)):
        assert beh.step(brain, 0.1, _on_window()) is None
    # danach darf es irgendwann wieder hinunter
    fired = any(beh.step(brain, 0.1, _on_window()) is not None for _ in range(200))
    assert fired


def test_leaving_the_window_resets_the_stay():
    brain = Brain(rng=random.Random(2))
    brain.set_state(State.IDLE, 0)
    beh = WalkOffEdge()
    beh.on_window_for = MIN_STAY + 5
    beh.step(brain, 0.1, _on_window(on_window=False))
    assert beh.on_window_for == 0.0


# ---------- mit der echten App ----------
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def pa(qapp, tmp_path):
    from desktop_pets.core.app import PetApp

    app = PetApp(qapp, settings_path=tmp_path / "settings.json")
    app.qapp.quit = lambda: None
    app.start()
    app.features.set_enabled("window_walking", False)
    yield app
    app.quit()


def test_mouse_chase_needs_wander(pa):
    fm = pa.features
    assert fm.is_enabled("wander") and fm.is_enabled("mouse_chase")
    fm.set_enabled("wander", False)
    assert not fm.is_enabled("mouse_chase")
    assert pa.settings.get("features.mouse_chase") is False
    assert fm.set_enabled("mouse_chase", True) is False          # geht nicht ohne Herumstreunen
    fm.set_enabled("wander", True)
    assert not fm.is_enabled("mouse_chase")                     # wird nicht automatisch wieder an
    assert fm.set_enabled("mouse_chase", True) and fm.is_enabled("mouse_chase")


def test_settings_dialog_greys_out_dependent_and_has_no_recolor(pa):
    from desktop_pets.ui.settings_dialog import SettingsDialog

    dlg = SettingsDialog(pa)
    dlg.open_fresh()
    boxes = dlg._feature_boxes
    assert "recolor" not in boxes and "fullscreen_hide" not in boxes
    assert boxes["mouse_chase"].isEnabled()
    boxes["wander"].setChecked(False)
    assert not boxes["mouse_chase"].isChecked() and not boxes["mouse_chase"].isEnabled()
    boxes["wander"].setChecked(True)
    assert boxes["mouse_chase"].isEnabled() and not boxes["mouse_chase"].isChecked()
    # Vollbild-Schalter gibt es genau einmal – im Tab „Pause & Freigabe“
    assert dlg.cb_fullscreen.isChecked()
    dlg.cb_fullscreen.setChecked(False)
    assert not pa.features.is_enabled("fullscreen_hide")
    assert pa.settings.get("pause.fullscreen_hide") is False
    dlg.close()


def test_pet_colors_apply_without_recolor_switch(pa):
    pa.settings.set(f"pet.colors.{pa.pack.id}", {"primary": "#ff0000"})
    assert pa.pet_colors() == {"primary": "#ff0000"}


def test_sleeping_at_bed_cuddles_in_and_wakes_out(pa):
    bed = pa.features.get("bed")
    b = bed.bottom_center()
    pa.teleport(b.x(), b.y())
    pa.brain.send_to_sleep(600)
    bed.tick(0.1)
    assert pa.in_bed and not pa.pet_window.isVisible() and bed.window.has_occupant
    bed.wake_pet()
    assert not pa.in_bed and pa.pet_window.isVisible() and not bed.window.has_occupant


def test_too_long_way_to_bed_hops_in(pa):
    bed = pa.features.get("bed")
    b = bed.bottom_center()
    pa.teleport(b.x() + 900, b.y())
    pa.brain.send_to_sleep(600)                  # z. B. Zeitlimit des Weges abgelaufen
    bed.on_brain_event("arrived:bed")
    assert bed.is_near(pa.body.x, pa.body.y)
    bed.tick(0.1)
    assert pa.in_bed


def test_message_wakes_pet_in_bed(pa):
    bed = pa.features.get("bed")
    b = bed.bottom_center()
    pa.teleport(b.x(), b.y())
    pa.brain.send_to_sleep(600)
    bed.tick(0.1)
    pa.say("Hallo", "Aufwachen!")
    assert not pa.in_bed and pa.bubble.isVisible()


def test_no_bed_trip_right_after_drop(pa):
    import time

    rhythm = pa.features.get("day_rhythm")
    rhythm.clock = lambda: datetime(2026, 10, 8, 23, 30)
    bed = pa.features.get("bed")
    pa.body.x = float(bed.bottom_center().x() + 400)
    pa.dropped_at = time.monotonic()
    rhythm.on_brain_event("nap")
    assert pa.brain.task is None                 # eben erst abgesetzt: döst dort
    pa.dropped_at = time.monotonic() - 600
    rhythm.on_brain_event("nap")
    assert pa.brain.task is not None and pa.brain.task.tag == "bed"
