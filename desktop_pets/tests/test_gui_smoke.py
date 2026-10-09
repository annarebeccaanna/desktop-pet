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
    pa.say("Test", "darf nicht erscheinen")
    assert not pa.bubble.isVisible()
    pa.toggle_pause()
    assert pa.in_bed                       # döst nach der Pause noch kurz im Körbchen …
    pa.features.get("bed").wake_pet()
    assert not pa.in_bed and pa.pet_window.isVisible()   # … und steigt dann heraus

    # Tierwechsel ohne Neustart
    for pid in ("dog", "dragon", "axolotl", "cat"):
        pa.switch_pet(pid)
        spin(50)
        assert pa.pack.id == pid
    assert pa.settings.get("pet.type") == "cat"

    # Füttern: Napf erscheint, Hunger sinkt
    pa.needs.hunger = 80
    needs = pa.features.get("needs")
    needs.feed()
    assert needs.bowl.isVisible()
    assert pa.needs.hunger < 80

    # Körbchen ausblenden → Tray bietet „Körbchen einblenden“ an → wieder da
    bed = pa.features.get("bed")
    assert bed.window.isVisible()
    bed.hide_by_user()
    assert not bed.window.isVisible()
    labels = [a.label for a in pa.features.menu_actions("tray")]
    assert "Körbchen einblenden" in labels
    bed.show_by_user()
    assert bed.window.isVisible()

    # Feature umschalten wirkt sofort und bleibt gespeichert
    pa.features.set_enabled("bed", False)
    assert not bed.window.isVisible()
    pa.settings.save()
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
    bed = pa.features.get("bed").bottom_center()
    ground = pa.world.ground_at(bed.x())
    # Ein „Fenster“ genau über Körbchen und Napf, das Tier steht oben drauf
    edge = Platform("win:test:0", ground.left, ground.right, ground.y - 300)
    pa.world.set_platforms([ground, edge])
    pa.body.x = float(bed.x())
    pa.body.place_on(edge)
    pa.needs.hunger = 80
    pa.features.get("needs").feed()
    for _ in range(200):          # ~6 s Spielzeit
        spin(30)
        if pa.body.support == ground.id:
            break
    assert pa.body.support == ground.id, f"Tier steht noch auf {pa.body.support}"
    # … und dann unten zum Napf laufen und fressen (Napf wird danach leer)
    for _ in range(400):
        spin(30)
        if pa.features.get("needs").bowl._overlay is None:
            break
    assert pa.features.get("needs").bowl._overlay is None, "Tier hat nicht gefressen"
    assert pa.body.support == ground.id
    pa.quit()


def test_send_to_sleep_from_window_walks_into_bed(qapp, tmp_path):
    """„Schlafen schicken“ auf einem Fenster: herunterspringen und ins Körbchen laufen (nicht teleportieren)."""
    from desktop_pets.core.app import PetApp
    from desktop_pets.pet.brain import State
    from desktop_pets.pet.physics import Platform

    pa = PetApp(qapp, settings_path=tmp_path / "settings.json")
    pa.qapp.quit = lambda: None
    pa.start()
    pa.features.set_enabled("window_walking", False)
    pa.features.set_enabled("mouse_chase", False)
    bed = pa.features.get("bed")
    target = bed.bottom_center()
    ground = pa.world.ground_at(target.x())
    edge = Platform("win:test:0", target.x() + 150, target.x() + 600, ground.y - 300)
    pa.world.set_platforms([ground, edge])
    pa.body.x = float(target.x() + 300)
    pa.body.place_on(edge)
    pa.send_to_sleep()
    for _ in range(400):
        spin(30)
        if pa.brain.state == State.SLEEP and pa.body.support == ground.id:
            break
    assert pa.body.support == ground.id
    assert pa.brain.state == State.SLEEP
    assert bed.is_near(pa.body.x, pa.body.y)
    pa.quit()


def test_settings_menu_bar_has_pet_chooser(qapp, tmp_path):
    """Einstellungen haben eine XP-Menüleiste; „Tier ▸ Tier wählen“ wechselt das Tier sofort."""
    from desktop_pets.core.app import PetApp

    pa = PetApp(qapp, settings_path=tmp_path / "settings.json")
    pa.qapp.quit = lambda: None
    pa.start()
    pa.open_settings()
    dlg = pa._settings_dialog
    titles = [a.text().replace("&", "") for a in dlg.menu_bar.actions()]
    assert titles == ["Datei", "Tier", "Ansicht", "?"]
    dlg._fill_pet_menu()
    choose = next(a.menu() for a in dlg.menu_pet.actions() if a.text() == "Tier wählen")
    names = [a.text() for a in choose.actions()]
    assert names == [p.name for p in pa.packs.values()]
    next(a for a in choose.actions() if a.text() == "Drache").trigger()
    assert pa.pack.id == "dragon"
    assert dlg.pet_list.currentItem().data(0x0100) == "dragon"   # Liste im Tab folgt
    dlg._fill_pet_menu()
    choose = next(a.menu() for a in dlg.menu_pet.actions() if a.text() == "Tier wählen")
    assert [a.text() for a in choose.actions() if a.isChecked()] == ["Drache"]
    dlg.close()
    pa.quit()
