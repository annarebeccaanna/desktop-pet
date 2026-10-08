"""Einstellungsdialog im Retro-Stil (XP × Paint).

Tabs: Tiere (Mini-Paint), Funktionen (automatisch aus der Registry),
Pause & Freigabe, Allgemein. Änderungen wirken sofort; „Abbrechen“ stellt den
Stand beim Öffnen wieder her, „Übernehmen“ macht den aktuellen Stand zum neuen
Ausgangspunkt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QRect, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QKeyEvent, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSizePolicy, QSlider, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,
)

from .. import __version__
from ..core import paths
from ..features.base import Feature
from ..pet.recolor import PAINT_PALETTE
from ..win import IS_WINDOWS, autostart, capture
from ..win import hotkeys as hk
from . import theme as theme_mod
from .retro import InfoBalloon, RetroWindow, pixel_label

if TYPE_CHECKING:  # pragma: no cover
    from ..core.app import PetApp
    from ..pet.sprites import SpriteSet


# --------------------------------------------------------------------------- #
# Kleine Bausteine
# --------------------------------------------------------------------------- #

class PetPreview(QWidget):
    """Weiße „Leinwand“ mit animierter Tiervorschau (Klick wechselt die Animation)."""

    CYCLE = ["idle", "walk", "run", "special", "happy", "fidget", "groom", "jump", "sleep", "eat", "angry"]
    TICK_MS = 40

    def __init__(self, parent: QWidget | None = None, checker: bool = True, background: str | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(200, 180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Klicken: andere Animation zeigen")
        self._sprites: SpriteSet | None = None
        self._anim = "idle"
        self._animator = None
        self._hold = 0.0          # kurze Pause, bevor eine Einmal-Animation wiederholt wird
        self._zoom = 8
        self._flip = False
        self._checker = checker
        self._background = background
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)

    def set_sprites(self, sprites: "SpriteSet", zoom: int, flip: bool = False, anim: str | None = None) -> None:
        self._sprites = sprites
        self._zoom = zoom
        self._flip = flip
        if anim:
            self._anim = anim
        self._restart()

    def _restart(self) -> None:
        from ..pet.animator import Animator

        if self._sprites is not None:
            self._animator = Animator(self._sprites.pack.animations)
            self._anim = self._animator.play(self._anim, restart=True)
            self._hold = 0.0
            self._timer.start(self.TICK_MS)
        self.update()

    def _advance(self) -> None:
        a = self._animator
        if a is None:
            return
        if a.finished:
            # Einmal-Animationen (Sprung, Signatur …) nach kurzer Pause wiederholen
            self._hold += self.TICK_MS / 1000
            if self._hold >= 0.8:
                self._hold = 0.0
                a.play(self._anim, restart=True)
                self.update()
            return
        if a.update(self.TICK_MS / 1000):
            self.update()

    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() == Qt.LeftButton:
            i = self.CYCLE.index(self._anim) if self._anim in self.CYCLE else 0
            self._anim = self.CYCLE[(i + 1) % len(self.CYCLE)]
            self._restart()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        if self._background:
            p.fillRect(self.rect(), QColor(self._background))
        else:
            p.fillRect(self.rect(), QColor("white"))
            if self._checker:
                c = QColor("#F0F0F0")
                s = 10
                for y in range(0, self.height(), s):
                    for x in range((y // s % 2) * s, self.width(), 2 * s):
                        p.fillRect(x, y, s, s, c)
        if self._sprites is None:
            return
        frame = self._sprites.frame(self._anim, self._animator.frame if self._animator else 0)
        pm = frame.pixmap(-1 if self._flip else 1)
        fw, fh = self._sprites.pack.sprite_size
        # Vorschau ganzzahlig vergrößert, passend zur Leinwand
        base = pm.toImage().scaled(fw, fh, Qt.IgnoreAspectRatio, Qt.FastTransformation)
        zoom = max(1, min(self._zoom, (self.width() - 20) // fw, (self.height() - 20) // fh))
        big = QPixmap.fromImage(base.scaled(fw * zoom, fh * zoom, Qt.IgnoreAspectRatio, Qt.FastTransformation))
        p.drawPixmap((self.width() - big.width()) // 2, (self.height() - big.height()) // 2, big)


class Swatch(QWidget):
    """Ein Feld der Paint-Palette. Linksklick = Hauptfarbe, Rechtsklick = Zweitfarbe."""

    picked = Signal(str, bool)   # Farbe, sekundär?

    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.color = color
        self.setFixedSize(QSize(22, 16))
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"{color}\nLinksklick: Hauptfarbe · Rechtsklick: Zweitfarbe")

    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if not self.isEnabled():
            return
        if e.button() == Qt.LeftButton:
            self.picked.emit(self.color, False)
        elif e.button() == Qt.RightButton:
            self.picked.emit(self.color, True)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        r = self.rect().adjusted(0, 0, -1, -1)
        # „eingedrückter“ Rahmen wie in Paint
        p.setPen(QColor("#808080"))
        p.drawLine(r.topLeft(), r.topRight())
        p.drawLine(r.topLeft(), r.bottomLeft())
        p.setPen(QColor("white"))
        p.drawLine(r.bottomLeft(), r.bottomRight())
        p.drawLine(r.topRight(), r.bottomRight())
        inner = r.adjusted(2, 2, -1, -1)
        p.fillRect(inner, QColor(self.color) if self.isEnabled() else QColor("#D8D6CC"))
        p.setPen(QColor("#404040"))
        p.drawRect(inner.adjusted(-1, -1, 0, 0))


class ColorPair(QWidget):
    """Vorder-/Hintergrundfarbe wie in Paint (Haupt- und Zweitfarbe)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(34, 34)
        self.primary = QColor("#E89C3C")
        self.secondary = QColor("#FDF0D2")

    def set_colors(self, primary: str, secondary: str) -> None:
        self.primary, self.secondary = QColor(primary), QColor(secondary)
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setPen(QPen(QColor("#404040")))
        p.fillRect(QRect(12, 12, 18, 18), self.secondary)
        p.drawRect(QRect(12, 12, 18, 18))
        p.fillRect(QRect(3, 3, 18, 18), self.primary)
        p.drawRect(QRect(3, 3, 18, 18))


class MirrorIcon(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(18, 14)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        c = QColor("#1D4FC9")
        for i in range(5):   # ◀
            p.fillRect(QRect(1 + i, 7 - i, 1, 1 + 2 * i), c)
        p.fillRect(QRect(8, 1, 2, 12), QColor("#333333"))
        for i in range(5):   # ▶
            p.fillRect(QRect(16 - i, 7 - i, 1, 1 + 2 * i), c)


class HotkeyEdit(QLineEdit):
    """Zeigt einen Hotkey; im Aufnahmemodus wird die nächste Tastenkombination übernommen."""

    captured = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self._recording = False
        self._value = ""

    def set_value(self, combo: str) -> None:
        self._value = combo
        try:
            self.setText(hk.format_hotkey(combo))
        except hk.HotkeyError:
            self.setText(combo)

    def start(self) -> None:
        self._recording = True
        self.setText("Tastenkombination drücken … (Esc = abbrechen)")
        self.setFocus()
        self.grabKeyboard()

    def _stop(self) -> None:
        self._recording = False
        self.releaseKeyboard()
        self.set_value(self._value)

    def keyPressEvent(self, e: QKeyEvent) -> None:  # noqa: N802
        if not self._recording:
            return super().keyPressEvent(e)
        key = e.key()
        if key == Qt.Key_Escape:
            self._stop()
            return
        if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta, Qt.Key_AltGr):
            return
        parts = []
        mods = e.modifiers()
        if mods & Qt.ControlModifier:
            parts.append("Ctrl")
        if mods & Qt.AltModifier:
            parts.append("Alt")
        if mods & Qt.ShiftModifier:
            parts.append("Shift")
        if mods & Qt.MetaModifier:
            parts.append("Win")
        if Qt.Key_F1 <= key <= Qt.Key_F24:
            parts.append(f"F{key - Qt.Key_F1 + 1}")
        elif Qt.Key_A <= key <= Qt.Key_Z or Qt.Key_0 <= key <= Qt.Key_9:
            parts.append(chr(key))
        elif key == Qt.Key_Space:
            parts.append("Space")
        elif key == Qt.Key_Pause:
            parts.append("Pause")
        else:
            return
        combo = "+".join(parts)
        try:
            hk.parse_hotkey(combo)
        except hk.HotkeyError as exc:
            self.setText(f"{exc} – nochmal …")
            return
        self._value = combo
        self._stop()
        self.captured.emit(combo)

    def focusOutEvent(self, e) -> None:  # noqa: N802
        if self._recording:
            self._stop()
        super().focusOutEvent(e)


class OptionsDialog(RetroWindow):
    """Detail-Optionen einer Funktion (Zahnrad). Änderungen wirken sofort."""

    def __init__(self, app: "PetApp", feature: Feature, parent: QWidget | None = None) -> None:
        super().__init__(f"{feature.name} – Optionen", app.icon_pixmap(16), minimizable=False, parent=parent)
        self.setWindowFlag(Qt.Tool, True)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.app, self.feature = app, feature
        lay = QVBoxLayout(self.body)
        lay.setContentsMargins(12, 12, 12, 10)
        box = QGroupBox(feature.name, self.body)
        grid = QGridLayout(box)
        grid.setHorizontalSpacing(10)
        for row, opt in enumerate(feature.options):
            value = feature.option(opt.key)
            if opt.kind == "bool":
                w = QCheckBox(opt.label, box)
                w.setChecked(bool(value))
                w.toggled.connect(lambda v, k=opt.key: self._set(k, bool(v)))
                grid.addWidget(w, row, 0, 1, 2)
                continue
            grid.addWidget(QLabel(opt.label + ":", box), row, 0)
            if opt.kind == "int":
                w = QSpinBox(box)
                w.setRange(opt.minimum, opt.maximum)
                w.setSuffix(opt.suffix)
                w.setValue(int(value))
                w.valueChanged.connect(lambda v, k=opt.key: self._set(k, int(v)))
            elif opt.kind == "choice":
                w = QComboBox(box)
                for val, label in opt.choices:
                    w.addItem(label, val)
                idx = max(0, w.findData(value))
                w.setCurrentIndex(idx)
                w.currentIndexChanged.connect(lambda _i, k=opt.key, cb=w: self._set(k, cb.currentData()))
            else:
                w = QLineEdit(str(value), box)
                w.editingFinished.connect(lambda k=opt.key, le=w: self._set(k, le.text()))
            grid.addWidget(w, row, 1)
        lay.addWidget(box)
        btns = QHBoxLayout()
        btns.addStretch(1)
        ok = QPushButton("OK", self.body)
        ok.clicked.connect(self.close)
        btns.addWidget(ok)
        lay.addLayout(btns)
        self.resize(340, 60 + 34 * max(1, len(feature.options)) + 70)

    def _set(self, key: str, value) -> None:
        self.app.settings.set_feature_option(self.feature.id, key, value)


# --------------------------------------------------------------------------- #
# Der Dialog
# --------------------------------------------------------------------------- #

class SettingsDialog(RetroWindow):
    def __init__(self, app: "PetApp") -> None:
        super().__init__("Desktop Pets - Einstellungen", app.icon_pixmap(16))
        self.app = app
        self.settings = app.settings
        self._snapshot = self.settings.snapshot()
        self._building = False
        self._feature_boxes: dict[str, QCheckBox] = {}
        self._build_menu_bar()

        lay = QVBoxLayout(self.body)
        lay.setContentsMargins(10, 10, 10, 8)
        lay.setSpacing(8)
        self.tabs = QTabWidget(self.body)
        self.tabs.setDocumentMode(False)
        self.tabs.addTab(self._build_pets_tab(), "Tiere")
        self.tabs.addTab(self._build_features_tab(), "Funktionen")
        self.tabs.addTab(self._build_pause_tab(), "Pause && Freigabe")
        self.tabs.addTab(self._build_general_tab(), "Allgemein")
        self.tabs.currentChanged.connect(lambda _i: self._update_status())
        lay.addWidget(self.tabs, 1)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_ok = QPushButton("OK", self.body)
        self.btn_cancel = QPushButton("Abbrechen", self.body)
        self.btn_apply = QPushButton("Übernehmen", self.body)
        self.btn_apply.setObjectName("primary")
        for b in (self.btn_ok, self.btn_cancel, self.btn_apply):
            b.setMinimumWidth(86)
            btns.addWidget(b)
        self.btn_ok.clicked.connect(self._ok)
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_apply.clicked.connect(self._apply)
        lay.addLayout(btns)
        self.add_status_bar()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_status)
        self._status_timer.start(2000)
        self.app.bus.subscribe("mode_changed", self._on_mode_changed)
        self.app.bus.subscribe("feature_toggled", self._on_feature_toggled)
        self.resize(760, 664)
        self._refresh_all()

    # ---------- Menüleiste ----------
    def _build_menu_bar(self) -> None:
        """Datei | Tier | Ansicht | ? – wie in XP-Programmen. „Tier wählen“ steckt im Menü Tier."""
        bar = self.add_menu_bar()

        m_file = bar.addMenu("&Datei")
        m_file.addAction("Übernehmen\tStrg+S", self._apply)
        m_file.addAction("Änderungen verwerfen", self._revert)
        m_file.addSeparator()
        m_file.addAction("Schließen", self.close)

        self.menu_pet = bar.addMenu("&Tier")
        self.menu_pet.aboutToShow.connect(self._fill_pet_menu)
        self._fill_pet_menu()

        m_view = bar.addMenu("&Ansicht")
        m_view.aboutToShow.connect(lambda: self._fill_view_menu(m_view))

        m_help = bar.addMenu("&?")
        m_help.addAction("Über Desktop Pets", self.app.open_about)

        from PySide6.QtGui import QKeySequence, QShortcut

        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._apply)

    def _fill_pet_menu(self) -> None:
        from PySide6.QtGui import QAction, QActionGroup

        app = self.app
        m = self.menu_pet
        m.clear()
        choose = m.addMenu("Tier wählen")
        group = QActionGroup(choose)
        for pack in app.packs.values():
            act = QAction(QIcon(app.icon_pixmap(16, pack.id)), pack.name, choose)
            act.setCheckable(True)
            act.setChecked(pack.id == app.pack.id)
            if pack.id == app.pack.id:   # Haken wird vom Icon verdeckt – darum zusätzlich fett
                font = act.font()
                font.setBold(True)
                act.setFont(font)
            act.triggered.connect(lambda _=False, pid=pack.id: self.select_pet(pid))
            group.addAction(act)
            choose.addAction(act)
        size_menu = m.addMenu("Größe")
        size_group = QActionGroup(size_menu)
        current = int(self.settings.get("pet.size", 2) or 2)
        for n in (1, 2, 3):
            act = QAction(f"{n}×", size_menu)
            act.setCheckable(True)
            act.setChecked(n == current)
            act.triggered.connect(lambda _=False, size=n: self._set_size(size))
            size_group.addAction(act)
            size_menu.addAction(act)
        m.addAction("Spiegeln", self._on_flip)
        reset = m.addAction("Originalfarben", self._on_reset_colors)
        reset.setEnabled(app.features.is_enabled("recolor"))
        m.addSeparator()
        m.addAction("Tier umbenennen …", self._rename_pet)

    def _fill_view_menu(self, menu) -> None:
        from PySide6.QtGui import QAction, QActionGroup

        menu.clear()
        group = QActionGroup(menu)
        for i in range(self.tabs.count()):
            act = QAction(self.tabs.tabText(i), menu)
            act.setCheckable(True)
            act.setChecked(i == self.tabs.currentIndex())
            act.triggered.connect(lambda _=False, idx=i: self.tabs.setCurrentIndex(idx))
            group.addAction(act)
            menu.addAction(act)

    def select_pet(self, pet_id: str) -> None:
        """Tier wechseln – aus dem Menü oder der Liste; hält beide in Sync."""
        self.app.switch_pet(pet_id)
        self._building = True
        for i in range(self.pet_list.count()):
            item = self.pet_list.item(i)
            if item.data(Qt.UserRole) == self.app.pack.id:
                self.pet_list.setCurrentItem(item)
        self.name_edit.setText(self.app.pet_name)
        self._building = False
        self.title_bar.set_icon(self.app.icon_pixmap(16))
        self._refresh_preview()
        self._update_status()

    def _set_size(self, n: int) -> None:
        btn = self.size_group.button(n)
        if btn is not None:
            btn.setChecked(True)
        self._on_size(n)

    def _rename_pet(self) -> None:
        self.tabs.setCurrentIndex(0)
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _revert(self) -> None:
        self.settings.restore(self._snapshot)
        self._refresh_all()
        self._update_status("Verworfen")

    # ---------- öffnen / schließen ----------
    def open_fresh(self) -> None:
        self._snapshot = self.settings.snapshot()
        self._refresh_all()
        if not self.isVisible():
            self.show()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _ok(self) -> None:
        self.close()

    def _apply(self) -> None:
        self._snapshot = self.settings.snapshot()
        self.settings.save()
        self._update_status("Gespeichert")

    def _cancel(self) -> None:
        self.settings.restore(self._snapshot)
        self.close()

    def _refresh_all(self) -> None:
        self._building = True
        try:
            self._refresh_pets_tab()
            self._refresh_features_tab()
            self._refresh_pause_tab()
            self._refresh_general_tab()
        finally:
            self._building = False
        self._update_status()

    # ------------------------------------------------------------------ #
    # Tab 1: Tiere (Mini-Paint)
    # ------------------------------------------------------------------ #
    def _build_pets_tab(self) -> QWidget:
        t = theme_mod.current()
        page = QWidget()
        page.setAutoFillBackground(False)
        outer = QHBoxLayout(page)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(10)

        # Werkzeugleiste links
        tools = QFrame(page)
        tools.setObjectName("panel")
        tools.setStyleSheet(f"QFrame#panel {{ background: {t.colors['dialog_bg']}; border: 1px solid #C9C7BA; }}")
        tools.setFixedWidth(62)
        tl = QVBoxLayout(tools)
        tl.setContentsMargins(6, 8, 6, 8)
        tl.setSpacing(6)
        lab = QLabel("Größe", tools)
        lab.setObjectName("muted")
        lab.setAlignment(Qt.AlignCenter)
        tl.addWidget(lab)
        self.size_group = QButtonGroup(self)
        for n in (1, 2, 3):
            b = QPushButton(f"{n}×", tools)
            b.setObjectName("tool")
            b.setCheckable(True)
            b.setToolTip(f"Tier in {n}-facher Größe")
            self.size_group.addButton(b, n)
            tl.addWidget(b)
        self.size_group.idClicked.connect(self._on_size)
        line = QFrame(tools)
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #C9C7BA;")
        tl.addWidget(line)
        self.btn_flip = QPushButton("", tools)
        self.btn_flip.setObjectName("tool")
        self.btn_flip.setToolTip("Blickrichtung spiegeln")
        fl = QHBoxLayout(self.btn_flip)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.addWidget(MirrorIcon(self.btn_flip), 0, Qt.AlignCenter)
        self.btn_flip.clicked.connect(self._on_flip)
        tl.addWidget(self.btn_flip)
        lab2 = QLabel("Spiegeln", tools)
        lab2.setObjectName("muted")
        lab2.setAlignment(Qt.AlignCenter)
        tl.addWidget(lab2)
        tl.addStretch(1)
        outer.addWidget(tools)

        # Mitte: Leinwand, Name, Palette
        mid = QVBoxLayout()
        mid.setSpacing(8)
        canvas_frame = QFrame(page)
        canvas_frame.setObjectName("sunken")
        canvas_frame.setStyleSheet("QFrame#sunken { border: 2px solid; border-color: #808080 #FFFFFF #FFFFFF #808080;"
                                   " background: white; }")
        cf = QVBoxLayout(canvas_frame)
        cf.setContentsMargins(2, 2, 2, 2)
        self.preview = PetPreview(canvas_frame)
        cf.addWidget(self.preview)
        mid.addWidget(canvas_frame, 1)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:", page))
        self.name_edit = QLineEdit(page)
        self.name_edit.setMaxLength(24)
        self.name_edit.setMaximumWidth(190)
        self.name_edit.editingFinished.connect(self._on_name)
        name_row.addWidget(self.name_edit)
        name_row.addStretch(1)
        self.btn_reset_colors = QPushButton("Originalfarben", page)
        self.btn_reset_colors.clicked.connect(self._on_reset_colors)
        name_row.addWidget(self.btn_reset_colors)
        mid.addLayout(name_row)

        pal = QFrame(page)
        pal.setObjectName("panel")
        pal.setStyleSheet(f"QFrame#panel {{ background: {t.colors['dialog_bg']}; border: 1px solid #C9C7BA; }}")
        pl = QHBoxLayout(pal)
        pl.setContentsMargins(6, 5, 6, 5)
        pl.setSpacing(8)
        self.color_pair = ColorPair(pal)
        pl.addWidget(self.color_pair)
        grid = QGridLayout()
        grid.setSpacing(1)
        self.swatches: list[Swatch] = []
        for i, color in enumerate(PAINT_PALETTE):
            sw = Swatch(color, pal)
            sw.picked.connect(self._on_color)
            grid.addWidget(sw, i // 14, i % 14)
            self.swatches.append(sw)
        pl.addLayout(grid)
        pl.addStretch(1)
        mid.addWidget(pal)
        outer.addLayout(mid, 1)

        # Rechts: Tierliste
        right = QVBoxLayout()
        head = QLabel("Tier wählen", page)
        head.setStyleSheet(f"color: {t.colors['group_title']}; font-weight: bold; font-size: 9pt;")
        right.addWidget(head)
        self.pet_list = QListWidget(page)
        self.pet_list.setIconSize(QSize(32, 32))
        self.pet_list.setFixedWidth(176)
        self.pet_list.currentItemChanged.connect(self._on_pet_selected)
        right.addWidget(self.pet_list, 1)
        right.addWidget(InfoBalloon("Neue Tiere: Ordner in <b>pets/</b> ablegen. Sie erscheinen hier automatisch.",
                                    icon=False, parent=page))
        outer.addLayout(right)
        return page

    def _refresh_pets_tab(self) -> None:
        app = self.app
        self.pet_list.blockSignals(True)
        self.pet_list.clear()
        for pack in app.packs.values():
            item = QListWidgetItem(QIcon(app.icon_pixmap(32, pack.id)), pack.name)
            item.setData(Qt.UserRole, pack.id)
            item.setSizeHint(QSize(160, 44))
            self.pet_list.addItem(item)
            if pack.id == app.pack.id:
                self.pet_list.setCurrentItem(item)
        self.pet_list.blockSignals(False)
        size = int(self.settings.get("pet.size", 2) or 2)
        btn = self.size_group.button(size)
        if btn:
            btn.setChecked(True)
        self.name_edit.setText(app.pet_name)
        recolor = app.features.is_enabled("recolor")
        for sw in self.swatches:
            sw.setEnabled(recolor)
        self.btn_reset_colors.setEnabled(recolor)
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        from ..pet.sprites import SpriteSet

        app = self.app
        colors = app.pet_colors()
        sprites = SpriteSet(app.pack, 1, colors)
        size = int(self.settings.get("pet.size", 2) or 2)
        self.preview.set_sprites(sprites, zoom=4 + 4 * size, flip=bool(self.settings.get("pet.flip")))
        pal = app.pack.palette
        c = colors or {}
        self.color_pair.set_colors(c.get("primary", pal.get("primary", "#000000")),
                                   c.get("secondary", pal.get("secondary", "#FFFFFF")))

    def _on_size(self, n: int) -> None:
        if not self._building:
            self.settings.set("pet.size", int(n))
            self._refresh_preview()

    def _on_flip(self) -> None:
        flip = not bool(self.settings.get("pet.flip"))
        self.settings.set("pet.flip", flip)
        self.app.brain.facing = -self.app.brain.facing
        self._refresh_preview()

    def _on_name(self) -> None:
        name = self.name_edit.text().strip()
        if name and name != self.app.pet_name:
            self.settings.set(f"pet.names.{self.app.pack.id}", name)
            self._update_status()

    def _on_color(self, color: str, secondary: bool) -> None:
        if not self.app.features.is_enabled("recolor"):
            return
        key = "secondary" if secondary else "primary"
        current = self.settings.get(f"pet.colors.{self.app.pack.id}") or {}
        current[key] = color
        self.settings.set(f"pet.colors.{self.app.pack.id}", current)
        self._refresh_preview()
        self._refresh_pet_icons()

    def _on_reset_colors(self) -> None:
        colors = self.settings.get("pet.colors") or {}
        colors.pop(self.app.pack.id, None)
        self.settings.set("pet.colors", colors)
        self._refresh_preview()
        self._refresh_pet_icons()

    def _refresh_pet_icons(self) -> None:
        for i in range(self.pet_list.count()):
            item = self.pet_list.item(i)
            item.setIcon(QIcon(self.app.icon_pixmap(32, item.data(Qt.UserRole))))
        self.title_bar.set_icon(self.app.icon_pixmap(16))

    def _on_pet_selected(self, item: QListWidgetItem | None, _prev=None) -> None:
        if item is None or self._building:
            return
        self.select_pet(item.data(Qt.UserRole))

    # ------------------------------------------------------------------ #
    # Tab 2: Funktionen
    # ------------------------------------------------------------------ #
    def _build_features_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(8, 8, 8, 8)
        scroll = QScrollArea(page)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner.setObjectName("featuresInner")
        inner.setStyleSheet("QWidget#featuresInner { background: transparent; }")
        il = QVBoxLayout(inner)
        il.setContentsMargins(4, 0, 8, 4)
        il.setSpacing(6)
        for _cat, label, features in self.app.features.by_category():
            box = QGroupBox(label.replace("&", "&&"), inner)
            grid = QGridLayout(box)
            grid.setContentsMargins(10, 10, 8, 6)
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(7)
            grid.setColumnStretch(1, 1)
            grid.setColumnMinimumWidth(0, 190)
            for row, f in enumerate(features):
                cb = QCheckBox(f.name.replace("&", "&&"), box)
                cb.setObjectName("featureName")
                cb.setEnabled(f.available)
                cb.toggled.connect(lambda checked, fid=f.id: self._on_feature(fid, checked))
                self._feature_boxes[f.id] = cb
                grid.addWidget(cb, row, 0)
                desc = QLabel(f.description, box)
                desc.setWordWrap(True)
                if not f.available:
                    desc.setObjectName("muted")
                grid.addWidget(desc, row, 1)
                pause = pixel_label(f"Pause: {f.pause_label}", color="pixel_red", parent=box)
                pause.setWordWrap(True)
                pause.setFixedWidth(84)
                pause.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                grid.addWidget(pause, row, 2)
                if f.options and f.available:
                    gear = QPushButton("⚙", box)
                    gear.setObjectName("gear")
                    gear.setToolTip(f"Optionen für {f.name}")
                    gear.clicked.connect(lambda _=False, feat=f: self._open_options(feat))
                    grid.addWidget(gear, row, 3)
                else:
                    spacer = QWidget(box)
                    spacer.setFixedWidth(20)
                    grid.addWidget(spacer, row, 3)
            il.addWidget(box)
        il.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        outer.addWidget(InfoBalloon("„Chaos &amp; Spaß“ ist ab Werk aus. Das Tier legt sich nie vor Buttons "
                                    "oder Eingabefelder.", parent=page))
        return page

    def _refresh_features_tab(self) -> None:
        for fid, cb in self._feature_boxes.items():
            f = self.app.features.get(fid)
            cb.blockSignals(True)
            cb.setChecked(bool(f and f.enabled))
            cb.blockSignals(False)
            if f is not None and fid in self.app.features.failed:
                cb.setToolTip(f"Abgestürzt und deaktiviert: {self.app.features.failed[fid]}")

    def _on_feature(self, fid: str, enabled: bool) -> None:
        if self._building:
            return
        ok = self.app.features.set_enabled(fid, enabled)
        if not ok:
            # z. B. beim Einschalten abgestürzt – Kästchen zurücksetzen
            self._refresh_features_tab()
        if fid == "recolor":
            self._refresh_pets_tab()
            self._refresh_pet_icons()
        self._update_status()

    def _on_feature_toggled(self, feature_id: str, enabled: bool) -> None:  # noqa: ARG002
        if self.isVisible():
            self._building = True
            self._refresh_features_tab()
            self._building = False
            self._update_status()

    def _open_options(self, feature: Feature) -> None:
        dlg = OptionsDialog(self.app, feature, self)
        dlg.move(self.geometry().center() - dlg.rect().center())
        dlg.show()

    # ------------------------------------------------------------------ #
    # Tab 3: Pause & Freigabe
    # ------------------------------------------------------------------ #
    def _build_pause_tab(self) -> QWidget:
        t = theme_mod.current()
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(16, 16, 16, 12)
        lay.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(16)
        frame = QFrame(page)
        frame.setFixedSize(176, 156)
        frame.setStyleSheet("border: 1px solid #5A7EAD;")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(1, 1, 1, 1)
        self.pause_preview = PetPreview(frame, checker=False, background=t.colors["desktop_blue"])
        self.pause_preview.setMinimumSize(170, 150)
        fl.addWidget(self.pause_preview)
        top.addWidget(frame, 0, Qt.AlignTop)
        text = QVBoxLayout()
        h = QLabel("Pause-Modus für Kundentermine", page)
        h.setObjectName("heading")
        text.addWidget(h)
        d = QLabel("Das Tier legt sich hinter alle Fenster und döst. Keine Sounds, keine Sprechblasen, "
                   "keine Bewegung. Erinnerungen werden gesammelt und kommen nach der Pause.", page)
        d.setWordWrap(True)
        text.addWidget(d)
        text.addStretch(1)
        row = QHBoxLayout()
        self.btn_pause = QPushButton("Pause-Modus starten", page)
        self.btn_pause.setObjectName("big")
        self.btn_pause.setMinimumWidth(180)
        self.btn_pause.clicked.connect(self.app.toggle_pause)
        row.addWidget(self.btn_pause)
        self.lbl_mode = pixel_label("Normalmodus", parent=page)
        row.addWidget(self.lbl_mode)
        row.addStretch(1)
        text.addLayout(row)
        top.addLayout(text, 1)
        lay.addLayout(top)

        keys = QGroupBox("Tastenkürzel", page)
        kg = QGridLayout(keys)
        kg.setHorizontalSpacing(12)
        self.hotkey_edits: dict[str, HotkeyEdit] = {}
        for row_i, (name, label) in enumerate((("toggle_pause", "Pause-Modus umschalten:"),
                                               ("toggle_visible", "Tier ein-/ausblenden:"))):
            kg.addWidget(QLabel(label, keys), row_i, 0)
            edit = HotkeyEdit(keys)
            edit.setFixedWidth(170)
            edit.captured.connect(lambda combo, n=name: self.settings.set(f"hotkeys.{n}", combo))
            self.hotkey_edits[name] = edit
            kg.addWidget(edit, row_i, 1)
            change = QPushButton("Ändern …", keys)
            change.clicked.connect(edit.start)
            kg.addWidget(change, row_i, 2)
        kg.setColumnStretch(3, 1)
        note = "Alternativ: Doppelklick auf das Tray-Icon."
        if not IS_WINDOWS:
            note += " Globale Tastenkürzel gibt es nur unter Windows."
        hint = QLabel(note, keys)
        hint.setObjectName("muted")
        kg.addWidget(hint, 2, 0, 1, 4)
        lay.addWidget(keys)

        share = QGroupBox("Bildschirmfreigabe", page)
        sl = QVBoxLayout(share)
        sl.setSpacing(8)
        self.cb_exclude = QCheckBox("Tier in Bildschirmaufnahmen unsichtbar machen (Teams, Zoom, OBS)", share)
        self.cb_exclude.toggled.connect(lambda v: self._set_if_live("pause.exclude_from_capture", v))
        sl.addWidget(self.cb_exclude)
        self.cb_always = QCheckBox("Auch im Normalmodus immer unsichtbar für Aufnahmen", share)
        self.cb_always.toggled.connect(lambda v: self._set_if_live("pause.always_exclude", v))
        sl.addWidget(self.cb_always)
        auto_row = QHBoxLayout()
        self.cb_auto = QCheckBox("Pause automatisch starten, wenn eine Freigabe erkannt wird", share)
        self.cb_auto.setEnabled(False)
        self.cb_auto.setToolTip("Kommt in Phase 4")
        auto_row.addWidget(self.cb_auto)
        auto_row.addStretch(1)
        auto_row.addWidget(pixel_label("Experimentell", parent=share))
        auto_row.itemAt(auto_row.count() - 1).widget().setObjectName("badge")
        sl.addLayout(auto_row)
        if not capture.is_supported():
            for cb in (self.cb_exclude, self.cb_always):
                cb.setEnabled(False)
            warn = QLabel("Unsichtbar für Aufnahmen braucht Windows 10 Version 2004 oder neuer.", share)
            warn.setObjectName("muted")
            sl.addWidget(warn)
        lay.addWidget(share)
        lay.addStretch(1)
        return page

    def _refresh_pause_tab(self) -> None:
        from ..pet.sprites import SpriteSet

        for name, edit in self.hotkey_edits.items():
            edit.set_value(self.settings.get(f"hotkeys.{name}", ""))
        self.cb_exclude.setChecked(bool(self.settings.get("pause.exclude_from_capture")))
        self.cb_always.setChecked(bool(self.settings.get("pause.always_exclude")))
        self.cb_auto.setChecked(bool(self.settings.get("pause.auto_detect")))
        paused = self.app.modes.paused
        self.btn_pause.setText("Pause-Modus beenden" if paused else "Pause-Modus starten")
        self.lbl_mode.setText("PAUSE AKTIV" if paused else "NORMALMODUS")
        sprites = SpriteSet(self.app.pack, 1, self.app.pet_colors())
        self.pause_preview.set_sprites(sprites, zoom=8, anim="sleep" if paused else "sit")

    def _on_mode_changed(self, mode, previous) -> None:  # noqa: ARG002
        if self.isVisible():
            self._building = True
            self._refresh_pause_tab()
            self._building = False
            self._update_status()

    def _set_if_live(self, key: str, value) -> None:
        if not self._building:
            self.settings.set(key, bool(value))
            self._update_status()

    # ------------------------------------------------------------------ #
    # Tab 4: Allgemein
    # ------------------------------------------------------------------ #
    def _build_general_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        start = QGroupBox("Start", page)
        st = QVBoxLayout(start)
        self.cb_autostart = QCheckBox("Mit Windows starten", start)
        self.cb_autostart.setEnabled(autostart.is_supported())
        self.cb_autostart.toggled.connect(self._on_autostart)
        st.addWidget(self.cb_autostart)
        lay.addWidget(start)

        snd = QGroupBox("Ton", page)
        sg = QGridLayout(snd)
        self.cb_mute = QCheckBox("Stumm", snd)
        self.cb_mute.toggled.connect(lambda v: self._set_if_live("general.muted", v))
        sg.addWidget(self.cb_mute, 0, 0, 1, 3)
        sg.addWidget(QLabel("Lautstärke:", snd), 1, 0)
        self.vol = QSlider(Qt.Horizontal, snd)
        self.vol.setRange(0, 100)
        self.vol.setFixedWidth(220)
        self.vol.valueChanged.connect(self._on_volume)
        sg.addWidget(self.vol, 1, 1)
        self.vol_label = pixel_label("70 %", parent=snd)
        sg.addWidget(self.vol_label, 1, 2)
        probe = QPushButton("Probe", snd)
        probe.clicked.connect(lambda: self.app.sound.play(self.app.pack.sounds.get("call"), self.app.pack.path))
        sg.addWidget(probe, 1, 3)
        sg.setColumnStretch(4, 1)
        hint = QLabel("Im Pause-Modus ist das Tier immer still.", snd)
        hint.setObjectName("muted")
        sg.addWidget(hint, 2, 0, 1, 5)
        lay.addWidget(snd)

        lang = QGroupBox("Sprache", page)
        lg = QHBoxLayout(lang)
        lg.addWidget(QLabel("Sprache:", lang))
        combo = QComboBox(lang)
        combo.addItem("Deutsch", "de")
        lg.addWidget(combo)
        lg.addStretch(1)
        lay.addWidget(lang)

        reset = QGroupBox("Zurücksetzen", page)
        rg = QVBoxLayout(reset)
        row = QHBoxLayout()
        self.btn_reset = QPushButton("Alle Einstellungen zurücksetzen", reset)
        self.btn_reset.clicked.connect(self._on_reset)
        row.addWidget(self.btn_reset)
        row.addStretch(1)
        rg.addLayout(row)
        info = QLabel(f"Einstellungen: {paths.settings_file()}<br>Protokoll: {paths.log_file()}", reset)
        info.setObjectName("muted")
        info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        rg.addWidget(info)
        row2 = QHBoxLayout()
        open_dir = QPushButton("Ordner öffnen", reset)
        open_dir.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.user_data_dir()))))
        row2.addWidget(open_dir)
        row2.addStretch(1)
        rg.addLayout(row2)
        lay.addWidget(reset)
        lay.addStretch(1)
        return page

    def _refresh_general_tab(self) -> None:
        self.cb_autostart.setChecked(autostart.is_enabled() if autostart.is_supported()
                                     else bool(self.settings.get("general.autostart")))
        self.cb_mute.setChecked(bool(self.settings.get("general.muted")))
        vol = int(self.settings.get("general.volume", 70))
        self.vol.setValue(vol)
        self.vol_label.setText(f"{vol} %")
        self.btn_reset.setText("Alle Einstellungen zurücksetzen")

    def _on_volume(self, v: int) -> None:
        self.vol_label.setText(f"{v} %")
        if not self._building:
            self.settings.set("general.volume", int(v))

    def _on_autostart(self, enabled: bool) -> None:
        if self._building:
            return
        autostart.set_enabled(enabled)
        self.settings.set("general.autostart", bool(enabled))

    def _on_reset(self) -> None:
        # Zweistufig statt Rückfrage-Dialog: erst bestätigen lassen
        if self.btn_reset.text() != "Wirklich zurücksetzen?":
            self.btn_reset.setText("Wirklich zurücksetzen?")
            QTimer.singleShot(4000, lambda: self.btn_reset.setText("Alle Einstellungen zurücksetzen"))
            return
        self.settings.reset()
        self._snapshot = self.settings.snapshot()
        self._refresh_all()
        self._update_status("Zurückgesetzt")

    # ------------------------------------------------------------------ #
    # Statusleiste
    # ------------------------------------------------------------------ #
    def _update_status(self, note: str | None = None) -> None:
        if self.status_bar is None:
            return
        idx = self.tabs.currentIndex()
        app = self.app
        if idx == 0:
            fields = [app.pet_name]
            if app.features.is_enabled("needs"):
                n = app.needs
                fields += [f"Laune: {n.mood_label}", f"Hunger: {round(n.hunger)} %", f"Energie: {round(n.energy)} %"]
        elif idx == 1:
            active, total = app.features.counts()
            fields = [f"{active} von {total} Funktionen aktiv", "Änderungen wirken sofort"]
        elif idx == 2:
            mode = "Pause" if app.modes.paused else "Normal"
            if capture.is_supported():
                protect = "an" if self.settings.get("pause.exclude_from_capture") else "aus"
            else:
                protect = "nicht verfügbar"
            fields = [f"Modus: {mode}", f"Aufnahme-Schutz: {protect}"]
        else:
            fields = [f"Version {__version__}", "Retro XP"]
        if note:
            fields.append(note)
        self.status_bar.set_fields(fields)

    def closeEvent(self, e) -> None:  # noqa: N802
        self._status_timer.stop()
        self.app.bus.unsubscribe("mode_changed", self._on_mode_changed)
        self.app.bus.unsubscribe("feature_toggled", self._on_feature_toggled)
        self.app._settings_dialog = None
        self.deleteLater()
        super().closeEvent(e)
