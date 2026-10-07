"""Körbchen: eigener Schlafplatz auf dem Desktop.

* Liegt hinter allen Fenstern, aber über dem Desktop (wie ein Desktop-Icon).
* Standard: unten links über der Taskleiste; ziehbar, Position pro Bildschirm gespeichert.
* Doppelklick weckt das Tier oder schickt es schlafen; Rechtsklick: verschieben,
  ausblenden, Tier hineinschicken. Ausgeblendet → „Körbchen einblenden“ im Tray-Menü.
* Pause-Modus: Das Tier schläft im Körbchen. Es wird dann im Körbchen-Fenster
  gezeichnet – so bleibt im Pause-Modus genau ein Fenster auf dem Desktop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.modes import Mode
from ..pet.brain import State
from .base import Feature, MenuAction, register

if TYPE_CHECKING:  # pragma: no cover
    from PySide6.QtCore import QPoint

    from ..pet.pet_window import PropWindow

REASSERT_MS = 2000      # Körbchen regelmäßig wieder direkt über den Desktop legen


@register
class Bed(Feature):
    id = "bed"
    name = "Körbchen"
    description = "Eigener Schlafplatz auf dem Desktop"
    default_enabled = True
    allowed_in_pause = True
    pause_label = "schläft"
    order = 60

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.window: PropWindow | None = None
        self._timer = None

    # ------------------------------------------------------------------ #
    # Lebenszyklus
    # ------------------------------------------------------------------ #
    def _ensure_window(self) -> "PropWindow":
        if self.window is None:
            from PySide6.QtCore import QTimer

            from ..pet.pet_window import PropWindow

            self.window = PropWindow(bottom=True, draggable=True)
            self.window.setWindowTitle("Desktop Pets – Körbchen")
            self.window.doubleClicked.connect(self._on_double_click)
            self.window.rightClicked.connect(self._on_right_click)
            self.window.moved.connect(self._on_moved)
            if self.ctx.app is not None:
                self.window.shown.connect(self.ctx.app.apply_capture)
            self._timer = QTimer(self.window)
            self._timer.timeout.connect(self._reassert)
        return self.window

    def enable(self) -> None:
        self._ensure_window()
        self.on_sprites_changed()
        self._update_visibility(reposition=True)
        if self._timer is not None:
            self._timer.start(REASSERT_MS)

    def disable(self) -> None:
        app = self.ctx.app
        if app is not None and app.in_bed:
            self._leave()
        if self.window is not None:
            self.window.hide()
        if self._timer is not None:
            self._timer.stop()

    @property
    def visible(self) -> bool:
        return self.window is not None and self.window.isVisible()

    @property
    def hidden_by_user(self) -> bool:
        return bool(self.ctx.settings.get("bed.hidden"))

    def _update_visibility(self, reposition: bool = False) -> None:
        win = self._ensure_window()
        if self.enabled and not self.hidden_by_user:
            if reposition or not win.isVisible():
                win.place_bottom_center(self._saved_position())
            win.show()
            win.set_pinned_bottom(True)
        else:
            if self.ctx.app is not None and self.ctx.app.in_bed:
                self._leave()
            win.hide()

    def _reassert(self) -> None:
        if self.visible:
            self.window.set_pinned_bottom(True)

    # ------------------------------------------------------------------ #
    # Position
    # ------------------------------------------------------------------ #
    def _saved_position(self) -> "QPoint":
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QGuiApplication

        positions = self.ctx.settings.get("bed.positions") or {}
        primary = QGuiApplication.primaryScreen()
        for screen in [primary] + QGuiApplication.screens():
            saved = positions.get(screen.name())
            if saved:
                pos = QPoint(int(saved[0]), int(saved[1]))
                if screen.geometry().contains(pos - QPoint(0, 1)):
                    return pos
        g = primary.availableGeometry()
        return QPoint(g.left() + 90, g.top() + g.height())

    def _on_moved(self, bottom_center: "QPoint") -> None:
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QGuiApplication

        screen = QGuiApplication.screenAt(bottom_center - QPoint(0, 1)) or QGuiApplication.primaryScreen()
        g = screen.availableGeometry()
        pos = QPoint(bottom_center.x(), min(bottom_center.y(), g.top() + g.height()))  # nicht unter die Taskleiste
        self.window.place_bottom_center(pos)
        self.window.set_pinned_bottom(True)
        self.ctx.settings.set(f"bed.positions.{screen.name()}", [pos.x(), pos.y()])
        app = self.ctx.app
        if app is not None and app.in_bed:
            app.body.x, app.body.y = float(pos.x()), float(pos.y())

    def bottom_center(self) -> "QPoint | None":
        return self.window.bottom_center() if self.visible else None

    def bowl_anchor(self) -> "QPoint | None":
        """Wo der Napf hinkommt: rechts neben das Körbchen."""
        if not self.visible:
            return None
        from PySide6.QtCore import QPoint

        b = self.window.bottom_center()
        return QPoint(b.x() + self.window.width() // 2 + 24, b.y())

    def is_near(self, x: float, y: float) -> bool:
        app = self.ctx.app
        if app is not None and app.in_bed:
            return True
        if not self.visible:
            return False
        b = self.window.bottom_center()
        return abs(b.x() - x) < self.window.width() * 0.6 and abs(b.y() - y) < 10

    # ------------------------------------------------------------------ #
    # Tier hineinschicken
    # ------------------------------------------------------------------ #
    def send_pet(self) -> bool:
        """Tier ins Körbchen schicken. False, wenn kein Körbchen sichtbar ist."""
        app = self.ctx.app
        if app is None or not self.visible or self.ctx.modes.paused:
            return False
        target = self.window.bottom_center()
        bed_ground = app.world.ground_at(target.x())
        bed_on_ground = bed_ground is not None and abs(bed_ground.y - target.y()) < 8
        pet_ground = app.world.ground_at(app.body.x)
        if bed_on_ground and pet_ground is not None and pet_ground.id == bed_ground.id:
            # Gleicher Boden: hinlaufen (vom Fenster vorher hinunterspringen)
            app.leave_window_edge()
            app.brain.go_to(target.x(), then=State.SLEEP, duration=600, tag="bed")
        else:
            # Anderer Bildschirm oder frei platziertes Körbchen: hineinhüpfen
            app.teleport(target.x(), target.y())
            app.brain.send_to_sleep(600)
        return True

    def _on_double_click(self) -> None:
        app = self.ctx.app
        if app is None or self.ctx.modes.paused:
            return
        if app.brain.state == State.SLEEP and self.is_near(app.body.x, app.body.y):
            app.brain.wake()
        else:
            self.send_pet()

    def _on_right_click(self, pos: "QPoint") -> None:
        from PySide6.QtWidgets import QMenu

        app = self.ctx.app
        name = app.pack.bed_name if app is not None else "Körbchen"
        m = QMenu()
        m.addAction(f"{name} verschieben", self.window.start_move_mode)
        m.addAction(f"{name} ausblenden", self.hide_by_user)
        m.addAction("Tier hineinschicken", self.send_pet).setEnabled(not self.ctx.modes.paused)
        m.exec(pos)

    def hide_by_user(self) -> None:
        self.ctx.settings.set("bed.hidden", True)

    def show_by_user(self) -> None:
        self.ctx.settings.set("bed.hidden", False)

    # ------------------------------------------------------------------ #
    # Pause-Modus: im Körbchen schlafen
    # ------------------------------------------------------------------ #
    def on_mode_changed(self, mode: Mode) -> None:
        app = self.ctx.app
        if app is None:
            return
        if mode == Mode.PAUSE and self.visible and not app.in_bed:
            self._enter()
        elif mode != Mode.PAUSE and app.in_bed:
            self._leave()
            app.brain.send_to_sleep(12)

    def _enter(self) -> None:
        app = self.ctx.app
        b = self.window.bottom_center()
        app.body.x, app.body.y = float(b.x()), float(b.y())
        ground = app.world.ground_at(app.body.x)
        if ground is not None and abs(ground.y - app.body.y) < 8:
            app.body.place_on(ground)
        app.brain.send_to_sleep(1e9)
        app.animator.play("sleep", restart=True)
        app.in_bed = True
        app.pet_window.hide()
        app.render(force=True)

    def _leave(self) -> None:
        app = self.ctx.app
        app.in_bed = False
        if self.window is not None:
            self.window.set_occupant(None)
        if not app.pet_hidden:
            app.pet_window.show()
        app.render(force=True)

    def show_occupant(self, pixmap) -> None:
        if self.window is not None:
            self.window.set_occupant(pixmap)

    # ------------------------------------------------------------------ #
    # Andockpunkte
    # ------------------------------------------------------------------ #
    def on_sprites_changed(self) -> None:
        app = self.ctx.app
        if app is None or app.sprites is None:
            return
        pixmap = app.sprites.extra("bed.png")
        if pixmap is not None:
            self._ensure_window().set_pixmap(pixmap)

    def on_settings_changed(self, key: str, value) -> None:  # noqa: ARG002
        if key == "*" or key.startswith("bed.hidden"):
            self._update_visibility(reposition=key == "*")

    def menu_actions(self, where: str) -> list[MenuAction]:
        paused = self.ctx.modes.paused
        if where == "tray":
            if self.hidden_by_user:
                return [MenuAction("Körbchen einblenden", self.show_by_user, order=46)]
            return [MenuAction("Ins Körbchen schicken", self.send_pet, enabled=not paused, order=45)]
        return []
