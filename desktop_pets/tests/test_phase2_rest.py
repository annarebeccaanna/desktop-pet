"""Phase-2-Abschluss: Körbchen bei Inaktivität/abends, Vollbild, Werte im Menü, Warten am Napf."""

import os
import random
from datetime import datetime

import pytest

from desktop_pets.features.idle_sleep import IdleSleepBehaviour
from desktop_pets.features.needs import WaitAtBowl
from desktop_pets.pet.brain import Brain, Perception, State
from desktop_pets.win.windows_enum import covers_a_screen

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def perc(**kw):
    base = dict(x=500, y=800, walk_left=20, walk_right=1900, features=frozenset(), user_idle=0.0, cursor=None)
    base.update(kw)
    return Perception(**base)


def walk(brain, x, seconds, **kw):
    for _ in range(int(seconds * 30)):
        intent = brain.tick(1 / 30, perc(x=x, **kw))
        x += intent.vx / 30
    return x


# ---------- Inaktivität → ins Körbchen ----------
def test_idle_pet_walks_to_bed_and_stays_asleep():
    b = Brain(rng=random.Random(1))
    calls = []

    def to_bed():
        calls.append(1)
        b.go_to(900, then=State.SLEEP, duration=600, tag="bed")
        return True

    b.behaviours.append(IdleSleepBehaviour(timeout=300, go_to_bed=to_bed))
    x = walk(b, 500, 12, user_idle=400)
    assert calls == [1]
    assert abs(x - 900) <= 5 and b.state == State.SLEEP and b.sleep_hold
    walk(b, x, 700, user_idle=1200)              # länger als die 600 s „Schlafen schicken“
    assert b.state == State.SLEEP


def test_input_while_walking_to_bed_cancels():
    b = Brain(rng=random.Random(2))
    beh = IdleSleepBehaviour(timeout=300, go_to_bed=lambda: (b.go_to(1500, State.SLEEP, 600, tag="bed"), True)[1])
    b.behaviours.append(beh)
    walk(b, 500, 1, user_idle=400)
    assert b.task is not None
    b.tick(1 / 30, perc(user_idle=0.3))
    assert b.task is None and b.state == State.GROOM and not beh.holding


def test_without_bed_sleeps_on_the_spot():
    b = Brain(rng=random.Random(3))
    b.behaviours.append(IdleSleepBehaviour(timeout=300, go_to_bed=lambda: False))
    b.tick(1 / 30, perc(user_idle=400))
    assert b.state == State.SLEEP


# ---------- Hungrig am Napf ----------
def test_hungry_pet_sits_next_to_bowl_and_looks_at_cursor():
    b = Brain(rng=random.Random(4))
    wait = WaitAtBowl(lambda: 700.0)
    wait.cooldown = 0
    b.behaviours.append(wait)
    b.set_state(State.SIT, 0)
    x = 400.0
    for _ in range(30 * 20):
        intent = b.tick(1 / 30, perc(x=x, cursor=(100, 300), height=64))
        x += intent.vx / 30
    assert abs(x - 700) < 64 * 1.6 and b.state == State.SIT
    assert b.facing == -1          # Maus liegt links


def test_not_hungry_no_waiting():
    b = Brain(rng=random.Random(5))
    wait = WaitAtBowl(lambda: None)
    wait.cooldown = 0
    b.behaviours.append(wait)
    b.set_state(State.SIT, 0)
    b.tick(1 / 30, perc())
    assert b.task is None


# ---------- Vollbild ----------
def test_covers_a_screen():
    screens = [(0, 0, 1920, 1080), (1920, 0, 4480, 1440)]
    assert covers_a_screen((0, 0, 1920, 1080), screens)
    assert covers_a_screen((1920, 0, 4480, 1440), screens)
    assert not covers_a_screen((0, 0, 1920, 1040), screens)     # Fenster bis zur Taskleiste
    assert not covers_a_screen((100, 100, 900, 700), screens)


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
    app.features.set_enabled("mouse_chase", False)
    app.features.set_enabled("window_walking", False)
    yield app
    app.quit()


def spin(ms):
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def test_fullscreen_hides_and_shows_again(pa):
    fs = pa.features.get("fullscreen_hide")
    fs.detector = lambda rects: True
    fs.tick(2.0)
    assert pa.pet_hidden and not pa.pet_window.isVisible()
    fs.detector = lambda rects: False
    fs.tick(2.0)
    assert not pa.pet_hidden and pa.pet_window.isVisible()
    # Benutzer-Ausblenden bleibt bestehen, auch wenn das Vollbild endet
    pa.toggle_visible()
    fs.detector = lambda rects: True
    fs.tick(2.0)
    fs.detector = lambda rects: False
    fs.tick(2.0)
    assert pa.pet_hidden


def test_idle_in_real_app_goes_to_bed(pa):
    bed = pa.features.get("bed")
    pa.idle.idle_seconds = lambda: 10_000.0
    for _ in range(500):
        spin(30)
        if pa.brain.state == State.SLEEP and bed.is_near(pa.body.x, pa.body.y):
            break
    assert pa.brain.state == State.SLEEP and bed.is_near(pa.body.x, pa.body.y)


def test_night_nap_goes_to_bed(pa):
    rhythm = pa.features.get("day_rhythm")
    rhythm.clock = lambda: datetime(2026, 10, 8, 23, 30)
    bed = pa.features.get("bed")
    pa.body.x = float(bed.bottom_center().x() + 400)
    rhythm.on_brain_event("nap")
    assert pa.brain.task is not None and pa.brain.task.tag == "bed"
    rhythm.clock = lambda: datetime(2026, 10, 8, 14, 0)
    pa.brain.task = None
    rhythm.on_brain_event("nap")
    assert pa.brain.task is None           # tagsüber: Nickerchen an Ort und Stelle


def test_pet_menu_shows_values(pa):
    from desktop_pets.ui.tray import build_pet_menu

    pa.needs.hunger, pa.needs.energy = 40, 75
    menu = build_pet_menu(pa)
    header = menu.actions()[0].defaultWidget()
    values = header.findChild(QtWidgets.QLabel, "menuValues")
    assert values is not None and "HUNGER 40 %" in values.text() and "ENERGIE 75 %" in values.text()


def test_hungry_shows_empty_bowl_and_food_lands_in_it(pa):
    needs = pa.features.get("needs")
    pa.needs.hunger = 90
    needs.tick(0.1)
    assert needs.bowl.isVisible() and needs.bowl._overlay is None      # leerer Napf steht bereit
    where = needs.bowl.bottom_center()
    needs.feed()
    assert needs.bowl.bottom_center() == where and needs.bowl._overlay is not None
