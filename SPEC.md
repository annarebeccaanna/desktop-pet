# Desktop Pets – Konzept & Spezifikation

Ein kleines Windows-Programm, bei dem ein Pixeltier (Katze, Hund, Drache …) auf dem Desktop lebt. Es ist verspielt, aber auch im Arbeitsalltag nützlich, und es lässt sich komplett steuern: Tierauswahl, einzelne Funktionen an/aus und ein Pause-Modus für Bildschirmfreigaben.

Zielplattform zunächst: **Windows 10 (ab 2004) und Windows 11**.

Look: **Retro** – eine Mischung aus Windows XP und dem klassischen Paint, umgesetzt mit eigenen Grafiken und modernem Unterbau (siehe Abschnitt 8).

---

## 1. Leitprinzipien

1. **Nie im Weg.** Das Tier blockiert keine Buttons, Eingabefelder oder Klicks. Durch transparente Bereiche geht jeder Klick durch, nur das Tier selbst ist anklickbar.
2. **Alles abschaltbar.** Jede Funktion hat einen eigenen Schalter. Störende oder „chaotische“ Funktionen sind standardmäßig **aus**.
3. **Kundentauglich.** Ein Tastendruck schaltet in den Pause-Modus. Das Tier ist dann unsichtbar für Bildschirmfreigaben und stört nicht.
4. **Erweiterbar.** Neue Tiere kommen als Ordner mit Sprites und einer JSON-Datei dazu, ohne Codeänderung.
5. **Privat.** Ohne ausdrückliche Aktivierung verlässt nichts den Rechner.

---

## 2. Technik-Stack

| Bereich | Wahl | Begründung |
|---|---|---|
| Sprache | Python 3.12 | Schnell zu entwickeln, gute Windows-Anbindung |
| GUI | **PySide6 (Qt)** | Transparente, rahmenlose Fenster, Tray-Icon, Einstellungsdialoge aus einer Hand |
| Windows-APIs | `ctypes` / `pywin32` | Klick-Durchlässigkeit, Capture-Ausschluss, Idle-Erkennung, Fensterpositionen |
| Globale Hotkeys | Win32 `RegisterHotKey` | Stabil, keine Admin-Rechte nötig |
| Einstellungen | JSON in `%APPDATA%\DesktopPets\settings.json` | Einfach, menschenlesbar |
| Paketierung | PyInstaller → einzelne `.exe` | Läuft ohne installiertes Python |
| Tests | pytest | Logik (Zustandsautomat, Einstellungen, Timer) testbar ohne GUI |

---

## 3. Architektur

```
desktop_pets/
├── main.py                 # Einstieg, startet App, Tray, Hotkeys
├── core/
│   ├── app.py              # Zentrale Steuerung, Event-Bus
│   ├── settings.py         # Laden/Speichern, Defaults, Migration
│   ├── events.py           # Einfacher Publish/Subscribe-Bus
│   └── modes.py            # Normal / Pause / Schlafen (global)
├── pet/
│   ├── pet_window.py       # Transparentes, rahmenloses Fenster
│   ├── animator.py         # Sprite-Sheets abspielen
│   ├── brain.py            # Zustandsautomat (Verhalten)
│   ├── needs.py            # Hunger, Laune, Energie
│   └── physics.py          # Laufen, Springen, Fallen, Fensterkanten
├── features/               # Jede Funktion = ein Modul mit enable()/disable()
│   ├── mouse_chase.py
│   ├── idle_sleep.py
│   ├── pomodoro.py
│   ├── reminders.py        # Trinken, Aufstehen, Lüften
│   ├── calendar_alerts.py
│   ├── event_webhook.py    # Build/Test-Ereignisse von außen
│   ├── system_monitor.py   # CPU, Akku
│   ├── window_walking.py
│   ├── gifts.py
│   ├── icon_shuffle.py
│   ├── cursor_steal.py
│   ├── multi_pet.py
│   ├── bed.py
│   ├── ai_chat.py
│   └── ai/providers/       # anthropic.py, openai.py, gemini.py, mistral.py, openai_compatible.py
├── win/
│   ├── capture.py          # SetWindowDisplayAffinity
│   ├── windows_enum.py     # Sichtbare Fenster + Positionen
│   ├── idle.py             # GetLastInputInfo
│   └── hotkeys.py
├── ui/
│   ├── tray.py             # Tray-Icon + Kontextmenü
│   ├── settings_dialog.py  # Tiere, Feature-Toggles, Hotkeys
│   └── speech_bubble.py    # Sprechblasen
├── themes/                 # retro_xp.qss + retro_xp.json (siehe Abschnitt 8)
├── assets/                 # Pixelschrift (+ Lizenz), 8-Bit-Sounds
├── pets/                   # Tier-Pakete (siehe Abschnitt 6)
│   ├── cat/
│   ├── dog/
│   ├── dragon/
│   └── axolotl/
└── tests/
```

**Feature-Schnittstelle:** Jede Funktion erbt von einer Basisklasse `Feature` mit `id`, `name`, `description`, `default_enabled`, `allowed_in_pause`, `enable()`, `disable()`. Der Einstellungsdialog baut die Toggle-Liste automatisch aus allen registrierten Features. Neue Funktion = neue Datei, kein Umbau.

---

## 4. Modi

### 4.1 Normal
Alles, was aktiviert ist, läuft.

### 4.2 Pause-Modus (Bildschirmfreigabe)
Gedacht für Kundentermine mit Bildschirmfreigabe. Das Tier existiert nur noch ruhig auf dem Desktop.

- **Aktivieren:** Hotkey (Standard `Strg + Alt + P`), Tray-Menü, Doppelklick aufs Tray-Icon.
- **Verhalten:**
  - Das Tierfenster rutscht in der Z-Reihenfolge **ganz nach unten** (hinter alle anderen Fenster). Es ist also nur sichtbar, wenn man den Desktop selbst sieht.
  - Das Tier „chillt“: Es geht in sein Körbchen (falls `bed` aktiv) und schläft dort, sonst liegt oder putzt es sich an einer festen Stelle. Es bewegt sich nicht über den Bildschirm.
  - **Keine** Sounds, Sprechblasen, Benachrichtigungen, Mausjagd oder Chaos-Funktionen.
  - Erinnerungen und Timer laufen intern weiter, melden sich aber erst nach der Pause (gesammelt, als eine dezente Sprechblase).
- **Unsichtbar für Freigaben (Option, standardmäßig an):** `SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)`. Das Tier bleibt für dich sichtbar, taucht aber in Teams/Zoom/OBS-Aufnahmen nicht auf. Kann auf Wunsch auch im Normalmodus dauerhaft aktiv sein.
- **Automatik (optional, Phase 4):** Pause-Modus automatisch einschalten, wenn eine Bildschirmfreigabe erkannt wird (Heuristik über bekannte Prozesse/Fenstertitel von Teams, Zoom, Webex). Muss als „experimentell“ gekennzeichnet sein und manuell überstimmbar bleiben.
- **Tray-Icon** zeigt den Modus an (z. B. kleines „Zzz“ im Icon).

### 4.3 Schlafen (automatisch)
Bei Inaktivität (Standard: 5 Minuten ohne Eingabe) schläft das Tier ein und wacht bei Tastatur- oder Mausaktivität auf.

---

## 5. Funktionen

`Default` = Zustand nach Erstinstallation. `Pause` = darf im Pause-Modus aktiv sein.

### Verhalten & Persönlichkeit
| ID | Funktion | Default | Pause |
|---|---|---|---|
| `wander` | Läuft zufällig herum, sitzt, gähnt, streckt sich, putzt sich | an | nur sitzen/liegen |
| `mouse_chase` | Folgt dem Mauszeiger, „fängt“ ihn, wenn er stillsteht | an | – |
| `idle_sleep` | Schläft bei Inaktivität, wacht beim Tippen auf | an | ja |
| `petting` | Streicheln durch Mausbewegung über dem Tier → Schnurren/Herzchen | an | ja (still) |
| `needs` | Hunger/Laune/Energie, Füttern und Spielen (Ablauf siehe 5.1) | an | pausiert |
| `bed` | Eigenes Körbchen auf dem Desktop als Schlafplatz (siehe 5.2) | an | ja (Tier schläft darin) |
| `window_walking` | Läuft auf Oberkanten von Fenstern, springt von Fenster zu Fenster, fällt, wenn ein Fenster verschwindet | an | – |
| `day_rhythm` | Abends schläfriger, morgens verspielter | an | ja |
| `memory` | Speichert Zustand (Laune, Hunger, letzte Position) zwischen Sitzungen | an | ja |

### Nützlich im Arbeitsalltag
| ID | Funktion | Default | Pause |
|---|---|---|---|
| `pomodoro` | 25/5-Minuten-Timer, Start per Klick; zur Pause legt sich das Tier gähnend mitten auf den Desktop und zeigt eine Sprechblase | aus | Zähler läuft, Meldung verzögert |
| `reminders` | Trinken, Aufstehen, Lüften – Intervalle einstellbar | aus | verzögert |
| `calendar_alerts` | Miaut X Minuten vor Terminen. Quelle: lokales Outlook (COM) **oder** ICS-URL | aus | verzögert |
| `event_webhook` | Lokaler HTTP-Endpunkt `http://127.0.0.1:<port>/event?type=…` (nur localhost). `build_success` → Freudensprung, `build_failed`/`test_failed` → Fauchen. Beispiel: `curl "http://127.0.0.1:47321/event?type=build_failed"` | aus | stumm, nur Animation |
| `system_monitor` | Hohe CPU-Last → hechelt; wenig Akku → wird müde | aus | ja (nur Animation) |

### Chaos & Spaß
| ID | Funktion | Default | Pause |
|---|---|---|---|
| `gifts` | Bringt gelegentlich ein „Geschenk“ (Pixelmaus, Wollknäuel), das per Klick verschwindet | aus | – |
| `icon_shuffle` | Schubst Desktop-Icons ein Stück; Ausgangspositionen werden vorher gespeichert und lassen sich per Menü wiederherstellen | aus | – |
| `cursor_steal` | Schnappt sich kurz den Mauszeiger und setzt ihn 1–2 Sekunden später wieder ab (nie während Tastatureingaben oder gedrückter Maustaste) | aus | – |

**Ausdrücklich ausgeschlossen:** Das Tier legt sich niemals vor Buttons, Fenster-Inhalte oder Eingabefelder, um zu stören.

### Sozial & Erweiterbar
| ID | Funktion | Default | Pause |
|---|---|---|---|
| `multi_pet` | Mehrere Tiere gleichzeitig; sie spielen, jagen sich, streiten gelegentlich | aus | alle liegen |
| `ai_chat` | Chat mit dem Tier über einen KI-Anbieter nach Wahl, mit eigenem API-Key (siehe 5.3). Optional: frecher Kommentar zum aktiven Fenstertitel | aus | **immer aus** |
| `network_visit` | Tier besucht Desktops von Freunden | später (Phase 5) | **immer aus** |
| `tts` | Tier als Text-to-Speech-Werkzeug: liest markierten Text oder Chat-Antworten vor | später, **noch nicht ausgearbeitet** | **immer aus** |

**Datenschutz bei `ai_chat`:** Standardmäßig wird nur der Chattext gesendet. Fenstertitel nur mit eigenem, zusätzlichem Schalter. Niemals Screenshots. Im Pause-Modus komplett deaktiviert, damit keine Kundendaten abfließen.

### 5.1 Füttern & Bedürfnisse (`needs`)
- **Werte:** Hunger, Laune und Energie laufen von 0 bis 100 % und verändern sich langsam über den Tag. Sie stehen in der Statusleiste des Einstellungsdialogs und im Kopf des Rechtsklick-Menüs.
- **Füttern** (Rechtsklick auf das Tier, Tray-Menü oder Tier-Kurzmenü):
  1. Neben dem Körbchen erscheint ein Pixel-Napf (ohne Körbchen direkt neben dem Tier).
  2. Das Tier läuft hin, spielt die Animation `eat` ab und zeigt kurz Herzchen oder ein zufriedenes „Mampf“.
  3. Hunger sinkt deutlich, Laune steigt etwas. Danach putzt es sich oder legt sich hin.
  4. Der leere Napf verschwindet nach einigen Sekunden.
- **Zu oft gefüttert** (mehrmals hintereinander, wenn es satt ist): Das Tier dreht sich weg und schläft ein. Kein Schaden, kein Strafsystem.
- **Länger nicht gefüttert:** Das Tier sitzt neben dem leeren Napf und schaut ab und zu zur Maus. Es quengelt höchstens mit einer kleinen Sprechblase (nie im Pause-Modus) und wird nie „krank“ oder stirbt.
- **Laune** steigt durch Streicheln, Spielen (Mausjagd) und Futter und sinkt langsam, wenn man das Tier lange ignoriert. Gute Laune heißt mehr verspielte Animationen, schlechte Laune heißt mehr Sitzen und Schmollen.
- **Energie** sinkt durch Herumlaufen und füllt sich im Schlaf (im Körbchen schneller).
- Jede Tierart kann eigenes Futter haben (Katze: Fisch, Hund: Knochen, Drache: Paprika, Axolotl: Wurm), festgelegt in `pet.json`.

### 5.2 Körbchen (`bed`)
- Jedes Tier hat ein eigenes Pixel-Bett, das auf dem Desktop liegt: Katze im Korb, Hund im Hundekissen, Drache im Nest, Axolotl im Glas. Die Grafik `bed.png` gehört zum Tier-Paket.
- **Platzierung:** Standardmäßig unten links über der Taskleiste. Per Ziehen frei verschiebbar, die Position wird gespeichert und pro Monitor gemerkt.
- Das Körbchen liegt **immer hinter allen Fenstern** (wie ein Desktop-Icon) und ist für Klicks durchlässig, außer auf der Grafik selbst.
- **Verhalten:** Das Tier geht zum Schlafen ins Körbchen: bei Inaktivität, abends (`day_rhythm`), über „Schlafen schicken“ und im Pause-Modus. Doppelklick auf das Körbchen weckt es auf oder schickt es schlafen.
- Futternapf und Geschenke (`gifts`) landen neben dem Körbchen.
- Mit `bed` aus schläft das Tier dort, wo es gerade ist.

### 5.3 KI-Anbieter & eigener API-Key (`ai_chat`)
**Prinzip: ein Feld.** Im Tab „KI“ gibt es ein einziges Eingabefeld „API-Key“. Der Anbieter wird automatisch erkannt, nur bei Bedarf wählt man ihn selbst.

**Oberfläche (von oben nach unten):**
1. **Anbieter** (Auswahlliste, Standard „Automatisch erkennen“):
   - **OneAI** (steht ganz oben, da im Arbeitsalltag am häufigsten genutzt)
   - Automatisch erkennen
   - Anthropic (Claude)
   - OpenAI
   - Google (Gemini)
   - Mistral
   - OpenRouter
   - Eigener Endpunkt (OpenAI-kompatibel, z. B. lokale Modelle über Ollama oder LM Studio)
2. **API-Key** (maskiert, mit „Einfügen“-Knopf).
3. Statuszeile darunter, z. B. „Erkannt: Anthropic (Claude) ✓“ oder „Anbieter nicht erkannt, bitte auswählen“.
4. **Erweitert** (eingeklappt): Modell (Auswahl oder Freitext), Basis-URL. Klappt automatisch auf, wenn nötig (eigener Endpunkt, nicht erkannter Key).
5. Knopf **„Verbindung testen“** mit klarer Erfolgs- oder Fehlermeldung.

**Automatische Erkennung** nur über das Präfix des Keys, lokal und ohne Netzwerkzugriff:

| Präfix | Anbieter |
|---|---|
| `sk-ant-` | Anthropic |
| `sk-or-` | OpenRouter |
| `sk-proj-`, `sk-` | OpenAI (Prüfung erst nach den spezifischeren `sk-`-Präfixen) |
| `AIza` | Google (Gemini) |
| `gsk_` | Groq |
| `xai-` | xAI |

Der Key wird **nie zum Ausprobieren** an mehrere Anbieter geschickt. Ohne eindeutiges Präfix muss der Anbieter manuell gewählt werden (z. B. Mistral, OneAI).

**OneAI:**
- Eigener Provider `features/ai/providers/oneai.py`, als erster Eintrag der Liste.
- **Offen, vor der Umsetzung zu klären:** Basis-URL, Authentifizierung (Header-Format), API-Format (eigenes oder OpenAI-kompatibel), verfügbare Modelle, ob ein Key-Präfix existiert. Diese Werte kommen in eine Konfigurationsdatei `features/ai/providers/oneai.json`, damit sie ohne Codeänderung angepasst werden können.
- Bis die Angaben vorliegen: OneAI als OpenAI-kompatiblen Endpunkt mit frei eintragbarer Basis-URL behandeln.

- Mehrere Keys können gespeichert sein (einer je Anbieter), einer ist aktiv. Wechsel über die Anbieter-Liste.
- **Technisch:** eine gemeinsame Schnittstelle `AIProvider` (`chat(messages) -> text`, `test_connection()`), je Anbieter ein kleines Modul in `features/ai/providers/`. Ein neuer Anbieter ist eine neue Datei.
- Die **Persönlichkeit** des Tiers (Systemprompt) hängt von der Tierart ab und ist im Einstellungsdialog anpassbar.
- **Keys** liegen im Windows Credential Manager, nie in der JSON und nie im Log. Ohne hinterlegten Key bleibt `ai_chat` ausgegraut.
- Auch `tts` soll später dieselbe Anbieter-Struktur nutzen können (Cloud-Stimme mit eigenem Key oder lokale Windows-Stimme).

---

## 6. Tiere & Sprites

### Tier-Paket
```
pets/cat/
├── pet.json
└── sprites.png
```

`pet.json`:
```json
{
  "id": "cat",
  "name": "Katze",
  "sprite_size": [32, 32],
  "scale": 2,
  "sounds": { "happy": "purr.wav", "angry": "hiss.wav" },
  "personality": { "playfulness": 0.7, "laziness": 0.6 },
  "animations": {
    "idle":    { "row": 0, "frames": 4, "fps": 4 },
    "walk":    { "row": 1, "frames": 6, "fps": 10 },
    "run":     { "row": 2, "frames": 6, "fps": 14 },
    "sit":     { "row": 3, "frames": 2, "fps": 2 },
    "sleep":   { "row": 4, "frames": 2, "fps": 1 },
    "groom":   { "row": 5, "frames": 6, "fps": 6 },
    "jump":    { "row": 6, "frames": 4, "fps": 10 },
    "fall":    { "row": 7, "frames": 2, "fps": 8 },
    "happy":   { "row": 8, "frames": 4, "fps": 8 },
    "angry":   { "row": 9, "frames": 4, "fps": 8 },
    "eat":     { "row": 10, "frames": 4, "fps": 6 }
  }
}
```

- Blickrichtung links/rechts durch horizontales Spiegeln, keine doppelten Sprites.
- Fehlt einer Animation, fällt das Tier auf `idle` zurück.
- Optional im Paket: `bed.png` (Körbchen), `food.png` (Futter), `bowl.png` (Napf). Fehlen sie, werden Standard-Grafiken genutzt.
- **Start-Tiere:** Katze, Hund, Drache, Axolotl.
- Sprites sind **eigene, selbst erstellte Pixel-Art** (z. B. per Skript generiert oder selbst gezeichnet), keine Assets aus bestehenden Spielen oder Programmen.
- Ein kleines Hilfsskript `tools/make_sprites.py` erzeugt Platzhalter-Sprites, damit die App von Anfang an lauffähig ist.

---

## 7. Bedienung

### Tray-Icon (Rechtsklick)
- Pause-Modus ✓
- Tier wählen ▸ (Liste aller Tier-Pakete mit Vorschau)
- Pomodoro starten / stoppen
- Füttern
- Tier zu mir rufen
- Ins Körbchen schicken
- Icons zurücksetzen (wenn `icon_shuffle` an war)
- Einstellungen …
- Beenden

### Rechtsklick auf das Tier
Kurzmenü: Füttern, Streicheln, Pomodoro, Schlafen schicken (geht ins Körbchen), Pause-Modus.

### Rechtsklick auf das Körbchen
Körbchen verschieben, Körbchen ausblenden, Tier hineinschicken.

### Einstellungsdialog
Tabs:
1. **Tiere:** Auswahl mit animierter Vorschau, Größe (1×/2×/3×), Name vergeben, bei `multi_pet` mehrere auswählen.
2. **Funktionen:** Automatisch erzeugte Liste aller Features mit Toggle, Kurzbeschreibung und Zahnrad für Detail-Optionen (Intervalle, Port, Kalenderquelle …). Gruppiert nach den Kategorien aus Abschnitt 5.
3. **Pause & Freigabe:** Hotkey, „Unsichtbar für Bildschirmaufnahmen“ (an/aus), Auto-Erkennung (experimentell).
4. **KI:** Anbieter, API-Key, Modell, Verbindung testen, Persönlichkeit.
5. **Allgemein:** Autostart mit Windows, Lautstärke/stumm, Sprache (Deutsch), Zurücksetzen.

Änderungen wirken sofort, ohne Neustart.

### Standard-Hotkeys
| Aktion | Hotkey |
|---|---|
| Pause-Modus umschalten | `Strg + Alt + P` |
| Tier ein-/ausblenden | `Strg + Alt + H` |
| Pomodoro starten/stoppen | `Strg + Alt + T` |

Alle änderbar.

---

## 8. Visuelles Design: Retro (XP × Paint)

### 8.1 Grundidee
Die Oberfläche soll sich anfühlen wie ein Programm aus der Windows-XP-Zeit, das man mit dem alten Paint gebaut hat: beige Dialoge, blaue Titelleisten mit Verlauf, dicke Buttons, gelbe Hinweis-Ballons und grobe Pixel-Art. Gleichzeitig läuft alles nativ und sauber auf Windows 10/11.

**Wichtig:** Der Stil ist nur *inspiriert*. Es werden **keine** Originalgrafiken, Icons, Logos, Hintergrundbilder, Schriftdateien oder Systemsounds von Microsoft kopiert oder mitgeliefert. Alle Assets sind selbst erstellt.

### 8.2 Umsetzung
- **Theme als Qt-Stylesheet:** `themes/retro_xp.qss` plus Theme-Loader. Alle Farben als Variablen in `themes/retro_xp.json`, damit später weitere Themes möglich sind (z. B. „Klassisch grau“ im Stil von Windows 98/2000).
- **Eigene Fensterrahmen:** Einstellungsdialog und Menüs sind rahmenlos und zeichnen ihre Titelleiste selbst (Verlauf, abgerundete obere Ecken, Minimieren/Schließen-Knöpfe). Dadurch sehen sie auf Windows 10 und 11 identisch aus, unabhängig vom System-Design. Verschieben per Ziehen an der Titelleiste, Schatten per DWM.
- **Windows-11-Ecken abschalten:** Für die Retro-Fenster `DwmSetWindowAttribute(DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_DONOTROUND)`, damit Windows 11 die Ecken nicht modern abrundet.
- **Dark Mode:** Das Retro-Theme ignoriert bewusst den System-Dark-Mode.
- **Kontextmenüs:** Ebenfalls per QSS gestylt (weißer Hintergrund, blaue Markierung, schmaler grauer Rand links für Häkchen).

### 8.3 Farbpalette (XP-Anmutung)
| Element | Farbe |
|---|---|
| Titelleiste Verlauf | `#0A5FE6` → `#3D95FF` (oben heller Glanzstreifen) |
| Titelleiste inaktiv | `#7A96DF` → `#A6BCF0` |
| Dialog-Hintergrund | `#ECE9D8` (Beige) |
| Button | Verlauf `#FFFFFF` → `#E3E1D6`, Rand `#003C74`, Radius 3 px |
| Button Hover | orangefarbener Innenrand `#F8B33A` |
| Schließen-Knopf | Rot `#E2563A` mit weißem X |
| Auswahl/Markierung | `#316AC5`, Text weiß |
| Tab-Leiste | Tabs mit orangefarbener Oberkante beim aktiven Tab |
| Hinweis-Ballon | `#FFFFE1`, Rand `#000000`, abgerundet, Schließen-X oben rechts |
| Primär-Aktion (z. B. „Übernehmen“) | Grün `#3C9A2E` |

### 8.4 Schrift
- UI-Schrift **Tahoma**, 8–9 pt (auf Windows 10/11 vorinstalliert, wird nicht mitgeliefert). Fallback: Segoe UI.
- Sprechblasen und Zähler (Pomodoro) in einer **frei lizenzierten Pixelschrift** (z. B. OFL-Lizenz), die mit der App ausgeliefert wird. Lizenzdatei beilegen.
- Kein ClearType-Weichzeichnen bei der Pixelschrift (Hinting aus, Antialiasing aus).

### 8.5 Paint-Elemente
- **Tab „Tiere“ als Mini-Paint:**
  - Links eine Werkzeugleiste mit kleinen Pixel-Icons (Größe, Spiegeln, Name).
  - In der Mitte eine weiße „Leinwand“ mit der animierten Tiervorschau.
  - Unten die **Farbpalette** (28 Felder, zwei Reihen) wie im klassischen Paint.
- **Fellfarbe ändern (neue Funktion `recolor`, Default an):** Klick auf ein Palettenfeld färbt das Tier per Palettentausch um (Hauptfarbe, Zweitfarbe per Rechtsklick – wie Vorder-/Hintergrundfarbe in Paint). Wird pro Tier gespeichert.
- **Statusleiste** am unteren Dialogrand mit Infos wie „Laune: 😺 gut | Hunger: 40 %“ in Pixelschrift.

### 8.6 Pixel-Art-Stil der Tiere
- Harte Kanten, kein Antialiasing, Skalierung nur in ganzzahligen Faktoren (1×/2×/3×) mit **Nearest-Neighbor**, damit nichts verschwimmt.
- Begrenzte Palette (die 28 Paint-Farben + Transparenz), 1 px schwarze Outline.
- Tray-Icon: 16×16 Pixel-Kopf des aktuellen Tiers, im Pause-Modus mit kleinem „Zzz“.

### 8.7 Sound
- Kurze, eigene 8-Bit-Sounds (Miau, Schnurren, Fauchen, „Pling“ für Erinnerungen), erzeugt per Skript oder selbst aufgenommen. Keine Windows-Systemklänge.
- Globale Lautstärke + Stummschalter im Theme-unabhängigen Tab „Allgemein“.

### 8.8 Kleine Retro-Extras (optional, Phase 4)
- „Über Desktop Pets“-Dialog im XP-Stil mit Versionsnummer und pixeliger Katze.
- Einstellungen öffnen sich mit kurzem Fenster-„Aufzieh“-Effekt.
- Ladebalken aus grünen Blöcken beim ersten Start.

---

## 9. Technische Details & Fallstricke

- **Fenster:** `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool` (kein Taskleisteneintrag), `WA_TranslucentBackground`.
- **Klick-Durchlässigkeit:** Nur Pixel mit Alpha > 0 sind anklickbar (Maske per `setMask` aus dem aktuellen Frame), damit transparente Bereiche Klicks durchlassen.
- **Pause = hinten:** Im Pause-Modus `WindowStaysOnTopHint` entfernen und per `SetWindowPos(HWND_BOTTOM)` nach hinten setzen.
- **Capture-Ausschluss:** `SetWindowDisplayAffinity(hwnd, 0x11)` (`WDA_EXCLUDEFROMCAPTURE`), ab Windows 10 2004. Auf älteren Systemen sauber ausblenden und Option ausgrauen.
- **Fenster-Erkennung:** `EnumWindows` + `DwmGetWindowAttribute(DWMWA_EXTENDED_FRAME_BOUNDS)` für korrekte Kanten (ohne unsichtbare Schattenränder); minimierte, unsichtbare und eigene Fenster ignorieren. Max. alle 250 ms aktualisieren.
- **Mehrere Monitore & DPI:** Per-Monitor-DPI-aware; das Tier darf zwischen Monitoren wechseln, Positionen in logischen Koordinaten.
- **Vollbild:** Läuft eine Vollbild-Anwendung (Spiel, Präsentation), versteckt sich das Tier automatisch.
- **Idle:** `GetLastInputInfo`.
- **Desktop-Icons (`icon_shuffle`):** Über den Desktop-ListView (`SysListView32`) per `LVM_SETITEMPOSITION`. Vor jeder Änderung alle Positionen in einer Datei sichern. Funktioniert nicht bei aktivierter „Symbole automatisch anordnen“-Option → dann Feature deaktivieren und Hinweis zeigen.
- **Performance-Ziel:** < 2 % CPU im Durchschnitt, < 80 MB RAM. Animation mit ~30 FPS, im Schlaf deutlich weniger.
- **Webhook:** Bindet ausschließlich an `127.0.0.1`, kein Zugriff von außen.
- **API-Keys:** Je Anbieter im Windows Credential Manager speichern (`keyring`), nie im Klartext in der JSON oder im Log. In der Oberfläche nur maskiert anzeigen.
- **Körbchen-Fenster:** Eigenes, rahmenloses Fenster mit `HWND_BOTTOM`, klick-durchlässig außerhalb der Grafik, ebenfalls mit Capture-Ausschluss-Option.
- **Absturzsicherheit:** Fehler in einem Feature deaktivieren nur dieses Feature und werden geloggt (`%APPDATA%\DesktopPets\log.txt`), die App läuft weiter.

---

## 10. Umsetzungsphasen

**Phase 1 – Lauffähiges Grundgerüst (MVP)**
- Transparentes Fenster, Platzhalter-Katze, Animator, Zustandsautomat
- `wander`, `mouse_chase`, `idle_sleep`, `petting`
- Tray-Icon mit Beenden und Pause-Modus inkl. Hotkey und Capture-Ausschluss
- Einstellungsdatei
- Retro-Theme-Grundlage (QSS, Farben, Tahoma) für Tray-Menü und Sprechblasen

**Phase 2 – Menüs & Tiere**
- Einstellungsdialog mit Tier-Auswahl und automatisch erzeugten Feature-Toggles
- Tier-Paket-System, vier Start-Tiere
- `needs` inkl. Füttern-Ablauf, `bed`, `day_rhythm`, `memory`, `window_walking`
- Retro-Einstellungsdialog mit eigener Titelleiste, Mini-Paint-Tab und `recolor`

**Phase 3 – Arbeitsalltag**
- `pomodoro`, `reminders`, `calendar_alerts`, `event_webhook`, `system_monitor`
- Gesammelte Meldungen nach dem Pause-Modus

**Phase 4 – Spaß & Komfort**
- `gifts`, `icon_shuffle`, `cursor_steal`, `multi_pet`
- Autostart, Vollbild-Erkennung, Auto-Pause bei Bildschirmfreigabe (experimentell)
- PyInstaller-Build als `.exe`

**Phase 5 – Optional**
- `ai_chat` mit Anbieter-Auswahl und eigenem API-Key, `network_visit`

**Später (Ideen-Speicher, noch nicht ausgearbeitet)**
- `tts`: Tier als Text-to-Speech-Werkzeug

---

## 11. Abnahmekriterien

- [ ] Klicks auf transparente Bereiche um das Tier landen im darunterliegenden Fenster.
- [ ] `Strg + Alt + P` schaltet den Pause-Modus zuverlässig, auch wenn ein anderes Programm den Fokus hat.
- [ ] In einer Teams- oder OBS-Aufnahme ist das Tier bei aktivem Capture-Ausschluss nicht zu sehen.
- [ ] Im Pause-Modus: keine Sounds, keine Sprechblasen, keine Bewegung über den Bildschirm, Tier liegt hinter allen Fenstern.
- [ ] Jedes Feature lässt sich im Dialog ein-/ausschalten, Änderung wirkt sofort und bleibt nach Neustart erhalten.
- [ ] Tierwechsel im Menü funktioniert ohne Neustart.
- [ ] Ein neues Tier-Paket im `pets/`-Ordner erscheint ohne Codeänderung in der Auswahl.
- [ ] Mit allen Chaos-Funktionen **aus** verändert die App nichts außerhalb ihres eigenen Fensters.
- [ ] Nach `icon_shuffle` stellt „Icons zurücksetzen“ alle ursprünglichen Positionen wieder her.
- [ ] Einstellungsdialog und Menüs sehen auf Windows 10 und 11 identisch im Retro-Stil aus (eckige Fenster, kein Dark Mode).
- [ ] Pixel-Art bleibt bei jeder Skalierung scharf (kein Verschwimmen).
- [ ] Läuft auf zwei Monitoren mit unterschiedlicher Skalierung korrekt.
- [ ] Füttern zeigt Napf und Fress-Animation, Hunger sinkt sichtbar in der Statusleiste.
- [ ] Im Pause-Modus geht das Tier ins Körbchen und schläft dort.
- [ ] Ein API-Key lässt sich pro Anbieter hinterlegen, testen und löschen und taucht nie in `settings.json` oder `log.txt` auf.

---

## 12. Arbeitsanweisung für Claude Code

1. Lies diese Datei vollständig.
2. Setze **eine Phase nach der anderen** um, beginnend mit Phase 1.
3. Lege nach jeder Phase eine kurze `CHANGELOG.md`-Notiz an und prüfe die zugehörigen Abnahmekriterien.
4. Halte die Logik (Zustandsautomat, Timer, Einstellungen) GUI-unabhängig und teste sie mit pytest.
5. Frag nach, bevor du von dieser Spezifikation abweichst.
