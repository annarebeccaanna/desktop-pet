"""Alle KI-Anbieter. Ein neuer Anbieter = eine neue Datei mit ``INFO`` (+ hier eintragen)."""

from __future__ import annotations

from typing import Callable

from . import anthropic, custom, gemini, groq, mistral, oneai, openai, openrouter, xai
from .anthropic import AnthropicProvider
from .base import AIError, AIProvider, Message, ProviderInfo
from .oneai import OneAIProvider
from .openai_compat import OpenAICompatProvider

PROVIDERS: dict[str, ProviderInfo] = {
    m.INFO.id: m.INFO
    for m in sorted((oneai, anthropic, openai, gemini, mistral, openrouter, groq, xai, custom),
                    key=lambda m: m.INFO.order)
}
KEY_OPTIONAL = {"custom"}      # lokale Modelle brauchen meist keinen Key


def make_provider(provider_id: str, api_key: str, model: str = "", base_url: str = "",
                  transport: Callable | None = None) -> AIProvider:
    info = PROVIDERS.get(provider_id)
    if info is None:
        raise AIError(f"Unbekannter Anbieter: {provider_id}")
    cls = {"anthropic": AnthropicProvider, "oneai": OneAIProvider}.get(info.kind, OpenAICompatProvider)
    return cls(info, api_key, model=model, base_url=base_url, transport=transport)


__all__ = ["AIError", "AIProvider", "KEY_OPTIONAL", "Message", "PROVIDERS", "ProviderInfo", "make_provider"]
