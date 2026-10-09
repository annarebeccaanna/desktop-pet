"""OpenAI-kompatible Schnittstelle (``/chat/completions``) – genutzt von OpenAI, OneAI,
Google Gemini, Mistral, OpenRouter, Groq, xAI und eigenen Endpunkten (Ollama, LM Studio …)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .base import AIError, AIProvider, Message

TIMEOUT = 60


def _parse(raw: bytes, content_type: str) -> dict | list:
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text or "{}")
    except ValueError:
        # Keine API-Antwort (z. B. Webseite, Anmeldeseite oder Sperrseite eines Firmen-Proxys)
        snippet = " ".join(text.split())[:160]
        return {"_raw": snippet, "_type": content_type}


def _http(method: str, url: str, headers: dict[str, str], body: dict | None) -> tuple[int, dict | list]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", "Accept": "application/json",
                                          "User-Agent": "DesktopPets", **headers})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, _parse(resp.read(), resp.headers.get("Content-Type", ""))
    except urllib.error.HTTPError as exc:
        return exc.code, _parse(exc.read(), exc.headers.get("Content-Type", "") if exc.headers else "")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AIError(f"Keine Verbindung zu {url.split('/')[2] if '//' in url else url} ({exc}).") from None


def not_api(payload) -> bool:
    """Kam statt JSON eine Webseite zurück?"""
    return isinstance(payload, dict) and "_raw" in payload


def _error_text(status: int, payload, url: str = "") -> str:
    payload = payload if isinstance(payload, dict) else {}
    err = payload.get("error")
    detail = err.get("message") if isinstance(err, dict) else (err if isinstance(err, str) else "")
    if not detail:
        detail = str(payload.get("message") or payload.get("detail") or "")
    where = f" – {url}" if url else ""
    if not_api(payload):
        return (f"Fehler {status}{where}: Die Antwort kam nicht von der KI-Schnittstelle, sondern war eine "
                f"Webseite (z. B. Firmen-Proxy oder falsche Adresse): „{payload['_raw']}“")
    if status == 401:
        return f"Der API-Key wurde abgelehnt (401{where}). {detail}".strip()
    if status == 403:
        return f"Zugriff verweigert (403{where}). Key gültig, aber ohne Berechtigung? {detail}".strip()
    if status == 404:
        return f"Adresse oder Modell nicht gefunden (404{where}). Basis-URL und Modell prüfen. {detail}".strip()
    if status == 429:
        return "Zu viele Anfragen oder Guthaben aufgebraucht – bitte später noch einmal."
    if status >= 500:
        return f"Der Anbieter hat gerade Probleme (Fehler {status}{where})."
    return f"Fehler {status}{where}: {detail}".strip()


class OpenAICompatProvider(AIProvider):
    models_found: list[str] = []          # nach „Verbindung testen“: was der Anbieter anbietet

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {self.info.auth_header: f"{self.info.auth_scheme}{self.api_key}"}

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        if not self.base_url:
            raise AIError("Bitte unter „Erweitert“ eine Basis-URL eintragen.")
        http = self.transport or _http
        url = f"{self.base_url}{path}"
        status, payload = http(method, url, self._headers(), body)
        if status >= 400 or not_api(payload):
            raise AIError(self.scrub(_error_text(status, payload, url)))
        return payload if isinstance(payload, (dict, list)) else {}

    def list_models(self) -> list[str]:
        payload = self._call("GET", "/models")
        data = payload.get("data", []) if isinstance(payload, dict) else payload
        return [m.get("id", "") for m in data if isinstance(m, dict) and m.get("id")]

    def chat(self, system: str, messages: list[Message], one_shot: bool = False) -> str:  # noqa: ARG002
        if not self.model:
            found = self.list_models()
            if not found:
                raise AIError("Bitte unter „Erweitert“ ein Modell eintragen.")
            self.model = found[0]
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
        names = self.list_models()
        self.models_found = names
        if not self.model and names:
            self.model = names[0]
        if names and self.model not in names:
            return f"Verbunden – aber das Modell „{self.model}“ kennt der Anbieter nicht. Bitte eins aus der Liste wählen."
        return f"Verbunden ✓ ({self.info.name}, {self.model or 'Modell wählen'})"
