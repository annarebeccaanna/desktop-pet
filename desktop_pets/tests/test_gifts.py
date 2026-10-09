"""Geschenke: Tier bringt etwas neben das Körbchen, Klick = annehmen."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture
def pa(tmp_path):
    qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from desktop_pets.core.app import PetApp

    app = PetApp(qapp, settings_path=tmp_path / "settings.json")
    app.qapp.quit = lambda: None
    app.start()
    app.features.set_enabled("mouse_chase", False)
    app.features.set_enabled("window_walking", False)
    app.needs.mood = 80
    app.features.set_enabled("gifts", True)
    yield app
    app.quit()


def arrive(pa, g):
    """Abkürzung: das Tier ist angekommen."""
    pa.brain.task = None
    g.on_brain_event("arrived:gift")


def test_pet_brings_gift_next_to_bed_and_it_can_be_accepted(pa):
    from desktop_pets.features.gifts import GIFTS

    g = pa.features.get("gifts")
    assert g.enabled and g.default_enabled is False          # Chaos & Spaß: ab Werk aus
    assert g.bring()
    assert pa.brain.task is not None and pa.brain.task.tag == "gift"
    bed = pa.features.get("bed")
    assert pa.brain.task.x < bed.bottom_center().x()             # links neben das Körbchen
    arrive(pa, g)
    assert len(g.lying) == 1 and g.lying[0].isVisible() and g.lying[0].gift in GIFTS[pa.pack.id]
    assert "mitgebracht" in pa.bubble.text.text()
    mood = pa.needs.mood
    g.lying[0].clicked.emit()
    assert g.lying == [] and pa.needs.mood > mood and pa.settings.get("state.gifts_received") == 1


def test_not_while_sleeping_paused_or_grumpy(pa):
    from desktop_pets.pet.brain import State

    g = pa.features.get("gifts")
    pa.brain.set_state(State.SLEEP, 100)
    assert not g.bring()
    pa.brain.set_state(State.IDLE, 1)
    pa.needs.mood = 10
    assert not g.bring()
    pa.needs.mood = 80
    pa.toggle_pause()
    assert not g.bring()


def test_at_most_three_lying_around(pa):
    g = pa.features.get("gifts")
    for _ in range(3):
        assert g.bring()
        arrive(pa, g)
    assert len(g.lying) == 3 and not g.bring(force=True)
    assert "genug" in pa.bubble.text.text()


def test_timer_triggers_and_disable_clears(pa):
    g = pa.features.get("gifts")
    g._next = 0.5
    g.tick(1.0)
    assert pa.brain.task is not None and pa.brain.task.tag == "gift" and g._next > 60
    arrive(pa, g)
    pa.features.set_enabled("gifts", False)
    assert g.lying == []
