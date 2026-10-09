"""Gesprächsverlauf und Persönlichkeit (reine Logik, ohne Qt)."""

from __future__ import annotations

from .providers import Message

MAX_TURNS = 8          # so viele Frage-Antwort-Paare gehen als Verlauf mit
FORGET_AFTER = 15 * 60  # s: nach so langer Pause beginnt ein neues Gespräch

BASE_RULES = (
    "Du lebst als kleines Pixeltier auf dem Windows-Desktop deines Menschen und heißt {name}. "
    "Deine Antworten erscheinen in einer kleinen Sprechblase: Antworte auf Deutsch, kurz "
    "(meist 1–3 Sätze), ohne Markdown, Tabellen oder Überschriften. Bleib in deiner Rolle, "
    "hilf aber ernsthaft und richtig, wenn du etwas gefragt wirst. Wenn eine Antwort länger "
    "sein muss, fasse dich trotzdem so knapp wie möglich."
)


SERIOUS_RULES = (
    "Du bist ein sachlicher, kompetenter Assistent. Antworte auf Deutsch, präzise, korrekt und so "
    "ausführlich wie nötig. Die Antwort wird als reiner Text angezeigt: kein Markdown (keine "
    "Sternchen, Rauten oder Tabellen); Aufzählungen mit „–“ sind in Ordnung."
)


def serious_prompt(custom: str = "") -> str:
    """Sachliche Anfrage: ohne Tier-Rolle (Spezialanweisungen aus den Einstellungen dazu)."""
    custom = (custom or "").strip()
    return f"{SERIOUS_RULES}\n\n{custom}" if custom else SERIOUS_RULES


def system_prompt(name: str, personality: str) -> str:
    rules = BASE_RULES.format(name=name or "Pixeltier")
    personality = (personality or "").strip()
    return f"{rules}\n\n{personality}" if personality else rules


class Conversation:
    def __init__(self) -> None:
        self.messages: list[Message] = []
        self.last_at = 0.0

    def reset(self) -> None:
        self.messages.clear()

    def prepare(self, text: str, now: float) -> list[Message]:
        """Nachricht anhängen und den Verlauf liefern, der an die KI geht."""
        if self.messages and now - self.last_at > FORGET_AFTER:
            self.reset()
        self.last_at = now
        self.messages.append(Message("user", text))
        self.messages = self.messages[-(MAX_TURNS * 2 + 1):]
        while self.messages and self.messages[0].role != "user":
            self.messages.pop(0)
        return list(self.messages)

    def answered(self, text: str) -> None:
        self.messages.append(Message("assistant", text))

    def failed(self) -> None:
        """Die letzte Frage kam nicht an – nicht im Verlauf lassen."""
        if self.messages and self.messages[-1].role == "user":
            self.messages.pop()
