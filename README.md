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
| Pomodoro starten/stoppen | `Strg + Alt + T` (wenn Pomodoro eingeschaltet ist) |
| Diktieren (einfügen, wo du schreibst) | `Strg + Alt + D` |
| Text-Werkzeuge für markierten Text | `Strg + Alt + M` oder Copilot-Taste (mit Markierung) |
| KI-Chat öffnen | `Strg + Alt + K` oder Copilot-Taste |
| KI-Chat mit Spracheingabe | `Strg + Alt + Umschalt + K` oder Alt + Copilot-Taste |
| Sachliche Frage (ohne Tier-Rolle) | `Strg + Alt + E` oder Strg + Copilot-Taste |
| Sachliche Frage per Sprache | `Strg + Alt + Umschalt + E` oder Strg + Alt + Copilot-Taste |

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

Ablegen in `desktop_pets/pets/` oder in `%APPDATA%\DesktopPets\pets\`. Fehlt eine Animation, spielt das Tier `idle`.

### Tiere zeichnen und ändern (Text-Sprites)

Die Pixel-Art der Start-Tiere liegt als Textdateien in `pets/<id>/art/` – eine Datei je Animation, ein Zeichen je Pixel. Du kannst sie direkt in VS Code bearbeiten:

```
# Katze – Fortbewegung: läuft (Seitenansicht, Blick nach rechts; nach links wird gespiegelt)
@durations 130 130 130 130        ← Dauer je Bild in ms

................
..........K...K.
.K.......KPK.KPK                  ← K = Umriss, O = Fell, P = Akzent …
…
```

* `palette.txt` legt fest, welches Zeichen welche Farbe ist (`primary`/`secondary` lassen sich in der App umfärben).
* Bilder in einer Datei sind durch Leerzeilen getrennt; `@loop false` für Einmal-Animationen.
* Seitenansichten (`move`, `move_fast`, `jump`, `fall`) blicken nach rechts, Sitzen/Fressen/Freuen sind von vorn.
* Ein neues Tier braucht nur diese Dateien – wie es sich bewegt (laufen, fliegen, schwimmen …), zeigen allein die Bilder.
* Danach `python tools/make_sprites.py` ausführen (Pillow nötig) – das erzeugt `sprites.png`, `icon.png` usw. und aktualisiert die Animationsliste in `pet.json`. Ein Test prüft, dass beides zusammenpasst.

Animationen je Tier (alle Tiere haben dieselben Dateien): `idle`, `move` (Fortbewegung – Katze/Hund laufen, Drache fliegt, Axolotl schwimmt), `move_fast`, `sit`, `sleep`, `groom`, `jump`, `fall`, `happy`, `angry`, `eat` · Übergänge `sit_down`, `stand_up`, `land`, `wake` · ab und zu `yawn`, `fidget`, `special` (Signatur: Katze Schwanz, Hund Wedeln & Hecheln, Drache Flügel & Rauch, Axolotl Kiemen & Schweben). Die 8-Bit-Sounds erzeugt `python tools/make_sounds.py`.

## Pause bei Bildschirmfreigabe (experimentell)

Unter Einstellungen → **Pause & Freigabe** lässt sich die Pause automatisch starten, sobald eine Freigabe erkannt wird. Erkannt werden die Freigabe-Leisten von Teams, Zoom, Webex und den gängigen Browsern. „Erkennung testen …“ zeigt live, was erkannt wird. Eigene Regeln (Programm, Fensterklasse, Titel als regulärer Ausdruck) kommen in `%APPDATA%\DesktopPets\share_signatures.json`.

## KI-Chat

Unter Einstellungen → **KI** einen API-Key einfügen (ChatGPT, Claude, OneAI, Gemini, Mistral, OpenRouter, Groq, xAI oder ein eigener OpenAI-kompatibler Endpunkt wie Ollama). Der Anbieter wird am Key erkannt, sonst wählt man ihn aus. „Verbindung testen“ prüft Key und Modell, ohne etwas zu kosten.

Dann öffnet die Copilot-Taste (Häkchen „Copilot-Taste öffnet den Chat“) oder `Strg + Alt + K` eine Sprechblase am Tier: Frage eintippen, Enter – die Antwort kommt als Sprechblase. **Alt + Copilot** (oder `Strg + Alt + Umschalt + K`) startet zusätzlich die Windows-Spracheingabe; sobald man aufhört zu sprechen, geht die Frage ab.

oneAI: Key aus den Hub-Einstellungen einfügen (`oai_…` oder `oai-gk_…`), fertig – Standard-Adresse ist `https://hub.oneai.eu`. Eine eigene Instanz kommt im Tab KI unter „Erweitert“ oder fest in `desktop_pets/features/ai/providers/oneai.json`.

## Daten & Datenschutz

* Einstellungen: `%APPDATA%\DesktopPets\settings.json`
* Protokoll: `%APPDATA%\DesktopPets\log.txt`
* Ohne ausdrückliche Aktivierung verlässt nichts den Rechner. API-Keys liegen im Windows-Anmeldeinformationsspeicher (Credential Manager), nie in der JSON oder im Log.
* KI-Chat: Gesendet wird nur, was man eintippt oder sagt – nie Fenstertitel oder Screenshots. Der Verlauf bleibt nur im Speicher (nach 15 Minuten Ruhe vergessen), im Pause-Modus ist der Chat aus.

## Aufbau

```
desktop_pets/
├── main.py            Einstieg
├── core/              app (Steuerung, Takt), platforms, settings, events, modes, sound, paths, log
├── pet/               pet_window, animator, choreo (Übergänge), brain, needs, physics, pack,
│                      sprites, textsprites, recolor
├── features/          eine Datei je Funktion – mit ihrer ganzen Logik, ihren Fenstern und Menüeinträgen
│   │                  (base.Feature: behaviours, contribute, on_brain_event, menu_actions …)
│   └── ai/            KI-Chat: providers/ (je Anbieter eine Datei), detect, keys, chat
├── win/               capture, hotkeys, keyhook, input, idle, windows_enum, zorder, dwm, autostart
├── ui/                tray, settings_dialog, ai_tab, chat_input, speech_bubble, retro, theme, about
├── themes/            retro_xp.qss + retro_xp.json
├── assets/            Pixelschrift (Silkscreen, OFL), Sounds, UI-Grafiken
├── pets/              cat, dog, dragon, axolotl (je art/*.txt = Pixel-Art als Text)
└── tests/
tools/                 make_sprites.py (Text-Sprites → PNG), make_sounds.py
```

Die vollständige Spezifikation steht in [`SPEC.md`](SPEC.md), der Stand der Umsetzung in [`CHANGELOG.md`](CHANGELOG.md).

## Lizenz

Code: MIT (siehe `LICENSE`). Pixelschrift „Silkscreen“: SIL Open Font License 1.1 (`desktop_pets/assets/fonts/Silkscreen-OFL.txt`).
