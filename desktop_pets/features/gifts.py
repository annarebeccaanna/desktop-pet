"""Geschenke: Ab und zu bringt das Tier etwas vorbei und legt es neben sein Körbchen.

* Katze: Pixelmaus, Wollknäuel · Hund: Knochen, Ball · Drache: Edelstein, Goldmünze ·
  Axolotl: Muschel, Perle (Grafiken in ``assets/art/gifts``).
* Nur bei guter Laune, wach, ohne anderen Auftrag und nie im Pause-Modus.
* Die Geschenke liegen wie das Körbchen auf dem Desktop (hinter den Fenstern).
  Klick = annehmen: Das Tier freut sich, das Geschenk verschwindet. Höchstens 3 liegen herum.
* Wie oft: Zahnrad (selten / normal / oft). Rechtsklick aufs Tier → „Bring mir was!“.
"""

from __future__ import annotations

import random

from ..core.log import get_logger
from ..pet.brain import State
from .base import Feature, MenuAction, Option, register

log = get_logger("gifts")

GIFTS = {"cat": ("mouse", "yarn"), "dog": ("bone", "ball"), "dragon": ("gem", "coin"),
         "axolotl": ("shell", "pearl")}
NAMES = {"mouse": "eine Pixelmaus", "yarn": "ein Wollknäuel", "bone": "einen Knochen", "ball": "einen Ball",
         "gem": "einen Edelstein", "coin": "eine Goldmünze", "shell": "eine Muschel", "pearl": "eine Perle"}
INTERVALS = {"rare": (60, 120), "normal": (25, 60), "often": (8, 20)}     # Minuten
MAX_LYING = 3
MIN_MOOD = 40


@register
class Gifts(Feature):
    id = "gifts"
    name = "Geschenke"
    description = "Bringt ab und zu ein kleines Geschenk vorbei"
    category = "chaos"
    default_enabled = False          # „Chaos & Spaß“ ist laut Spezifikation ab Werk aus
    allowed_in_pause = False
    pause_label = "aus"
    order = 10
    options = [
        Option("frequency", "Wie oft", "normal", kind="choice",
               choices=[("rare", "selten (1–2 Std.)"), ("normal", "normal (25–60 Min.)"), ("often", "oft (8–20 Min.)")]),
    ]

    def __init__(self, ctx) -> None:
        super().__init__(ctx)
        self.lying: list = []                 # PropWindows auf dem Desktop
        self.rng = random.Random()
        self._next = self._schedule()
        self._carrying: str | None = None

    # ------------------------------------------------------------------ #
    def _schedule(self) -> float:
        lo, hi = INTERVALS.get(str(self.option("frequency")), INTERVALS["normal"])
        return self.rng.uniform(lo, hi) * 60.0

    @property
    def windows(self) -> list:
        return list(self.lying)

    def disable(self) -> None:
        for w in self.lying:
            w.hide()
            w.deleteLater()
        self.lying.clear()
        self._carrying = None

    def menu_actions(self, where: str) -> list[MenuAction]:
        if where != "pet" or self.ctx.modes.paused:
            return []
        return [MenuAction("Bring mir was!", lambda: self.bring(force=True), order=35)]

    def tick(self, dt: float) -> None:
        if not self.active:
            return
        self._next -= dt
        if self._next <= 0:
            self._next = self._schedule()
            self.bring()

    # ------------------------------------------------------------------ #
    def can_bring(self) -> bool:
        app = self.ctx.app
        if app is None or self.ctx.modes.paused or app.pet_hidden or app.in_bed or app.dragging:
            return False
        if app.brain.state == State.SLEEP or app.brain.task is not None or len(self.lying) >= MAX_LYING:
            return False
        return app.needs.mood >= MIN_MOOD or not app.features.is_enabled("needs")

    def bring(self, force: bool = False) -> bool:
        app = self.ctx.app
        if not self.active or app is None:
            return False
        if not self.can_bring():
            if force:
                text = ("Hier liegen schon genug Geschenke!" if len(self.lying) >= MAX_LYING
                        else "Gerade nicht – vielleicht später.")
                app.say(app.pet_name, text, 4)
            return False
        self._carrying = self.rng.choice(GIFTS.get(app.pack.id, tuple(NAMES)))
        x, _y = self._drop_point()
        app.leave_window_edge()
        app.brain.go_to(x, then=State.HAPPY, duration=1.6, run=True, tag="gift")
        log.info("bringt %s", self._carrying)
        return True

    def _drop_point(self) -> tuple[float, float]:
        """Links neben das Körbchen (nebeneinander), sonst dort, wo das Tier steht."""
        app = self.ctx.app
        bed = app.features.get("bed")
        if bed is not None and bed.visible:
            b = bed.bottom_center()
            step = 18 * app.scale_factor
            return b.x() - bed.window.width() // 2 - step * (len(self.lying) + 1), float(b.y())
        return app.body.x, app.body.y

    def on_brain_event(self, event: str) -> None:
        if event != "arrived:gift" or self._carrying is None:
            return
        gift, self._carrying = self._carrying, None
        app = self.ctx.app
        if app is None or not self.active:
            return
        self._place(gift, app.body.x + 10 * app.scale_factor * app.facing, app.body.y)
        app.hearts(2)
        app.say(app.pet_name, f"Ich hab dir {NAMES.get(gift, 'etwas')} mitgebracht!", 5)

    def _place(self, gift: str, x: float, y: float):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtGui import QPixmap

        from ..core import paths
        from ..pet.pet_window import PropWindow

        app = self.ctx.app
        pm = QPixmap(str(paths.assets_dir() / "gifts" / f"{gift}.png"))
        f = max(1, app.scale_factor)
        pm = pm.scaled(pm.width() * f, pm.height() * f, Qt.IgnoreAspectRatio, Qt.FastTransformation)
        w = PropWindow(bottom=True, draggable=True)
        w.setWindowTitle("Desktop Pets – Geschenk")
        w.setToolTip("Klicken: Geschenk annehmen")
        w.gift = gift
        w.set_pixmap(pm)
        w.place_bottom_center(QPoint(int(x), int(y)))
        w.clicked.connect(lambda win=w: self.accept(win))
        w.shown.connect(app.apply_capture)
        w.show()
        w.set_pinned_bottom(True)
        self.lying.append(w)
        return w

    def accept(self, window) -> None:
        """Geschenk angeklickt: Das Tier freut sich, das Geschenk verschwindet."""
        app = self.ctx.app
        if window in self.lying:
            self.lying.remove(window)
        window.hide()
        window.deleteLater()
        if app is None:
            return
        count = int(self.ctx.settings.get("state.gifts_received") or 0) + 1
        self.ctx.settings.set("state.gifts_received", count)
        app.needs.play(5.0)                   # angenommenes Geschenk hebt die Laune
        if not self.ctx.modes.paused and not app.pet_hidden:
            app.hearts(3)
            app.brain.set_state(State.HAPPY, 1.5)
            app.say(app.pet_name, "Freut mich, dass es dir gefällt!" if count > 1
                    else "Mein erstes Geschenk für dich – gern geschehen!", 4)
