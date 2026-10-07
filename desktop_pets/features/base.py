"""Basisklasse und Registry für Funktionen.

Jede Funktion ist eine Unterklasse von :class:`Feature`, die mit ``@register``
angemeldet wird. Der Einstellungsdialog baut seine Schalterliste automatisch
daraus. Fehler in einer Funktion schalten nur diese ab (siehe FeatureManager).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from ..core.app import AppContext
    from ..core.modes import Mode

CATEGORIES = [
    ("behavior", "Verhalten & Persönlichkeit"),
    ("work", "Nützlich im Arbeitsalltag"),
    ("chaos", "Chaos & Spaß"),
    ("social", "Sozial & Erweiterbar"),
]


@dataclass
class Option:
    """Eine Detail-Option (Zahnrad im Einstellungsdialog)."""

    key: str
    label: str
    default: Any
    kind: str = "int"            # "int", "bool", "choice", "text"
    minimum: int = 0
    maximum: int = 9999
    suffix: str = ""
    choices: list[tuple[str, str]] = field(default_factory=list)   # (wert, anzeige)


class Feature:
    id: str = ""
    name: str = ""
    description: str = ""
    category: str = "behavior"
    default_enabled: bool = False
    allowed_in_pause: bool = False
    pause_label: str = "aus"         # Kurztext für die Spalte „Pause:“
    available: bool = True            # False = geplant, noch nicht umgesetzt
    order: int = 100                  # Reihenfolge innerhalb der Kategorie
    options: list[Option] = []

    def __init__(self, ctx: "AppContext") -> None:
        self.ctx = ctx
        self.enabled = False

    # Lebenszyklus ---------------------------------------------------------
    def enable(self) -> None:
        """Wird beim Einschalten aufgerufen (auch beim Start)."""

    def disable(self) -> None:
        """Wird beim Ausschalten aufgerufen (auch beim Beenden)."""

    def tick(self, dt: float) -> None:
        """Optional: wird ~30× pro Sekunde aufgerufen, solange aktiv."""

    def on_mode_changed(self, mode: "Mode") -> None:
        """Optional: Moduswechsel (Normal/Pause/Schlafen)."""

    # Hilfen -----------------------------------------------------------------
    def option(self, key: str) -> Any:
        default = next((o.default for o in self.options if o.key == key), None)
        return self.ctx.settings.feature_option(self.id, key, default)

    @property
    def active(self) -> bool:
        """Aktiv und – falls im Pause-Modus – dort erlaubt."""
        if not self.enabled:
            return False
        return self.allowed_in_pause or not self.ctx.modes.paused


REGISTRY: dict[str, type[Feature]] = {}


def register(cls: type[Feature]) -> type[Feature]:
    if not cls.id:
        raise ValueError(f"{cls.__name__} hat keine id")
    REGISTRY[cls.id] = cls
    return cls


def planned(feature_id: str, name: str, description: str, category: str, pause_label: str,
            phase: str, order: int = 100) -> type[Feature]:
    """Platzhalter für noch nicht umgesetzte Funktionen (ausgegraut im Dialog)."""
    cls = type(f"Planned_{feature_id}", (Feature,), {
        "id": feature_id, "name": name, "description": f"{description} (kommt in {phase})",
        "category": category, "pause_label": pause_label, "available": False, "order": order,
    })
    return register(cls)
