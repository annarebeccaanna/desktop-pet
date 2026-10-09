"""KI-Chat: Erkennung, Anbieter, Keys (nie in JSON/Log), Ablauf mit dem Tier, Copilot/Alt."""

import json
import logging
import os
import types

import pytest

from desktop_pets.features.ai.chat import FORGET_AFTER, MAX_TURNS, Conversation, system_prompt
from desktop_pets.features.ai.detect import detect_provider, mask
from desktop_pets.features.ai.keys import KeyStore
from desktop_pets.features.ai.providers import PROVIDERS, AIError, Message, make_provider
from desktop_pets.win.keyhook import VK_F23, ComboMatcher

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
KEY = "sk-ant-api03-GEHEIM-1234567890abcdef"


# ---------- reine Logik ----------
@pytest.mark.parametrize("key, provider", [
    ("sk-ant-abc", "anthropic"), ("sk-or-v1-x", "openrouter"), ("sk-proj-x", "openai"), ("sk-abc", "openai"),
    ("AIzaSyX", "gemini"), ("gsk_x", "groq"), ("xai-x", "xai"), ("irgendwas", None), ("", None),
])
def test_detect_provider_by_prefix(key, provider):
    assert detect_provider(key) == provider


def test_mask_never_shows_the_whole_key():
    shown = mask(KEY)
    assert shown.startswith("sk-ant-") and shown.endswith("cdef") and "GEHEIM" not in shown


def test_provider_list_has_oneai_first_and_all_from_spec():
    assert list(PROVIDERS)[0] == "oneai"
    for pid in ("anthropic", "openai", "gemini", "mistral", "openrouter", "custom"):
        assert pid in PROVIDERS


def test_openai_compatible_request_and_answer():
    calls = []

    def transport(method, url, headers, body):
        calls.append((method, url, headers, body))
        return 200, {"choices": [{"message": {"content": " Miau! "}}]}

    p = make_provider("openai", "sk-test", transport=transport)
    answer = p.chat("Du bist eine Katze.", [Message("user", "Hallo")])
    assert answer == "Miau!"
    method, url, headers, body = calls[0]
    assert url == "https://api.openai.com/v1/chat/completions" and headers["Authorization"] == "Bearer sk-test"
    assert body["messages"][0] == {"role": "system", "content": "Du bist eine Katze."}
    assert body["messages"][1] == {"role": "user", "content": "Hallo"}


def test_errors_are_friendly_and_never_contain_the_key():
    p = make_provider("openai", "sk-geheim", transport=lambda *a: (401, {"error": {"message": "bad key sk-geheim"}}))
    with pytest.raises(AIError) as exc:
        p.chat("s", [Message("user", "x")])
    assert "abgelehnt" in str(exc.value) and "sk-geheim" not in str(exc.value)
    p = make_provider("mistral", "k", transport=lambda *a: (400, {"error": {"message": "zeigt sk-k k"}}))
    p.api_key = "sk-k"
    with pytest.raises(AIError) as exc:
        p.chat("s", [Message("user", "x")])
    assert "sk-k" not in str(exc.value)


def test_oneai_without_url_asks_for_it():
    p = make_provider("oneai", "key", transport=lambda *a: (200, {}))
    with pytest.raises(AIError, match="Basis-URL"):
        p.chat("s", [Message("user", "x")])
    p = make_provider("oneai", "key", base_url="https://oneai.example/v1",
                      transport=lambda m, url, h, b: (200, {"choices": [{"message": {"content": url}}]}))
    assert p.chat("s", [Message("user", "x")]) == "https://oneai.example/v1/chat/completions"


def test_connection_test_checks_model():
    p = make_provider("openai", "k", model="gpt-5-mini",
                      transport=lambda *a: (200, {"data": [{"id": "gpt-5-mini"}]}))
    assert "Verbunden" in p.test_connection()


class _FakeAnthropic:
    """Nachbau des SDK-Clients: merkt sich die Parameter."""

    def __init__(self, stop_reason="end_turn"):
        self.sent = {}
        self.stop_reason = stop_reason
        outer = self

        class _Msgs:
            def create(self, **kw):
                outer.sent = kw
                return types.SimpleNamespace(stop_reason=outer.stop_reason, content=[
                    types.SimpleNamespace(type="thinking", text=""),
                    types.SimpleNamespace(type="text", text="Grrr, hallo!")])

        self.beta = types.SimpleNamespace(messages=_Msgs())
        self.messages = _Msgs()
        self.models = types.SimpleNamespace(retrieve=lambda model: {"id": model})


def test_anthropic_uses_sdk_with_fallback_and_low_effort():
    fake = _FakeAnthropic()
    p = make_provider("anthropic", KEY, transport=fake)
    assert p.chat("System", [Message("user", "Hi")]) == "Grrr, hallo!"
    assert fake.sent["model"] == "claude-opus-5-5" and fake.sent["system"] == "System"
    assert fake.sent["fallbacks"] == "default" and fake.sent["betas"] == ["server-side-fallback-2026-07-01"]
    assert fake.sent["output_config"] == {"effort": "low"}
    assert "Verbunden" in p.test_connection()


def test_anthropic_refusal_gives_friendly_text():
    p = make_provider("anthropic", KEY, transport=_FakeAnthropic(stop_reason="refusal"))
    assert "lieber nichts" in p.chat("s", [Message("user", "x")])


def test_conversation_keeps_recent_turns_and_forgets_after_a_while():
    c = Conversation()
    for i in range(MAX_TURNS + 3):
        c.prepare(f"Frage {i}", now=float(i))
        c.answered(f"Antwort {i}")
    msgs = c.prepare("Neu", now=100.0)
    assert msgs[0].role == "user" and msgs[-1].content == "Neu" and len(msgs) <= MAX_TURNS * 2 + 1
    msgs = c.prepare("Später", now=100.0 + FORGET_AFTER + 1)
    assert [m.content for m in msgs] == ["Später"]
    c.failed()
    assert c.messages == []


def test_system_prompt_contains_name_and_personality():
    s = system_prompt("Mieze", "Du bist eine Katze.")
    assert "Mieze" in s and "Du bist eine Katze." in s and "Deutsch" in s


def test_keystore_uses_backend_and_handles_errors():
    store = {}

    class Backend:
        def get_password(self, s, u):
            return store.get((s, u))

        def set_password(self, s, u, p):
            store[(s, u)] = p

        def delete_password(self, s, u):
            store.pop((s, u))

    ks = KeyStore(backend=Backend())
    assert ks.persistent and not ks.has("anthropic")
    ks.set("anthropic", KEY)
    assert ks.get("anthropic") == KEY and ("DesktopPets", "ai:anthropic") in store
    ks.delete("anthropic")
    assert not ks.has("anthropic")

    class Broken:
        def get_password(self, *a):
            raise RuntimeError("kaputt")

    assert KeyStore(backend=Broken()).get("x") == ""


def test_alt_copilot_is_reported():
    m = ComboMatcher()
    LWIN, LSHIFT, LALT = 0x5B, 0xA0, 0xA4
    for vk in (LALT, LWIN, LSHIFT):
        m.on_key(vk, True)
    assert m.on_key(VK_F23, True) == (True, True) and m.alt
    for vk in (VK_F23, LSHIFT, LWIN, LALT):
        m.on_key(vk, False)
    for vk in (LWIN, LSHIFT):
        m.on_key(vk, True)
    assert m.on_key(VK_F23, True) == (True, True) and not m.alt


# ---------- mit der echten App ----------
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


class _Instant:
    """Anbieter, der sofort antwortet (statt übers Netz)."""

    def __init__(self, answer="Miau, die Antwort ist 42.", error=None):
        self.answer, self.error, self.seen = answer, error, None
        self.model = "test"

    def chat(self, system, messages):
        self.seen = (system, list(messages))
        if self.error:
            raise AIError(self.error)
        return self.answer

    def scrub(self, t):
        return t


def spin(ms=50):
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def wait_answer(chat, ms=3000):
    for _ in range(ms // 20):
        spin(20)
        if not chat.busy:
            return


def test_greyed_out_without_key_and_ready_with_key(pa):
    chat = pa.features.get("ai_chat")
    assert not chat.available and pa.features.set_enabled("ai_chat", True) is False
    chat.open_input()
    assert pa.bubble.isVisible() and "API-Key" in pa.bubble.text.text()
    chat.keys.set("anthropic", KEY)
    pa.settings.set("ai.provider", "anthropic")
    assert chat.available and pa.features.set_enabled("ai_chat", True)


def test_full_chat_round_trip(pa):
    chat = pa.features.get("ai_chat")
    chat.keys.set("anthropic", KEY)
    pa.settings.set("ai.provider", "anthropic")
    pa.features.set_enabled("ai_chat", True)
    fake = _Instant()
    chat.provider_factory = lambda *a, **k: fake
    chat.open_input()
    assert chat.input.isVisible() and pa.pet_name.upper() in chat.input.title.text()
    chat.input.line.setText("Was ist der Sinn des Lebens?")
    chat.input.line.returnPressed.emit()
    assert not chat.input.isVisible()
    wait_answer(chat)
    assert pa.bubble.isVisible() and "42" in pa.bubble.text.text()
    system, messages = fake.seen
    assert pa.pet_name in system and messages[-1].content == "Was ist der Sinn des Lebens?"
    # zweite Frage hat den Verlauf dabei
    chat.send("Und warum?")
    wait_answer(chat)
    assert [m.role for m in fake.seen[1]] == ["user", "assistant", "user"]


def test_chat_error_shows_hint_and_keeps_history_clean(pa):
    chat = pa.features.get("ai_chat")
    chat.keys.set("openai", "sk-x")
    pa.settings.set("ai.provider", "openai")
    pa.features.set_enabled("ai_chat", True)
    chat.provider_factory = lambda *a, **k: _Instant(error="Der API-Key wurde abgelehnt. Bitte prüfen.")
    chat.send("Hallo?")
    wait_answer(chat)
    assert "abgelehnt" in pa.bubble.text.text() and chat.conversation.messages == []


def test_pause_mode_turns_chat_off_and_drops_pending_answer(pa):
    chat = pa.features.get("ai_chat")
    chat.keys.set("anthropic", KEY)
    pa.settings.set("ai.provider", "anthropic")
    pa.features.set_enabled("ai_chat", True)
    chat.provider_factory = lambda *a, **k: _Instant()
    chat.send("Hallo")
    pa.toggle_pause()
    wait_answer(chat, 300)
    spin(100)
    assert not pa.bubble.isVisible()
    chat.open_input()
    assert chat.input is None or not chat.input.isVisible()


def test_copilot_action_opens_chat_and_alt_means_voice(pa, monkeypatch):
    chat = pa.features.get("ai_chat")
    chat.keys.set("anthropic", KEY)
    pa.settings.set("ai.provider", "anthropic")
    pa.features.set_enabled("ai_chat", True)
    opened = []
    monkeypatch.setattr(chat, "open_input", lambda voice=False: opened.append(voice))
    cop = pa.features.get("copilot_key")
    pa.settings.set("general.copilot_key", True)
    pa.settings.set("general.copilot_action", "settings")
    cop.trigger(alt=True)                     # Alt + Copilot → Spracheingabe, egal welche Aktion
    pa.settings.set("general.copilot_action", "ai_chat")
    cop.trigger(alt=False)
    assert opened == [True, False]
    assert ("ai_chat", ) == tuple(n for n, _ in chat.hotkeys())[:1]


def test_key_never_in_settings_or_log(pa, tmp_path, caplog):
    from desktop_pets.ui.settings_dialog import SettingsDialog

    caplog.set_level(logging.DEBUG)
    dlg = SettingsDialog(pa)
    dlg.open_fresh("KI")
    tab = dlg.ai_tab
    assert dlg.tabs.tabText(dlg.tabs.currentIndex()) == "KI"
    assert not tab.cb_enabled.isEnabled()
    tab.combo.setCurrentIndex(tab.combo.findData("auto"))
    tab.key.setText(KEY)
    assert "Anthropic" in tab.status.text()
    tab._save_key()
    chat = pa.features.get("ai_chat")
    assert chat.keys.get("anthropic") == KEY and chat.enabled
    assert pa.settings.get("ai.provider") == "anthropic"
    assert tab.combo.currentData() == "anthropic" and "GEHEIM" not in tab.key.placeholderText()
    pa.settings.save()
    assert "GEHEIM" not in (tmp_path / "settings.json").read_text(encoding="utf-8")
    assert "GEHEIM" not in json.dumps(pa.settings.data)
    assert "GEHEIM" not in caplog.text
    tab._delete_key()
    assert not chat.keys.has("anthropic") and not chat.enabled
    dlg.close()


def test_unknown_key_needs_manual_choice(pa):
    from desktop_pets.ui.settings_dialog import SettingsDialog

    dlg = SettingsDialog(pa)
    dlg.open_fresh("KI")
    tab = dlg.ai_tab
    tab.combo.setCurrentIndex(tab.combo.findData("auto"))
    tab.key.setText("mistral-ohne-praefix")
    tab._save_key()
    assert "nicht erkannt" in tab.status.text() and not pa.features.get("ai_chat").keys.has("mistral")
    tab.combo.setCurrentIndex(tab.combo.findData("mistral"))
    tab._save_key()
    assert pa.features.get("ai_chat").keys.has("mistral")
    dlg.close()


def test_personality_is_editable_per_pet(pa):
    chat = pa.features.get("ai_chat")
    assert chat.personality() == pa.pack.prompt
    pa.settings.set(f"ai.personality.{pa.pack.id}", "Du bist sehr höflich.")
    assert chat.personality() == "Du bist sehr höflich."
