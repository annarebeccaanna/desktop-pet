"""Startet die echte App offscreen (ohne Fenster auf dem Bildschirm)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def spin(ms):
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def test_app_starts_pauses_and_switches_pets(qapp, tmp_path):
    from desktop_pets.core.app import PetApp

    pa = PetApp(qapp, settings_path=tmp_path / "settings.json")
    pa.qapp.quit = lambda: None  # Testprozess nicht beenden
    pa.start()
    spin(300)
    assert pa.pet_window.isVisible()

    # Pause: Tier liegt im Körbchen, keine Sounds, keine Sprechblasen
    pa.toggle_pause()
    assert pa.modes.paused and pa.in_bed and pa.sound.blocked
    pa._say("Test", "darf nicht erscheinen")
    assert not pa.bubble.isVisible()
    pa.toggle_pause()
    assert not pa.in_bed and pa.pet_window.isVisible()

    # Tierwechsel ohne Neustart
    for pid in ("dog", "dragon", "axolotl", "cat"):
        pa.switch_pet(pid)
        spin(50)
        assert pa.pack.id == pid
    assert pa.settings.get("pet.type") == "cat"

    # Füttern: Napf erscheint, Hunger sinkt
    pa.needs.hunger = 80
    pa.feed()
    assert pa.bowl_window.isVisible()
    assert pa.needs.hunger < 80

    # Feature umschalten wirkt sofort und bleibt gespeichert
    pa.features.set_enabled("bed", False)
    assert not pa.bed_window.isVisible()
    assert pa.settings.feature_enabled("bed", True) is False

    pa.open_settings()
    dlg = pa._settings_dialog
    for i in range(dlg.tabs.count()):
        dlg.tabs.setCurrentIndex(i)
        spin(20)
    dlg._cancel()   # stellt den Stand beim Öffnen wieder her
    pa.quit()
    assert "needs" in (pa.settings.get("state") or {})
