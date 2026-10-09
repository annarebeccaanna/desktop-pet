"""OpenAI-kompatible Schnittstelle (``/chat/completions``) – genutzt von OpenAI, OneAI,
Google Gemini, Mistral, OpenRouter, Groq, xAI und eigenen Endpunkten (Ollama, LM Studio …)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .base import AIError, AIProvider, Message

TIMEOUT = 60


def _http(method: str, url: str, headers: dict[str, str], body: dict | None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8") or "{}")
        except ValueError:
            payload = {}
        return exc.code, payload
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AIError(f"Keine Verbindung zu {url.split('/')[2] if '//' in url else url} ({exc}).") from None


def _error_text(status: int, payload: dict) -> str:
    err = payload.get("error") if isinstance(payload, dict) else None
    detail = err.get("message") if isinstance(err, dict) else (err if isinstance(err, str) else "")
    if status in (401, 403):
        return "Der API-Key wurde abgelehnt. Bitte prüfen."
    if status == 404:
        return f"Modell oder Adresse nicht gefunden. {detail}".strip()
    if status == 429:
        return "Zu viele Anfragen oder Guthaben aufgebraucht – bitte später noch einmal."
    if status >= 500:
        return f"Der Anbieter hat gerade Probleme (Fehler {status})."
    return f"Fehler {status}: {detail}".strip()


class OpenAICompatProvider(AIProvider):
    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {self.info.auth_header: f"{self.info.auth_scheme}{self.api_key}"}

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        if not self.base_url:
            raise AIError("Bitte unter „Erweitert“ eine Basis-URL eintragen.")
        http = self.transport or _http
        status, payload = http(method, f"{self.base_url}{path}", self._headers(), body)
        if status >= 400:
            raise AIError(self.scrub(_error_text(status, payload)))
        return payload

    def chat(self, system: str, messages: list[Message]) -> str:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}]
            + [{"role": m.role, "content": m.content} for m in messages],
        }
        payload = self._call("POST", "/chat/completions", body)
        try:
            text = payload["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise AIError("Unerwartete Antwort vom Anbieter.") from None
        return text.strip()

    def test_connection(self) -> str:
        payload = self._call("GET", "/models")
        names = [m.get("id", "") for m in payload.get("data", []) if isinstance(m, dict)]
        if names and self.model not in names:
            return f"Verbunden – aber das Modell „{self.model}“ kennt der Anbieter nicht."
        return f"Verbunden ✓ ({self.info.name}, {self.model})"
