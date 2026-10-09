"""API-Keys je Anbieter im Windows-Anmeldeinformationsspeicher (Credential Manager, über
``keyring``). Nie in settings.json, nie im Log. Ohne ``keyring`` (z. B. in Tests) bleiben
Keys nur im Speicher und sind nach dem Beenden weg."""

from __future__ import annotations

from ...core.log import get_logger

log = get_logger("ai.keys")
SERVICE = "DesktopPets"
USE_KEYRING = True          # Tests schalten das ab


class KeyStore:
    def __init__(self, backend=None) -> None:
        self._memory: dict[str, str] = {}
        if backend is None and USE_KEYRING:
            try:
                import keyring

                backend = keyring
            except ImportError:
                log.warning("keyring fehlt – API-Keys werden nicht dauerhaft gespeichert")
        self._backend = backend

    @property
    def persistent(self) -> bool:
        return self._backend is not None

    @staticmethod
    def _user(provider_id: str) -> str:
        return f"ai:{provider_id}"

    def get(self, provider_id: str) -> str:
        if self._backend is not None:
            try:
                return self._backend.get_password(SERVICE, self._user(provider_id)) or ""
            except Exception as exc:  # noqa: BLE001 – Keyring-Fehler nie bis zur Oberfläche durchreichen
                log.warning("Key für %s nicht lesbar (%s)", provider_id, type(exc).__name__)
                return ""
        return self._memory.get(provider_id, "")

    def set(self, provider_id: str, key: str) -> bool:
        key = (key or "").strip()
        if not key:
            return self.delete(provider_id)
        if self._backend is not None:
            try:
                self._backend.set_password(SERVICE, self._user(provider_id), key)
                log.info("API-Key für %s gespeichert", provider_id)
                return True
            except Exception as exc:  # noqa: BLE001
                log.warning("Key für %s nicht speicherbar (%s)", provider_id, type(exc).__name__)
                return False
        self._memory[provider_id] = key
        return True

    def delete(self, provider_id: str) -> bool:
        if self._backend is not None:
            try:
                self._backend.delete_password(SERVICE, self._user(provider_id))
            except Exception:  # noqa: BLE001 – war schon leer
                pass
        self._memory.pop(provider_id, None)
        log.info("API-Key für %s gelöscht", provider_id)
        return True

    def has(self, provider_id: str) -> bool:
        return bool(self.get(provider_id))
