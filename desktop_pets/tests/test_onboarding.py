"""Einführung beim ersten Start."""

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
    yield app
    app.quit()


def buttons(pa):
    return {b.text(): b for b in pa.bubble.findChildren(QtWidgets.QPushButton) if b.isVisibleTo(pa.bubble)}


def test_walkthrough_until_the_end(pa):
    ob = pa.features.get("onboarding")
    ob.start()
    assert "1/5" in pa.bubble.title.text() and "Mieze" in pa.bubble.text.text()
    assert "deine neue Katze" in pa.bubble.text.text()
    for _ in range(4):
        buttons(pa)["Weiter"].click()
    assert "5/5" in pa.bubble.title.text()
    buttons(pa)["Los geht's!"].click()
    assert pa.settings.get("state.onboarded") is True and not pa.bubble.isVisible()


def test_skip_and_settings_button(pa):
    ob = pa.features.get("onboarding")
    ob.start()
    buttons(pa)["Überspringen"].click()
    assert pa.settings.get("state.onboarded") is True
    ob.start()
    for _ in range(3):
        buttons(pa)["Weiter"].click()
    buttons(pa)["KI einrichten"].click()
    dlg = pa._settings_dialog
    assert dlg is not None and dlg.tabs.tabText(dlg.tabs.currentIndex()) == "KI"
    dlg.close()


def test_shown_only_once_and_not_in_pause(pa):
    ob = pa.features.get("onboarding")
    assert any(a.label == "Einführung zeigen" for a in ob.menu_actions("tray"))
    pa.toggle_pause()
    ob.start()
    assert not pa.bubble.isVisible()
    pa.toggle_pause()
    pa.settings.set("state.onboarded", True)
    assert pa.features.set_enabled("onboarding", False) is False      # fester Bestandteil


def test_dog_grammar(pa):
    pa.switch_pet("dog")
    pa.features.get("onboarding").start()
    assert "dein neuer Hund" in pa.bubble.text.text()
