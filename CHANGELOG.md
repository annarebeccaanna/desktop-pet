# Changelog

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
- [x] Pixel-Art bleibt bei jeder Skalierung scharf: nur ganzzahlige Faktoren, Nearest-Neighbor
- [x] Füttern zeigt Napf und Fress-Animation, Hunger sinkt sichtbar in der Statusleiste *(GUI-Smoke-Test)*
- [x] Im Pause-Modus geht das Tier ins Körbchen und schläft dort *(GUI-Smoke-Test)*
- [ ] Dialog und Menüs sehen auf Windows 10 und 11 identisch aus – **unter Windows prüfen** (unter Linux offscreen gerendert und mit den Mockups verglichen)
- [ ] Zwei Monitore mit unterschiedlicher Skalierung – **unter Windows prüfen** (Umrechnung physisch → logisch ist eingebaut)

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
- [ ] Klicks auf transparente Bereiche landen im Fenster darunter – **unter Windows prüfen**
- [ ] `Strg + Alt + P` schaltet zuverlässig, auch wenn ein anderes Programm den Fokus hat – **unter Windows prüfen**
- [ ] In einer Teams-/OBS-Aufnahme ist das Tier bei aktivem Capture-Ausschluss nicht zu sehen – **unter Windows prüfen**
- [ ] Tier liegt im Pause-Modus hinter allen Fenstern – **unter Windows prüfen**

Entwickelt und getestet wurde unter Linux (offscreen). Alles, was Win32 direkt anspricht, ist eingebaut, muss aber noch auf einem echten Windows-Rechner abgenommen werden.

## Abweichungen von der Spezifikation (bitte bestätigen)

- **Sprite-Größe:** Die Start-Tiere sind 16×16 Pixel (wie in den Skizzen) mit `scale: 2` im Paket. Die Größe 1×/2×/3× multipliziert das, also 32/64/96 px auf dem Bildschirm (Standard 2× = 64 px). Das Beispiel in der Spezifikation nennt 32×32.
- **Farben der Tiere** folgen den Mockups (weicheres Orange, Braun, Grün, Rosa) statt streng den 28 Paint-Farben aus Abschnitt 8.6. Die Paint-Palette gibt es zum Umfärben.
- **`bed` in der Funktionsliste:** Das Mockup zeigt 9 Verhaltens-Funktionen ohne Körbchen, die Spezifikation listet `bed` als Funktion. Es ist als eigener Schalter drin (darum „10 von 21“).
- **Geplante Funktionen** späterer Phasen stehen schon ausgegraut in der Liste, damit sie sichtbar sind.
- **Pause mit Körbchen:** Das schlafende Tier wird im Körbchen-Fenster gezeichnet. So bleibt im Pause-Modus genau ein Fenster ganz unten, und das Tier kann nicht hinter sein eigenes Körbchen rutschen.
- **Schließen-X** im Einstellungsdialog behält die (sofort wirksamen) Änderungen wie „OK“. Nur „Abbrechen“ setzt zurück.
- Kleine Extras aus Phase 4 sind schon da: „Über“-Dialog und Autostart. Der KI-Tab kommt mit Phase 5.
