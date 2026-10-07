import json

import pytest

from desktop_pets.core.events import MODE_CHANGED, NOTIFY, SETTINGS_CHANGED, EventBus
from desktop_pets.core.modes import Mode, ModeManager
from desktop_pets.core.settings import DEFAULTS, SCHEMA_VERSION, Settings, migrate


# ---------- EventBus ----------
def test_bus_delivers_and_unsubscribes():
    bus = EventBus()
    got = []
    unsub = bus.subscribe("x", lambda **kw: got.append(kw))
    bus.publish("x", a=1)
    unsub()
    bus.publish("x", a=2)
    assert got == [{"a": 1}]


def test_bus_survives_broken_handler():
    bus = EventBus()
    got = []

    def broken(**_):
        raise RuntimeError("kaputt")

    bus.subscribe("x", broken)
    bus.subscribe("x", lambda **kw: got.append(kw))
    bus.publish("x", v=3)
    assert got == [{"v": 3}]


# ---------- Settings ----------
def test_defaults_without_file(tmp_path):
    s = Settings(tmp_path / "settings.json").load()
    assert s.get("hotkeys.toggle_pause") == "Ctrl+Alt+P"
    assert s.get("pause.exclude_from_capture") is True
    assert s.get("does.not.exist", 42) == 42


def test_set_persists_and_publishes(tmp_path):
    bus = EventBus()
    seen = []
    bus.subscribe(SETTINGS_CHANGED, lambda key, value: seen.append((key, value)))
    path = tmp_path / "settings.json"
    s = Settings(path, bus).load()
    s.set("pet.size", 3)
    s.set_feature_enabled("gifts", True)
    assert seen == [("pet.size", 3), ("features.gifts", True)]
    again = Settings(path).load()
    assert again.get("pet.size") == 3
    assert again.feature_enabled("gifts", False) is True
    assert again.feature_enabled("wander", True) is True  # Default, wenn nicht gesetzt


def test_set_same_value_is_noop(tmp_path):
    bus = EventBus()
    seen = []
    bus.subscribe(SETTINGS_CHANGED, lambda **kw: seen.append(kw))
    s = Settings(tmp_path / "s.json", bus)
    s.set("pet.size", 2)  # entspricht dem Default
    assert seen == []


def test_secrets_are_rejected(tmp_path):
    s = Settings(tmp_path / "s.json")
    with pytest.raises(ValueError):
        s.set("ai.api_key", "sk-ant-123")
    with pytest.raises(ValueError):
        s.set("ai.anthropic.token", "x")


def test_corrupt_file_falls_back_and_keeps_backup(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ kaputt", encoding="utf-8")
    s = Settings(path).load()
    assert s.get("pet.type") == "cat"
    assert (tmp_path / "settings.json.bak").exists()


def test_migration_from_v1(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"version": 1, "pause": {"hotkey": "Ctrl+Shift+F9"},
                                "pet": {"type": "dog", "name": "Rex"}}), encoding="utf-8")
    s = Settings(path).load()
    assert s.get("version") == SCHEMA_VERSION
    assert s.get("hotkeys.toggle_pause") == "Ctrl+Shift+F9"
    assert s.get("pet.names.dog") == "Rex"
    assert s.get("pause.hotkey") is None
    assert s.get("hotkeys.toggle_visible") == DEFAULTS["hotkeys"]["toggle_visible"]


def test_migrate_is_idempotent_for_current_version():
    data = {"version": SCHEMA_VERSION, "pet": {"type": "cat"}}
    assert migrate(dict(data))["version"] == SCHEMA_VERSION


def test_snapshot_restore_and_reset(tmp_path):
    s = Settings(tmp_path / "s.json")
    snap = s.snapshot()
    s.set("pet.size", 1)
    s.set("state", {"needs": {"hunger": 10}})
    s.restore(snap)
    assert s.get("pet.size") == 2
    s.set("pet.size", 3)
    s.set("state", {"needs": {"hunger": 10}})
    s.reset()
    assert s.get("pet.size") == 2
    assert s.get("state") == {"needs": {"hunger": 10}}  # Gedächtnis bleibt


# ---------- Modi ----------
def test_pause_toggles_and_publishes():
    bus = EventBus()
    seen = []
    bus.subscribe(MODE_CHANGED, lambda mode, previous: seen.append((previous, mode)))
    m = ModeManager(bus)
    assert m.mode == Mode.NORMAL
    m.toggle_pause()
    assert m.paused and m.mode == Mode.PAUSE
    m.toggle_pause()
    assert seen == [(Mode.NORMAL, Mode.PAUSE), (Mode.PAUSE, Mode.NORMAL)]


def test_pause_wins_over_sleep():
    m = ModeManager(EventBus())
    m.set_sleeping(True)
    assert m.mode == Mode.SLEEP
    m.set_paused(True)
    assert m.mode == Mode.PAUSE
    m.set_paused(False)
    assert m.mode == Mode.SLEEP


def test_notifications_are_collected_during_pause():
    bus = EventBus()
    shown = []
    bus.subscribe(NOTIFY, lambda title, text: shown.append((title, text)))
    m = ModeManager(bus)
    assert m.notify("Trinken", "Ein Glas Wasser?") is True
    m.set_paused(True)
    assert m.notify("Pomodoro", "Pause!") is False
    m.notify("Aufstehen", "Kurz strecken", key="stand")
    m.notify("Aufstehen", "Jetzt aber", key="stand")  # ersetzt die vorige
    assert m.pending_count == 2
    assert len(shown) == 1
    m.set_paused(False)
    assert m.pending_count == 0
    assert len(shown) == 2
    title, text = shown[-1]
    assert title == "Während der Pause"
    assert "Pomodoro" in text and "Jetzt aber" in text and "Kurz strecken" not in text


def test_single_queued_notification_is_shown_as_is():
    bus = EventBus()
    shown = []
    bus.subscribe(NOTIFY, lambda title, text: shown.append((title, text)))
    m = ModeManager(bus)
    m.set_paused(True)
    m.notify("Pomodoro", "Pause!")
    m.set_paused(False)
    assert shown == [("Pomodoro", "Pause!")]
