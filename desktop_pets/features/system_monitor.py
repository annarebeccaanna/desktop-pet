"""Systemlast: Läuft der Rechner heiß (hohe CPU), schwitzt und hechelt das Tier und
setzt sich lieber hin. Ist der Akku fast leer, wird es müde. Kommt der Stecker, freut es sich.

Gemessen wird per Windows-API (win/sysinfo.py) – alle 2 Sekunden die CPU, alle
15 Sekunden der Akku. Sprechblasen nur einmal pro „Episode“ (mit Pause dazwischen).
"""

from __future__ import annotations

import random

from ..pet.brain import Behaviour, Brain, Intent, Perception, State
from ..win import sysinfo
from .base import Feature, register

CPU_EVERY = 2.0
BATTERY_EVERY = 15.0
HOT_ON, HOT_OFF = 85.0, 65.0      # % (geglättet)
HOT_AFTER = 15.0                  # s so heiß, bevor das Tier es merkt
LOW_BATTERY = 20                  # %
SAY_COOLDOWN = 10 * 60.0          # s zwischen zwei Sprechblasen derselben Art
SWEAT_EVERY = 3.0


class LoadMood:
    """Reine Logik: aus Messwerten wird „heiß“/„müde“ – mit Glättung und Hysterese."""

    def __init__(self) -> None:
        self.cpu_avg: float | None = None
        self.hot = False
        self.tired = False
        self.plugged: bool | None = None
        self.battery: int | None = None
        self._hot_for = 0.0

    def cpu(self, value: float | None, dt: float) -> list[str]:
        if value is None:
            return []
        alpha = min(1.0, dt / 10.0)               # ~10 s Glättung
        self.cpu_avg = value if self.cpu_avg is None else self.cpu_avg + alpha * (value - self.cpu_avg)
        events = []
        if not self.hot:
            self._hot_for = self._hot_for + dt if self.cpu_avg >= HOT_ON else 0.0
            if self._hot_for >= HOT_AFTER:
                self.hot = True
                events.append("hot")
        elif self.cpu_avg < HOT_OFF:
            self.hot = False
            self._hot_for = 0.0
            events.append("cool")
        return events

    def power(self, bat) -> list[str]:
        if bat is None:
            return []
        events = []
        was_plugged = self.plugged
        self.plugged, self.battery = bat.plugged, bat.percent
        low = bat.percent <= LOW_BATTERY and not bat.plugged
        if low and not self.tired:
            events.append("low_battery")
        if self.tired and bat.plugged and was_plugged is False:
            events.append("plugged_in")
        self.tired = low
        return events


class HotBehaviour(Behaviour):
    """Bei Hitze: lieber sitzen als herumlaufen."""

    phase = "post"

    def __init__(self, mood: LoadMood) -> None:
        self.mood = mood

    def step(self, brain: Brain, dt: float, p: Perception) -> Intent | None:
        if not self.mood.hot or brain.timer > 0 or brain.state not in (State.IDLE, State.WALK):
            return None
        if brain.rng.random() < 0.6:
            brain.target_x = None
            brain.set_state(State.SIT, 6 + brain.rng.random() * 6)
            return brain.intent()
        return None


@register
class SystemMonitor(Feature):
    id = "system_monitor"
    name = "Systemlast"
    description = "Hohe CPU: schwitzt und hechelt · wenig Akku: müde"
    category = "work"
    default_enabled = True
    allowed_in_pause = True          # misst weiter, zeigt im Pause-Modus aber nichts
    pause_label = "still"
    order = 50

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.mood = LoadMood()
        self.behaviour = HotBehaviour(self.mood)
        self.sampler = sysinfo.CpuSampler()
        self.read_battery = sysinfo.battery          # in Tests ersetzbar
        self._cpu_t = CPU_EVERY
        self._bat_t = BATTERY_EVERY
        self._sweat_t = 0.0
        self._said: dict[str, float] = {}
        self._clock = 0.0
        self._sweat = None
        self._battery_icon = None

    def behaviours(self) -> list:
        return [self.behaviour]

    def contribute(self, p: Perception) -> None:
        if self.mood.tired:
            p.energy = min(p.energy, 15.0)           # müde → mehr sitzen und dösen

    def on_sprites_changed(self) -> None:
        self._sweat = self._battery_icon = None

    def _icons(self):
        app = self.ctx.app
        if self._sweat is None and app is not None:
            from PySide6.QtGui import QPixmap

            from ..core import paths

            self._sweat = app._scaled_asset(QPixmap(str(paths.assets_dir() / "sweat.png")))
            self._battery_icon = app._scaled_asset(QPixmap(str(paths.assets_dir() / "battery.png")))
        return self._sweat, self._battery_icon

    def tick(self, dt: float) -> None:
        self._clock += dt
        self._cpu_t += dt
        self._bat_t += dt
        events = []
        if self._cpu_t >= CPU_EVERY:
            events += self.mood.cpu(self.sampler.sample(), self._cpu_t)
            self._cpu_t = 0.0
        if self._bat_t >= BATTERY_EVERY:
            events += self.mood.power(self.read_battery())
            self._bat_t = 0.0
        for event in events:
            self.react(event)
        self._effects(dt)

    def _visible(self) -> bool:
        app = self.ctx.app
        return app is not None and not self.ctx.modes.paused and not app.pet_hidden and not app.in_bed

    def _effects(self, dt: float) -> None:
        if not self._visible() or not (self.mood.hot or self.mood.tired):
            return
        self._sweat_t += dt
        if self._sweat_t < (SWEAT_EVERY if self.mood.hot else 20.0):
            return
        self._sweat_t = 0.0
        sweat, battery = self._icons()
        app = self.ctx.app
        if self.mood.hot and sweat is not None:
            app.pet_window.add_particle(sweat, random.choice((1, 2)), life=1.6)
        elif battery is not None:
            app.pet_window.add_particle(battery, 1, life=2.4)

    def _say_once(self, kind: str, text: str, timeout: float = 7) -> None:
        if self._clock - self._said.get(kind, -1e9) < SAY_COOLDOWN or not self._visible():
            return
        self._said[kind] = self._clock
        app = self.ctx.app
        app.say(app.pet_name, text, timeout)

    def react(self, event: str) -> None:
        app = self.ctx.app
        if app is None:
            return
        if event == "hot":
            cpu = round(self.mood.cpu_avg or 0)
            self._say_once("hot", f"Puh, ist das heiß hier! *hechel* Dein Rechner ackert mit {cpu} %.")
            if self._visible():
                app.brain.set_state(State.SIT, 8)
        elif event == "low_battery":
            self._say_once("battery", f"Ich werde sooo müde … dein Akku hat nur noch {self.mood.battery} %. "
                                      "Ein Ladekabel wäre toll.", 9)
        elif event == "plugged_in" and self._visible():
            app.hearts(3)
            self._say_once("plugged", "Ahh, Strom! Danke, das tut gut.", 4)
