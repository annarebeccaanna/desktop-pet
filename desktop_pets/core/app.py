"""Zentrale Steuerung: verbindet Einstellungen, Modi, Funktionen, Tier, Fenster und Tray.

Hier steht nur, was *jedes* Tier braucht: Takt, Physik, Zeichnen, Ziehen,
Pause-Modus, Einstellungen, Hotkeys. Alles Weitere bringen die Funktionen in
``features/`` selbst mit (Verhalten, Menüeinträge, eigene Fenster wie Körbchen
und Napf) – siehe ``features/base.py``.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QPoint, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import QApplication

from .. import APP_NAME
from ..pet.animator import Animator
from ..pet.brain import Brain, Perception, State
from ..pet.choreo import Choreographer
from ..pet.needs import Needs
from ..pet.pack import PetPack, discover_packs
from ..pet.physics import Body, World, jump_velocity
from ..win import capture, hotkeys as hk
from ..win.idle import IdleMonitor
from . import paths, platforms
from .events import FEATURE_TOGGLED, MODE_CHANGED, NOTIFY, PET_CHANGED, SETTINGS_CHANGED, EventBus
from .log import get_logger
from .modes import Mode, ModeManager
from .settings import Settings
from .sound import SoundPlayer

if TYPE_CHECKING:  # pragma: no cover
    from ..pet.sprites import SpriteSet

log = get_logger("app")

FAST_MS = 33          # ~30 FPS bei Bewegung
CALM_MS = 100         # sitzt/putzt
SLEEP_MS = 250        # schläft
SAVE_DELAY_MS = 600   # Einstellungen gebündelt speichern (z. B. beim Schieberegler)
REASSERT_MS = 2000    # im Pause-Modus regelmäßig wieder auf den Desktop legen


@dataclass
class AppContext:
    settings: Settings
    bus: EventBus
    modes: ModeManager
    app: "PetApp | None" = None


class PetApp(QObject):
    def __init__(self, qapp: QApplication, settings_path: Path | None = None) -> None:
        super().__init__()
        import desktop_pets.features  # noqa: F401  (registriert alle Funktionen)

        from ..features.manager import FeatureManager
        from ..pet.pet_window import PetWindow
        from ..ui import theme
        from ..ui.speech_bubble import SpeechBubble
        from ..ui.tray import TrayController

        self.qapp = qapp
        self.bus = EventBus()
        self.settings = Settings(settings_path or paths.settings_file(), self.bus).load()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self.settings.save)
        self.settings.saver = lambda: self._save_timer.start(SAVE_DELAY_MS)
        self.modes = ModeManager(self.bus)
        self.ctx = AppContext(self.settings, self.bus, self.modes, None)
        self.theme = theme.apply(qapp, self.settings.get("theme", "retro_xp"))

        self.packs: dict[str, PetPack] = discover_packs(paths.pets_dirs())
        if not self.packs:
            raise RuntimeError("Keine Tier-Pakete gefunden (pets/<id>/pet.json + sprites.png)")
        pet_id = self.settings.get("pet.type", "cat")
        self.pack = self.packs.get(pet_id) or self.packs.get("cat") or next(iter(self.packs.values()))

        self.sound = SoundPlayer()
        self._configure_sound()
        self.world = World()
        self.body = Body(x=200, y=200)
        self.needs = Needs()
        self.brain = self._make_brain(self.pack)
        self.animator = Animator(self.pack.animations)
        self.choreo = Choreographer(self.animator)
        self.sprites: SpriteSet | None = None
        self.facing = -1 if self.settings.get("pet.flip") else 1

        self.pet_window = PetWindow()
        self.bubble = SpeechBubble()
        self._heart = QPixmap(str(paths.assets_dir() / "heart.png"))
        self._zzz = QPixmap(str(paths.assets_dir() / "zzz.png"))
        self._heart_scaled = self._heart
        self._zzz_scaled = self._zzz

        self._hidden: set[str] = set()   # Gründe fürs Ausblenden: "user", "fullscreen"
        self.in_bed = False           # Tier liegt (im Pause-Modus) im Körbchen-Fenster
        self.dragging = False
        self.user_idle = 0.0
        self._last_tick = time.monotonic()
        self._cursor_prev = QCursor.pos()
        self._cursor_still = 0.0
        self._cursor_speed = 0.0
        self._zzz_timer = 0.0
        self._settings_dialog = None
        self._about = None

        self.ctx.app = self
        self.features = FeatureManager(self.ctx)
        self.idle = IdleMonitor(lambda: (QCursor.pos().x(), QCursor.pos().y()))
        self.hotkeys = hk.HotkeyManager(qapp)
        self.tray = TrayController(self)

        self._connect_pet_window()
        self.bus.subscribe(MODE_CHANGED, self._on_mode_changed)
        self.bus.subscribe(NOTIFY, lambda title, text: self.say(title, text, 9))
        self.bus.subscribe(SETTINGS_CHANGED, self._on_settings_changed)
        self.bus.subscribe(FEATURE_TOGGLED, lambda feature_id, enabled: self.register_hotkeys()
                           if self.timer.isActive() else None)
        qapp.screenAdded.connect(self._on_screen_added)
        qapp.screenRemoved.connect(lambda *_: self._on_screens_changed())
        for screen in qapp.screens():
            self._on_screen_added(screen)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._reassert_timer = QTimer(self)
        self._reassert_timer.timeout.connect(self._reassert_desktop)
        self._reassert_timer.start(REASSERT_MS)

    # ------------------------------------------------------------------ #
    # Start / Ende
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        self.update_platforms(include_windows=False)
        self._restore_memory()
        self.refresh_sprites()
        self.qapp.setWindowIcon(QIcon(self.icon_pixmap(32)))
        self.pet_window.show()
        self.render()
        self.features.start()
        self.tray.show()
        self.register_hotkeys()
        self.apply_capture()
        self._last_tick = time.monotonic()
        self.timer.start(FAST_MS)
        log.info("%s gestartet mit %s (%d Tier-Pakete)", APP_NAME, self.pack.id, len(self.packs))

    def quit(self) -> None:
        if self.settings.feature_enabled("memory", True):
            self.save_memory()
        self.timer.stop()
        self.features.stop()
        self._save_timer.stop()
        self.settings.save()
        self.hotkeys.unregister_all()
        self.tray.hide()
        for w in self._windows():
            w.hide()
        self.qapp.quit()

    # ------------------------------------------------------------------ #
    # Eigenschaften (für Menüs und Funktionen)
    # ------------------------------------------------------------------ #
    @property
    def pet_name(self) -> str:
        return self.settings.get(f"pet.names.{self.pack.id}") or self.pack.default_name or self.pack.name

    @property
    def is_sleeping(self) -> bool:
        return self.brain.state == State.SLEEP

    @property
    def capture_protected(self) -> bool:
        if not capture.is_supported():
            return False
        return bool(self.settings.get("pause.always_exclude")) or (
            self.modes.paused and bool(self.settings.get("pause.exclude_from_capture")))

    @property
    def scale_factor(self) -> int:
        size = int(self.settings.get("pet.size", 2) or 2)
        return max(1, self.pack.scale * max(1, min(3, size)))

    def pet_colors(self, pet_id: str | None = None) -> dict[str, str] | None:
        if not self.settings.feature_enabled("recolor", True):
            return None
        return self.settings.get(f"pet.colors.{pet_id or self.pack.id}") or None

    def icon_pixmap(self, size: int = 16, pet_id: str | None = None, zzz: bool = False) -> QPixmap:
        from ..pet.sprites import pet_icon

        pack = self.packs.get(pet_id or self.pack.id, self.pack)
        return pet_icon(pack, size, self.pet_colors(pack.id), zzz=zzz)

    def tray_icon_pixmap(self) -> QPixmap:
        return self.icon_pixmap(32, zzz=self.modes.paused)

    # ------------------------------------------------------------------ #
    # Aktionen (Menüs, Hotkeys)
    # ------------------------------------------------------------------ #
    def toggle_pause(self) -> None:
        self.modes.toggle_pause()

    @property
    def pet_hidden(self) -> bool:
        return bool(self._hidden)

    @property
    def hidden_by_user(self) -> bool:
        return "user" in self._hidden

    def toggle_visible(self) -> None:
        self.set_hidden("user", not self.hidden_by_user)

    def set_hidden(self, reason: str, hidden: bool) -> None:
        """Tier aus- oder einblenden. Sichtbar ist es nur, wenn kein Grund mehr dagegen spricht."""
        before = self.pet_hidden
        if hidden:
            self._hidden.add(reason)
        else:
            self._hidden.discard(reason)
        if self.pet_hidden == before:
            return
        if self.pet_hidden:
            self.pet_window.hide()
            self.bubble.dismiss()
        elif not self.in_bed:
            self.pet_window.show()
            self.render()
        self.features.dispatch("on_visibility_changed", not self.pet_hidden)

    def switch_pet(self, pet_id: str) -> None:
        if pet_id not in self.packs or pet_id == self.pack.id:
            return
        self.pack = self.packs[pet_id]
        self.settings.set("pet.type", pet_id)
        new_brain = self._make_brain(self.pack)
        new_brain.facing = self.brain.facing
        self.brain = new_brain
        self.animator = Animator(self.pack.animations)
        self.choreo = Choreographer(self.animator)
        if self.in_bed:
            self.brain.send_to_sleep(1e9)
        self.refresh_sprites()
        self.bus.publish(PET_CHANGED, pet_id=pet_id)
        if not self.modes.paused:
            self.sound.play(self.pack.sounds.get("call"), self.pack.path)

    def pet_pet(self) -> None:
        """Streicheln (Menü oder Mausbewegung über dem Tier)."""
        self.brain.petted()
        self.sound.play(self.pack.sounds.get("happy"), self.pack.path)

    def call_pet(self) -> None:
        if self.modes.paused:
            return
        self.brain.go_to(QCursor.pos().x(), then=State.HAPPY, duration=1.5, run=True, tag="call")
        self.sound.play(self.pack.sounds.get("call"), self.pack.path)

    def send_to_sleep(self) -> None:
        """„Schlafen schicken“: ins Körbchen, falls vorhanden, sonst an Ort und Stelle."""
        if self.modes.paused:
            return
        bed = self.features.get("bed")
        if not (bed and bed.enabled and bed.send_pet()):
            self.brain.send_to_sleep(600)

    def wake_pet(self) -> None:
        self.brain.wake()

    def open_settings(self) -> None:
        from ..ui.settings_dialog import SettingsDialog

        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(self)
        self._settings_dialog.open_fresh()

    def open_about(self) -> None:
        from ..ui.about import AboutDialog

        self._about = AboutDialog(self)
        self._about.show()

    # ------------------------------------------------------------------ #
    # Hilfen für Funktionen
    # ------------------------------------------------------------------ #
    def say(self, title: str, text: str, timeout: float = 6, buttons=None) -> None:
        """Sprechblase über dem Tier (im Pause-Modus nie)."""
        if self.modes.paused:
            return
        if self.pet_hidden or self.in_bed:
            self.tray.tray.showMessage(title or APP_NAME, text)
            return
        self.bubble.show_message(title, text, self.pet_window.head_anchor(), timeout, buttons)
        self.apply_capture()

    def hearts(self, count: int = 3) -> None:
        self.pet_window.add_particle(self._heart_scaled, count)

    def leave_window_edge(self, target_y: float | None = None) -> None:
        """Steht das Tier auf einem Fenster, das Ziel liegt aber woanders: zum Boden hinunter."""
        plat = self.world.platforms.get(self.body.support or "")
        if plat is not None and not plat.solid and (target_y is None or abs(plat.y - target_y) > 8):
            self.body.drop_to_ground()

    def teleport(self, x: float, y: float) -> None:
        self.body.x, self.body.y = float(x), float(y)
        self.body.vx = self.body.vy = 0.0
        ground = self.world.ground_at(self.body.x)
        if ground is not None and abs(ground.y - y) < 8:
            self.body.place_on(ground)
        else:
            self.body.support = None
        self.hearts(2)

    def save_memory(self) -> None:
        self.settings.set("state", {
            "pet": self.pack.id,
            "needs": self.needs.to_dict(),
            "x": round(self.body.x, 1),
            "y": round(self.body.y, 1),
        })

    def refresh_sprites(self, force_original: bool = False) -> None:
        from ..pet.sprites import SpriteSet

        colors = None if force_original else self.pet_colors()
        self.sprites = SpriteSet(self.pack, self.scale_factor, colors)
        self.pet_window.set_frame_size(self.sprites.frame_w, self.sprites.frame_h)
        self.body.width = self.sprites.frame_w * 0.7
        self.body.height = self.sprites.frame_h
        self._heart_scaled = self._scaled_asset(self._heart)
        self._zzz_scaled = self._scaled_asset(self._zzz)
        self.features.dispatch("on_sprites_changed")
        self.render(force=True)
        self.tray.refresh()

    def update_platforms(self, include_windows: bool) -> None:
        plats = platforms.screen_grounds()
        if include_windows:
            plats += platforms.window_edges(self.sprites.frame_h if self.sprites else 64)
        self.world.set_platforms(plats)

    def apply_capture(self) -> None:
        want = self.capture_protected
        for w in self._windows():
            if w.isVisible():
                capture.set_excluded(int(w.winId()), want)

    # ------------------------------------------------------------------ #
    # Haupt-Takt
    # ------------------------------------------------------------------ #
    def _tick(self) -> None:
        now = time.monotonic()
        dt = min(0.1, max(0.0, now - self._last_tick))   # echte Zeit – ruckelfrei auch bei Last
        self._last_tick = now

        cursor = QCursor.pos()
        moved = math.hypot(cursor.x() - self._cursor_prev.x(), cursor.y() - self._cursor_prev.y())
        self._cursor_prev = cursor
        self._cursor_speed = moved / dt if dt > 0 else 0.0
        self._cursor_still = 0.0 if moved > 1 else self._cursor_still + dt
        self.user_idle = self.idle.idle_seconds()

        self.features.tick(dt)
        if self.pet_hidden:
            return

        paused = self.modes.paused
        left, right = self.world.walk_span(self.body)
        support = self.world.platforms.get(self.body.support or "")
        perception = Perception(
            x=self.body.x, y=self.body.y, on_ground=self.body.on_ground or self.dragging, vy=self.body.vy,
            cursor=(cursor.x(), cursor.y()), cursor_speed=self._cursor_speed, cursor_still_for=self._cursor_still,
            user_idle=self.user_idle, paused=paused, features=self.features.active_ids(),
            walk_left=left, walk_right=right, hour=datetime.now().hour, mood=self.needs.mood,
            energy=self.needs.energy, hunger=self.needs.hunger, height=self.body.height,
            on_window=support is not None and not support.solid,
        )
        if not paused:
            self.features.contribute(perception)
        self.brain.behaviours = self.features.behaviours()
        intent = self.brain.tick(dt, perception)

        if self.dragging:
            pass
        elif paused and self.body.on_ground:
            self.body.vx = 0.0      # Pause: keine Bewegung über den Bildschirm
        else:
            if intent.jump_to is not None and self.body.on_ground:
                tx, ty = intent.jump_to
                self.body.support = None
                self.body.vx, self.body.vy = jump_velocity(tx - self.body.x, ty - self.body.y)
            elif self.body.on_ground:
                # Während Übergängen (hinsetzen, aufstehen, landen) steht das Tier kurz still
                self.body.vx = 0.0 if self.choreo.blocking else intent.vx * self.scale_factor / 4.0
            self.world.step(self.body, dt)

        self.facing = intent.facing
        self.choreo.update(intent.animation, dt, extras=not self.dragging, quiet=paused)
        for event in self.brain.pop_events():
            if event == "hearts":
                self.hearts(3)
            elif event == "arrived:call":
                self.sound.play(self.pack.sounds.get("call"), self.pack.path)
                self.hearts(2)
            self.features.dispatch("on_brain_event", event)

        self.pet_window.tick_particles(dt)
        if self.brain.state == State.SLEEP and not paused and not self.in_bed:
            self._zzz_timer -= dt
            if self._zzz_timer <= 0:
                self._zzz_timer = 2.5
                self.pet_window.add_particle(self._zzz_scaled, 1, life=2.2)
        self.render()
        self._adapt_timer()

    def render(self, force: bool = False) -> None:
        if self.sprites is None:
            return
        frame = self.sprites.frame(self.animator.name, self.animator.frame)
        if self.in_bed:
            bed = self.features.get("bed")
            if bed is not None:
                bed.show_occupant(frame.pixmap(self.facing))
            return
        self.pet_window.set_frame(frame, self.facing)
        self.pet_window.place_feet(self.body.x, self.body.y)
        if self.bubble.isVisible():
            self.bubble.follow(self.pet_window.head_anchor())
        if force:
            self.pet_window.update()

    def _adapt_timer(self) -> None:
        if self.brain.is_moving or self.dragging or self.pet_window.has_particles or self.bubble.isVisible():
            ms = FAST_MS
        elif self.brain.state == State.SLEEP:
            ms = SLEEP_MS
        else:
            ms = min(CALM_MS, self.animator.suggested_interval_ms())
        if self.timer.interval() != ms:
            self.timer.setInterval(ms)

    # ------------------------------------------------------------------ #
    # Tierfenster: Klick, Rechtsklick, Ziehen
    # ------------------------------------------------------------------ #
    def _connect_pet_window(self) -> None:
        pw = self.pet_window
        pw.clicked.connect(self._on_pet_clicked)
        pw.rightClicked.connect(self._on_pet_right_click)
        pw.dragStarted.connect(self._on_drag_start)
        pw.dragMoved.connect(self._on_drag_move)
        pw.dragEnded.connect(self._on_drag_end)
        pw.shown.connect(self.apply_capture)

    def _on_pet_clicked(self) -> None:
        if self.modes.paused:
            return
        if self.brain.state == State.SLEEP:
            self.brain.wake()
        else:
            self.brain.react("happy", 1.2)
            self.sound.play(self.pack.sounds.get("call"), self.pack.path)

    def _on_pet_right_click(self, pos: QPoint) -> None:
        from ..ui.tray import build_pet_menu

        build_pet_menu(self).exec(pos)

    def _on_drag_start(self) -> None:
        self.dragging = True
        self.brain.start_drag()
        self.body.support = None
        self.body.drop_through = False
        self.body.vx = self.body.vy = 0.0

    def _on_drag_move(self, feet: QPoint) -> None:
        self.body.x, self.body.y = float(feet.x()), float(feet.y())
        self.body.vx = self.body.vy = 0.0
        self.render()

    def _on_drag_end(self) -> None:
        self.dragging = False
        self.brain.end_drag()
        ground = self.world.ground_at(self.body.x)
        if ground is not None and self.body.y >= ground.y:
            self.body.place_on(ground)

    # ------------------------------------------------------------------ #
    # Modus, Einstellungen, Hotkeys
    # ------------------------------------------------------------------ #
    def _on_mode_changed(self, mode: Mode, previous: Mode) -> None:
        # Funktionen (z. B. Körbchen) haben schon reagiert – sie hören zuerst zu.
        if mode == Mode.PAUSE:
            self.sound.blocked = True
            self.bubble.dismiss()
            self.dragging = False
            if not self.in_bed:
                self.pet_window.set_pinned_bottom(True)
        elif previous == Mode.PAUSE:
            self.sound.blocked = False
            self.pet_window.set_pinned_bottom(False)
        self.apply_capture()
        self.tray.refresh()

    def _reassert_desktop(self) -> None:
        if self.modes.paused and self.pet_window.isVisible() and self.pet_window.pinned_bottom:
            self.pet_window.set_pinned_bottom(True)

    def _on_settings_changed(self, key: str, value) -> None:
        everything = key == "*"
        if everything:
            self.features.sync_from_settings()
            wanted = self.settings.get("pet.type")
            if wanted in self.packs and wanted != self.pack.id:
                self.switch_pet(wanted)
        if key == "pet.type" and value in self.packs and value != self.pack.id:
            self.switch_pet(value)
        if everything or key.startswith("pet.size") or key.startswith("pet.colors"):
            self.refresh_sprites()
        if key.startswith("pet.names"):
            self.tray.refresh()
        if everything or key.startswith("hotkeys"):
            self.register_hotkeys()
        if everything or key.startswith("pause"):
            self.apply_capture()
            self.tray.refresh()
        if everything or key.startswith("general"):
            self._configure_sound()

    def register_hotkeys(self) -> None:
        failed = []
        wanted = [("toggle_pause", self.toggle_pause), ("toggle_visible", self.toggle_visible)]
        for f in self.features.features.values():
            if f.enabled:
                wanted += f.hotkeys()
        for name in list(self.hotkeys._names):          # abgeschaltete Funktionen freigeben
            if name not in dict(wanted):
                self.hotkeys.unregister(name)
        for name, action in wanted:
            combo = self.settings.get(f"hotkeys.{name}")
            if combo and not self.hotkeys.register(name, combo, action) and self.hotkeys.available:
                failed.append(combo)
        if failed:
            self.say("Hotkey belegt", "Folgende Tastenkürzel sind schon vergeben: " + ", ".join(failed), 8)

    def _configure_sound(self) -> None:
        self.sound.configure(self.settings.get("general.volume", 70),
                             pet_sounds=self.settings.get("general.pet_sounds", True),
                             notice_sounds=self.settings.get("general.notice_sounds", True))

    def _on_screen_added(self, screen) -> None:
        screen.availableGeometryChanged.connect(lambda *_: self._on_screens_changed())
        self._on_screens_changed()

    def _on_screens_changed(self) -> None:
        self.update_platforms(include_windows=self.features.is_active("window_walking")
                              if hasattr(self, "features") else False)
        if self.body.support is not None and self.body.support not in self.world.platforms:
            self.body.support = None

    # ------------------------------------------------------------------ #
    # Sonstiges
    # ------------------------------------------------------------------ #
    def _windows(self) -> list:
        out = [self.pet_window, self.bubble]
        for f in self.features.features.values():
            out += [w for w in (getattr(f, "window", None), *getattr(f, "windows", [])) if w is not None]
        return out

    def _make_brain(self, pack: PetPack) -> Brain:
        return Brain(playfulness=pack.trait("playfulness", 0.6), laziness=pack.trait("laziness", 0.5))

    def _scaled_asset(self, pm: QPixmap) -> QPixmap:
        if pm.isNull():
            return pm
        f = max(1, self.scale_factor // 2)
        return pm.scaled(pm.width() * f, pm.height() * f, Qt.IgnoreAspectRatio, Qt.FastTransformation)

    def _restore_memory(self) -> None:
        state = self.settings.get("state") or {}
        if self.settings.feature_enabled("memory", True) and state:
            if isinstance(state.get("needs"), dict):
                self.needs = Needs.from_dict(state["needs"])
            x, y = state.get("x"), state.get("y")
            if isinstance(x, (int, float)) and QGuiApplication.screenAt(QPoint(int(x), int(y or 0) - 4)):
                self.body.x = float(x)
                ground = self.world.ground_at(self.body.x)
                if ground is not None:
                    self.body.place_on(ground)
                return
        g = QGuiApplication.primaryScreen().availableGeometry()
        self.body.x = float(g.left() + g.width() - 220)
        ground = self.world.ground_at(self.body.x)
        if ground is not None:
            self.body.place_on(ground)
        else:
            self.body.y = float(g.top() + g.height())
