"""Verwaltet alle Funktionen: Ein-/Ausschalten, Ticks, Absturzsicherheit."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.events import FEATURE_TOGGLED, MODE_CHANGED, SETTINGS_CHANGED
from ..core.log import get_logger
from .base import CATEGORIES, REGISTRY, Feature

if TYPE_CHECKING:  # pragma: no cover
    from ..core.app import AppContext

log = get_logger("features")


class FeatureManager:
    def __init__(self, ctx: "AppContext", registry: dict[str, type[Feature]] | None = None) -> None:
        self.ctx = ctx
        self.features: dict[str, Feature] = {}
        self.failed: dict[str, str] = {}
        for fid, cls in (registry if registry is not None else REGISTRY).items():
            try:
                self.features[fid] = cls(ctx)
            except Exception as exc:  # noqa: BLE001
                log.exception("Funktion %s konnte nicht erzeugt werden", fid)
                self.failed[fid] = str(exc)
        ctx.bus.subscribe(MODE_CHANGED, self._on_mode_changed)
        ctx.bus.subscribe(SETTINGS_CHANGED, self._on_settings_changed)

    # ---------- Abfragen ----------
    def get(self, fid: str) -> Feature | None:
        return self.features.get(fid)

    def is_enabled(self, fid: str) -> bool:
        f = self.features.get(fid)
        return bool(f and f.enabled)

    def is_active(self, fid: str) -> bool:
        f = self.features.get(fid)
        return bool(f and f.active)

    def active_ids(self) -> frozenset[str]:
        return frozenset(fid for fid, f in self.features.items() if f.active)

    def by_category(self) -> list[tuple[str, str, list[Feature]]]:
        out = []
        for cat, label in CATEGORIES:
            items = sorted((f for f in self.features.values() if f.category == cat and f.listed),
                           key=lambda f: f.order)
            if items:
                out.append((cat, label, items))
        return out

    def counts(self) -> tuple[int, int]:
        """(aktiv, gesamt) – für die Statusleiste."""
        listed = [f for f in self.features.values() if f.listed]
        return sum(1 for f in listed if f.enabled), len(listed)

    # ---------- Schalten ----------
    def start(self) -> None:
        for fid, f in self.features.items():
            if f.available and self._wanted(f):
                self._enable(f)

    def set_enabled(self, fid: str, enabled: bool, persist: bool = True) -> bool:
        f = self.features.get(fid)
        if f is None or not f.available:
            return False
        if not enabled and f.always_on:
            return False                       # z. B. das Körbchen ist immer da
        if enabled and f.requires and not self.is_enabled(f.requires):
            return False                       # z. B. Mausjagd ohne Herumstreunen
        if persist:
            if f.settings_key:
                self.ctx.settings.set(f.settings_key, bool(enabled))
            else:
                self.ctx.settings.set_feature_enabled(fid, enabled)
        if enabled and not f.enabled:
            self._enable(f)
        elif not enabled and f.enabled:
            self._disable(f)
        if not enabled:
            # Abhängige Funktionen mit ausschalten (und so speichern) – beim Wiedereinschalten
            # bleiben sie aus, bis man sie selbst wieder anhakt.
            for child in self.dependents(fid):
                if child.enabled or (persist and self._wanted(child, ignore_parent=True)):
                    self.set_enabled(child.id, False, persist=persist)
        return f.enabled == enabled

    def dependents(self, fid: str) -> list[Feature]:
        return [f for f in self.features.values() if f.requires == fid]

    def sync_from_settings(self) -> None:
        """Nach „Abbrechen“/„Zurücksetzen“: Zustand aus den Einstellungen übernehmen."""
        for fid, f in self.features.items():
            if not f.available:
                continue
            want = self._wanted(f)
            if want != f.enabled:
                self.set_enabled(fid, want, persist=False)

    def stop(self) -> None:
        for f in self.features.values():
            if f.enabled:
                self._disable(f, publish=False)

    def tick(self, dt: float) -> None:
        for f in list(self.features.values()):
            if f.enabled:
                self._guard(f, "tick", f.tick, dt)

    # ---------- Andockpunkte ----------
    def behaviours(self) -> list:
        out = []
        for f in list(self.features.values()):
            if f.active:
                self._guard(f, "behaviours", lambda feat=f: out.extend(feat.behaviours()))
        return out

    def contribute(self, perception) -> None:
        for f in list(self.features.values()):
            if f.active:
                self._guard(f, "contribute", f.contribute, perception)

    def dispatch(self, hook: str, *args) -> None:
        """Ruft ``hook`` bei allen eingeschalteten Funktionen auf (Fehler schalten nur diese ab)."""
        for f in list(self.features.values()):
            if f.enabled:
                self._guard(f, hook, getattr(f, hook), *args)

    def menu_actions(self, where: str) -> list:
        out = []
        for f in self.features.values():
            if f.enabled:
                try:
                    out.extend(f.menu_actions(where))
                except Exception:  # noqa: BLE001
                    log.exception("Menüeinträge von %s fehlerhaft", f.id)
        return out

    # ---------- intern ----------
    def _enable(self, f: Feature) -> None:
        f.enabled = True
        if not self._guard(f, "enable", f.enable):
            return
        self.ctx.bus.publish(FEATURE_TOGGLED, feature_id=f.id, enabled=True)

    def _disable(self, f: Feature, publish: bool = True) -> None:
        f.enabled = False
        try:
            f.disable()
        except Exception:  # noqa: BLE001
            log.exception("Fehler beim Abschalten von %s", f.id)
        if publish:
            self.ctx.bus.publish(FEATURE_TOGGLED, feature_id=f.id, enabled=False)

    def _guard(self, f: Feature, what: str, fn, *args) -> bool:
        try:
            fn(*args)
            return True
        except Exception as exc:  # noqa: BLE001
            log.exception("Funktion %s ist bei %s abgestürzt und wird deaktiviert", f.id, what)
            self.failed[f.id] = f"{type(exc).__name__}: {exc}"
            self._disable(f)
            return False

    def _wanted(self, f: Feature, ignore_parent: bool = False) -> bool:
        if f.always_on:
            return True
        if f.requires and not ignore_parent:
            parent = self.features.get(f.requires)
            if parent is not None and not self._wanted(parent):
                return False
        if f.settings_key:
            return bool(self.ctx.settings.get(f.settings_key, f.default_enabled))
        return self.ctx.settings.feature_enabled(f.id, f.default_enabled)

    def _on_settings_changed(self, key, value) -> None:
        for f in self.features.values():
            if f.settings_key and f.settings_key == key and f.available and bool(value) != f.enabled:
                self.set_enabled(f.id, bool(value), persist=False)
        self.dispatch("on_settings_changed", key, value)

    def _on_mode_changed(self, mode, previous) -> None:  # noqa: ARG002
        for f in list(self.features.values()):
            if f.enabled:
                self._guard(f, "on_mode_changed", f.on_mode_changed, mode)
