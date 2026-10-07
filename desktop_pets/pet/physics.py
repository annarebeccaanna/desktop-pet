"""Laufen, Springen, Fallen auf Plattformen (Boden je Bildschirm, Fensterkanten).

Koordinaten sind logische Bildschirmkoordinaten; ``y`` wächst nach unten.
Der Körper wird über seine *Fußmitte* beschrieben (x = Mitte, y = Unterkante).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

GRAVITY = 2200.0          # px/s²
MAX_FALL_SPEED = 1600.0   # px/s


@dataclass(frozen=True)
class Platform:
    id: str
    left: float
    right: float
    y: float
    solid: bool = False   # Boden eines Bildschirms: seitlich nicht durchlaufbar

    def spans(self, x: float) -> bool:
        return self.left <= x <= self.right


@dataclass
class Body:
    x: float
    y: float
    width: float = 32.0
    height: float = 32.0
    vx: float = 0.0
    vy: float = 0.0
    support: str | None = None        # id der Plattform, auf der der Körper steht
    _support_offset: float = 0.0      # x relativ zur linken Kante der Plattform

    @property
    def on_ground(self) -> bool:
        return self.support is not None

    def place_on(self, platform: Platform) -> None:
        self.y = platform.y
        self.vy = 0.0
        self.support = platform.id
        self._support_offset = self.x - platform.left


def jump_velocity(dx: float, dy: float, margin: float = 24.0, gravity: float = GRAVITY) -> tuple[float, float]:
    """Startgeschwindigkeit für einen Sprung um (dx, dy). dy < 0 heißt nach oben.

    Der Scheitelpunkt liegt ``margin`` Pixel über dem höheren der beiden Punkte,
    damit das Tier von oben auf der Zielkante landet.
    """
    rise = max(0.0, -dy) + margin
    vy0 = -math.sqrt(2.0 * gravity * rise)
    # Zeit bis zum Erreichen der Zielhöhe auf dem absteigenden Ast
    disc = vy0 * vy0 + 2.0 * gravity * dy
    t = (-vy0 + math.sqrt(max(disc, 0.0))) / gravity
    return dx / max(t, 1e-3), vy0


class World:
    """Kennt alle Plattformen und bewegt Körper zwischen ihnen."""

    def __init__(self) -> None:
        self.platforms: dict[str, Platform] = {}
        self.left = 0.0
        self.right = 1920.0

    def set_platforms(self, platforms: list[Platform]) -> None:
        self.platforms = {p.id: p for p in platforms}
        grounds = [p for p in platforms if p.solid] or platforms
        if grounds:
            self.left = min(p.left for p in grounds)
            self.right = max(p.right for p in grounds)

    @property
    def lowest_y(self) -> float:
        return max((p.y for p in self.platforms.values()), default=0.0)

    def ground_at(self, x: float) -> Platform | None:
        cands = [p for p in self.platforms.values() if p.solid and p.spans(x)]
        return min(cands, key=lambda p: p.y) if cands else None

    def walk_span(self, body: Body) -> tuple[float, float]:
        """Wie weit der Körper auf seiner aktuellen Fläche laufen kann (für die Wegplanung)."""
        half = body.width / 2
        plat = self.platforms.get(body.support or "")
        if plat is None:
            return self.left + half, self.right - half
        if not plat.solid:
            return plat.left + half * 0.5, plat.right - half * 0.5
        left, right = plat.left, plat.right
        # Angrenzende Böden auf gleicher oder tieferer Höhe erweitern die Fläche nicht –
        # das Tier fällt dort einfach hinunter. Für die Planung reicht der eigene Boden.
        return left + half, right - half

    def step(self, body: Body, dt: float) -> str | None:
        """Bewegt den Körper. Gibt ein Ereignis zurück: "landed", "fell" oder None."""
        event: str | None = None
        half = body.width / 2

        if body.support is not None:
            plat = self.platforms.get(body.support)
            if plat is None:
                body.support = None
                event = "fell"
            else:
                # Mit der Plattform mitbewegen (z. B. verschobenes Fenster)
                body.x = plat.left + body._support_offset
                body.y = plat.y
                new_x = body.x + body.vx * dt
                new_x = self._block_walls(body, new_x)
                if plat.spans(new_x):
                    body.x = new_x
                    body._support_offset = body.x - plat.left
                else:
                    # Über die Kante: auf einer angrenzenden Fläche gleicher Höhe weiterlaufen?
                    nxt = self._platform_at_height(new_x, plat.y, exclude=plat.id)
                    body.x = new_x
                    if nxt is not None:
                        body.place_on(nxt)
                    else:
                        body.support = None
                        event = "fell"

        if body.support is None:
            prev_y = body.y
            body.vy = min(body.vy + GRAVITY * dt, MAX_FALL_SPEED)
            new_x = self._block_walls(body, body.x + body.vx * dt)
            new_y = body.y + body.vy * dt
            body.x = new_x
            body.y = new_y
            if body.vy >= 0:
                landing = self._landing(body.x, prev_y, new_y)
                if landing is not None:
                    body.x = min(max(body.x, landing.left), landing.right)
                    body.place_on(landing)
                    body.vx = 0.0
                    event = "landed"
            if body.support is None and body.y > self.lowest_y + 400:
                # Ins Leere gefallen (Lücke zwischen Bildschirmen): auf den nächsten Boden setzen
                ground = self.ground_at(body.x) or self._nearest_ground(body.x)
                if ground is not None:
                    body.x = min(max(body.x, ground.left + half), ground.right - half)
                    body.place_on(ground)
                    event = "landed"

        body.x = min(max(body.x, self.left + half), self.right - half)
        return event

    # ---------- Hilfen ----------
    def _block_walls(self, body: Body, new_x: float) -> float:
        """Böden, die höher liegen als die Füße, wirken seitlich wie eine Wand."""
        half = body.width / 2
        lead = new_x + (half if new_x > body.x else -half)
        for p in self.platforms.values():
            if p.solid and p.spans(lead) and p.y < body.y - 2 and not p.spans(body.x):
                return body.x
        return new_x

    def _platform_at_height(self, x: float, y: float, exclude: str) -> Platform | None:
        for p in self.platforms.values():
            if p.id != exclude and p.spans(x) and abs(p.y - y) <= 2:
                return p
        return None

    def _landing(self, x: float, prev_y: float, new_y: float) -> Platform | None:
        cands = [p for p in self.platforms.values() if p.spans(x) and prev_y - 1 <= p.y <= new_y]
        return min(cands, key=lambda p: p.y) if cands else None

    def _nearest_ground(self, x: float) -> Platform | None:
        grounds = [p for p in self.platforms.values() if p.solid]
        if not grounds:
            return None
        return min(grounds, key=lambda p: min(abs(p.left - x), abs(p.right - x)))

    def platforms_near(self, body: Body, max_dx: float, max_up: float, max_down: float) -> list[Platform]:
        """Erreichbare Fensterkanten für einen Sprung."""
        out = []
        for p in self.platforms.values():
            if p.id == body.support:
                continue
            dy = p.y - body.y
            if not (-max_up <= dy <= max_down):
                continue
            if p.right - p.left < body.width * 1.5:
                continue
            nearest_x = min(max(body.x, p.left + body.width), p.right - body.width)
            if abs(nearest_x - body.x) <= max_dx:
                out.append(p)
        return out
