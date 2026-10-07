import logging

import pytest

from desktop_pets.core.events import EventBus
from desktop_pets.core.log import _RedactFilter
from desktop_pets.core.modes import ModeManager
from desktop_pets.core.settings import Settings
from desktop_pets.features.base import Feature
from desktop_pets.features.manager import FeatureManager
from desktop_pets.win import capture
from desktop_pets.win.hotkeys import (
    MOD_ALT, MOD_CONTROL, MOD_SHIFT, HotkeyError, format_hotkey, parse_hotkey, to_settings,
)
from desktop_pets.win.windows_enum import WinRect, visible_top_edges


# ---------- Hotkeys ----------
@pytest.mark.parametrize("text,mods,vk", [
    ("Ctrl+Alt+P", MOD_CONTROL | MOD_ALT, ord("P")),
    ("Strg + Alt + P", MOD_CONTROL | MOD_ALT, ord("P")),
    ("ctrl+shift+f9", MOD_CONTROL | MOD_SHIFT, 0x78),
    ("Alt+Space", MOD_ALT, 0x20),
    ("Ctrl+Alt+7", MOD_CONTROL | MOD_ALT, ord("7")),
])
def test_parse_hotkey(text, mods, vk):
    assert parse_hotkey(text) == (mods, vk)


@pytest.mark.parametrize("text", ["", "P", "Ctrl+Alt", "Ctrl+P+Q", "Ctrl+Gibtsnicht"])
def test_parse_hotkey_rejects(text):
    with pytest.raises(HotkeyError):
        parse_hotkey(text)


def test_hotkey_formatting():
    assert format_hotkey("ctrl+alt+p") == "Strg + Alt + P"
    assert to_settings("Strg + Alt + P") == "Ctrl+Alt+P"


# ---------- Fensterkanten ----------
def test_visible_top_edges_cut_by_windows_above():
    top = WinRect(1, 300, 100, 500, 400)        # verdeckt die Mitte der Kante darunter
    below = WinRect(2, 100, 200, 800, 600)
    edges = visible_top_edges([top, below])
    ids = {e.id: (e.left, e.right, e.y) for e in edges}
    assert ids["win:1:0"] == (300, 500, 100)
    assert ids["win:2:0"] == (100, 300, 200)
    assert ids["win:2:1"] == (500, 800, 200)


def test_fully_covered_edge_disappears():
    edges = visible_top_edges([WinRect(1, 0, 0, 1000, 900), WinRect(2, 100, 200, 800, 600)])
    assert [e.id for e in edges] == ["win:1:0"]


def test_capture_not_supported_off_windows():
    import sys

    if sys.platform != "win32":
        assert capture.is_supported() is False
        assert capture.set_excluded(123, True) is False


# ---------- Log ----------
def test_log_redacts_api_keys():
    rec = logging.LogRecord("x", logging.INFO, "f", 1, "Key ist %s", ("sk-ant-abcdefghijklmnop",), None)
    _RedactFilter().filter(rec)
    assert "sk-ant" not in rec.getMessage()


# ---------- Funktionen ----------
class Ctx:
    def __init__(self, tmp_path):
        self.bus = EventBus()
        self.settings = Settings(tmp_path / "s.json", self.bus)
        self.modes = ModeManager(self.bus)
        self.app = None


class Good(Feature):
    id = "good"
    name = "Gut"
    default_enabled = True

    def enable(self):
        self.started = True

    def tick(self, dt):
        self.ticks = getattr(self, "ticks", 0) + 1


class Crashy(Feature):
    id = "crashy"
    name = "Kaputt"
    default_enabled = True

    def tick(self, dt):
        raise RuntimeError("boom")


class OffByDefault(Feature):
    id = "chaos"
    name = "Chaos"
    category = "chaos"
    default_enabled = False


class PauseOk(Feature):
    id = "pause_ok"
    name = "Darf in Pause"
    default_enabled = True
    allowed_in_pause = True


def make_manager(tmp_path):
    ctx = Ctx(tmp_path)
    reg = {c.id: c for c in (Good, Crashy, OffByDefault, PauseOk)}
    return ctx, FeatureManager(ctx, reg)


def test_defaults_and_crash_isolation(tmp_path):
    ctx, fm = make_manager(tmp_path)
    fm.start()
    assert fm.is_enabled("good") and fm.is_enabled("crashy") and not fm.is_enabled("chaos")
    fm.tick(0.03)
    fm.tick(0.03)
    assert not fm.is_enabled("crashy")            # nur diese Funktion ist aus
    assert "crashy" in fm.failed
    assert fm.get("good").ticks == 2              # die anderen laufen weiter


def test_toggle_persists_and_survives_restart(tmp_path):
    ctx, fm = make_manager(tmp_path)
    fm.start()
    fm.set_enabled("chaos", True)
    fm.set_enabled("good", False)
    ctx2 = Ctx(tmp_path)
    ctx2.settings.load()
    fm2 = FeatureManager(ctx2, {c.id: c for c in (Good, Crashy, OffByDefault, PauseOk)})
    fm2.start()
    assert fm2.is_enabled("chaos") and not fm2.is_enabled("good")


def test_active_respects_pause(tmp_path):
    ctx, fm = make_manager(tmp_path)
    fm.start()
    ctx.modes.set_paused(True)
    active = fm.active_ids()
    assert "pause_ok" in active and "good" not in active


def test_real_registry_chaos_is_off_by_default():
    import desktop_pets.features  # noqa: F401
    from desktop_pets.features.base import REGISTRY

    for fid in ("gifts", "icon_shuffle", "cursor_steal"):
        assert REGISTRY[fid].default_enabled is False
    for fid in ("wander", "mouse_chase", "idle_sleep", "petting"):
        assert REGISTRY[fid].default_enabled is True and REGISTRY[fid].available
