# Desktop Pets

Ein kleines Pixeltier, das auf deinem Windows-Desktop wohnt. Es streunt herum, jagt deinen Mauszeiger, schläft in seinem Körbchen und erinnert dich an Pausen. Optik: irgendwo zwischen Windows XP und dem alten Paint.

<img width="75" height="auto" alt="Baustein Pixeltier" src="https://github.com/user-attachments/assets/e50b7267-5e04-4c5a-a6e7-0fde1a2dd173" />

## Funktionen

**Ein Tier mit Persönlichkeit**

- Läuft herum, putzt sich, gähnt, klettert auf Fensterkanten
- Jagt den Mauszeiger, lässt sich streicheln und füttern
- Hat Hunger, Laune und Energie und schläft in seinem eigenen Körbchen
- Vier Tiere zur Auswahl: Katze, Hund, Drache, Axolotl, jeweils umfärbbar wie in Paint
<img width="500" height="auto" alt="Die vier Start-Tiere" src="https://github.com/user-attachments/assets/4bf6607d-46be-42fc-b223-130bcf1095d2" />

**Nützlich im Arbeitsalltag**

- Pomodoro-Timer, Trink- und Bewegungserinnerungen
- Reagiert auf Kalendertermine und auf Build- oder Testergebnisse

**Kundentermin-tauglich**

- Pause-Modus per Tastenkürzel: Das Tier legt sich hinter alle Fenster und döst
- Für Bildschirmfreigaben in Teams, Zoom & Co. unsichtbar

**Alles abschaltbar**

- Jede Funktion hat einen eigenen Schalter
- Störende Funktionen sind standardmäßig aus
- Ohne ausdrückliche Aktivierung verlässt nichts den Rechner
<img width="250" height="auto" alt="Einstellungen, Tab „Funktionen“" src="https://github.com/user-attachments/assets/865f8499-fba7-4e44-a924-5b224d37b576" />
<img width="250" height="auto" alt="Einstellungen, Tab „Tiere“ (Mini-Paint)" src="https://github.com/user-attachments/assets/b51976cb-8e09-491d-91dc-2417a15808e1" />
<img width="250" height="auto" alt="Einstellungen, Tab „Pause   Freigabe“" src="https://github.com/user-attachments/assets/4185ee0f-efd0-405e-9df7-363260322136" />

--------------
<img width="500" height="auto" alt="Desktop im Normalmodus mit Rechtsklick-Menü" src="https://github.com/user-attachments/assets/ab80763b-7dd3-4d2d-a9c7-f753bd765034" />
<img width="500" height="auto" alt="Desktop im Pause-Modus mit Tray-Menü" src="https://github.com/user-attachments/assets/546bf3c0-8d09-49d6-8497-6ba55387f9ec" />


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
├── core/              app (Steuerung), settings, events, modes, sound, paths, log
├── pet/               pet_window, animator, brain, needs, physics, pack, sprites, recolor
├── features/          eine Datei je Funktion (base.Feature + Registry)
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
