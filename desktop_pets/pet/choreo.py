"""Choreografie: Übergänge zwischen Animationen und gelegentliche Zwischenbilder.

Das Gehirn sagt nur, *was* das Tier gerade tun will („walk“, „sit“ …). Der
Choreograf sorgt dafür, dass es dabei nicht von einem Bild ins nächste springt:

* Laufen (Seite) → Sitzen (vorn):   ``sit_down``
* Sitzen (vorn)  → Laufen (Seite):  ``stand_up``
* in der Luft    → am Boden:        ``land`` (Stauchen)
* Schlafen       → wach:            ``wake`` (strecken, gähnen)

Wer längere Zeit nur steht oder sitzt, zeigt ab und zu ein Zwischenbild:
``fidget`` (Ohrzucken, Kopf schief), ``yawn`` oder die Signatur-Bewegung
``special``. Fehlt eine dieser Animationen im Tier-Paket, wird sie einfach
übersprungen. Reine Zeitlogik ohne Qt – testbar.
"""

from __future__ import annotations

import random

from .animator import Animator

GROUP = {"move": "side", "move_fast": "side", "land": "side", "stand_up": "side",
         "jump": "air", "fall": "air", "sleep": "sleep"}          # alles andere: "front"
TRANSITION_END = {"sit_down": "front", "stand_up": "side", "land": "side", "wake": "front"}
BLOCKING = set(TRANSITION_END)      # währenddessen steht das Tier still (keine Rutschpartie)
CALM = {"idle", "sit"}
EXTRAS = (("fidget", 3.0), ("yawn", 1.0), ("special", 2.0))
QUIET_EXTRAS = (("fidget", 3.0), ("yawn", 1.0))                   # Pause-Modus: nichts Auffälliges
EXTRA_DELAY = (7.0, 16.0)           # Sekunden zwischen zwei Zwischenbildern


def group(name: str) -> str:
    return GROUP.get(name, "front")


class Choreographer:
    def __init__(self, animator: Animator, rng: random.Random | None = None) -> None:
        self.animator = animator
        self.rng = rng or random.Random()
        self.target = animator.name
        self.queue: list[str] = []
        self.transient: str | None = None     # gerade laufender Übergang oder Zwischenbild
        self.extra_timer = self._extra_delay()

    # ---------- öffentlich ----------
    @property
    def blocking(self) -> bool:
        """True, solange ein Übergang läuft, bei dem das Tier nicht vorwärtskommt."""
        return self.transient in BLOCKING

    def update(self, wanted: str, dt: float, extras: bool = True, quiet: bool = False) -> None:
        wanted = self.animator.resolve(wanted)
        if wanted != self.target:
            self._retarget(wanted)
        elif self.transient is not None and self.animator.finished:
            self._next()
        elif self.transient is None:
            self._maybe_extra(dt, extras, quiet)
        self.animator.update(dt)

    def chain(self, from_group: str, to_name: str) -> list[str]:
        """Welche Übergänge zwischen zwei Gruppen nötig sind (nur vorhandene)."""
        to = group(to_name)
        steps: list[str] = []
        g = from_group
        for _ in range(4):
            if g == to:
                break
            if g == "air":
                step = "land"
            elif g == "sleep":
                step = "wake"
            elif g == "side" and to in ("front", "sleep"):
                step = "sit_down"
            elif g == "front" and to == "side":
                step = "stand_up"
            else:
                break
            if step not in self.animator.animations:
                break
            steps.append(step)
            g = TRANSITION_END[step]
        return steps

    # ---------- intern ----------
    def _retarget(self, wanted: str) -> None:
        self.target = wanted
        running = self.transient
        if running in TRANSITION_END and group(wanted) != "air":
            # Übergang zu Ende spielen, danach passend weiter
            self.queue = self.chain(TRANSITION_END[running], wanted)
            return
        # Zwischenbilder werden abgebrochen; in die Luft geht es sofort
        current = self.animator.name if running is None else "idle"
        self.transient = None
        self.queue = self.chain(group(current), wanted)
        self._next()

    def _next(self) -> None:
        if self.queue:
            self.transient = self.queue.pop(0)
            self.animator.play(self.transient, restart=True)
        else:
            self.transient = None
            self.animator.play(self.target, restart=True)
            self.extra_timer = self._extra_delay()

    def _maybe_extra(self, dt: float, allowed: bool, quiet: bool) -> None:
        if not allowed or self.target not in CALM:
            return
        self.extra_timer -= dt
        if self.extra_timer > 0:
            return
        options = [(n, w) for n, w in (QUIET_EXTRAS if quiet else EXTRAS) if n in self.animator.animations]
        self.extra_timer = self._extra_delay()
        if not options:
            return
        roll = self.rng.random() * sum(w for _, w in options)
        for name, weight in options:
            roll -= weight
            if roll <= 0:
                break
        self.transient = name
        self.queue = []
        self.animator.play(name, restart=True)

    def _extra_delay(self) -> float:
        return self.rng.uniform(*EXTRA_DELAY)
