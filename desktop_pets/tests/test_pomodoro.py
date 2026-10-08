"""Pomodoro: Zeitlogik, Ablauf mit dem Tier, Zähler, Pause-Modus, Hotkey."""

import os

import pytest

from desktop_pets.features.pomodoro import Phase, PomodoroTimer, fmt
from desktop_pets.pet.brain import State

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


# ---------- Zeitlogik ----------
def test_timer_phases_and_no_automatic_restart():
    c = Clock()
    t = PomodoroTimer(clock=c)
    assert t.work_seconds == 55 * 60 and t.break_seconds == 5 * 60   # Standard 55 + 5
    t.start_work()
    c.t += 30 * 60
    assert t.update() is None and fmt(t.remaining) == "25:00" and 0.5 < t.progress < 0.6
    c.t += 25 * 60
    assert t.update() == "work_done" and t.phase == Phase.WORK_DONE
    c.t += 600
    assert t.update() is None                       # wartet auf „Pause starten“
    t.start_break()
    c.t += 5 * 60
    assert t.update() == "break_done" and t.phase == Phase.IDLE   # nicht automatisch neu


def test_fmt():
    assert fmt(0) == "00:00" and fmt(3299) == "54:59" and fmt(7200) == "2h00"


# ---------- mit der echten App ----------
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def setup(qapp, tmp_path):
    from desktop_pets.core.app import PetApp

    pa = PetApp(qapp, settings_path=tmp_path / "settings.json")
    pa.qapp.quit = lambda: None
    pa.start()
    pa.features.set_enabled("mouse_chase", False)
    pa.features.set_enabled("window_walking", False)
    pa.features.set_enabled("pomodoro", True)
    pomo = pa.features.get("pomodoro")
    clock = Clock()
    pomo.timer.clock = clock
    yield pa, pomo, clock
    pa.quit()


def spin(ms):
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def labels(pa, where="tray"):
    return [a.label for a in pa.features.menu_actions(where)]


def test_off_by_default(qapp, tmp_path):
    from desktop_pets.core.app import PetApp

    pa = PetApp(qapp, settings_path=tmp_path / "s.json")
    pa.qapp.quit = lambda: None
    pa.start()
    assert not pa.features.is_enabled("pomodoro")
    pa.quit()


def test_full_round_with_pet(setup):
    pa, pomo, clock = setup
    assert "Pomodoro starten" in labels(pa) and "Pomodoro starten" in labels(pa, "pet")
    pomo.start()
    assert pomo.counter is not None and pomo.counter.isVisible()
    clock.t += 30 * 60
    pomo.tick(0.1)
    assert any(lbl.startswith("Pomodoro stoppen (25:00") for lbl in labels(pa))
    clock.t += 25 * 60
    pomo.tick(0.1)                                   # Arbeitszeit vorbei
    assert pa.bubble.isVisible() and "GESCHAFFT" in pa.bubble.title.text()
    assert pomo.timer.phase == Phase.WORK_DONE
    pomo.start_break()                               # „Pause starten“
    assert pa.brain.task is not None and pa.brain.task.tag == "pomodoro" and pa.brain.task.then == State.SLEEP
    from PySide6.QtGui import QGuiApplication

    center = QGuiApplication.primaryScreen().availableGeometry().center().x()
    assert abs(pa.brain.task.x - center) < 2         # mitten auf den Desktop
    clock.t += 5 * 60
    pa.brain.send_to_sleep(1e9)                      # schläft gerade
    pomo.tick(0.1)                                   # Pause vorbei
    assert pa.brain.state != State.SLEEP             # steht auf
    assert "PAUSE VORBEI" in pa.bubble.title.text()
    assert pomo.timer.phase == Phase.IDLE and "Pomodoro starten" in labels(pa)   # kein Auto-Neustart
    spin(50)
    assert not pomo.counter.isVisible()


def test_settings_change_durations_and_hide_counter(setup):
    pa, pomo, clock = setup
    pa.settings.set_feature_option("pomodoro", "work_minutes", 25)
    pa.settings.set_feature_option("pomodoro", "break_minutes", 10)
    pomo.start()
    assert pomo.timer.work_seconds == 25 * 60 and pomo.timer.break_seconds == 10 * 60
    assert pomo.counter.isVisible()
    pa.settings.set_feature_option("pomodoro", "show_counter", False)
    assert not pomo.counter.isVisible()
    assert any(lbl.startswith("Pomodoro stoppen (25:00") for lbl in labels(pa))   # Restzeit im Menü


def test_counter_can_be_moved_and_remembers_position(setup):
    pa, pomo, clock = setup
    pomo.start()
    pomo.counter.move(300, 200)
    pomo.counter.moved.emit(300, 200)
    assert pa.settings.feature_option("pomodoro", "position", None) == [300, 200]
    pomo.stop()
    pomo.start()
    pomo.counter.hide()
    pomo.counter = None                              # neu erzeugen → gespeicherte Position
    pomo.tick(0.1)
    assert (pomo.counter.x(), pomo.counter.y()) == (300, 200)


def test_pause_mode_keeps_counting_and_delays_message(setup):
    pa, pomo, clock = setup
    pomo.start()
    pa.toggle_pause()
    assert not pomo.counter.isVisible()              # im Pause-Modus kein Zähler
    clock.t += 55 * 60
    pomo.tick(0.1)
    assert pomo.timer.phase == Phase.WORK_DONE and not pa.bubble.isVisible()
    assert pa.modes.pending_count == 1
    pa.toggle_pause()
    assert pa.bubble.isVisible() and "GESCHAFFT" in pa.bubble.title.text()


def test_snooze_reminds_again(setup):
    pa, pomo, clock = setup
    pomo.start()
    clock.t += 55 * 60
    pomo.tick(0.1)
    pa.bubble.dismiss()
    pomo._snooze()                                   # „Später“
    clock.t += 4 * 60
    pomo.tick(0.1)
    assert not pa.bubble.isVisible()
    clock.t += 2 * 60
    pomo.tick(0.1)
    assert pa.bubble.isVisible()


def test_hotkey_belongs_to_the_feature(setup):
    pa, pomo, clock = setup
    assert ("pomodoro", pomo.toggle) in [(n, a) for n, a in pomo.hotkeys()]
    pomo.toggle()
    assert pomo.timer.phase == Phase.WORK
    pomo.toggle()
    assert pomo.timer.phase == Phase.IDLE


def test_bubble_buttons_are_not_cut_off(setup):
    """Knöpfe in Sprechblasen müssen ihre volle Breite bekommen (sonst „…use start…“)."""
    pa, pomo, clock = setup
    pomo.start()
    clock.t += 55 * 60
    pomo.tick(0.1)
    for btn in pa.bubble.findChildren(QtWidgets.QPushButton):
        if btn.text():
            assert btn.isVisible() and btn.width() >= btn.sizeHint().width(), btn.text()
