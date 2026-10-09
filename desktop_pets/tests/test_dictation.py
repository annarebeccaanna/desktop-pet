"""Diktieren: Sprechen → einfügen, wo man schreibt – sonst Zwischenablage + Tier sagt Bescheid."""

import os

import pytest

from desktop_pets.win import speech
from desktop_pets.win.textinsert import CLIPBOARD, CT_DOCUMENT, CT_EDIT, INSERT, FocusInfo, decide

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---------- reine Logik ----------
def test_text_field_is_a_sure_insert():
    assert decide(FocusInfo(known=True, focusable=True, control_type=CT_EDIT)) == (INSERT, True)
    assert decide(FocusInfo(known=True, focusable=True, value_pattern=True, read_only=False)) == (INSERT, True)


def test_read_only_or_nothing_focused_goes_to_clipboard():
    assert decide(FocusInfo(known=True, focusable=True, control_type=CT_EDIT, read_only=True))[0] == CLIPBOARD
    assert decide(FocusInfo(known=True, focusable=False, control_type=CT_EDIT))[0] == CLIPBOARD
    assert decide(FocusInfo(known=True, focusable=True, control_type=50000))[0] == CLIPBOARD   # Knopf
    assert decide(FocusInfo())[0] == CLIPBOARD


def test_documents_and_caret_insert_but_keep_clipboard():
    assert decide(FocusInfo(known=True, focusable=True, control_type=CT_DOCUMENT, text_pattern=True)) == (INSERT, False)
    assert decide(FocusInfo(caret=True)) == (INSERT, False)


# ---------- mit der App ----------
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
    yield app
    app.quit()


@pytest.fixture
def dic(pa, monkeypatch):
    d = pa.features.get("dictation")
    started, pasted = [], []
    d.speech_available = lambda: True
    monkeypatch.setattr(d.listener, "start", lambda: started.append(1) or True)
    monkeypatch.setattr(d.listener, "finish", lambda: started.append("finish"))
    d.paste = lambda: pasted.append(1) or True
    return d, started, pasted


def clipboard():
    from PySide6.QtGui import QGuiApplication

    return QGuiApplication.clipboard()


def test_on_by_default_with_hotkey(pa):
    d = pa.features.get("dictation")
    assert d.enabled and ("dictate", d.toggle) in d.hotkeys()
    assert pa.settings.get("hotkeys.dictate") == "Ctrl+Alt+D"


def test_dictation_into_text_field_pastes_and_restores_clipboard(pa, dic):
    d, started, pasted = dic
    clipboard().setText("alter Inhalt")
    d.focus_info = lambda: FocusInfo(known=True, focusable=True, control_type=CT_EDIT)
    d.toggle()
    assert d.listening and started == [1] and "höre zu" in pa.bubble.text.text()
    d._bridge.partial.emit("Hallo Welt")
    assert "Hallo Welt" in pa.bubble.text.text()
    d._bridge.final.emit("Hallo Welt.")
    assert pasted == [1] and d.last_result == "inserted" and not pa.bubble.isVisible()
    assert clipboard().text() == "Hallo Welt."
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(900, loop.quit)
    loop.exec()
    assert clipboard().text() == "alter Inhalt"          # alte Zwischenablage ist zurück


def test_no_text_field_clipboard_and_pet_says_so(pa, dic):
    d, started, pasted = dic
    d.focus_info = lambda: FocusInfo(known=True, focusable=True, control_type=50000)
    d.toggle()
    d._bridge.final.emit("Einkaufsliste: Milch")
    assert pasted == [] and d.last_result == "clipboard"
    assert clipboard().text() == "Einkaufsliste: Milch"
    assert pa.bubble.isVisible() and "Zwischenablage" in pa.bubble.text.text()
    assert "Einkaufsliste" in pa.bubble.text.text()


def test_hotkey_again_finishes_early(pa, dic):
    d, started, pasted = dic
    d.toggle()
    d.toggle()
    assert started == [1, "finish"]


def test_privacy_off_falls_back_to_win_h(pa, dic, monkeypatch):
    from desktop_pets.win import input as win_input

    d, started, pasted = dic
    winh = []
    monkeypatch.setattr(win_input, "start_dictation", lambda: winh.append(1) or True)
    d.toggle()
    d._bridge.error.emit(speech.PRIVACY)
    assert winh == [1] and d.last_result == "winh" and "Online-Spracherkennung" in pa.bubble.text.text()


def test_nothing_heard(pa, dic):
    d, started, pasted = dic
    d.toggle()
    d._bridge.error.emit(speech.NOTHING)
    assert not d.listening and "nichts gehört" in pa.bubble.text.text()


def test_pause_mode_dictates_without_bubble(pa, dic):
    d, started, pasted = dic
    pa.toggle_pause()
    d.focus_info = lambda: FocusInfo()
    d.toggle()
    assert d.listening and not pa.bubble.isVisible()
    d._bridge.final.emit("Notiz")
    assert d.last_result == "clipboard" and not pa.bubble.isVisible() and clipboard().text() == "Notiz"


def test_copilot_action_dictate(pa, dic):
    d, started, pasted = dic
    cop = pa.features.get("copilot_key")
    pa.settings.set("general.copilot_key", True)
    pa.settings.set("general.copilot_action", "dictate")
    cop.trigger()
    assert d.listening and started == [1]
