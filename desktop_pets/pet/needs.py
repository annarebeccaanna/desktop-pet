"""Hunger, Laune und Energie (0–100 %).

* Hunger steigt langsam (0 = satt, 100 = sehr hungrig).
* Laune steigt durch Streicheln, Spielen, Futter und sinkt, wenn man das Tier
  lange ignoriert.
* Energie sinkt durch Herumlaufen und füllt sich im Schlaf (im Körbchen schneller).

Kein Strafsystem: Das Tier wird nie krank und stirbt nie.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

HOUR = 3600.0
IGNORED_AFTER = 15 * 60      # ab dann sinkt die Laune langsam
FULL_THRESHOLD = 15          # Hunger darunter = satt


class Activity(str, Enum):
    REST = "rest"
    WALK = "walk"
    RUN = "run"
    SLEEP = "sleep"
    BED_SLEEP = "bed_sleep"


# Änderung pro Stunde
HUNGER_RATE = 12.0
ENERGY_RATES = {
    Activity.REST: -3.0,
    Activity.WALK: -18.0,
    Activity.RUN: -45.0,
    Activity.SLEEP: 35.0,
    Activity.BED_SLEEP: 70.0,
}
MOOD_DECAY_IGNORED = 6.0
MOOD_DECAY_HUNGRY = 4.0     # zusätzlich, wenn Hunger > 70


class FeedResult(str, Enum):
    EATEN = "eaten"          # frisst, Hunger sinkt
    FULL = "full"            # satt – nimmt es trotzdem, aber ohne Effekt
    TURN_AWAY = "turn_away"  # zu oft gefüttert: dreht sich weg und schläft


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


@dataclass
class Needs:
    hunger: float = 30.0
    mood: float = 70.0
    energy: float = 80.0
    ignored_for: float = 0.0
    _overfeed_count: int = 0

    def tick(self, dt: float, activity: Activity = Activity.REST, rate: float = 1.0) -> None:
        """``rate`` > 1 beschleunigt alles (z. B. für Tests oder Tagesrhythmus)."""
        h = dt / HOUR * rate
        self.hunger = _clamp(self.hunger + HUNGER_RATE * h)
        self.energy = _clamp(self.energy + ENERGY_RATES[activity] * h)
        self.ignored_for += dt
        if self.ignored_for > IGNORED_AFTER:
            self.mood = _clamp(self.mood - MOOD_DECAY_IGNORED * h)
        if self.hunger > 70:
            self.mood = _clamp(self.mood - MOOD_DECAY_HUNGRY * h)
        if self.hunger > FULL_THRESHOLD:
            self._overfeed_count = 0

    # ---------- Interaktionen ----------
    def feed(self) -> FeedResult:
        self.ignored_for = 0.0
        if self.hunger <= FULL_THRESHOLD:
            self._overfeed_count += 1
            if self._overfeed_count >= 2:
                self._overfeed_count = 0
                return FeedResult.TURN_AWAY
            return FeedResult.FULL
        self.hunger = _clamp(self.hunger - 55)
        self.mood = _clamp(self.mood + 10)
        return FeedResult.EATEN

    def pet(self, amount: float = 4.0) -> None:
        self.ignored_for = 0.0
        self.mood = _clamp(self.mood + amount)

    def play(self, amount: float = 6.0) -> None:
        self.ignored_for = 0.0
        self.mood = _clamp(self.mood + amount)
        self.energy = _clamp(self.energy - 1.5)

    # ---------- Anzeige ----------
    @property
    def is_full(self) -> bool:
        return self.hunger <= FULL_THRESHOLD

    @property
    def is_hungry(self) -> bool:
        return self.hunger >= 75

    @property
    def is_tired(self) -> bool:
        return self.energy <= 20

    @property
    def mood_label(self) -> str:
        if self.mood >= 80:
            return "super"
        if self.mood >= 55:
            return "gut"
        if self.mood >= 30:
            return "okay"
        return "mies"

    @property
    def mood_emoji(self) -> str:
        return {"super": "😸", "gut": "😺", "okay": "🐱", "mies": "😾"}[self.mood_label]

    # ---------- Gedächtnis ----------
    def to_dict(self) -> dict:
        return {
            "hunger": round(self.hunger, 2),
            "mood": round(self.mood, 2),
            "energy": round(self.energy, 2),
            "saved_at": time.time(),
        }

    @classmethod
    def from_dict(cls, data: dict, now: float | None = None) -> "Needs":
        needs = cls(
            hunger=_clamp(float(data.get("hunger", 30))),
            mood=_clamp(float(data.get("mood", 70))),
            energy=_clamp(float(data.get("energy", 80))),
        )
        saved_at = data.get("saved_at")
        if saved_at:
            # Während die App aus war: nur Hunger steigt etwas, Energie erholt sich.
            away = max(0.0, (now or time.time()) - float(saved_at))
            away = min(away, 12 * HOUR)
            needs.hunger = _clamp(needs.hunger + HUNGER_RATE * 0.5 * away / HOUR)
            needs.energy = _clamp(needs.energy + ENERGY_RATES[Activity.SLEEP] * away / HOUR)
        return needs
