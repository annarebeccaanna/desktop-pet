"""Zentrale Steuerung: verbindet Einstellungen, Modi, Funktionen, Tier, Fenster und Tray."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QPoint, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QPixmap
from PySide6.QtWidgets import QApplication

from .. import APP_NAME
from ..pet.animator import Animator
from ..pet.brain import Brain, Perception, State
from ..pet.needs import Activity, FeedResult, Needs
from ..pet.pack import PetPack, discover_packs
from ..pet.physics import Body, Platform, World, jump_velocity
from ..win import capture, hotkeys as hk
from ..win.idle import IdleMonitor
from ..win.windows_enum import WinRect, list_windows, visible_top_edges
from . import paths
from .events import MODE_CHANGED, NOTIFY, PET_CHANGED, SETTINGS_CHANGED, EventBus
from .log import get_logger
from .modes import Mode, ModeManager
from .settings import Settings
from .sound import SoundPlayer

if TYPE_CHECKING:  # pragma: no cover
    from ..pet.sprites import SpriteSet

log = get_logger("app")

FAST_MS = 33        # ~30 FPS bei Bewegung
CALM_MS = 100       # sitzt/putzt
SLEEP_MS = 250      # schläft
HUNGER_NAG_EVERY = 20 * 60
PET_STROKE_NEEDED = 140.0


@dataclass
class AppContext:
    settings: Settings
    bus: EventBus
    modes: ModeManager
    app: "PetApp | None" = None


class PetApp(QObject):
    def __init__(self, qapp: QApplication, settings_path: Path | None = None) -> None:
        super().__init__()
        from ..features.manager import FeatureManager
        from ..pet.pet_window import PetWindow, PropWindow
        from ..ui import theme
        from ..ui.speech_bubble import SpeechBubble
        from ..ui.tray import TrayController
        import desktop_pets.features  # noqa: F401  (registriert alle Funktionen)

        self.qapp = qapp
        self.bus = EventBus()
        self.settings = Settings(settings_path or paths.settings_file(), self.bus).load()
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
        self.sprites: SpriteSet | None = None
        self.facing = -1 if self.settings.get("pet.flip") else 1

        self.pet_window = PetWindow()
        self.bed_window = PropWindow(bottom=True, draggable=True)
        self.bowl_window = PropWindow(bottom=False, draggable=False)
        self.bubble = SpeechBubble()
        self._heart = QPixmap(str(paths.assets_dir() / "heart.png"))
        self._zzz = QPixmap(str(paths.assets_dir() / "zzz.png"))

        self.pet_hidden = False
        self.in_bed = False           # Tier liegt (im Pause-Modus) im Körbchen-Fenster
        self._dragging = False
        self._feed_result: FeedResult | None = None
        self._last_tick = time.monotonic()
        self._cursor_prev = QCursor.pos()
        self._cursor_still = 0.0
        self._cursor_speed = 0.0
        self._stroke = 0.0
        self._stroke_decay = 0.0
        self._pet_cooldown = 0.0
        self._nag_timer = 0.0
        self._zzz_timer = 0.0
        self._settings_dialog = None
        self._about = None

        self.ctx.app = self
        self.features = FeatureManager(self.ctx)
        self.idle = IdleMonitor(lambda: (QCursor.pos().x(), QCursor.pos().y()))
        self.hotkeys = hk.HotkeyManager(qapp)
        self.tray = TrayController(self)

        self._connect_windows()
        self.bus.subscribe(MODE_CHANGED, self._on_mode_changed)
        self.bus.subscribe(NOTIFY, self._on_notify)
        self.bus.subscribe(SETTINGS_CHANGED, self._on_settings_changed)
        qapp.screenAdded.connect(lambda *_: self._on_screens_changed())
        qapp.screenRemoved.connect(lambda *_: self._on_screens_changed())
        for screen in qapp.screens():
            screen.availableGeometryChanged.connect(lambda *_: self._on_screens_changed())

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._bowl_timer = QTimer(self)
        self._bowl_timer.setSingleShot(True)
        self._bowl_timer.timeout.connect(self.bowl_window.hide)
        self._bottom_timer = QTimer(self)   # hält Körbchen/Tier im Pause-Modus hinten
        self._bottom_timer.timeout.connect(self._reassert_bottom)
        self._bottom_timer.start(3000)

    # ------------------------------------------------------------------ #
    # Start / Ende
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        self.update_platforms(include_windows=False)
        self._restore_memory()
        self.refresh_sprites()
        self._place_bed()
        from PySide6.QtGui import QIcon

        self.qapp.setWindowIcon(QIcon(self.icon_pixmap(32)))
        self.pet_window.show()
        self._render()
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
        self.hotkeys.unregister_all()
        self.tray.hide()
        for w in (self.pet_window, self.bed_window, self.bowl_window, self.bubble):
            w.hide()
        self.qapp.quit()

    # ------------------------------------------------------------------ #
    # Eigenschaften für Menüs
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

    @property
    def scale_factor(self) -> int:
        size = int(self.settings.get("pet.size", 2) or 2)
        return max(1, self.pack.scale * max(1, min(3, size)))

    # ------------------------------------------------------------------ #
    # Aktionen (Menüs, Hotkeys)
    # ------------------------------------------------------------------ #
    def toggle_pause(self) -> None:
        self.modes.toggle_pause()

    def toggle_visible(self) -> None:
        self.pet_hidden = not self.pet_hidden
        if self.pet_hidden:
            self.pet_window.hide()
            self.bubble.dismiss()
            self.bowl_window.hide()
        elif not self.in_bed:
            self.pet_window.show()
            self._render()

    def switch_pet(self, pet_id: str) -> None:
        if pet_id not in self.packs:
            return
        if pet_id != self.pack.id:
            self.pack = self.packs[pet_id]
            self.settings.set("pet.type", pet_id)
            new_brain = self._make_brain(self.pack)
            new_brain.facing = self.brain.facing
            self.brain = new_brain
            self.animator = Animator(self.pack.animations)
            self.refresh_sprites()
            self._place_bed(keep_position=True)
            if self.in_bed:
                self.brain.send_to_sleep(1e9)
            self.tray.refresh()
            self.bus.publish(PET_CHANGED, pet_id=pet_id)
            if not self.modes.paused:
                self.sound.play(self.pack.sounds.get("call"), self.pack.path)

    def feed(self) -> None:
        if self.modes.paused or not self.features.is_active("needs"):
            return
        result = self.needs.feed()
        if result == FeedResult.TURN_AWAY:
            self.brain.turn_away_and_sleep()
            self._say("", "Zu viel … *dreht sich weg und schläft*", 4)
            return
        self._feed_result = result
        bowl_pos = self._bowl_position()
        bowl = self.sprites.extra("bowl.png") if self.sprites else None
        food = self.sprites.extra("food.png") if self.sprites else None
        if bowl is not None:
            self.bowl_window.set_pixmap(bowl, food)
            self.bowl_window.place_bottom_center(bowl_pos)
            self.bowl_window.show()
            self.apply_capture()
        self._bowl_timer.stop()
        self._leave_window_edge_if_needed(bowl_pos)
        self.brain.go_to(bowl_pos.x(), then=State.EAT, duration=3.2, tag="feed")
        self.bus.publish("needs_changed", needs=self.needs)

    def pet_pet(self) -> None:
        """Streicheln über das Menü."""
        self._petted()

    def call_pet(self) -> None:
        if self.modes.paused:
            return
        pos = QCursor.pos()
        self.brain.go_to(pos.x(), then=State.HAPPY, duration=1.5, run=True, tag="call")
        self.sound.play(self.pack.sounds.get("call"), self.pack.path)

    def send_to_bed(self) -> None:
        if self.modes.paused:
            return
        if self.features.is_enabled("bed") and self.bed_window.isVisible():
            target = self.bed_window.bottom_center()
            ground = self.world.ground_at(target.x())
            on_same = ground is not None and abs(ground.y - target.y()) < 8 and self.body.support == ground.id
            if on_same:
                self.brain.go_to(target.x(), then=State.SLEEP, duration=600, tag="bed")
            else:
                self._teleport(target.x(), target.y())
                self.brain.send_to_sleep(600)
        else:
            self.brain.send_to_sleep(600)

    def wake_pet(self) -> None:
        self.brain.wake()

    def start_bed_move(self) -> None:
        if self.bed_window.isVisible():
            self.bed_window.start_move_mode()

    def hide_bed(self) -> None:
        self.settings.set("bed.hidden", True)

    def show_bed(self, show: bool) -> None:
        visible = show and not self.settings.get("bed.hidden") and self.features.is_enabled("bed")
        if visible:
            self._place_bed(keep_position=self.bed_window.isVisible())
            self.bed_window.show()
            self.bed_window.set_pinned_bottom(True)
            self.apply_capture()
        else:
            if self.in_bed:
                self._leave_bed()
            self.bed_window.hide()

    def open_settings(self) -> None:
        from ..ui.settings_dialog import SettingsDialog

        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(self)
            self._settings_dialog.destroyed.connect(lambda *_: setattr(self, "_settings_dialog", None))
        self._settings_dialog.open_fresh()

    def open_about(self) -> None:
        from ..ui.about import AboutDialog

        self._about = AboutDialog(self)
        self._about.show()

    # ------------------------------------------------------------------ #
    # Funktionen rufen diese Hilfen auf
    # ------------------------------------------------------------------ #
    def tick_needs(self, dt: float, rate: float) -> None:
        state = self.brain.state
        if state == State.SLEEP:
            activity = Activity.BED_SLEEP if self._near_bed() else Activity.SLEEP
        elif state == State.RUN:
            activity = Activity.RUN
        elif state == State.WALK:
            activity = Activity.WALK
        else:
            activity = Activity.REST
        if self.features.is_active("day_rhythm"):
            hour = datetime.now().hour
            if 22 <= hour or hour < 6:
                rate *= 0.6     # nachts alles langsamer
        self.needs.tick(dt, activity, rate)

    def save_memory(self) -> None:
        state = {
            "pet": self.pack.id,
            "needs": self.needs.to_dict(),
            "x": round(self.body.x, 1),
            "y": round(self.body.y, 1),
        }
        self.settings.set("state", state)

    def refresh_sprites(self, force_original: bool = False) -> None:
        from ..pet.sprites import SpriteSet

        colors = None if force_original else self.pet_colors()
        self.sprites = SpriteSet(self.pack, self.scale_factor, colors)
        self.pet_window.set_frame_size(self.sprites.frame_w, self.sprites.frame_h)
        self.body.width = self.sprites.frame_w * 0.7
        self.body.height = self.sprites.frame_h
        bed = self.sprites.extra("bed.png")
        if bed is not None:
            self.bed_window.set_pixmap(bed)
        self._heart_scaled = self._scaled_asset(self._heart)
        self._zzz_scaled = self._scaled_asset(self._zzz)
        self._render(force=True)
        self.tray.refresh()

    def update_platforms(self, include_windows: bool) -> None:
        platforms: list[Platform] = []
        screens = QGuiApplication.screens()
        for s in screens:
            g = s.availableGeometry()
            platforms.append(Platform(f"screen:{s.name()}", g.left(), g.left() + g.width(), g.top() + g.height(),
                                      solid=True))
        if include_windows:
            pet_h = self.sprites.frame_h if self.sprites else 64
            rects = [self._to_logical(w) for w in list_windows()]
            for e in visible_top_edges(rects):
                screen = QGuiApplication.screenAt(QPoint(int((e.left + e.right) / 2), int(e.y)))
                if screen is None:
                    continue
                g = screen.availableGeometry()
                if e.y - pet_h < g.top() or e.y > g.bottom() - 20:
                    continue
                platforms.append(Platform(e.id, e.left, e.right, e.y))
        self.world.set_platforms(platforms)

    # ------------------------------------------------------------------ #
    # Haupt-Tick
    # ------------------------------------------------------------------ #
    def _tick(self) -> None:
        now = time.monotonic()
        dt = min(0.1, max(0.0, now - self._last_tick))
        self._last_tick = now

        cursor = QCursor.pos()
        moved = math.hypot(cursor.x() - self._cursor_prev.x(), cursor.y() - self._cursor_prev.y())
        self._cursor_prev = cursor
        self._cursor_speed = moved / dt if dt > 0 else 0.0
        self._cursor_still = 0.0 if moved > 1 else self._cursor_still + dt

        idle_feature = self.features.get("idle_sleep")
        timeout = getattr(idle_feature, "timeout_seconds", 300.0)
        user_idle = self.idle.idle_seconds()
        self.modes.set_sleeping(self.features.is_active("idle_sleep") and user_idle >= timeout)

        self.features.tick(dt)
        self._pet_cooldown = max(0.0, self._pet_cooldown - dt)
        self._stroke = max(0.0, self._stroke - 60.0 * dt)

        if self.pet_hidden:
            return

        paused = self.modes.paused
        left, right = self.world.walk_span(self.body)
        targets: tuple[tuple[float, float], ...] = ()
        if self.features.is_active("window_walking") and self.body.on_ground and not paused:
            targets = self._jump_targets()
        perception = Perception(
            x=self.body.x, y=self.body.y, on_ground=self.body.on_ground or self._dragging, vy=self.body.vy,
            cursor=(cursor.x(), cursor.y()), cursor_speed=self._cursor_speed * self._chase_eagerness(),
            cursor_still_for=self._cursor_still, user_idle=user_idle, paused=paused,
            features=self.features.active_ids(), walk_left=left, walk_right=right, idle_timeout=timeout,
            hour=datetime.now().hour, mood=self.needs.mood, energy=self.needs.energy,
            hunger=self.needs.hunger, jump_targets=targets, height=self.body.height,
        )
        intent = self.brain.tick(dt, perception)
        if self._dragging:
            pass
        elif paused and self.body.on_ground:
            self.body.vx = 0.0      # Pause: keine Bewegung über den Bildschirm
        else:
            speed = self.scale_factor / 4.0
            if intent.jump_to is not None and self.body.on_ground:
                tx, ty = intent.jump_to
                vx, vy = jump_velocity(tx - self.body.x, ty - self.body.y)
                self.body.support = None
                self.body.vx, self.body.vy = vx, vy
            elif self.body.on_ground:
                self.body.vx = intent.vx * speed
            self.world.step(self.body, dt)

        self.facing = intent.facing
        self.animator.play(intent.animation)
        self.animator.update(dt)
        for event in self.brain.pop_events():
            self._on_brain_event(event)

        self._effects(dt)
        self._render()
        self._adapt_timer()

    def _effects(self, dt: float) -> None:
        self.pet_window.tick_particles(dt)
        if self.brain.state == State.SLEEP and not self.modes.paused and not self.in_bed:
            self._zzz_timer -= dt
            if self._zzz_timer <= 0:
                self._zzz_timer = 2.5
                self.pet_window.add_particle(self._zzz_scaled, 1, life=2.2)
        self._nag_timer += dt
        if self._nag_timer >= 60:
            self._nag_timer = 0.0
            self._maybe_nag()

    def _render(self, force: bool = False) -> None:
        if self.sprites is None:
            return
        frame = self.sprites.frame(self.animator.name, self.animator.frame)
        if self.in_bed:
            pm = frame.pixmap(self.facing)
            self.bed_window.set_occupant(pm)
            return
        self.pet_window.set_frame(frame, self.facing)
        self.pet_window.place_feet(self.body.x, self.body.y)
        if self.bubble.isVisible():
            self.bubble.follow(self.pet_window.head_anchor())
        if force:
            self.pet_window.update()

    def _adapt_timer(self) -> None:
        if self.brain.is_moving or self._dragging or self.pet_window.has_particles or self.bubble.isVisible():
            ms = FAST_MS
        elif self.brain.state == State.SLEEP:
            ms = SLEEP_MS
        else:
            ms = min(CALM_MS, self.animator.suggested_interval_ms())
        if self.timer.interval() != ms:
            self.timer.setInterval(ms)

    # ------------------------------------------------------------------ #
    # Gehirn-Ereignisse
    # ------------------------------------------------------------------ #
    def _on_brain_event(self, event: str) -> None:
        if event == "hearts":
            self.pet_window.add_particle(self._heart_scaled, 3)
        elif event == "caught":
            if self.features.is_active("needs"):
                self.needs.play()
            self.sound.play("jump.wav")
        elif event == "arrived:feed":
            self.sound.play(self.pack.sounds.get("eat"), self.pack.path)
        elif event == "done:feed":
            self.bowl_window.set_overlay(None)
            self._bowl_timer.start(5000)
            if self._feed_result == FeedResult.EATEN:
                self.pet_window.add_particle(self._heart_scaled, 3)
                self._say("", "Mampf! 😋", 2.5)
                self.brain.react("groom", 3.0)
            else:
                self._say("", "Bin satt.", 2.5)
                self.brain.react("sit", 3.0)
            self._feed_result = None
        elif event == "arrived:call":
            self.sound.play(self.pack.sounds.get("call"), self.pack.path)
            self.pet_window.add_particle(self._heart_scaled, 2)

    # ------------------------------------------------------------------ #
    # Interaktion mit dem Tierfenster
    # ------------------------------------------------------------------ #
    def _connect_windows(self) -> None:
        pw = self.pet_window
        pw.clicked.connect(self._on_pet_clicked)
        pw.rightClicked.connect(self._on_pet_right_click)
        pw.dragStarted.connect(self._on_drag_start)
        pw.dragMoved.connect(self._on_drag_move)
        pw.dragEnded.connect(self._on_drag_end)
        pw.stroked.connect(self._on_stroke)
        pw.shown.connect(self.apply_capture)
        bw = self.bed_window
        bw.doubleClicked.connect(self._on_bed_double_click)
        bw.rightClicked.connect(self._on_bed_right_click)
        bw.moved.connect(self._on_bed_moved)
        bw.shown.connect(self.apply_capture)
        self.bowl_window.clicked.connect(self.bowl_window.hide)
        self.bubble.closed.connect(lambda: None)

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

        menu = build_pet_menu(self)
        menu.exec(pos)

    def _on_drag_start(self) -> None:
        self._dragging = True
        self.brain.start_drag()
        self.body.support = None
        self.body.vx = self.body.vy = 0.0

    def _on_drag_move(self, feet: QPoint) -> None:
        self.body.x, self.body.y = float(feet.x()), float(feet.y())
        self.body.vx = self.body.vy = 0.0
        self._render()

    def _on_drag_end(self) -> None:
        self._dragging = False
        self.brain.end_drag()
        ground = self.world.ground_at(self.body.x)
        if ground is not None and self.body.y >= ground.y:
            self.body.y = ground.y
            self.body.place_on(ground)

    def _on_stroke(self, dist: float) -> None:
        if not self.features.is_active("petting") or self._dragging:
            return
        self._stroke += dist
        if self._stroke >= PET_STROKE_NEEDED and self._pet_cooldown <= 0:
            self._stroke = 0.0
            self._pet_cooldown = 1.2
            self._petted()

    def _petted(self) -> None:
        self.brain.petted()
        if self.features.is_active("needs"):
            self.needs.pet()
        self.sound.play(self.pack.sounds.get("happy"), self.pack.path)

    # ------------------------------------------------------------------ #
    # Körbchen
    # ------------------------------------------------------------------ #
    def _place_bed(self, keep_position: bool = False) -> None:
        if self.sprites is None:
            return
        bed = self.sprites.extra("bed.png")
        if bed is not None:
            self.bed_window.set_pixmap(bed)
        if keep_position and self.bed_window.isVisible():
            return
        positions = self.settings.get("bed.positions") or {}
        pos = None
        for screen in [QGuiApplication.primaryScreen()] + QGuiApplication.screens():
            saved = positions.get(screen.name())
            if saved:
                pos = QPoint(int(saved[0]), int(saved[1]))
                if screen.geometry().contains(pos - QPoint(0, 1)):
                    break
                pos = None
        if pos is None:
            g = QGuiApplication.primaryScreen().availableGeometry()
            pos = QPoint(g.left() + 90, g.top() + g.height())
        self.bed_window.place_bottom_center(pos)
        if self.features.is_enabled("bed") and not self.settings.get("bed.hidden"):
            self.bed_window.show()
            self.bed_window.set_pinned_bottom(True)

    def _on_bed_moved(self, bottom_center: QPoint) -> None:
        screen = QGuiApplication.screenAt(bottom_center - QPoint(0, 1)) or QGuiApplication.primaryScreen()
        g = screen.availableGeometry()
        # nicht unter die Taskleiste rutschen lassen
        y = min(bottom_center.y(), g.top() + g.height())
        pos = QPoint(bottom_center.x(), y)
        self.bed_window.place_bottom_center(pos)
        self.settings.set(f"bed.positions.{screen.name()}", [pos.x(), pos.y()])
        if self.in_bed:
            self.body.x, self.body.y = float(pos.x()), float(pos.y())

    def _on_bed_double_click(self) -> None:
        if self.modes.paused:
            return
        if self.brain.state == State.SLEEP and self._near_bed():
            self.brain.wake()
        else:
            self.send_to_bed()

    def _on_bed_right_click(self, pos: QPoint) -> None:
        from ..ui.tray import build_bed_menu

        build_bed_menu(self).exec(pos)

    def _near_bed(self) -> bool:
        if self.in_bed:
            return True
        if not self.bed_window.isVisible():
            return False
        b = self.bed_window.bottom_center()
        return abs(b.x() - self.body.x) < self.bed_window.width() * 0.6 and abs(b.y() - self.body.y) < 10

    def _enter_bed(self) -> None:
        """Pause-Modus: Tier schläft im Körbchen (ein Fenster, ganz hinten)."""
        b = self.bed_window.bottom_center()
        self.body.x, self.body.y = float(b.x()), float(b.y())
        ground = self.world.ground_at(self.body.x)
        if ground is not None and abs(ground.y - self.body.y) < 8:
            self.body.place_on(ground)
        self.brain.send_to_sleep(1e9)
        self.animator.play("sleep", restart=True)
        self.in_bed = True
        self.pet_window.hide()
        self._render(force=True)

    def _leave_bed(self) -> None:
        self.in_bed = False
        self.bed_window.set_occupant(None)
        if not self.pet_hidden:
            self.pet_window.show()
        self._render(force=True)

    def _reassert_bottom(self) -> None:
        if self.bed_window.isVisible():
            self.bed_window.set_pinned_bottom(True)
        if self.modes.paused and self.pet_window.isVisible():
            self.pet_window.set_pinned_bottom(True)

    # ------------------------------------------------------------------ #
    # Modus, Meldungen, Einstellungen
    # ------------------------------------------------------------------ #
    def _on_mode_changed(self, mode: Mode, previous: Mode) -> None:
        if mode == Mode.PAUSE:
            self.sound.blocked = True
            self.bubble.dismiss()
            self.bowl_window.hide()
            self._dragging = False
            if self.features.is_enabled("bed") and self.bed_window.isVisible():
                self._enter_bed()
            else:
                self.pet_window.set_pinned_bottom(True)
        elif previous == Mode.PAUSE:
            self.sound.blocked = False
            if self.in_bed:
                self._leave_bed()
                self.brain.send_to_sleep(12)
            self.pet_window.set_pinned_bottom(False)
        self.apply_capture()
        self.tray.refresh()

    def apply_capture(self) -> None:
        want = self.capture_protected
        for w in (self.pet_window, self.bed_window, self.bowl_window, self.bubble):
            if w.isVisible():
                capture.set_excluded(int(w.winId()), want)

    def _on_notify(self, title: str, text: str) -> None:
        self._say(title, text, 9)

    def _say(self, title: str, text: str, timeout: float = 6, buttons=None) -> None:
        if self.modes.paused:
            return
        if self.pet_hidden or self.in_bed:
            self.tray.tray.showMessage(title or APP_NAME, text)
            return
        self.bubble.show_message(title, text, self.pet_window.head_anchor(), timeout, buttons)
        self.apply_capture()

    def _maybe_nag(self) -> None:
        if not self.features.is_active("needs") or self.modes.paused:
            return
        needs_feature = self.features.get("needs")
        if not needs_feature or not needs_feature.option("nag") or not self.needs.is_hungry:
            return
        if getattr(self, "_last_nag", 0) and time.monotonic() - self._last_nag < HUNGER_NAG_EVERY:
            return
        self._last_nag = time.monotonic()
        self._say("Hunger!", f"Ein bisschen {self.pack.food} wäre jetzt toll …", 8,
                  [("Füttern", self.feed, True), ("Später", lambda: None, False)])

    def _on_settings_changed(self, key: str, value) -> None:  # noqa: ARG002
        everything = key == "*"
        if everything:
            self.features.sync_from_settings()
            if self.settings.get("pet.type") in self.packs and self.settings.get("pet.type") != self.pack.id:
                self.switch_pet(self.settings.get("pet.type"))
        if everything or key.startswith("pet.size") or key.startswith("pet.colors"):
            self.refresh_sprites()
            self._place_bed(keep_position=True)
        if key.startswith("pet.names"):
            self.tray.refresh()
        if key == "pet.type" and value in self.packs and value != self.pack.id:
            self.switch_pet(value)
        if everything or key.startswith("hotkeys"):
            self.register_hotkeys()
        if everything or key.startswith("pause"):
            self.apply_capture()
            self.tray.refresh()
        if everything or key.startswith("general"):
            self._configure_sound()
        if everything or key.startswith("bed.hidden"):
            self.show_bed(self.features.is_enabled("bed"))

    def register_hotkeys(self) -> None:
        failed = []
        for name, action in (("toggle_pause", self.toggle_pause), ("toggle_visible", self.toggle_visible)):
            combo = self.settings.get(f"hotkeys.{name}")
            if combo and not self.hotkeys.register(name, combo, action) and self.hotkeys.available:
                failed.append(combo)
        if failed:
            self._say("Hotkey belegt", "Folgende Tastenkürzel sind schon vergeben: " + ", ".join(failed), 8)

    def _configure_sound(self) -> None:
        self.sound.configure(self.settings.get("general.volume", 70), self.settings.get("general.muted", False))

    def _on_screens_changed(self) -> None:
        for screen in self.qapp.screens():
            try:
                screen.availableGeometryChanged.disconnect()
            except (RuntimeError, TypeError):
                pass
            screen.availableGeometryChanged.connect(lambda *_: self._on_screens_changed())
        self.update_platforms(include_windows=self.features.is_active("window_walking"))
        if self.body.support is not None and self.body.support not in self.world.platforms:
            self.body.support = None

    # ------------------------------------------------------------------ #
    # Hilfen
    # ------------------------------------------------------------------ #
    def _make_brain(self, pack: PetPack) -> Brain:
        return Brain(playfulness=pack.trait("playfulness", 0.6), laziness=pack.trait("laziness", 0.5))

    def _chase_eagerness(self) -> float:
        f = self.features.get("mouse_chase")
        try:
            return max(0.0, float(f.option("eagerness")) / 100.0) if f else 1.0
        except (TypeError, ValueError):
            return 1.0

    def _scaled_asset(self, pm: QPixmap) -> QPixmap:
        if pm.isNull():
            return pm
        f = max(1, self.scale_factor // 2)
        from PySide6.QtCore import Qt

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

    def _bowl_position(self) -> QPoint:
        if self.features.is_enabled("bed") and self.bed_window.isVisible():
            b = self.bed_window.bottom_center()
            return QPoint(b.x() + self.bed_window.width() // 2 + 14 * self.scale_factor // 2, b.y())
        offset = int(self.sprites.frame_w if self.sprites else 40) * self.brain.facing
        return QPoint(int(self.body.x + offset), int(self.body.y))

    def _leave_window_edge_if_needed(self, target: QPoint) -> None:
        """Steht das Tier auf einem Fenster, das Ziel liegt aber am Boden: herunterspringen."""
        plat = self.world.platforms.get(self.body.support or "")
        if plat is not None and not plat.solid and abs(plat.y - target.y()) > 8:
            self.body.drop_to_ground()

    def _teleport(self, x: float, y: float) -> None:
        self.body.x, self.body.y = float(x), float(y)
        self.body.vx = self.body.vy = 0.0
        ground = self.world.ground_at(self.body.x)
        if ground is not None and abs(ground.y - y) < 8:
            self.body.place_on(ground)
        else:
            self.body.support = None
        self.pet_window.add_particle(self._heart_scaled, 2)

    def _jump_targets(self) -> tuple[tuple[float, float], ...]:
        reach = 260 * self.scale_factor / 4
        plats = self.world.platforms_near(self.body, max_dx=reach * 1.6, max_up=reach * 1.2, max_down=reach * 3)
        out = []
        margin = self.body.width
        for p in plats:
            x = min(max(self.body.x, p.left + margin), p.right - margin)
            out.append((x, p.y))
        return tuple(out)

    def _to_logical(self, w: WinRect) -> WinRect:
        """Physische Pixel (Win32) → logische Qt-Koordinaten (pro Bildschirm skaliert)."""
        cx, cy = (w.left + w.right) / 2, w.top
        for s in QGuiApplication.screens():
            g = s.geometry()
            dpr = s.devicePixelRatio()
            nw, nh = g.width() * dpr, g.height() * dpr
            if g.left() <= cx < g.left() + nw and g.top() <= cy < g.top() + nh:
                ox, oy = g.left(), g.top()

                def conv(v: float, o: float) -> int:
                    return int(round(o + (v - o) / dpr))

                return WinRect(w.hwnd, conv(w.left, ox), conv(w.top, oy), conv(w.right, ox), conv(w.bottom, oy),
                               w.title)
        return w
