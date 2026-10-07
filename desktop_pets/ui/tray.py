"""Tray-Icon und Kontextmenüs (Tray, Tier, Körbchen) im Retro-Stil."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QActionGroup, QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QSystemTrayIcon, QWidget, QWidgetAction

from ..win import hotkeys as hk
from . import theme as theme_mod
from .retro import pixel_label

if TYPE_CHECKING:  # pragma: no cover
    from ..core.app import PetApp


def _hotkey_text(combo: str) -> str:
    try:
        return hk.format_hotkey(combo).replace(" + ", "+")
    except hk.HotkeyError:
        return ""


def _header(menu: QMenu, icon: QPixmap, title: str, right: QWidget | None = None, dark: bool = True) -> None:
    t = theme_mod.current()
    w = QWidget(menu)
    w.setObjectName("menuHeader" if dark else "menuHeaderLight")
    w.setAttribute(Qt.WA_StyledBackground, True)
    lay = QHBoxLayout(w)
    lay.setContentsMargins(6, 5, 8, 5)
    lay.setSpacing(6)
    ico = QLabel(w)
    ico.setPixmap(icon)
    ico.setStyleSheet("background: transparent;")
    lay.addWidget(ico)
    lab = QLabel(title, w)
    lab.setFont(t.ui_font(9, bold=True))
    lab.setStyleSheet(f"color: {'white' if dark else 'black'}; background: transparent;")
    lay.addWidget(lab, 1)
    if right is not None:
        lay.addWidget(right)
    act = QWidgetAction(menu)
    act.setDefaultWidget(w)
    act.setEnabled(False)
    menu.addAction(act)


def _footer(menu: QMenu, fields: list[str]) -> None:
    w = QWidget(menu)
    w.setObjectName("menuFooter")
    w.setAttribute(Qt.WA_StyledBackground, True)
    lay = QHBoxLayout(w)
    lay.setContentsMargins(8, 5, 8, 5)
    lay.setSpacing(14)
    for text in fields:
        lab = pixel_label(text, color="pixel_green", parent=w)
        lab.setWordWrap(True)
        lay.addWidget(lab)
    lay.addStretch(1)
    act = QWidgetAction(menu)
    act.setDefaultWidget(w)
    act.setEnabled(False)
    menu.addAction(act)


class TrayController:
    def __init__(self, app: "PetApp") -> None:
        self.app = app
        self.tray = QSystemTrayIcon()
        self.menu = QMenu()
        self.menu.aboutToShow.connect(self._rebuild)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_activated)
        self._rebuild()
        self.refresh()

    def show(self) -> None:
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def hide(self) -> None:
        self.tray.hide()

    def refresh(self) -> None:
        """Icon und Tooltip nach Moduswechsel/Tierwechsel aktualisieren."""
        icon = self.app.tray_icon_pixmap()
        self.tray.setIcon(QIcon(icon))
        mode = "Pause-Modus" if self.app.modes.paused else "Normal"
        self.tray.setToolTip(f"Desktop Pets – {self.app.pet_name} ({mode})")

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self.app.toggle_pause()

    # ---------- Tray-Menü ----------
    def _rebuild(self) -> None:
        app = self.app
        m = self.menu
        m.clear()
        paused = app.modes.paused
        _header(m, app.icon_pixmap(16), "Desktop Pets")

        act_pause = QAction(f"Pause-Modus\t{_hotkey_text(app.settings.get('hotkeys.toggle_pause'))}", m)
        act_pause.setCheckable(True)
        act_pause.setChecked(paused)
        f = act_pause.font()
        f.setBold(paused)
        act_pause.setFont(f)
        act_pause.triggered.connect(lambda _=False: app.toggle_pause())
        m.addAction(act_pause)

        pets_menu = m.addMenu("Tier wählen")
        group = QActionGroup(pets_menu)
        for pack in app.packs.values():
            a = QAction(QIcon(app.icon_pixmap(16, pack.id)), pack.name, pets_menu)
            a.setCheckable(True)
            a.setChecked(pack.id == app.pack.id)
            a.triggered.connect(lambda _=False, pid=pack.id: app.switch_pet(pid))
            group.addAction(a)
            pets_menu.addAction(a)

        act_feed = m.addAction("Füttern", app.feed)
        act_feed.setEnabled(not paused and app.features.is_active("needs"))
        m.addAction("Tier zu mir rufen", app.call_pet).setEnabled(not paused)
        if app.features.is_enabled("bed"):
            m.addAction("Ins Körbchen schicken", app.send_to_bed).setEnabled(not paused)
        hide_text = "Tier einblenden" if app.pet_hidden else "Tier ausblenden"
        m.addAction(f"{hide_text}\t{_hotkey_text(app.settings.get('hotkeys.toggle_visible'))}", app.toggle_visible)
        m.addSeparator()
        m.addAction("Einstellungen …", app.open_settings)
        m.addAction("Über Desktop Pets", app.open_about)
        m.addAction("Beenden", app.quit)

        protect = "an" if app.capture_protected else "aus"
        pending = app.modes.pending_count
        fields = [f"Aufnahme-Schutz {protect}"]
        if pending:
            fields.append(f"{pending} Meldung{'en' if pending != 1 else ''} warten")
        _footer(m, fields)


def build_pet_menu(app: "PetApp") -> QMenu:
    """Rechtsklick auf das Tier: Füttern, Streicheln, Schlafen schicken, Pause-Modus."""
    m = QMenu()
    paused = app.modes.paused
    mood = app.needs.mood_label if app.features.is_enabled("needs") else ""
    mood_text = {"super": "Super Laune", "gut": "Gute Laune", "okay": "Geht so", "mies": "Schlechte Laune"}.get(mood, "")
    right = pixel_label(mood_text, color="pixel_green" if mood in ("super", "gut") else "pixel_red")
    _header(m, app.icon_pixmap(16), app.pet_name, right=right, dark=False)
    a = m.addAction("Füttern", app.feed)
    a.setEnabled(not paused and app.features.is_active("needs"))
    m.addAction("Streicheln", app.pet_pet)
    if app.is_sleeping:
        m.addAction("Aufwecken", app.wake_pet)
    else:
        m.addAction("Schlafen schicken", app.send_to_bed)
    m.addSeparator()
    act = QAction(f"Pause-Modus\t{_hotkey_text(app.settings.get('hotkeys.toggle_pause'))}", m)
    act.setCheckable(True)
    act.setChecked(paused)
    act.triggered.connect(lambda _=False: app.toggle_pause())
    m.addAction(act)
    m.addAction("Einstellungen …", app.open_settings)
    return m


def build_bed_menu(app: "PetApp") -> QMenu:
    m = QMenu()
    m.addAction(f"{app.pack.bed_name} verschieben", app.start_bed_move)
    m.addAction(f"{app.pack.bed_name} ausblenden", app.hide_bed)
    m.addAction("Tier hineinschicken", app.send_to_bed).setEnabled(not app.modes.paused)
    return m


def popup(menu: QMenu, pos: QPoint) -> None:
    menu.exec(pos)
