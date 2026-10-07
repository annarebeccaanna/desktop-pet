"""Theme-Loader: Farben aus ``themes/<name>.json`` in ``themes/<name>.qss`` einsetzen.

Das Retro-Theme ignoriert bewusst den System-Dark-Mode.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from ..core import paths
from ..core.log import get_logger

log = get_logger("theme")


@dataclass
class Theme:
    name: str
    colors: dict[str, str]
    fonts: dict = field(default_factory=dict)
    qss: str = ""
    pixel_family: str = ""

    def color(self, key: str) -> QColor:
        return QColor(self.colors.get(key, "#FF00FF"))

    # ---------- Schriften ----------
    def ui_font(self, size_pt: float | None = None, bold: bool = False) -> QFont:
        families = self.fonts.get("ui", ["Tahoma", "Segoe UI"])
        font = QFont()
        font.setFamilies(families)
        font.setPointSizeF(size_pt or float(self.fonts.get("ui_size_pt", 8)))
        font.setBold(bold)
        return font

    def pixel_font(self, size_px: int | None = None) -> QFont:
        """Pixelschrift ohne Glättung und ohne Hinting (scharfe Kanten)."""
        font = QFont(self.pixel_family or "Monospace")
        font.setPixelSize(size_px or int(self.fonts.get("pixel_size_px", 8)))
        font.setStyleStrategy(QFont.StyleStrategy(QFont.NoAntialias | QFont.PreferBitmap))
        font.setHintingPreference(QFont.PreferNoHinting)
        return font


_CURRENT: Theme | None = None


def current() -> Theme:
    global _CURRENT
    if _CURRENT is None:
        _CURRENT = load_theme("retro_xp")
    return _CURRENT


def _load_pixel_font() -> str:
    fonts_dir = paths.assets_dir() / "fonts"
    for ttf in sorted(fonts_dir.glob("*.ttf")):
        fid = QFontDatabase.addApplicationFont(str(ttf))
        if fid >= 0:
            families = QFontDatabase.applicationFontFamilies(fid)
            if families:
                return families[0]
    log.warning("Keine Pixelschrift gefunden – Fallback auf Systemschrift")
    return ""


def load_theme(name: str) -> Theme:
    base = paths.themes_dir()
    meta = json.loads((base / f"{name}.json").read_text(encoding="utf-8"))
    colors = dict(meta.get("colors", {}))
    fonts = dict(meta.get("fonts", {}))
    pixel_family = _load_pixel_font() if QApplication.instance() else fonts.get("pixel", "")
    variables = dict(colors)
    variables["assets"] = paths.assets_dir().as_posix()
    variables["pixel_font"] = pixel_family or "Monospace"
    raw = (base / f"{name}.qss").read_text(encoding="utf-8")
    qss = re.sub(r"\$\{(\w+)\}", lambda m: variables.get(m.group(1), m.group(0)), raw)
    return Theme(name=name, colors=colors, fonts=fonts, qss=qss, pixel_family=pixel_family)


def apply(app: QApplication, name: str = "retro_xp") -> Theme:
    global _CURRENT
    theme = load_theme(name)
    _CURRENT = theme
    app.setStyle("Fusion")
    # Hell erzwingen – unabhängig vom System-Dark-Mode
    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except AttributeError:
        pass
    pal = QPalette()
    c = theme.color
    pal.setColor(QPalette.Window, c("dialog_bg"))
    pal.setColor(QPalette.WindowText, c("text"))
    pal.setColor(QPalette.Base, QColor("white"))
    pal.setColor(QPalette.AlternateBase, c("panel_bg"))
    pal.setColor(QPalette.Text, c("text"))
    pal.setColor(QPalette.Button, c("button_to"))
    pal.setColor(QPalette.ButtonText, c("text"))
    pal.setColor(QPalette.Highlight, c("selection"))
    pal.setColor(QPalette.HighlightedText, c("selection_text"))
    pal.setColor(QPalette.ToolTipBase, c("balloon"))
    pal.setColor(QPalette.ToolTipText, c("text"))
    pal.setColor(QPalette.PlaceholderText, c("text_muted"))
    app.setPalette(pal)
    app.setFont(theme.ui_font())
    app.setStyleSheet(theme.qss)
    return theme
