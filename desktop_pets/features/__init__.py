"""Alle Funktionen. Import registriert sie in ``base.REGISTRY`` (Reihenfolge = Anzeige)."""

from . import behavior, mouse_chase, idle_sleep, needs, window_walking, bed, fullscreen, share_autopause, pomodoro, copilot_key, planned  # noqa: F401
from .base import REGISTRY, Feature, Option, register  # noqa: F401
