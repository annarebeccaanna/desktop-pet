"""Alle Funktionen. Import registriert sie in ``base.REGISTRY`` (Reihenfolge = Anzeige)."""

from . import behavior, mouse_chase, idle_sleep, needs, window_walking, bed, fullscreen, share_autopause, pomodoro, dictation, text_tools, system_monitor, copilot_key, ai_chat, planned  # noqa: F401
from .base import REGISTRY, Feature, Option, register  # noqa: F401
