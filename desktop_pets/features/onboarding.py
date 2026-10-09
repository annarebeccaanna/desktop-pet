"""Einführung beim ersten Start: Das Tier stellt sich in ein paar Sprechblasen vor und
zeigt das Wichtigste (Streicheln & Menü, Pause-Modus, KI & Copilot-Taste, Diktieren).

* Läuft genau einmal (``state.onboarded``) – „Überspringen“ beendet sie sofort.
* Jederzeit wieder: Tray-Menü → „Einführung zeigen“.
* Nie im Pause-Modus; startet ein paar Sekunden nach dem Programmstart.
"""

from __future__ import annotations

from ..pet.brain import State
from ..win import IS_WINDOWS
from .base import Feature, MenuAction, register

START_DELAY_MS = 2500
INTRO = {"cat": "deine neue Katze", "dog": "dein neuer Hund", "dragon": "dein neuer Drache",
         "axolotl": "dein neuer Axolotl"}


@register
class Onboarding(Feature):
    id = "onboarding"
    name = "Einführung"
    description = "Kurze Vorstellung beim ersten Start"
    default_enabled = True
    allowed_in_pause = False
    listed = False
    always_on = True

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.step = -1

    def enable(self) -> None:
        if not self.ctx.settings.get("state.onboarded"):
            from PySide6.QtCore import QTimer

            QTimer.singleShot(START_DELAY_MS, self.start)

    def menu_actions(self, where: str) -> list[MenuAction]:
        if where != "tray" or self.ctx.modes.paused:
            return []
        return [MenuAction("Einführung zeigen", self.start, order=88)]

    # ------------------------------------------------------------------ #
    def steps(self) -> list[tuple[str, str, list]]:
        app = self.ctx.app
        name = app.pet_name
        species = INTRO.get(app.pack.id, f"dein neues Pixeltier ({app.pack.name})")
        steps = [
            ("Hallo!", f"Ich bin {name}, {species}. Ab jetzt wohne ich hier auf deinem Desktop "
                       "– keine Sorge, ich störe nie: Klicks gehen durch mich hindurch.", []),
            ("Streicheln & Menü", "Fahr mit der Maus über mir hin und her, dann schnurre ich. "
                                  "Rechtsklick auf mich öffnet mein Menü – zum Füttern zum Beispiel.",
             ["hearts"]),
            ("Pause-Modus", "Kundentermin oder Bildschirm teilen? Strg + Alt + P – dann lege ich mich "
                            "hinter alle Fenster in mein Körbchen und bin mucksmäuschenstill.", []),
            ("KI & Diktieren", "Mit einem KI-Zugang (Einstellungen → KI) kann ich chatten und markierte Texte "
                               "verbessern – per Copilot-Taste oder Strg + Alt + K. Und mit Strg + Alt + D "
                               "schreibe ich auf, was du sagst.", ["settings"]),
            ("Viel Spaß!", "Alles Weitere findest du über das Tray-Icon unten rechts. "
                           "Doppelklick darauf = Pause-Modus.", []),
        ]
        if not IS_WINDOWS:
            steps[3] = ("KI", "Mit einem KI-Zugang (Einstellungen → KI) kann ich mit dir chatten "
                              "(Strg + Alt + K).", ["settings"])
        return steps

    def start(self) -> None:
        app = self.ctx.app
        if app is None or self.ctx.modes.paused:
            return
        bed = app.features.get("bed")
        if app.in_bed and bed is not None:
            bed.wake_pet()
        self.step = -1
        self.next()

    def next(self) -> None:
        app = self.ctx.app
        if app is None or self.ctx.modes.paused:
            return
        self.step += 1
        steps = self.steps()
        if self.step >= len(steps):
            self.finish()
            return
        title, text, extras = steps[self.step]
        last = self.step == len(steps) - 1
        app.brain.task = None
        app.brain.set_state(State.HAPPY if self.step == 0 else State.SIT, 2.0 if self.step == 0 else 30)
        if "hearts" in extras:
            app.hearts(3)
        buttons = [("Los geht's!" if last else "Weiter", self.next, True)]
        if "settings" in extras:
            buttons.append(("KI einrichten", lambda: (self.finish(), app.open_settings("KI")), False))
        if not last:
            buttons.append(("Überspringen", self.finish, False))
        app.say(f"{title}  ({self.step + 1}/{len(steps)})", text, 0, buttons=buttons, wide=True)

    def finish(self) -> None:
        self.step = -1
        self.ctx.settings.set("state.onboarded", True)
        app = self.ctx.app
        if app is not None:
            app.bubble.dismiss()
            if not self.ctx.modes.paused:
                app.brain.set_state(State.IDLE, 1.0)
