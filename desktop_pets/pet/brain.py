"""Zustandsautomat für das Verhalten des Tiers (ohne Qt, vollständig testbar).

Pro Tick bekommt das Gehirn eine :class:`Perception` (was das Tier gerade
„wahrnimmt“) und liefert eine :class:`Intent` (welche Animation, wie schnell
laufen, ob springen). Physik und Fenster setzen das um.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum


class State(str, Enum):
    IDLE = "idle"
    WALK = "walk"
    RUN = "run"          # Mausjagd / gerufen
    SIT = "sit"
    SLEEP = "sleep"
    GROOM = "groom"
    JUMP = "jump"        # in der Luft nach einem eigenen Sprung
    FALL = "fall"        # in der Luft ohne Absicht
    HAPPY = "happy"
    ANGRY = "angry"
    EAT = "eat"
    SULK = "sulk"        # schmollen (schlechte Laune) – wird als "sit" gezeigt
    DRAGGED = "dragged"


ANIMATION_FOR = {
    State.IDLE: "idle", State.WALK: "move", State.RUN: "move_fast", State.SIT: "sit",
    State.SLEEP: "sleep", State.GROOM: "groom", State.JUMP: "jump", State.FALL: "fall",
    State.HAPPY: "happy", State.ANGRY: "angry", State.EAT: "eat", State.SULK: "sit",
    State.DRAGGED: "fall",
}

# Zustände, die von selbst enden und nicht durch Wandern unterbrochen werden
ONE_SHOT = {State.HAPPY, State.ANGRY, State.EAT, State.GROOM}


@dataclass
class Perception:
    x: float
    y: float
    on_ground: bool = True
    vy: float = 0.0
    cursor: tuple[float, float] | None = None
    cursor_speed: float = 0.0          # px/s
    cursor_still_for: float = 0.0      # s
    user_idle: float = 0.0             # s seit letzter Eingabe
    paused: bool = False
    features: frozenset[str] = frozenset()
    walk_left: float = 0.0
    walk_right: float = 1920.0
    hour: int = 12
    mood: float = 70.0
    energy: float = 80.0
    hunger: float = 30.0
    jump_targets: tuple[tuple[float, float], ...] = ()   # (x, y) erreichbarer Fensterkanten
    height: float = 32.0
    on_window: bool = False            # steht auf einer Fensterkante (nicht am Boden)


@dataclass
class Intent:
    animation: str
    vx: float = 0.0
    facing: int = 1
    jump_to: tuple[float, float] | None = None


class Behaviour:
    """Zusätzliches Verhalten, das eine Funktion (features/…) ins Gehirn einklinkt.

    ``phase``: "pre" läuft vor Schlaf/Aufgaben (z. B. Einschlafen bei Inaktivität),
    "post" nach Aufgaben und Einmal-Animationen, vor dem Herumstreunen (z. B. Mausjagd).
    ``step`` gibt eine :class:`Intent` zurück, um diesen Tick zu übernehmen, sonst None.
    """

    phase = "post"

    def step(self, brain: "Brain", dt: float, p: "Perception") -> "Intent | None":  # pragma: no cover
        return None


@dataclass
class _Task:
    kind: str                 # "goto"
    x: float
    then: State = State.SIT
    then_duration: float = 3.0
    run: bool = False
    tag: str = ""             # z. B. "feed", "bed", "call" – für Rückmeldungen
    timeout: float = 30.0


@dataclass
class Brain:
    playfulness: float = 0.6
    laziness: float = 0.5
    walk_speed: float = 55.0
    run_speed: float = 170.0
    rng: random.Random = field(default_factory=random.Random)

    state: State = State.IDLE
    facing: int = 1
    timer: float = 2.0
    target_x: float | None = None
    forced_sleep: float = 0.0         # „Schlafen schicken“: Restdauer
    sleep_hold: bool = False          # ein Verhalten hält das Tier im Schlaf (z. B. Inaktivität)
    after_landing: State | None = None  # was nach der nächsten Landung kommt (z. B. Freude nach dem Fangen)
    task: _Task | None = None
    behaviours: list[Behaviour] = field(default_factory=list)
    events: list[str] = field(default_factory=list)   # z. B. "hearts", "arrived:feed", "caught", "woke"
    _pending_jump: tuple[float, float] | None = None

    # ---------- Befehle von außen ----------
    def go_to(self, x: float, then: State = State.SIT, duration: float = 3.0, run: bool = False,
              tag: str = "") -> None:
        if self.state == State.SLEEP:
            self.events.append("woke")
        self.forced_sleep = 0.0
        self.task = _Task("goto", x, then, duration, run, tag)
        self.set_state(State.RUN if run else State.WALK, 30.0)

    def send_to_sleep(self, duration: float = 600.0) -> None:
        self.task = None
        self.forced_sleep = duration
        self.set_state(State.SLEEP, duration)

    def wake(self) -> None:
        if self.state == State.SLEEP:
            self.forced_sleep = 0.0
            self.events.append("woke")
            self.set_state(State.IDLE, 1.5)

    def petted(self) -> None:
        self.events.append("hearts")
        self.events.append("petted")
        if self.state in (State.SLEEP, State.DRAGGED, State.JUMP, State.FALL, State.EAT):
            return
        self.task = None
        self.set_state(State.HAPPY, 2.5)

    def react(self, reaction: str, duration: float = 2.0) -> None:
        """Freudensprung, Fauchen … (z. B. vom Webhook)."""
        state = {"happy": State.HAPPY, "angry": State.ANGRY, "eat": State.EAT,
                 "groom": State.GROOM, "sit": State.SIT}.get(reaction)
        if state is None or self.state in (State.DRAGGED,):
            return
        if self.state == State.SLEEP:
            self.events.append("woke")
        self.forced_sleep = 0.0
        self.set_state(state, duration)

    def turn_away_and_sleep(self) -> None:
        self.facing = -self.facing
        self.send_to_sleep(120.0)

    def start_drag(self) -> None:
        self.task = None
        self.forced_sleep = 0.0
        self.set_state(State.DRAGGED, 1e9)

    def end_drag(self) -> None:
        self.set_state(State.FALL, 0.5)

    # ---------- Haupt-Tick ----------
    def tick(self, dt: float, p: Perception) -> Intent:
        self.timer -= dt
        if self.forced_sleep > 0:
            self.forced_sleep = max(0.0, self.forced_sleep - dt)

        if self.state == State.DRAGGED:
            return self.intent()

        # In der Luft: springen oder fallen, bis gelandet
        if not p.on_ground:
            if self.state != State.JUMP:
                self.set_state(State.FALL, 1e9)
            return self.intent()
        if self.state in (State.JUMP, State.FALL):
            self.events.append("landed")
            if self.after_landing is not None:
                self.set_state(self.after_landing, 1.8)
                self.after_landing = None
            else:
                self.set_state(State.IDLE, 0.6)

        if p.paused:
            return self._tick_paused(p)

        intent = self._run_behaviours("pre", dt, p)
        if intent is not None:
            return intent

        if self.state == State.SLEEP:
            if self.forced_sleep > 0 or self.sleep_hold or self.timer > 0:
                return self.intent()
            self.events.append("woke")
            self.set_state(State.IDLE, 1.2)

        if self.task is not None:
            return self._tick_task(dt, p)

        if self.state in ONE_SHOT and self.timer > 0:
            return self.intent()

        intent = self._run_behaviours("post", dt, p)
        if intent is not None:
            return intent

        # Unterwegs zu einem Ziel?
        if self.state in (State.WALK, State.RUN) and self.target_x is not None:
            return self.walk_towards(self.target_x, p, run=self.state == State.RUN,
                                     on_arrive=lambda: self.set_state(State.IDLE, 0.8 + self.rng.random()))

        if self.timer > 0:
            return self.intent()

        self._choose_next(p)
        return self.intent(jump=self._pending_jump)

    def _run_behaviours(self, phase: str, dt: float, p: Perception) -> Intent | None:
        for behaviour in self.behaviours:
            if behaviour.phase == phase:
                intent = behaviour.step(self, dt, p)
                if intent is not None:
                    return intent
        return None

    # ---------- Teilverhalten ----------
    def _tick_paused(self, p: Perception) -> Intent:
        """Pause-Modus: keine Bewegung über den Bildschirm, nur liegen/sitzen/putzen."""
        self.task = None
        self.target_x = None
        if self.state not in (State.SLEEP, State.SIT, State.GROOM, State.IDLE) or self.timer <= 0:
            roll = self.rng.random()
            if self.state != State.SLEEP and roll < 0.6:
                self.set_state(State.SLEEP, 60 + self.rng.random() * 120)
            elif roll < 0.85:
                self.set_state(State.SIT, 20 + self.rng.random() * 40)
            else:
                self.set_state(State.GROOM, 4)
        return self.intent()

    def _tick_task(self, dt: float, p: Perception) -> Intent:
        task = self.task
        assert task is not None
        task.timeout -= dt
        if self.state == task.then and self.state not in (State.WALK, State.RUN):
            if self.timer <= 0:
                self.task = None
                self.events.append(f"done:{task.tag}")
                self.set_state(State.IDLE, 1.0)
            return self.intent()
        if task.timeout <= 0:
            self._arrive(task)
            return self.intent()
        target = min(max(task.x, p.walk_left), p.walk_right)
        return self.walk_towards(target, p, run=task.run, on_arrive=lambda: self._arrive(task))

    def _arrive(self, task: _Task) -> None:
        self.events.append(f"arrived:{task.tag}")
        if task.then == State.SLEEP:
            self.send_to_sleep(task.then_duration)
        else:
            self.set_state(task.then, task.then_duration)

    def walk_towards(self, target: float, p: Perception, run: bool, on_arrive) -> Intent:
        dx = target - p.x
        if abs(dx) <= 4:
            on_arrive()
            return self.intent()
        self.facing = 1 if dx > 0 else -1
        speed = self.run_speed if run else self.walk_speed
        anim = "move_fast" if run else "move"
        return Intent(animation=anim, vx=self.facing * speed, facing=self.facing)

    def _choose_next(self, p: Perception) -> None:
        self._pending_jump = None
        self.target_x = None
        wander = "wander" in p.features
        tired = p.energy < 25
        night = "day_rhythm" in p.features and (p.hour >= 22 or p.hour < 6)
        evening = "day_rhythm" in p.features and 19 <= p.hour < 22
        morning = "day_rhythm" in p.features and 6 <= p.hour < 10
        lazy = self.laziness + (0.25 if evening else 0) + (0.45 if night else 0) + (0.3 if tired else 0)
        play = self.playfulness + (0.2 if morning else 0) - (0.3 if p.mood < 30 else 0)

        if not wander:
            # Ohne Herumstreunen bleibt das Tier an Ort und Stelle
            if lazy > 0.9 and self.rng.random() < 0.3:
                self.set_state(State.SLEEP, 30 + self.rng.random() * 60)
                self.events.append("nap")
            else:
                self.set_state(self.rng.choice([State.SIT, State.IDLE, State.SIT, State.GROOM]),
                          4 + self.rng.random() * 8)
            return

        options: list[tuple[State, float]] = [
            (State.WALK, 2.0 * max(0.2, play) * (1.3 - min(lazy, 1.2))),
            (State.SIT, 1.2 + lazy),
            (State.IDLE, 1.0),
            (State.GROOM, 0.6),
            (State.SLEEP, max(0.0, lazy - 0.6) * 2.5),
        ]
        if p.mood < 30:
            options.append((State.SULK, 1.5))
        elif p.mood > 80:
            options.append((State.HAPPY, 0.3 * play))
        if p.jump_targets and "window_walking" in p.features:
            options.append((State.JUMP, 0.9 * max(0.2, play)))

        total = sum(w for _, w in options)
        roll = self.rng.random() * total
        choice = options[-1][0]
        for state, weight in options:
            roll -= weight
            if roll <= 0:
                choice = state
                break

        if choice == State.WALK:
            span = max(40.0, (p.walk_right - p.walk_left))
            dist = self.rng.uniform(60, min(500, span))
            direction = self.rng.choice((-1, 1))
            tx = p.x + direction * dist
            if not (p.walk_left <= tx <= p.walk_right):
                tx = p.x - direction * dist
            self.target_x = min(max(tx, p.walk_left), p.walk_right)
            self.set_state(State.WALK, 1e9)
        elif choice == State.JUMP:
            self._pending_jump = self.rng.choice(p.jump_targets)
            self.facing = 1 if self._pending_jump[0] >= p.x else -1
            self.set_state(State.JUMP, 1e9)
        elif choice == State.SLEEP:
            self.set_state(State.SLEEP, 40 + self.rng.random() * 90)
            self.events.append("nap")       # z. B. Tagesrhythmus: abends lieber ins Körbchen
        elif choice == State.SIT:
            self.set_state(State.SIT, 4 + self.rng.random() * 10)
        elif choice == State.SULK:
            self.set_state(State.SULK, 8 + self.rng.random() * 8)
        elif choice == State.GROOM:
            self.set_state(State.GROOM, 3 + self.rng.random() * 2)
        elif choice == State.HAPPY:
            self.set_state(State.HAPPY, 1.5)
        else:
            self.set_state(State.IDLE, 2 + self.rng.random() * 4)

    # ---------- Hilfen ----------
    def set_state(self, state: State, duration: float) -> None:
        self.state = state
        self.timer = duration

    def intent(self, jump: tuple[float, float] | None = None) -> Intent:
        return Intent(animation=ANIMATION_FOR[self.state], vx=0.0, facing=self.facing, jump_to=jump)

    def pop_events(self) -> list[str]:
        events, self.events = self.events, []
        return events

    @property
    def is_moving(self) -> bool:
        return self.state in (State.WALK, State.RUN, State.JUMP, State.FALL, State.DRAGGED)
