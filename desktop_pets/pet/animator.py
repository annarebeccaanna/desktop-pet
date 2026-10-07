"""Spielt Animationen aus einem Sprite-Sheet ab (reine Zeitlogik, ohne Qt).

Das Sheet hat eine Zeile pro Animation und eine Spalte pro Frame. Fehlt eine
Animation, wird ``idle`` gespielt.
"""

from __future__ import annotations

from .pack import AnimationDef


class Animator:
    def __init__(self, animations: dict[str, AnimationDef]) -> None:
        if "idle" not in animations:
            raise ValueError("Animation 'idle' fehlt")
        self.animations = animations
        self.name = "idle"
        self.frame = 0
        self._elapsed = 0.0
        self.finished = False

    @property
    def current(self) -> AnimationDef:
        return self.animations[self.name]

    @property
    def row(self) -> int:
        return self.current.row

    def resolve(self, name: str) -> str:
        return name if name in self.animations else "idle"

    def play(self, name: str, restart: bool = False) -> str:
        """Startet eine Animation. Gibt den tatsächlich gespielten Namen zurück."""
        name = self.resolve(name)
        if name != self.name or restart:
            self.name = name
            self.frame = 0
            self._elapsed = 0.0
            self.finished = False
        return name

    def update(self, dt: float) -> bool:
        """Schreitet um ``dt`` Sekunden fort. True, wenn sich der Frame geändert hat."""
        anim = self.current
        if anim.frames <= 1 or self.finished:
            return False
        self._elapsed += dt
        step = 1.0 / anim.fps
        changed = False
        while self._elapsed >= step:
            self._elapsed -= step
            if self.frame + 1 >= anim.frames:
                if anim.loop:
                    self.frame = 0
                else:
                    self.finished = True
                    self._elapsed = 0.0
                    return changed
            else:
                self.frame += 1
            changed = True
        return changed

    def suggested_interval_ms(self) -> int:
        """Wie oft neu gezeichnet werden muss (spart CPU im Schlaf)."""
        return max(16, int(1000 / max(self.current.fps, 0.1)))
