"""oneAI (oneai.eu) – zwei Arten von Keys:

* ``oai-gk_…`` (Gateway): OpenAI-kompatibel unter ``<Hub>/api/openai/v1``.
* ``oai_…`` (Hub): eigene Chat-Schnittstelle des Hubs –
  ``GET /api/auth/check`` (liefert das persönliche Projekt), ``POST /api/chats``
  (neuer Chat), ``GET /api/chats/models``, ``POST /api/chats/<id>/http`` (Nachricht → Antwort).
  Der Hub merkt sich den Verlauf selbst; geschickt wird nur die neue Nachricht.

Feste Werte (Hub-Adresse, Präfixe …) stehen in ``oneai.json`` und lassen sich ohne
Codeänderung anpassen. Die Basis-URL ist im Tab KI unter „Erweitert“ änderbar (eigene Instanz).
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from ....core.log import get_logger
from .base import AIError, AIProvider, Message, ProviderInfo
from .openai_compat import OpenAICompatProvider, _error_text, _http

log = get_logger("ai.oneai")
CONFIG = Path(__file__).with_name("oneai.json")


def _load() -> dict:
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError) as exc:
        log.warning("oneai.json unlesbar: %s", exc)
        return {}


_cfg = _load()
GATEWAY_PREFIX = str(_cfg.get("gateway_prefix") or "oai-gk_")
GATEWAY_PATH = str(_cfg.get("gateway_path") or "/api/openai/v1")
INFO = ProviderInfo(
    id="oneai", name=str(_cfg.get("name") or "OneAI"), kind="oneai",
    default_model=str(_cfg.get("default_model") or ""),
    models=tuple(str(m) for m in _cfg.get("models") or ()),
    base_url=str(_cfg.get("base_url") or "https://hub.oneai.eu"),
    prefixes=tuple(str(p) for p in _cfg.get("prefixes") or ("oai-gk_", "oai_")),
    auth_header=str(_cfg.get("auth_header") or "Authorization"),
    auth_scheme=str(_cfg.get("auth_scheme") if _cfg.get("auth_scheme") is not None else "Bearer "),
    order=10, url_editable=True,
)

# Laufende Hub-Chats: (Hub, Key-Ende) -> Chat-ID. Ein neues Gespräch (erste Nachricht) legt
# einen neuen Chat an; danach geht es im selben Chat weiter.
_CHATS: dict[tuple[str, str], str] = {}


def hub_root(url: str) -> str:
    """Nur die Hub-Adresse – auch wenn jemand die Gateway-Adresse mit eingefügt hat."""
    url = (url or "").strip().rstrip("/")
    for suffix in (GATEWAY_PATH, "/v1", "/api"):
        if url.endswith(suffix):
            url = url[: -len(suffix)].rstrip("/")
    return url


class OneAIProvider(AIProvider):
    models_found: list[str] = []

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.hub = hub_root(self.base_url)

    @property
    def gateway(self) -> bool:
        return self.api_key.startswith(GATEWAY_PREFIX)

    def _gateway(self) -> OpenAICompatProvider:
        return OpenAICompatProvider(self.info, self.api_key, model=self.model,
                                    base_url=f"{self.hub}{GATEWAY_PATH}", transport=self.transport)

    # ---------- Hub ----------
    def _call(self, method: str, path: str, body: dict | None = None):
        if not self.hub:
            raise AIError("Bitte unter „Erweitert“ die Adresse des oneAI-Hubs eintragen.")
        http = self.transport or _http
        url = f"{self.hub}{path}"
        status, payload = http(method, url, {"Authorization": f"Bearer {self.api_key}",
                                             "Accept": "application/json"}, body)
        if status >= 400:
            raise _HubError(status, self.scrub(_error_text(status, payload if isinstance(payload, dict) else {}, url)))
        return payload

    def _hub_models(self) -> list[dict]:
        payload = self._call("GET", "/api/chats/models")
        models = payload if isinstance(payload, list) else (payload.get("models") or payload.get("data") or [])
        return [m for m in models if isinstance(m, dict) and m.get("id")]

    def _new_chat(self, title: str) -> str:
        auth = self._call("GET", "/api/auth/check")
        project = auth.get("personalProject") if isinstance(auth, dict) else None
        if not project:
            raise AIError("oneAI: persönliches Projekt nicht gefunden (Antwort von /api/auth/check).")
        body = {"spaceId": project, "name": title, "origin": "desktop-pets"}
        try:
            chat = self._call("POST", "/api/chats", body)
        except _HubError as exc:
            if exc.status not in (400, 422):
                raise
            body.pop("origin")                       # falls der Hub nur bekannte Herkunftswerte kennt
            chat = self._call("POST", "/api/chats", body)
        chat_id = (chat.get("chatId") or chat.get("id")) if isinstance(chat, dict) else None
        if not chat_id:
            raise AIError("oneAI: Chat konnte nicht angelegt werden.")
        return str(chat_id)

    # ---------- Schnittstelle ----------
    def list_models(self) -> list[str]:
        if self.gateway:
            return self._gateway().list_models()
        return [str(m["id"]) for m in self._hub_models()]

    def chat(self, system: str, messages: list[Message]) -> str:
        if self.gateway:
            return self._gateway().chat(system, messages)
        last = next((m.content for m in reversed(messages) if m.role == "user"), "")
        models = self._hub_models()
        if not self.model:
            if not models:
                raise AIError("oneAI: keine Modelle freigeschaltet.")
            self.model = str(models[0]["id"])
        info = next((m for m in models if m.get("id") == self.model), None)
        slot = (self.hub, self.api_key[-6:])
        fresh = len([m for m in messages if m.role == "user"]) == 1 or slot not in _CHATS
        text = last
        if fresh:
            stamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
            _CHATS[slot] = self._new_chat(f"Desktop Pets {stamp}")
            text = f"{system}\n\n---\n\n{last}"       # der Hub kennt keinen Systemtext – vorn anhängen
        body = {"message": text, "model": self.model}
        if info and info.get("reasoning"):
            body["reasoningEffort"] = "low"
        try:
            answer = self._call("POST", f"/api/chats/{_CHATS[slot]}/http", body)
        except _HubError as exc:
            if exc.status != 404 or fresh:
                raise
            _CHATS.pop(slot, None)                   # Chat im Hub gelöscht → neu anfangen
            return self.chat(system, [Message("user", last)])
        if isinstance(answer, dict):
            reply = answer.get("response") or answer.get("text") or answer.get("message") or ""
        else:
            reply = str(answer or "")
        return str(reply).strip()

    def test_connection(self) -> str:
        if self.gateway:
            gw = self._gateway()
            result = gw.test_connection()
            self.models_found, self.model = gw.models_found, gw.model
            return result.replace("Verbunden ✓", "Verbunden ✓ Gateway")
        self._call("GET", "/api/auth/check")
        names = [str(m["id"]) for m in self._hub_models()]
        self.models_found = names
        if not self.model and names:
            self.model = names[0]
        if names and self.model not in names:
            return f"Verbunden – aber das Modell „{self.model}“ ist im Hub nicht freigeschaltet. Bitte eins aus der Liste wählen."
        return f"Verbunden ✓ Hub ({self.hub}, {self.model or 'kein Modell freigeschaltet'})"


class _HubError(AIError):
    def __init__(self, status: int, text: str) -> None:
        super().__init__(text)
        self.status = status
