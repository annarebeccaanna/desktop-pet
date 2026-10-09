"""Pomodoro: konzentriert arbeiten, dann kurz Pause – das Tier macht mit.

Ablauf (Standard 55 + 5 Minuten, beides einstellbar):

1. Starten (Menü, Tier-Menü oder ``Strg + Alt + T``) → Arbeitszeit läuft.
2. Arbeitszeit vorbei → Sprechblase „Pomodoro geschafft!“ mit „Pause starten“ / „Später“.
3. Pause → das Tier legt sich mitten auf den Desktop und schläft.
4. Pause vorbei → das Tier steht auf und ruft per Sprechblase zurück an die Arbeit.
   Die nächste Runde startet bewusst *nicht* automatisch.

Restzeit: kleiner Pixelzähler in einer Bildschirmecke (wegziehbar, ausblendbar)
und immer im Tray-/Tier-Menü. Im Pause-Modus läuft die Zeit weiter, Meldungen
kommen gesammelt danach; der Zähler ist dann ausgeblendet.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Callable

from ..core.modes import Mode
from ..pet.brain import State
from .base import Feature, MenuAction, Option, register

SNOOZE_SECONDS = 5 * 60      # „Später“ erinnert nach 5 Minuten erneut


class Phase(str, Enum):
    IDLE = "idle"            # nichts läuft
    WORK = "work"            # Arbeitszeit läuft
    WORK_DONE = "work_done"  # Arbeitszeit vorbei, Pause noch nicht gestartet
    BREAK = "break"          # Pause läuft


class PomodoroTimer:
    """Reine Zeitlogik (Wanduhr, damit auch Standby-Zeit zählt). ``clock`` ist in Tests ersetzbar."""

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self.clock = clock
        self.phase = Phase.IDLE
        self.ends_at = 0.0
        self.started_at = 0.0
        self.work_seconds = 55 * 60.0
        self.break_seconds = 5 * 60.0

    @property
    def running(self) -> bool:
        return self.phase in (Phase.WORK, Phase.BREAK)

    @property
    def remaining(self) -> float:
        return max(0.0, self.ends_at - self.clock()) if self.running else 0.0

    @property
    def progress(self) -> float:
        """0.0 … 1.0 der aktuellen Phase."""
        if not self.running:
            return 1.0 if self.phase == Phase.WORK_DONE else 0.0
        total = self.ends_at - self.started_at
        return 1.0 - self.remaining / total if total > 0 else 1.0

    def start_work(self) -> None:
        self._start(Phase.WORK, self.work_seconds)

    def start_break(self) -> None:
        self._start(Phase.BREAK, self.break_seconds)

    def stop(self) -> None:
        self.phase = Phase.IDLE
        self.ends_at = self.started_at = 0.0

    def update(self) -> str | None:
        """Gibt "work_done" oder "break_done" zurück, wenn eine Phase gerade endet."""
        if not self.running or self.clock() < self.ends_at:
            return None
        if self.phase == Phase.WORK:
            self.phase = Phase.WORK_DONE
            return "work_done"
        self.stop()
        return "break_done"

    def _start(self, phase: Phase, seconds: float) -> None:
        self.phase = phase
        self.started_at = self.clock()
        self.ends_at = self.started_at + max(1.0, seconds)


def fmt(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60:02d}:{s % 60:02d}" if s < 6000 else f"{s // 3600}h{(s % 3600) // 60:02d}"


@register
class Pomodoro(Feature):
    id = "pomodoro"
    name = "Pomodoro"
    description = "55 / 5 Minuten, Tier legt sich zur Pause hin"
    category = "work"
    default_enabled = False
    allowed_in_pause = True          # Zähler läuft weiter, Meldung kommt danach
    pause_label = "später"
    order = 10
    options = [
        Option("work_minutes", "Arbeitszeit", 55, kind="int", minimum=1, maximum=240, suffix=" Min."),
        Option("break_minutes", "Pause", 5, kind="int", minimum=1, maximum=60, suffix=" Min."),
        Option("show_counter", "Zähler auf dem Bildschirm anzeigen", True, kind="bool"),
    ]

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.timer = PomodoroTimer()
        self.counter = None
        self._snooze_at = 0.0

    # ------------------------------------------------------------------ #
    # Steuerung
    # ------------------------------------------------------------------ #
    def toggle(self) -> None:
        if self.timer.phase == Phase.IDLE:
            self.start()
        elif self.timer.phase == Phase.WORK_DONE:
            self.start_break()
        else:
            self.stop()

    def start(self) -> None:
        if not self.enabled:
            return
        self._apply_durations()
        self.timer.start_work()
        self._snooze_at = 0.0
        app = self.ctx.app
        if app is not None:
            app.say("Pomodoro", f"Los geht's! {self._minutes('work_minutes')} Minuten konzentriert arbeiten.", 4)
        self._update_counter()

    def stop(self) -> None:
        was_break = self.timer.phase == Phase.BREAK
        self.timer.stop()
        self._snooze_at = 0.0
        if was_break and self.ctx.app is not None:
            self.ctx.app.brain.wake()
        self._update_counter()

    def start_break(self) -> None:
        if self.timer.phase not in (Phase.WORK_DONE, Phase.WORK):
            return
        self._apply_durations()
        self.timer.start_break()
        self._snooze_at = 0.0
        app = self.ctx.app
        if app is not None and not self.ctx.modes.paused:
            # Mitten auf den Desktop legen und schlafen, solange die Pause dauert
            from PySide6.QtGui import QGuiApplication

            g = QGuiApplication.primaryScreen().availableGeometry()
            app.leave_window_edge(target_y=g.top() + g.height())
            app.brain.go_to(g.center().x(), then=State.SLEEP, duration=self.timer.break_seconds, tag="pomodoro")
            app.say("", "Ich leg mich schon mal hin …", 3)
        self._update_counter()

    # ------------------------------------------------------------------ #
    # Takt
    # ------------------------------------------------------------------ #
    def tick(self, dt: float) -> None:
        event = self.timer.update()
        if event == "work_done":
            self._snooze_at = 0.0
            self._announce_work_done()
        elif event == "break_done":
            self._announce_break_done()
        elif self.timer.phase == Phase.WORK_DONE and self._snooze_at and self.timer.clock() >= self._snooze_at:
            self._snooze_at = 0.0
            self._announce_work_done()
        self._update_counter()

    def _announce_work_done(self) -> None:
        app = self.ctx.app
        title = "Pomodoro geschafft!"
        text = (f"{self._minutes('work_minutes')} Minuten konzentriert. "
                f"Zeit für {self._minutes('break_minutes')} Minuten Pause. Ich leg mich schon mal hin.")
        if app is None:
            return
        if self.ctx.modes.paused:
            self.ctx.modes.notify(title, text, key="pomodoro")
            return
        app.sound.play("pling.wav", kind="notice")
        app.say(title, text, 60, [("Pause starten", self.start_break, True), ("Später", self._snooze, False)])

    def _announce_break_done(self) -> None:
        app = self.ctx.app
        if app is None:
            return
        app.brain.wake()                         # steht auf (Aufwach-Animation: strecken, gähnen)
        title, text = "Pause vorbei!", "Ausgeruht? Dann zurück an die Arbeit."
        if self.ctx.modes.paused:
            self.ctx.modes.notify(title, text, key="pomodoro")
            return
        app.sound.play("pling.wav", kind="notice")
        app.say(title, text, 60, [("Neue Runde starten", self.start, True), ("Fertig", lambda: None, False)])

    def _snooze(self) -> None:
        self._snooze_at = self.timer.clock() + SNOOZE_SECONDS

    # ------------------------------------------------------------------ #
    # Zähler
    # ------------------------------------------------------------------ #
    def _update_counter(self) -> None:
        app = self.ctx.app
        if app is None:
            return
        want = (self.enabled and bool(self.option("show_counter")) and self.timer.phase != Phase.IDLE
                and not self.ctx.modes.paused and not app.pet_hidden)
        if not want:
            if self.counter is not None and self.counter.isVisible():
                self.counter.hide()
            return
        if self.counter is None:
            from ..ui.pomodoro_counter import PomodoroCounter

            self.counter = PomodoroCounter()
            self.counter.moved.connect(self._remember_position)
            self.counter.rightClicked.connect(self._counter_menu)
            self.counter.clicked.connect(self.toggle_from_counter)
            self.counter.shown.connect(app.apply_capture)
            self.counter.place(self.option("position"))
        label = {Phase.WORK: "Arbeit", Phase.BREAK: "Pause", Phase.WORK_DONE: "Geschafft!"}[self.timer.phase]
        shown = self.timer.remaining if self.timer.running else 0
        self.counter.set_state(fmt(shown), label, self.timer.progress, self.timer.phase == Phase.BREAK)
        if not self.counter.isVisible():
            self.counter.show()

    def toggle_from_counter(self) -> None:
        if self.timer.phase == Phase.WORK_DONE:
            self.start_break()

    def _remember_position(self, x: int, y: int) -> None:
        self.ctx.settings.set_feature_option(self.id, "position", [x, y])

    def _counter_menu(self, pos) -> None:
        from PySide6.QtWidgets import QMenu

        m = QMenu()
        for entry in self.menu_actions("pet"):
            m.addAction(entry.label, entry.callback).setEnabled(entry.enabled)
        m.addSeparator()
        m.addAction("Zähler ausblenden", lambda: self.ctx.settings.set_feature_option(self.id, "show_counter", False))
        m.exec(pos)

    # ------------------------------------------------------------------ #
    # Andockpunkte
    # ------------------------------------------------------------------ #
    def menu_actions(self, where: str) -> list[MenuAction]:
        app = self.ctx.app
        shortcut = ""
        if app is not None:
            from ..win import hotkeys as hk

            try:
                shortcut = hk.format_hotkey(app.settings.get("hotkeys.pomodoro") or "").replace(" + ", "+")
            except hk.HotkeyError:
                shortcut = ""
        order = 25 if where == "tray" else 30
        phase = self.timer.phase
        if phase == Phase.IDLE:
            return [MenuAction("Pomodoro starten", self.start, order=order, shortcut=shortcut)]
        if phase == Phase.WORK:
            return [MenuAction(f"Pomodoro stoppen ({fmt(self.timer.remaining)})", self.stop, order=order,
                               shortcut=shortcut)]
        if phase == Phase.WORK_DONE:
            return [MenuAction("Pomodoro-Pause starten", self.start_break, order=order, shortcut=shortcut),
                    MenuAction("Pomodoro beenden", self.stop, order=order + 1)]
        return [MenuAction(f"Pomodoro-Pause beenden ({fmt(self.timer.remaining)})", self.stop, order=order,
                           shortcut=shortcut)]

    def hotkeys(self) -> list[tuple[str, Callable[[], None]]]:
        return [("pomodoro", self.toggle)]

    def on_mode_changed(self, mode: Mode) -> None:
        self._update_counter()

    def on_visibility_changed(self, visible: bool) -> None:
        self._update_counter()

    def on_settings_changed(self, key: str, value) -> None:
        if key == "*" or key.startswith("feature_options.pomodoro"):
            self._update_counter()

    def disable(self) -> None:
        self.timer.stop()
        if self.counter is not None:
            self.counter.hide()

    @property
    def windows(self) -> list:
        return [self.counter] if self.counter is not None else []

    # ------------------------------------------------------------------ #
    def _minutes(self, key: str) -> int:
        try:
            return max(1, int(self.option(key)))
        except (TypeError, ValueError):
            return 55 if key == "work_minutes" else 5

    def _apply_durations(self) -> None:
        self.timer.work_seconds = self._minutes("work_minutes") * 60.0
        self.timer.break_seconds = self._minutes("break_minutes") * 60.0
