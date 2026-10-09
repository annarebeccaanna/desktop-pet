"""Tiergeräusche und Hinweistöne getrennt ein-/ausschaltbar."""

import json
import os

import pytest

from desktop_pets.core.settings import SCHEMA_VERSION, Settings
from desktop_pets.core.sound import SoundPlayer

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_defaults_both_on(tmp_path):
    s = Settings(tmp_path / "s.json").load()
    assert s.get("general.pet_sounds") is True and s.get("general.notice_sounds") is True


@pytest.mark.parametrize("muted", [True, False])
def test_old_mute_setting_is_migrated(tmp_path, muted):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"version": 2, "general": {"muted": muted, "volume": 40}}), encoding="utf-8")
    s = Settings(path).load()
    assert s.get("version") == SCHEMA_VERSION
    assert s.get("general.pet_sounds") is (not muted) and s.get("general.notice_sounds") is (not muted)
    assert s.get("general.muted") is None and s.get("general.volume") == 40


def test_sound_kinds_are_gated_separately():
    p = SoundPlayer()
    p.configure(70, pet_sounds=False, notice_sounds=True)
    assert not p.allowed("pet") and p.allowed("notice")
    p.configure(70, pet_sounds=True, notice_sounds=False)
    assert p.allowed("pet") and not p.allowed("notice")
    p.blocked = True                     # Pause-Modus: alles still
    assert not p.allowed("pet") and not p.allowed("notice")
    p.blocked = False
    p.configure(0, True, True)           # Lautstärke 0
    assert not p.allowed("pet")


def test_pet_sounds_off_keeps_notice_sounds(tmp_path, monkeypatch):
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from desktop_pets.core.app import PetApp

    pa = PetApp(qapp, settings_path=tmp_path / "settings.json")
    pa.qapp.quit = lambda: None
    pa.start()
    played = []
    monkeypatch.setattr(pa.sound, "_available", True)

    def fake_play(filename, pack_dir=None, kind="pet", force=False):
        if pa.sound.allowed(kind) or force:
            played.append((filename, kind))

    monkeypatch.setattr(pa.sound, "play", fake_play)
    pa.open_settings()
    dlg = pa._settings_dialog
    dlg.cb_pet_sounds.setChecked(False)              # im Dialog ausschalten
    assert pa.settings.get("general.pet_sounds") is False and not pa.sound.pet_sounds
    pa.pet_pet()                                     # Streicheln → kein Schnurren
    pa.features.set_enabled("pomodoro", True)
    pomo = pa.features.get("pomodoro")
    pomo.start()
    pomo.timer.ends_at = 0
    pomo.tick(0.1)                                   # Pling ist ein Hinweiston → kommt
    assert played == [("pling.wav", "notice")]
    dlg.close()
    pa.quit()
