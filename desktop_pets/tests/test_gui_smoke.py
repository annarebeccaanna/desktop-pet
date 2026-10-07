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


def test_feeding_from_window_edge_goes_down_to_ground(qapp, tmp_path):
    """Steht das Tier auf einem Fenster, muss es zum Napf am Boden herunter (nicht oben bleiben)."""
    from desktop_pets.pet.physics import Platform

    from desktop_pets.core.app import PetApp

    pa = PetApp(qapp, settings_path=tmp_path / "settings.json")
    pa.qapp.quit = lambda: None
    pa.start()
    pa.features.set_enabled("window_walking", False)   # Testfenster nicht durch echte Fenster ersetzen
    pa.features.set_enabled("mouse_chase", False)
    bed = pa.bed_window.bottom_center()
    ground = pa.world.ground_at(bed.x())
    # Ein „Fenster“ genau über Körbchen und Napf, das Tier steht oben drauf
    edge = Platform("win:test:0", ground.left, ground.right, ground.y - 300)
    pa.world.set_platforms([ground, edge])
    pa.body.x = float(bed.x())
    pa.body.place_on(edge)
    pa.needs.hunger = 80
    pa.feed()
    for _ in range(200):          # ~6 s Spielzeit
        spin(30)
        if pa.body.support == ground.id:
            break
    assert pa.body.support == ground.id, f"Tier steht noch auf {pa.body.support}"
    # … und dann unten zum Napf laufen und fressen (Napf wird danach leer)
    for _ in range(400):
        spin(30)
        if pa.bowl_window._overlay is None:
            break
    assert pa.bowl_window._overlay is None, "Tier hat nicht gefressen"
    assert pa.body.support == ground.id
    pa.quit()
