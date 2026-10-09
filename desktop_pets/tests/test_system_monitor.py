"""Systemlast: hohe CPU → schwitzen/sitzen, wenig Akku → müde, Stecker → Freude."""

import os
import random

import pytest

from desktop_pets.features.system_monitor import HOT_AFTER, HotBehaviour, LoadMood
from desktop_pets.pet.brain import Brain, Perception, State
from desktop_pets.win.sysinfo import Battery

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def feed(mood, value, seconds, dt=2.0):
    events = []
    for _ in range(int(seconds / dt)):
        events += mood.cpu(value, dt)
    return events


def test_short_spike_is_not_hot():
    m = LoadMood()
    feed(m, 20, 20)
    assert feed(m, 100, 6) == [] and not m.hot


def test_long_load_gets_hot_and_cools_down_with_hysteresis():
    m = LoadMood()
    events = feed(m, 98, 30 + HOT_AFTER)
    assert events == ["hot"] and m.hot
    assert feed(m, 75, 40) == [] and m.hot              # zwischen den Schwellen: bleibt heiß
    assert feed(m, 10, 40) == ["cool"] and not m.hot


def test_battery_low_and_plugged_in():
    m = LoadMood()
    assert m.power(Battery(50, False)) == []
    assert m.power(Battery(18, False)) == ["low_battery"] and m.tired
    assert m.power(Battery(17, False)) == []             # nur einmal
    assert m.power(Battery(17, True)) == ["plugged_in"] and not m.tired
    assert m.power(None) == []                           # Desktop-PC ohne Akku


def test_hot_pet_prefers_sitting():
    m = LoadMood()
    m.hot = True
    b = Brain(rng=random.Random(1))
    b.behaviours.append(HotBehaviour(m))
    b.set_state(State.IDLE, 0)
    p = Perception(x=500, y=800, features=frozenset({"wander"}))
    sits = 0
    for _ in range(30):
        b.set_state(State.IDLE, 0)
        b.tick(1 / 30, p)
        sits += b.state == State.SIT
    assert sits >= 12


QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture
def pa(tmp_path):
    qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from desktop_pets.core.app import PetApp

    app = PetApp(qapp, settings_path=tmp_path / "settings.json")
    app.qapp.quit = lambda: None
    app.start()
    yield app
    app.quit()


def test_feature_reacts_with_bubbles_and_particles(pa):
    sm = pa.features.get("system_monitor")
    assert sm.enabled
    values = iter([None] + [99.0] * 200)
    sm.sampler.sample = lambda: next(values)
    sm.read_battery = lambda: None
    for _ in range(60):
        sm.tick(1.0)
    assert sm.mood.hot and "heiß" in pa.bubble.text.text()
    assert pa.pet_window.has_particles
    # müde bei leerem Akku, Freude beim Einstecken
    pa.bubble.dismiss()
    sm.read_battery = lambda: Battery(12, False)
    sm.tick(20.0)
    assert sm.mood.tired and "Akku" in pa.bubble.text.text()
    p = Perception(x=0, y=0, energy=80)
    sm.contribute(p)
    assert p.energy <= 15
    sm.read_battery = lambda: Battery(12, True)
    sm.tick(20.0)
    assert not sm.mood.tired and "Strom" in pa.bubble.text.text()


def test_pause_mode_shows_nothing(pa):
    sm = pa.features.get("system_monitor")
    pa.toggle_pause()
    sm.read_battery = lambda: Battery(10, False)
    sm.tick(20.0)
    assert sm.mood.tired and not pa.bubble.isVisible()
