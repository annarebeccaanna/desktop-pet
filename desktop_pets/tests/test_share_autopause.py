"""Automatische Pause bei Bildschirmfreigabe."""

import json
import os

import pytest

from desktop_pets.core.events import EventBus
from desktop_pets.core.modes import ModeManager
from desktop_pets.core.settings import Settings
from desktop_pets.win.share_detect import ShareDetector, WindowInfo, find_sharing, load_rules, parse_rules

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

TEAMS_MAIN = WindowInfo("Chat | Kundenprojekt | Microsoft Teams", "TeamsWebView", "ms-teams.exe")
TEAMS_BAR = WindowInfo("Freigabesteuerleiste | Microsoft Teams", "TeamsWebView", "ms-teams.exe")
MEET_TAB = WindowInfo("Meet – abc-defg-hij - Google Chrome", "Chrome_WidgetWin_1", "chrome.exe")
MEET_BAR = WindowInfo("meet.google.com teilt Ihren Bildschirm.", "Chrome_WidgetWin_1", "chrome.exe")
CHROME_EN = WindowInfo("meet.google.com is sharing your screen.", "Chrome_WidgetWin_1", "chrome.exe")
ZOOM_BAR = WindowInfo("", "ZPFloatToolbarClass", "zoom.exe")
NOTEPAD = WindowInfo("Freigabe beenden – Notizen.txt - Editor", "Notepad", "notepad.exe")


# ---------- Regeln ----------
def test_builtin_rules_recognise_share_bars_but_not_normal_windows():
    rules = load_rules()
    hits = dict((w.title or w.class_name, app) for app, w in
                find_sharing([TEAMS_MAIN, TEAMS_BAR, MEET_TAB, MEET_BAR, CHROME_EN, ZOOM_BAR, NOTEPAD], rules))
    assert hits == {
        "Freigabesteuerleiste | Microsoft Teams": "Microsoft Teams",
        "meet.google.com teilt Ihren Bildschirm.": "Browser (Meet, Teams im Browser, Jitsi …)",
        "meet.google.com is sharing your screen.": "Browser (Meet, Teams im Browser, Jitsi …)",
        "ZPFloatToolbarClass": "Zoom",
    }


def test_user_rules_are_added_and_broken_ones_skipped(tmp_path):
    user = tmp_path / "share_signatures.json"
    user.write_text(json.dumps({"rules": [
        {"app": "Mein Tool", "process": "tool.exe", "title": "(?i)live"},
        {"app": "Kaputt", "title": "(unclosed"},
    ]}), encoding="utf-8")
    rules = load_rules(user)
    assert any(r.app == "Mein Tool" for r in rules) and not any(r.app == "Kaputt" for r in rules)
    assert find_sharing([WindowInfo("LIVE", "X", "tool.exe")], rules)[0][0] == "Mein Tool"


def test_empty_rule_matches_nothing():
    assert find_sharing([NOTEPAD], parse_rules([{"app": "leer"}])) == []


# ---------- Automatik ----------
class Ctx:
    def __init__(self, tmp_path):
        self.bus = EventBus()
        self.settings = Settings(tmp_path / "s.json", self.bus)
        self.modes = ModeManager(self.bus)
        self.app = None


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("DESKTOP_PETS_HOME", str(tmp_path / "home"))
    import desktop_pets.features  # noqa: F401
    from desktop_pets.features.manager import FeatureManager
    from desktop_pets.features.share_autopause import ShareAutoPause

    ctx = Ctx(tmp_path)
    fm = FeatureManager(ctx, {"share_autopause": ShareAutoPause})
    fm.start()
    feature = fm.get("share_autopause")
    screen = {"windows": []}
    feature.detector.lister = lambda: screen["windows"]
    return ctx, fm, feature, screen


def tick(feature):
    feature.tick(5.0)


def test_off_by_default_and_bound_to_pause_setting(setup):
    ctx, fm, feature, screen = setup
    assert not feature.enabled
    ctx.settings.set("pause.auto_detect", True)
    assert feature.enabled
    assert fm.by_category() == [] and fm.counts() == (0, 0)   # nicht in der Funktionsliste


def test_share_starts_and_ends_pause(setup):
    ctx, fm, feature, screen = setup
    ctx.settings.set("pause.auto_detect", True)
    screen["windows"] = [TEAMS_MAIN, TEAMS_BAR]
    tick(feature)
    assert ctx.modes.paused and feature.sharing_app == "Microsoft Teams"
    screen["windows"] = [TEAMS_MAIN]
    tick(feature)
    assert not ctx.modes.paused


def test_manual_pause_before_share_is_kept(setup):
    ctx, fm, feature, screen = setup
    ctx.settings.set("pause.auto_detect", True)
    ctx.modes.set_paused(True)
    screen["windows"] = [MEET_BAR]
    tick(feature)
    screen["windows"] = []
    tick(feature)
    assert ctx.modes.paused          # war schon vorher pausiert → bleibt so


def test_manual_unpause_during_share_wins_until_next_share(setup):
    ctx, fm, feature, screen = setup
    ctx.settings.set("pause.auto_detect", True)
    screen["windows"] = [ZOOM_BAR]
    tick(feature)
    assert ctx.modes.paused
    ctx.modes.set_paused(False)      # Benutzer überstimmt
    tick(feature)
    assert not ctx.modes.paused      # bleibt aus, obwohl noch geteilt wird
    screen["windows"] = []
    tick(feature)
    screen["windows"] = [ZOOM_BAR]   # nächste Freigabe
    tick(feature)
    assert ctx.modes.paused


def test_switching_off_releases_automatic_pause(setup):
    ctx, fm, feature, screen = setup
    ctx.settings.set("pause.auto_detect", True)
    screen["windows"] = [TEAMS_BAR]
    tick(feature)
    ctx.settings.set("pause.auto_detect", False)
    assert not feature.enabled and not ctx.modes.paused


def test_detector_errors_never_break_the_app():
    def broken():
        raise OSError("weg")

    assert ShareDetector(lister=broken).check() == []


# ---------- Testfenster ----------
def test_share_test_dialog_lists_and_marks_windows(tmp_path):
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from desktop_pets.core.app import PetApp
    from desktop_pets.ui.share_test import ShareTestDialog

    pa = PetApp(qapp, settings_path=tmp_path / "settings.json")
    pa.qapp.quit = lambda: None
    pa.start()
    pa.features.get("share_autopause").detector.lister = lambda: [TEAMS_MAIN, TEAMS_BAR, NOTEPAD]
    dlg = ShareTestDialog(pa)
    assert dlg.table.rowCount() == 2                 # nur Meeting-Programme/Browser, kein Editor
    assert "MICROSOFT TEAMS" in dlg.status.text()
    assert dlg.table.item(1, 2).text().startswith("✓")
    dlg.close()
    pa.quit()
