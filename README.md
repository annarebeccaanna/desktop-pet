# Desktop Pets

Ein Pixeltier (Katze, Hund, Drache, Axolotl) lebt auf deinem Windows-Desktop. Es ist verspielt, stört aber nie: Klicks gehen durch transparente Bereiche hindurch, jede Funktion lässt sich abschalten, und ein Tastendruck (`Strg + Alt + P`) schaltet in den **Pause-Modus** für Bildschirmfreigaben.

Look: **Retro** – XP-Dialoge × klassisches Paint, alle Grafiken, Sounds und Pixel-Art selbst erstellt.

Zielplattform: Windows 10 (ab 2004) und Windows 11. Unter Linux/macOS startet die App auch (zum Entwickeln), aber ohne Windows-Funktionen wie globale Hotkeys, Capture-Ausschluss oder Fenster-Klettern.

## Starten

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m desktop_pets
```

Das Tier erscheint unten rechts über der Taskleiste, das Tray-Icon zeigt seinen Kopf.

* **Rechtsklick aufs Tier:** Füttern, Streicheln, Schlafen schicken, Pause-Modus, Einstellungen
* **Rechtsklick aufs Tray-Icon:** Pause-Modus, Tier wählen, Füttern, Tier zu mir rufen, Ins Körbchen schicken, Einstellungen, Beenden
* **Doppelklick aufs Tray-Icon:** Pause-Modus umschalten
* **Ziehen:** Tier oder Körbchen mit der Maus verschieben
* **Streicheln:** Maus über dem Tier hin- und herbewegen

| Aktion | Hotkey |
|---|---|
| Pause-Modus umschalten | `Strg + Alt + P` |
| Tier ein-/ausblenden | `Strg + Alt + H` |

Alle Tastenkürzel lassen sich im Einstellungsdialog ändern.

## Als .exe bauen

```bat
pip install -r requirements-dev.txt
pyinstaller desktop_pets.spec
```

Ergebnis: `dist\DesktopPets.exe` (eine Datei, läuft ohne installiertes Python).

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Die Logik (Zustandsautomat, Physik, Bedürfnisse, Einstellungen, Modi, Hotkey-Parser, Fensterkanten) ist GUI-unabhängig und wird direkt getestet. Ein Smoke-Test startet die echte App ohne Bildschirm (`QT_QPA_PLATFORM=offscreen`).

## Eigene Tiere

Ein neues Tier ist ein Ordner mit `pet.json` und `sprites.png` – ohne Codeänderung:

```
pets/hamster/
├── pet.json      # Name, Framegröße, Animationen (Zeile/Frames/fps), Palette, Futter
├── sprites.png   # eine Zeile pro Animation, eine Spalte pro Frame
├── icon.png      # optional: 16×16 Kopf
├── bed.png       # optional: Körbchen
├── bowl.png      # optional: Napf
└── food.png      # optional: Futter
```

Ablegen in `desktop_pets/pets/` oder in `%APPDATA%\DesktopPets\pets\`. Fehlt eine Animation, spielt das Tier `idle`. Die vier Start-Tiere erzeugt `python tools/make_sprites.py` (Pillow nötig), die 8-Bit-Sounds `python tools/make_sounds.py`.

## Daten & Datenschutz

* Einstellungen: `%APPDATA%\DesktopPets\settings.json`
* Protokoll: `%APPDATA%\DesktopPets\log.txt`
* Ohne ausdrückliche Aktivierung verlässt nichts den Rechner. API-Keys (ab Phase 5) landen nie in der JSON oder im Log.

## Aufbau

```
desktop_pets/
├── main.py            Einstieg
├── core/              app (Steuerung, Takt), platforms, settings, events, modes, sound, paths, log
├── pet/               pet_window, animator, brain, needs, physics, pack, sprites, recolor
├── features/          eine Datei je Funktion – mit ihrer ganzen Logik, ihren Fenstern und Menüeinträgen
│                      (base.Feature: behaviours, contribute, on_brain_event, menu_actions …)
├── win/               capture, hotkeys, idle, windows_enum, zorder, dwm, autostart
├── ui/                tray, settings_dialog, speech_bubble, retro (Titelleiste usw.), theme, about
├── themes/            retro_xp.qss + retro_xp.json
├── assets/            Pixelschrift (Silkscreen, OFL), Sounds, UI-Grafiken
├── pets/              cat, dog, dragon, axolotl
└── tests/
tools/                 make_sprites.py, make_sounds.py
```

Die vollständige Spezifikation steht in [`SPEC.md`](SPEC.md), der Stand der Umsetzung in [`CHANGELOG.md`](CHANGELOG.md).

## Lizenz

Code: MIT (siehe `LICENSE`). Pixelschrift „Silkscreen“: SIL Open Font License 1.1 (`desktop_pets/assets/fonts/Silkscreen-OFL.txt`).
