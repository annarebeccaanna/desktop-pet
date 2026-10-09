# Changelog

## 0.8.0 – Copilot-Taste

- Einstellungen → **Allgemein → Copilot-Taste**: Häkchen „Copilot-Taste für Desktop Pets verwenden“ (ab Werk aus) plus Aktion: **Einstellungen öffnen** (Standard), Tier zu mir rufen, Pause-Modus umschalten. Später kommt „KI-Chat öffnen“ dazu.
- Technik: Die Taste sendet Win + Umschalt + F23. Ein Low-Level-Tastatur-Hook in eigenem Thread schluckt *nur* diese Kombination, alles andere läuft unberührt durch. Ein unbelegter Dummy-Tastendruck verhindert, dass beim Loslassen der Win-Taste das Startmenü aufgeht. Häkchen raus oder App beendet → die Taste gehört wieder Windows.
- Hinweis: Eine Umbelegung derselben Taste in PowerToys vorher entfernen, sonst greifen beide zu.

Tests: 139 (neu: Tastenerkennung inkl. Wiederholung/fremder Tasten/künstlicher Tasten, Häkchen, Aktionen).

- [ ] **Auf Windows prüfen:** Häkchen setzen → Copilot-Taste öffnet die Einstellungen, kein Copilot, kein Startmenü. Häkchen raus → Copilot öffnet wieder.

## 0.7.1 – Tiergeräusche einzeln abschaltbar

- Einstellungen → **Allgemein → Ton**: statt eines einzigen „Stumm“ jetzt zwei Häkchen –
  **Tier macht Geräusche** (Miau, Schnurren, Bellen, Mampf …) und **Hinweistöne** (z. B. Pomodoro-„Pling“), je mit eigenem „Probe“-Knopf (spielt auch bei ausgeschalteter Art zur Probe). Lautstärke gilt für beide; im Pause-Modus ist weiterhin alles still.
- Alte Einstellungen werden übernommen: wer „Stumm“ an hatte, hat danach beide Häkchen aus.

Tests: 134.

## 0.7.0 – Phase 3: Pomodoro

- **Pomodoro** (ab Werk aus, unter Funktionen → Nützlich im Arbeitsalltag): Standard **55 Minuten Arbeit + 5 Minuten Pause**, beides über das Zahnrad einstellbar.
- **Start/Stopp:** Tray-Menü, Rechtsklick aufs Tier oder `Strg + Alt + T` (änderbar unter Pause & Freigabe). Die Menüs zeigen immer die Restzeit, z. B. „Pomodoro stoppen (25:00)“.
- **Pixelzähler:** kleiner Retro-Zähler mit Tomate, Restzeit in Pixelschrift und grünem Block-Fortschrittsbalken – anfangs unten rechts in der Ecke, mit der Maus wegziehbar (Position wird gemerkt). Abschaltbar über das Zahnrad oder per Rechtsklick „Zähler ausblenden“; dann steht die Zeit nur im Menü.
- **Arbeitszeit vorbei:** „Pling“ und Sprechblase „Pomodoro geschafft!“ mit **Pause starten** / **Später** (erinnert nach 5 Minuten erneut).
- **Pause:** Das Tier läuft/fliegt/schwimmt mitten auf den Desktop und schläft dort.
- **Pause vorbei:** Das Tier steht auf (strecken, gähnen) und ruft per Sprechblase zurück an die Arbeit – **Neue Runde starten** startet die nächste Runde; automatisch geht nichts weiter.
- **Pause-Modus:** Die Zeit läuft weiter, der Zähler ist ausgeblendet, die Meldung kommt gesammelt danach.
- Funktionen können eigene Tastenkürzel mitbringen (`hotkeys()`), abgeschaltete geben ihr Kürzel frei.
- **Behoben:** Knöpfe in Sprechblasen wurden beim ersten Anzeigen abgeschnitten („…use start…“) – betraf auch die Hunger-Blase.

Tests: 129 (neu: Zeitlogik, kompletter Ablauf mit dem Tier, Einstellungen, Zähler verschieben/ausblenden, Pause-Modus, „Später“, Hotkey, Knopfbreite).

## 0.6.0 – Pause automatisch bei Bildschirmfreigabe (experimentell)

- Neues Häkchen unter **Pause & Freigabe**: „Pause automatisch starten, wenn eine Freigabe erkannt wird“ (ab Werk aus).
- **Erkennung:** Windows meldet eine Freigabe nicht selbst. Erkannt werden deshalb die Freigabe-Leisten der Programme (Teams, Zoom, Webex, Chrome/Edge/Brave/Opera/Vivaldi, Firefox) anhand von Programm, Fensterklasse und Titel – geprüft jede Sekunde.
- **Regeln ohne Codeänderung erweiterbar:** `desktop_pets/win/share_signatures.json` (mitgeliefert) plus eigene Regeln in `%APPDATA%\DesktopPets\share_signatures.json`.
- **„Erkennung testen …“:** zeigt live die Fenster der Meeting-Programme und Browser, markiert die erkannten, kopiert die Liste in die Zwischenablage und legt bei Bedarf die eigene Regeldatei an.
- **Verhalten:** Freigabe beginnt → Pause an. Freigabe endet → Pause aus, aber nur, wenn die Automatik sie eingeschaltet hat. Manuell überstimmbar: Wer während der Freigabe die Pause ausschaltet, behält das bis zur nächsten Freigabe. Tray-Tooltip und -Menü zeigen „Freigabe erkannt“.
- Technisch: Funktionen können ihren Schalter an eine beliebige Einstellung binden (`settings_key`) und aus der Funktionsliste ausgeblendet werden (`listed = False`).

Tests: 119 (neu: Erkennungsregeln mit typischen Fenstertiteln, Start/Ende der Pause, manuelles Überstimmen, Abschalten, Testfenster).

- [ ] **Auf Windows prüfen:** Freigabe in Teams (und ggf. Zoom/Browser) starten → Pause an; beenden → Pause aus. Wird nichts erkannt: „Erkennung testen …“ öffnen, „Kopieren“ und die Liste schicken – dann wird die Regel nachgeschärft.

## 0.5.0 – Phase 2 abgeschlossen

- **Ins Körbchen bei Inaktivität:** Nach X Minuten ohne Eingabe geht das Tier erst ins Körbchen (laufend, fliegend, schwimmend – vom Fenster springt es dafür herunter) und schläft dort; Tippen weckt es, auch unterwegs.
- **Abends ins Körbchen** (`day_rhythm`): Nickerchen ab 21 Uhr und vor 6 Uhr finden im Körbchen statt.
- **Rücksicht bei Vollbild** (neue Funktion `fullscreen_hide`, ab Werk an): Läuft im Vordergrund ein Spiel oder eine Präsentation im Vollbild, versteckt sich das Tier und kommt danach von selbst zurück. Unabhängig vom eigenen Ausblenden per `Strg + Alt + H`. *(laut Spezifikation eigentlich Phase 4)*
- **Werte im Rechtsklick-Menü:** Unter dem Namen stehen Hunger und Energie, rechts die Laune.
- **Hungrig am Napf:** Ist das Tier hungrig, steht der leere Napf bereit; ab und zu setzt es sich daneben und schaut zur Maus. Beim Füttern landet das Futter genau in diesem Napf.

Tests: 109 (neu u. a. Körbchen bei Inaktivität/abends, Vollbild ein/aus, Werte im Menü, Warten am Napf).

**Abnahmekriterien Phase 2 (Nachtrag)**
- [x] Bei Inaktivität und abends schläft das Tier im Körbchen *(Tests)*
- [x] Bedürfniswerte im Kopf des Rechtsklick-Menüs *(Test)*
- [x] Länger nicht gefüttert: sitzt neben dem leeren Napf, schaut zur Maus *(Tests)*
- [ ] Vollbild-Erkennung – **auf Windows prüfen** (z. B. YouTube im Vollbild oder PowerPoint-Präsentation)

## 0.4.1 – Einheitliche Struktur: „move“ statt „walk“

- Alle Tiere haben dieselben Animationsdateien; die Fortbewegung heißt jetzt `move` / `move_fast` (vorher `walk` / `run`). Wie sich ein Tier bewegt, zeigen allein seine Bilder – der Code ist für alle gleich, neue Tiere brauchen keine Codeänderung.
- **Drache fliegt:** Flügelschlag (oben – Mitte – unten), Beine angezogen, schwebt über dem Boden; Abheben und Gleiten bei `jump`/`fall`.
- **Axolotl schwimmt:** Wellenbewegung von Körper und Schwanzflosse, wehende Kiemen, gemütlicher Takt.
- Ältere Tier-Pakete mit `walk`/`run` funktionieren weiter (werden automatisch als `move`/`move_fast` genutzt).

## 0.4.0 – Neue Animationen (Option B)

- **Seitenansicht fürs Laufen, Rennen und Springen** bei allen vier Tieren – Spiegeln für links/rechts wirkt jetzt richtig. Sitzen, Fressen, Freuen, Putzen und Schlafen bleiben von vorn wie in den Mockups.
- **Signatur-Bewegung je Tier** (`special`, auch beim Freuen): Katze Schwanzschwingen & Pfote lecken, Hund Schwanzwedeln & Hecheln, Drache Flügelschlag & Rauchwölkchen, Axolotl Kiemenwackeln & Schweben.
- **Unterschiedlich lange Bilder:** z. B. lange Augen auf, kurz blinzeln (`@durations` / `durations` in `pet.json`).
- **Übergänge** statt harter Wechsel (`pet/choreo.py`): hinsetzen, aufstehen, Landung mit Stauchen, Aufwachen mit Strecken und Gähnen. Währenddessen steht das Tier kurz still.
- **Ab und zu Zwischenbilder** beim Stehen/Sitzen: Ohrzucken & Kopf schief (`fidget`), Gähnen, Signatur-Bewegung – im Pause-Modus nur die unauffälligen.
- **Sprites als Textdateien** (`pets/<id>/art/*.txt`, `palette.txt`), direkt im Editor bearbeitbar; `tools/make_sprites.py` ist jetzt ein schlanker Konverter. Auch Körbchen, Futter, Napf, Herz, Zzz und die UI-Häkchen liegen als Text vor.
- 18 Animationen je Tier (vorher 11). Hund: Zweitfarbe minimal vom Augen-Weiß getrennt, damit Umfärben die Augen nicht mitfärbt.

Tests: 93 (neu: Bilddauern, Übergangsketten, Zwischenbilder, Textformat, `sprites.png` passt zu den Textdateien).

## 0.3.1 – Menüleiste im Einstellungsfenster

- Einstellungen haben jetzt eine klassische XP-Menüleiste: **Datei** (Übernehmen `Strg+S`, Änderungen verwerfen, Schließen), **Tier** (**Tier wählen ▸** mit allen Tier-Paketen, Größe ▸, Spiegeln, Originalfarben, Tier umbenennen …), **Ansicht** (Tabs), **?** (Über). Menü, Tierliste und Vorschau bleiben synchron.

## 0.3.0 – Umbau & Absicherung für Windows

**Behoben**
- **Körbchen unsichtbar:** Es lag per `HWND_BOTTOM` „ganz unten“ – unter Windows 10/11 also hinter dem Desktop selbst (Hintergrundbild). Jetzt wird es direkt *über* dem obersten Desktop-Fenster (`Progman`/`WorkerW`) einsortiert und alle 2 s dort gehalten; nach „Desktop anzeigen“ (Win+D) liegt es wieder sichtbar darüber. Gleiches gilt für das Tier im Pause-Modus. Der Eingriff in jede Fensterverschiebung (`WM_WINDOWPOSCHANGING`) ist entfernt.
- **Körbchen ausgeblendet = für immer weg:** Im Tray-Menü gibt es jetzt „Körbchen einblenden“.
- **„Schlafen schicken“ auf einem Fenster:** Das Tier springt herunter und läuft ins Körbchen, statt hineinzuteleportieren (Teleport nur noch, wenn das Körbchen auf einem anderen Bildschirm liegt).
- **Tier blieb auf hohen Fenstern hängen:** Auf einem Fenster läuft es jetzt ab und zu absichtlich über die Kante und fällt hinunter – egal wie hoch.

**Umgebaut**
- `core/app.py` von 856 auf ~570 Zeilen: Füttern/Napf/Quengeln → `features/needs.py`, Körbchen samt Fenster, Menü und Pause-Schlaf → `features/bed.py`, Mausjagd-Logik → `features/mouse_chase.py`, Einschlafen bei Inaktivität → `features/idle_sleep.py`, Streicheln → `features/behavior.py`, Plattformen → `core/platforms.py`.
- Funktionen docken jetzt über feste Punkte an (`features/base.py`): eigenes Verhalten fürs Gehirn (`Behaviour`), Wahrnehmung ergänzen, auf Ereignisse reagieren, eigene Menüeinträge. Eine neue Funktion braucht keine Änderung mehr an `app.py` oder `brain.py`.
- Unter Windows keine `setMask`-Berechnung mehr (transparente Pixel sind dort ohnehin klick-durchlässig).
- Einstellungen werden gebündelt gespeichert (600 ms), nicht mehr bei jedem Schritt eines Schiebereglers; beim Beenden sofort.
- Win32-Fehlercodes über `use_last_error=True`, Fenster-Handles typsicher übergeben.

**Pixel-Schärfe (Korrektur der Abnahme 0.2.0):** Bei 100 % und 200 % Windows-Skalierung exakt scharf. Bei 125 %/150 % ist Größe 2× scharf, 1× und 3× können minimal ungleichmäßig sein. Nach Rückmeldung bewusst so belassen; das Häkchen in 0.2.0 war zu optimistisch.

Tests: 73 (neu u. a. Desktop-Einsortierung, Über-die-Kante-Laufen, Schlafen schicken vom Fenster, Körbchen einblenden, gebündeltes Speichern).

## 0.2.1 – Fehlerbehebung

- Füttern, während das Tier auf einem Fenster steht: Das Tier sprang hoch und landete sofort wieder auf derselben Fensterkante, statt zum Napf am Körbchen hinunterzugehen. Jetzt ignoriert ein absichtlicher Sprung nach unten alle Fensterkanten, bis das Tier am Boden ist (`Body.drop_to_ground`). Tests: `test_drop_through_ignores_window_edges_until_ground`, `test_feeding_from_window_edge_goes_down_to_ground`.

## 0.2.0 – Phase 2: Menüs & Tiere

**Neu**
- Einstellungsdialog im Retro-Stil: rahmenlos, eigene XP-Titelleiste (Verlauf, Glanzstreifen, pixelige obere Ecken, Minimieren/Schließen), blauer Rahmen, DWM-Schatten, unter Windows 11 eckig (`DWMWCP_DONOTROUND`), Statusleiste in Pixelschrift.
  - **Tiere** als Mini-Paint: Werkzeugleiste (Größe 1×/2×/3×, Spiegeln), Leinwand mit animierter Vorschau (Klick wechselt die Animation), Name, „Originalfarben“, 28-Farben-Palette (Linksklick Haupt-, Rechtsklick Zweitfarbe), Tierliste mit Hinweis-Ballon.
  - **Funktionen**: Liste wird automatisch aus allen registrierten Features gebaut, gruppiert nach Kategorien, mit „Pause:“-Spalte und Zahnrad für Detail-Optionen (Mausjagd: Jagdlust, Inaktivität: Minuten, Bedürfnisse: Tempo/Quengeln). Geplante Funktionen späterer Phasen stehen ausgegraut mit „kommt in Phase X“ darin.
  - **Pause & Freigabe**: Pause-Modus starten/beenden, Hotkeys aufnehmen („Ändern …“), Capture-Ausschluss (Pause / immer), Auto-Erkennung als „experimentell“ (noch aus, Phase 4).
  - **Allgemein**: Autostart mit Windows (HKCU\…\Run), Stumm, Lautstärke + Probe, Sprache, Zurücksetzen (zweistufig), Pfade zu Einstellungen/Log.
  - Änderungen wirken sofort. „Abbrechen“ stellt den Stand beim Öffnen wieder her, „Übernehmen“ macht den aktuellen Stand zum neuen Ausgangspunkt.
- Tier-Paket-System: `pets/<id>/pet.json` + `sprites.png` (+ optional `icon/bed/bowl/food.png`). Pakete im Benutzerordner `%APPDATA%\DesktopPets\pets` überschreiben mitgelieferte. Kaputte Pakete werden übersprungen und geloggt.
- Vier Start-Tiere (Katze, Hund, Drache, Axolotl) mit je 11 Animationen, Körbchen/Kissen/Nest/Glas, Napf und Futter (Fisch/Knochen/Paprika/Wurm) – eigene Pixel-Art aus `tools/make_sprites.py`.
- `needs`: Hunger/Laune/Energie mit Füttern-Ablauf (Napf erscheint neben dem Körbchen, Tier läuft hin, frisst, Herzchen/„Mampf!“, leerer Napf verschwindet nach 5 s). Zu oft gefüttert → dreht sich weg und schläft. Hunger → kleine Quengel-Blase mit „Füttern“-Knopf (nie im Pause-Modus).
- `bed`: Körbchen auf dem Desktop, immer hinter allen Fenstern, ziehbar, Position pro Bildschirm gespeichert. Doppelklick weckt/schickt schlafen, Rechtsklick: verschieben, ausblenden, Tier hineinschicken.
- `window_walking`: Fensteroberkanten über `EnumWindows` + `DWMWA_EXTENDED_FRAME_BOUNDS` (max. alle 250 ms), verdeckte Kantenstücke werden abgeschnitten. Das Tier springt von Fenster zu Fenster, fährt mit verschobenen Fenstern mit und fällt, wenn ein Fenster verschwindet.
- `day_rhythm` (abends schläfrig, morgens verspielt), `memory` (Bedürfnisse + Position, alle 60 s und beim Beenden), `recolor` (Palettentausch, pro Tier gespeichert).
- 8-Bit-Sounds aus `tools/make_sounds.py` (Miau, Schnurren, Fauchen, Wuff, Knurren, Zirpen, Blub, Mampf, Pling, Sprung). Im Pause-Modus immer still.
- „Über Desktop Pets“-Dialog, PyInstaller-Spezifikation (`desktop_pets.spec`) mit eigenem App-Icon.

**Abnahmekriterien Phase 2**
- [x] Jedes Feature lässt sich im Dialog ein-/ausschalten, Änderung wirkt sofort und bleibt nach Neustart erhalten *(Test: `test_toggle_persists_and_survives_restart`, GUI-Smoke-Test)*
- [x] Tierwechsel im Menü funktioniert ohne Neustart *(GUI-Smoke-Test)*
- [x] Ein neues Tier-Paket im `pets/`-Ordner erscheint ohne Codeänderung *(Test: `test_new_pack_folder_is_discovered_without_code_change`)*
- [x] Pixel-Art bleibt scharf: ganzzahlige Faktoren + Nearest-Neighbor; bei 125/150 % nicht in jeder Größe exakt – so abgenommen (siehe 0.3.0)
- [x] Füttern zeigt Napf und Fress-Animation, Hunger sinkt sichtbar in der Statusleiste *(GUI-Smoke-Test)*
- [x] Im Pause-Modus geht das Tier ins Körbchen und schläft dort *(GUI-Smoke-Test)*
- [x] Dialog und Menüs im Retro-Stil – auf Windows geprüft
- [x] Mehrere Monitore / Skalierung – auf Windows geprüft

## 0.1.0 – Phase 1: Lauffähiges Grundgerüst

**Neu**
- Transparentes, rahmenloses Tierfenster (`Tool`, kein Taskleisteneintrag, nimmt nie den Fokus). Klick-Durchlässigkeit über `setMask` aus dem aktuellen Frame – nur Pixel des Tiers sind anklickbar.
- Animator (Sprite-Sheet, eine Zeile pro Animation, Rückfall auf `idle`), Spiegeln für links/rechts.
- Zustandsautomat (`pet/brain.py`, ohne Qt): Herumlaufen, Sitzen, Putzen, Schlafen, Mausjagd mit Fangen, Freude, Fauchen, Fressen, Ziehen/Fallen, Aufgaben („geh zu X, dann …“).
- Physik mit Plattformen (Boden je Bildschirm, später Fensterkanten), Schwerkraft, Sprungbahnen.
- Funktionen `wander`, `mouse_chase`, `idle_sleep` (`GetLastInputInfo`), `petting`.
- Funktions-Schnittstelle `Feature` (`id`, `name`, `description`, `default_enabled`, `allowed_in_pause`, `enable()`, `disable()`) mit Registry. Fehler in einer Funktion schalten nur diese ab und landen im Log.
- Modi Normal / Pause / Schlafen. Pause: Fenster ganz nach hinten (`SetWindowPos(HWND_BOTTOM)` + Festhalten in `WM_WINDOWPOSCHANGING`), keine Sounds, keine Sprechblasen, keine Bewegung; Meldungen werden gesammelt und danach als eine Blase gezeigt.
- Capture-Ausschluss `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` ab Build 19041, sonst ausgegraut.
- Globale Hotkeys über `RegisterHotKey` (`Strg + Alt + P`, `Strg + Alt + H`).
- Tray-Icon (16×16-Pixelkopf, im Pause-Modus mit „Z“), Menü mit blauem Kopf und gelber Statuszeile („Aufnahme-Schutz an · 2 Meldungen warten“).
- Einstellungen als JSON in `%APPDATA%\DesktopPets\settings.json` (atomar gespeichert, Migration, Sicherung kaputter Dateien, Geheimnisse werden abgewiesen). Log in `log.txt` (rotierend, API-Keys maskiert).
- Retro-Theme: `themes/retro_xp.qss` + Farben in `retro_xp.json`, Tahoma 8 pt (Fallback Segoe UI), Pixelschrift Silkscreen (OFL) ohne Glättung, Dark Mode wird ignoriert. Sprechblasen im Ballon-Stil.

**Abnahmekriterien Phase 1**
- [x] Pause-Modus: keine Sounds, keine Sprechblasen, keine Bewegung über den Bildschirm *(Tests: `test_pause_means_no_movement`, GUI-Smoke-Test)*
- [x] Mit allen Chaos-Funktionen aus verändert die App nichts außerhalb ihrer eigenen Fenster (Chaos-Funktionen sind ab Werk aus und noch gar nicht umgesetzt)
- [x] Klicks auf transparente Bereiche landen im Fenster darunter – auf Windows geprüft
- [x] `Strg + Alt + P` schaltet zuverlässig, auch wenn ein anderes Programm den Fokus hat – auf Windows geprüft
- [x] In einer Teams-/OBS-Aufnahme ist das Tier bei aktivem Capture-Ausschluss nicht zu sehen – auf Windows geprüft
- [x] Tier liegt im Pause-Modus hinter allen Fenstern – auf Windows geprüft

Entwickelt unter Linux (offscreen); die Windows-Abnahme der Phasen 1 und 2 ist erfolgt (Stand 0.4.0).

## Abweichungen von der Spezifikation (bitte bestätigen)

- **Sprite-Größe:** Die Start-Tiere sind 16×16 Pixel (wie in den Skizzen) mit `scale: 2` im Paket. Die Größe 1×/2×/3× multipliziert das, also 32/64/96 px auf dem Bildschirm (Standard 2× = 64 px). Das Beispiel in der Spezifikation nennt 32×32.
- **Farben der Tiere** folgen den Mockups (weicheres Orange, Braun, Grün, Rosa) statt streng den 28 Paint-Farben aus Abschnitt 8.6. Die Paint-Palette gibt es zum Umfärben.
- **`bed` in der Funktionsliste:** Das Mockup zeigt 9 Verhaltens-Funktionen ohne Körbchen, die Spezifikation listet `bed` als Funktion. Es ist als eigener Schalter drin (darum „10 von 21“).
- **Geplante Funktionen** späterer Phasen stehen schon ausgegraut in der Liste, damit sie sichtbar sind.
- **Pause mit Körbchen:** Das schlafende Tier wird im Körbchen-Fenster gezeichnet. So bleibt im Pause-Modus genau ein Fenster ganz unten, und das Tier kann nicht hinter sein eigenes Körbchen rutschen.
- **Schließen-X** im Einstellungsdialog behält die (sofort wirksamen) Änderungen wie „OK“. Nur „Abbrechen“ setzt zurück.
- Kleine Extras aus Phase 4 sind schon da: „Über“-Dialog und Autostart. Der KI-Tab kommt mit Phase 5.
