"""Gemeinsame Schnittstelle aller KI-Anbieter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


class AIError(Exception):
    """Verständliche Fehlermeldung für die Oberfläche (enthält nie den Key)."""


@dataclass(frozen=True)
class ProviderInfo:
    id: str
    name: str
    kind: str                         # "anthropic" oder "openai" (OpenAI-kompatibel)
    default_model: str
    models: tuple[str, ...] = ()
    base_url: str = ""                # leer = muss eingetragen werden
    prefixes: tuple[str, ...] = ()    # Key-Präfixe für die automatische Erkennung
    order: int = 100
    url_editable: bool = False        # Basis-URL im Bereich „Erweitert“ änderbar
    auth_header: str = "Authorization"
    auth_scheme: str = "Bearer "
    signup_url: str = ""


@dataclass
class Message:
    role: str                         # "user" oder "assistant"
    content: str


@dataclass
class ChatRequest:
    system: str
    messages: list[Message] = field(default_factory=list)
    model: str = ""
    base_url: str = ""


class AIProvider:
    """``chat(request) -> Text`` und ``test_connection() -> Meldung``. Wirft :class:`AIError`."""

    def __init__(self, info: ProviderInfo, api_key: str, model: str = "", base_url: str = "",
                 transport: Callable | None = None) -> None:
        self.info = info
        self.api_key = api_key
        self.model = model or info.default_model
        self.base_url = (base_url or info.base_url).rstrip("/")
        self.transport = transport        # in Tests ersetzbar

    def chat(self, system: str, messages: list[Message], one_shot: bool = False) -> str:  # pragma: no cover
        """``one_shot``: Einzelauftrag ohne Gesprächsverlauf (z. B. Text-Werkzeuge)."""
        raise NotImplementedError

    def test_connection(self) -> str:  # pragma: no cover – abstrakt
        raise NotImplementedError

    def scrub(self, text: str) -> str:
        """Den Key aus Fehlermeldungen entfernen – er darf nie in Oberfläche oder Log landen."""
        if self.api_key and self.api_key in text:
            text = text.replace(self.api_key, "•••")
        return text
