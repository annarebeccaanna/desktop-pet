"""Anthropic (Claude) über das offizielle ``anthropic``-SDK."""

from __future__ import annotations

from .base import AIError, AIProvider, Message, ProviderInfo

INFO = ProviderInfo(
    id="anthropic", name="Anthropic (Claude)", kind="anthropic",
    default_model="claude-opus-5-5",
    models=("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-1"),
    prefixes=("sk-ant-",), order=20, signup_url="https://console.anthropic.com/settings/keys",
)

# Serverseitiger Ersatz, falls ein Modell eine Anfrage ablehnt (nur diese Modelle unterstützen ihn)
FALLBACK_MODELS = {"claude-fable-5-1", "claude-fable-5", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
# Kurze Plauderantworten brauchen wenig Nachdenken
EFFORT_MODELS = FALLBACK_MODELS | {"claude-haiku-5-5", "claude-opus-4-8", "claude-opus-4-7", "claude-sonnet-5"}
MAX_TOKENS = 16000


class AnthropicProvider(AIProvider):
    def _client(self):
        if self.transport is not None:
            return self.transport
        try:
            import anthropic
        except ImportError:
            raise AIError("Das Paket „anthropic“ fehlt (pip install anthropic).") from None
        kwargs = {"api_key": self.api_key, "timeout": 90.0, "max_retries": 1}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        return anthropic.Anthropic(**kwargs)

    def _translate(self, exc: Exception) -> AIError:
        try:
            import anthropic
        except ImportError:  # pragma: no cover
            return AIError(self.scrub(str(exc)))
        if isinstance(exc, anthropic.AuthenticationError):
            return AIError("Der API-Key wurde abgelehnt. Bitte prüfen.")
        if isinstance(exc, anthropic.PermissionDeniedError):
            return AIError("Der API-Key darf dieses Modell nicht nutzen.")
        if isinstance(exc, anthropic.NotFoundError):
            return AIError(f"Das Modell „{self.model}“ gibt es nicht.")
        if isinstance(exc, anthropic.RateLimitError):
            return AIError("Zu viele Anfragen oder Guthaben aufgebraucht – bitte später noch einmal.")
        if isinstance(exc, anthropic.APIStatusError):
            if exc.status_code >= 500:
                return AIError(f"Anthropic hat gerade Probleme (Fehler {exc.status_code}).")
            return AIError(self.scrub(f"Fehler {exc.status_code}: {exc.message}"))
        if isinstance(exc, anthropic.APIConnectionError):
            return AIError("Keine Verbindung zu Anthropic. Internet prüfen.")
        return AIError(self.scrub(str(exc)))

    def chat(self, system: str, messages: list[Message], one_shot: bool = False) -> str:  # noqa: ARG002
        client = self._client()
        params = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "system": system,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if self.model in EFFORT_MODELS:
            params["output_config"] = {"effort": "low"}
        try:
            if self.model in FALLBACK_MODELS:
                response = client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params)
            else:
                response = client.messages.create(**params)
        except AIError:
            raise
        except Exception as exc:  # noqa: BLE001 – SDK-Fehler in verständliche Meldung übersetzen
            raise self._translate(exc) from None
        if getattr(response, "stop_reason", None) == "refusal":
            return "Dazu sage ich lieber nichts. Frag mich etwas anderes!"
        text = "".join(getattr(b, "text", "") for b in response.content if getattr(b, "type", "") == "text")
        return text.strip()

    def test_connection(self) -> str:
        client = self._client()
        try:
            client.models.retrieve(self.model)        # prüft Key und Modell, kostet nichts
        except Exception as exc:  # noqa: BLE001
            raise self._translate(exc) from None
        return f"Verbunden ✓ ({self.info.name}, {self.model})"
