"""Anbieter am Präfix des API-Keys erkennen – nur lokal, der Key wird nie zum Ausprobieren
an mehrere Anbieter geschickt."""

from __future__ import annotations

from .providers import PROVIDERS


def detect_provider(key: str) -> str | None:
    key = (key or "").strip()
    if not key:
        return None
    # Spezifischere Präfixe zuerst (z. B. „sk-ant-“ vor „sk-“)
    pairs = [(prefix, pid) for pid, info in PROVIDERS.items() for prefix in info.prefixes]
    for prefix, pid in sorted(pairs, key=lambda pp: -len(pp[0])):
        if key.startswith(prefix):
            return pid
    return None


def mask(key: str) -> str:
    """Zum Anzeigen: Anfang und die letzten vier Zeichen, Rest Punkte."""
    key = (key or "").strip()
    if not key:
        return ""
    head = key[:7] if len(key) > 16 else key[:3]
    return f"{head}…{key[-4:]}" if len(key) > 8 else "•" * len(key)
