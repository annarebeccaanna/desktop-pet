"""Text-Werkzeuge: markierten Text holen → Pixel-Menü → KI → Ersetzen/Kopieren."""

import os

import pytest

from desktop_pets.features.ai.providers import AIError
from desktop_pets.features.ai.text_tools import SYSTEM, TOOLS, build_request, clean_result, tool_by_id
from desktop_pets.win.textinsert import CT_EDIT, FocusInfo

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
KEY = "sk-ant-api03-TEST-1234567890abcdef"


# ---------- reine Logik ----------
def test_tools_and_request():
    ids = [t.id for t in TOOLS]
    assert ids == ["improve", "shorter", "friendly", "formal", "translate", "summarize", "explain"]
    assert not tool_by_id("summarize").replace and tool_by_id("improve").replace
    msg = build_request("Kürze.", "Ein langer Text")[0]
    assert msg.role == "user" and "<<<\nEin langer Text\n>>>" in msg.content and "Kürze." in msg.content
    assert "ausschließlich" in SYSTEM


def test_clean_result_strips_wrappers():
    assert clean_result("„Hallo“", "Hallo") == "Hallo"
    assert clean_result("<<<\nHallo\n>>>", "Hi") == "Hallo"
    assert clean_result('"Zitat"', '"Zitat"') == '"Zitat"'      # war schon im Original so


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


def spin(ms=50):
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def clipboard():
    from PySide6.QtGui import QGuiApplication

    return QGuiApplication.clipboard()


class _Fake:
    def __init__(self, answer="Sehr geehrter Herr Meier,", error=None):
        self.answer, self.error, self.seen, self.model = answer, error, None, "x"

    def chat(self, system, messages, one_shot=False):
        self.seen = (system, messages, one_shot)
        if self.error:
            raise AIError(self.error)
        return self.answer

    def scrub(self, t):
        return t


@pytest.fixture
def tools(pa):
    """Text-Werkzeuge mit nachgestelltem Windows: markierter Text kommt per „Strg + C“."""
    chat = pa.features.get("ai_chat")
    chat.keys.set("anthropic", KEY)
    pa.settings.set("ai.provider", "anthropic")
    pa.features.set_enabled("ai_chat", True)
    fake = _Fake()
    chat.provider_factory = lambda *a, **k: fake
    t = pa.features.get("text_tools")
    state = {"seq": 1, "selection": "hallo herr meier", "pasted": [], "back": []}

    def send_copy():
        if state["selection"]:
            clipboard().setText(state["selection"])
            state["seq"] += 1
        return True

    t.foreground_window = lambda: 4711
    t.foreground_process = lambda: "outlook.exe"
    t.clipboard_sequence = lambda: state["seq"]
    t.send_copy = send_copy
    t.focus_info = lambda: FocusInfo(known=True, focusable=True, control_type=CT_EDIT)
    t.paste = lambda: state["pasted"].append(clipboard().text()) or True
    t.bring_back = lambda hwnd: state["back"].append(hwnd) or True
    return t, fake, state


def wait(cond, ms=2000):
    for _ in range(ms // 20):
        if cond():
            return True
        spin(20)
    return cond()


def test_on_by_default_with_hotkey(pa):
    t = pa.features.get("text_tools")
    assert t.enabled and pa.settings.get("hotkeys.text_tools") == "Ctrl+Alt+M"


def test_selection_menu_tool_and_replace(pa, tools):
    t, fake, state = tools
    clipboard().setText("meine Zwischenablage")
    t.start()
    assert wait(lambda: t.menu is not None and t.menu.isVisible())
    assert clipboard().text() == "meine Zwischenablage"               # nach dem Kopieren wiederhergestellt
    assert "hallo herr meier" in t.menu.preview.text()
    t.menu.tool_buttons["formal"].click()
    assert wait(lambda: not t.busy)
    system, messages, one_shot = fake.seen
    assert system == SYSTEM and one_shot and "förmlicher" in messages[0].content
    assert t.menu.pages.currentIndex() == 2 and "Meier" in t.menu.result.toPlainText()
    assert t.menu.btn_primary.text() == "ERSETZEN"
    t.menu.btn_primary.click()
    assert wait(lambda: state["pasted"])
    assert state["back"] == [4711] and state["pasted"] == ["Sehr geehrter Herr Meier,"]
    assert wait(lambda: clipboard().text() == "meine Zwischenablage", 1500)  # alte Zwischenablage zurück


def test_summary_defaults_to_copy(pa, tools):
    t, fake, state = tools
    t.start()
    assert wait(lambda: t.menu is not None and t.menu.isVisible())
    t.menu.tool_buttons["summarize"].click()
    assert wait(lambda: not t.busy)
    assert t.menu.btn_primary.text() == "KOPIEREN"
    t.menu.btn_primary.click()
    assert clipboard().text() == "Sehr geehrter Herr Meier," and state["pasted"] == []


def test_custom_instruction(pa, tools):
    t, fake, state = tools
    t.start()
    assert wait(lambda: t.menu is not None and t.menu.isVisible())
    t.menu.custom.setText("als Stichpunkte")
    t.menu.custom.returnPressed.emit()
    assert wait(lambda: not t.busy)
    assert "als Stichpunkte" in fake.seen[1][0].content


def test_nothing_selected_falls_back_to_chat(pa, tools):
    t, fake, state = tools
    state["selection"] = ""
    opened = []
    t.start(fallback=lambda: opened.append(1))
    assert wait(lambda: opened == [1])
    assert t.menu is None or not t.menu.isVisible()


def test_terminal_is_never_copied(pa, tools):
    t, fake, state = tools
    t.foreground_process = lambda: "windowsterminal.exe"
    t.start()
    spin(100)
    assert state["seq"] == 1 and "Konsolen" in pa.bubble.text.text()


def test_error_goes_back_to_menu(pa, tools):
    t, fake, state = tools
    fake.error = "Der API-Key wurde abgelehnt."
    t.start()
    assert wait(lambda: t.menu is not None and t.menu.isVisible())
    t.menu.tool_buttons["improve"].click()
    assert wait(lambda: not t.busy)
    assert t.menu.pages.currentIndex() == 0 and "abgelehnt" in pa.bubble.text.text()


def test_copilot_with_selection_opens_tools(pa, tools):
    t, fake, state = tools
    cop = pa.features.get("copilot_key")
    pa.settings.set("general.copilot_key", True)
    cop.trigger()
    assert wait(lambda: t.menu is not None and t.menu.isVisible())


def test_pause_mode_turns_tools_off(pa, tools):
    t, fake, state = tools
    pa.toggle_pause()
    t.start()
    spin(100)
    assert state["seq"] == 1
