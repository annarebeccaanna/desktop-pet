"""OneAI – Werte stehen in ``oneai.json`` (Basis-URL, Anmeldung, Modelle), damit sie sich
ohne Codeänderung anpassen lassen. Bis dahin: OpenAI-kompatibel mit frei eintragbarer URL."""

from __future__ import annotations

import json
from pathlib import Path

from ....core.log import get_logger
from .base import ProviderInfo

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
INFO = ProviderInfo(
    id="oneai", name=str(_cfg.get("name") or "OneAI"), kind="openai",
    default_model=str(_cfg.get("default_model") or ""),
    models=tuple(str(m) for m in _cfg.get("models") or ()),
    base_url=str(_cfg.get("base_url") or ""),
    prefixes=tuple(str(p) for p in _cfg.get("prefixes") or ()),
    auth_header=str(_cfg.get("auth_header") or "Authorization"),
    auth_scheme=str(_cfg.get("auth_scheme") if _cfg.get("auth_scheme") is not None else "Bearer "),
    order=10, url_editable=True,
)
