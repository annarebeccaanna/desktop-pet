"""Tray-Icon und Kontextmenüs (Tray, Tier, Körbchen) im Retro-Stil."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QActionGroup, QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QLabel, QMenu, QSystemTrayIcon, QWidget, QWidgetAction

from ..features.base import MenuAction
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


def _header(menu: QMenu, icon: QPixmap, title: str, right: QWidget | None = None, dark: bool = True,
            subtitle: str = "") -> None:
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
    texts = QVBoxLayout()
    texts.setSpacing(1)
    lab = QLabel(title, w)
    lab.setFont(t.ui_font(9, bold=True))
    lab.setStyleSheet(f"color: {'white' if dark else 'black'}; background: transparent;")
    texts.addWidget(lab)
    if subtitle:
        sub = pixel_label(subtitle, color="text_muted", parent=w)
        sub.setObjectName("menuValues")
        texts.addWidget(sub)
    lay.addLayout(texts, 1)
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
        share = self.app.features.get("share_autopause")
        if share is not None and share.enabled and share.sharing_app:
            mode += f", Freigabe erkannt: {share.sharing_app}"
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

        core = [
            MenuAction(f"Pause-Modus\t{_hotkey_text(app.settings.get('hotkeys.toggle_pause'))}",
                       app.toggle_pause, order=10),
            MenuAction("Tier zu mir rufen", app.call_pet, enabled=not paused, order=40),
            MenuAction(f"{'Tier einblenden' if app.hidden_by_user else 'Tier ausblenden'}"
                       f"\t{_hotkey_text(app.settings.get('hotkeys.toggle_visible'))}", app.toggle_visible, order=50),
        ]
        entries = sorted(core + app.features.menu_actions("tray"), key=lambda a: a.order)
        for entry in entries:
            if entry.order == 10:
                act = QAction(entry.label, m)
                act.setCheckable(True)
                act.setChecked(paused)
                f = act.font()
                f.setBold(paused)
                act.setFont(f)
                act.triggered.connect(lambda _=False: app.toggle_pause())
                m.addAction(act)
                self._add_pet_chooser(m)
                continue
            _add(m, entry)
        m.addSeparator()
        m.addAction("Einstellungen …", app.open_settings)
        m.addAction("Über Desktop Pets", app.open_about)
        m.addAction("Beenden", app.quit)

        protect = "an" if app.capture_protected else "aus"
        pending = app.modes.pending_count
        fields = [f"Aufnahme-Schutz {protect}"]
        if pending:
            fields.append(f"{pending} Meldung{'en' if pending != 1 else ''} warten")
        share = app.features.get("share_autopause")
        if share is not None and share.enabled and share.sharing_app:
            fields.append("Freigabe erkannt")
        _footer(m, fields)

    def _add_pet_chooser(self, m: QMenu) -> None:
        app = self.app
        pets_menu = m.addMenu("Tier wählen")
        group = QActionGroup(pets_menu)
        for pack in app.packs.values():
            a = QAction(QIcon(app.icon_pixmap(16, pack.id)), pack.name, pets_menu)
            a.setCheckable(True)
            a.setChecked(pack.id == app.pack.id)
            a.triggered.connect(lambda _=False, pid=pack.id: app.switch_pet(pid))
            group.addAction(a)
            pets_menu.addAction(a)


def _add(menu: QMenu, entry: MenuAction) -> None:
    label = entry.label + (f"\t{entry.shortcut}" if entry.shortcut else "")
    act = menu.addAction(label)
    act.triggered.connect(lambda _=False, cb=entry.callback: cb())
    act.setEnabled(entry.enabled)


def build_pet_menu(app: "PetApp") -> QMenu:
    """Rechtsklick auf das Tier: Füttern, Streicheln, Schlafen schicken, Pause-Modus …"""
    m = QMenu()
    paused = app.modes.paused
    mood = app.needs.mood_label if app.features.is_enabled("needs") else ""
    mood_text = {"super": "Super Laune", "gut": "Gute Laune", "okay": "Geht so", "mies": "Schlechte Laune"}.get(mood, "")
    right = pixel_label(mood_text, color="pixel_green" if mood in ("super", "gut") else "pixel_red")
    values = ""
    if mood:
        n = app.needs
        values = f"Hunger {round(n.hunger)} %  ·  Energie {round(n.energy)} %"
    _header(m, app.icon_pixmap(16), app.pet_name, right=right, dark=False, subtitle=values)
    core = [MenuAction("Streicheln", app.pet_pet, order=20)]
    if app.is_sleeping:
        core.append(MenuAction("Aufwecken", app.wake_pet, enabled=not paused, order=40))
    else:
        core.append(MenuAction("Schlafen schicken", app.send_to_sleep, enabled=not paused, order=40))
    for entry in sorted(core + app.features.menu_actions("pet"), key=lambda a: a.order):
        _add(m, entry)
    m.addSeparator()
    act = QAction(f"Pause-Modus\t{_hotkey_text(app.settings.get('hotkeys.toggle_pause'))}", m)
    act.setCheckable(True)
    act.setChecked(paused)
    act.triggered.connect(lambda _=False: app.toggle_pause())
    m.addAction(act)
    m.addAction("Einstellungen …", app.open_settings)
    return m


def popup(menu: QMenu, pos: QPoint) -> None:
    menu.exec(pos)
