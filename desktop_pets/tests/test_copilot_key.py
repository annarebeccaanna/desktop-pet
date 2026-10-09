"""Copilot-Taste (Win + Umschalt + F23)."""

import os

import pytest

from desktop_pets.win.keyhook import VK_F23, ComboMatcher

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
LWIN, LSHIFT, A = 0x5B, 0xA0, 0x41


def press(m, *seq):
    return [m.on_key(vk, down) for vk, down in seq]


def test_copilot_combo_is_swallowed_and_fires_once():
    m = ComboMatcher()
    out = press(m, (LWIN, True), (LSHIFT, True), (VK_F23, True), (VK_F23, True), (VK_F23, False),
                (LSHIFT, False), (LWIN, False))
    assert out == [(False, False), (False, False), (True, True), (True, False), (True, False),
                   (False, False), (False, False)]


def test_everything_else_passes_through():
    m = ComboMatcher()
    assert press(m, (VK_F23, True), (VK_F23, False)) == [(False, False), (False, False)]   # F23 allein
    assert press(m, (LWIN, True), (A, True), (A, False), (LWIN, False)) == [(False, False)] * 4
    assert press(m, (LSHIFT, True), (VK_F23, True)) == [(False, False), (False, False)]     # ohne Win


def test_injected_keys_are_ignored():
    m = ComboMatcher()
    press(m, (LWIN, True), (LSHIFT, True))
    assert m.on_key(VK_F23, True, injected=True) == (False, False)


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


def test_off_by_default_and_checkbox_switches_it(pa):
    feature = pa.features.get("copilot_key")
    assert not feature.enabled
    pa.open_settings()
    dlg = pa._settings_dialog
    if not feature.hook.available:            # unter Linux: Häkchen ausgegraut, Hinweis sichtbar
        assert not dlg.cb_copilot.isEnabled() and "Windows" in dlg.lbl_copilot.text()
    pa.settings.set("general.copilot_key", True)
    assert feature.enabled
    pa.settings.set("general.copilot_key", False)
    assert not feature.enabled
    dlg.close()


def test_key_press_opens_settings_and_other_actions(pa):
    feature = pa.features.get("copilot_key")
    pa.settings.set("general.copilot_key", True)
    feature._bridge.fired.emit()             # so meldet der Hook-Thread einen Tastendruck
    assert pa._settings_dialog is not None and pa._settings_dialog.isVisible()
    pa._settings_dialog.close()
    pa.settings.set("general.copilot_action", "pause")
    feature.trigger()
    assert pa.modes.paused
    pa.settings.set("general.copilot_key", False)
    feature.trigger()                        # aus → nichts passiert
    assert pa.modes.paused and feature.fired_count == 2
