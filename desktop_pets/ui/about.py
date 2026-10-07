"""„Über Desktop Pets“ im XP-Stil mit pixeliger Katze."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .. import APP_NAME, __version__
from .retro import RetroWindow, pixel_label

if TYPE_CHECKING:  # pragma: no cover
    from ..core.app import PetApp


class AboutDialog(RetroWindow):
    def __init__(self, app: "PetApp") -> None:
        super().__init__(f"Über {APP_NAME}", app.icon_pixmap(16), minimizable=False)
        self.setAttribute(Qt.WA_DeleteOnClose)
        lay = QVBoxLayout(self.body)
        lay.setContentsMargins(16, 14, 16, 12)
        row = QHBoxLayout()
        pic = QLabel(self.body)
        cat = app.packs.get("cat", app.pack)
        pic.setPixmap(app.icon_pixmap(64, cat.id))
        row.addWidget(pic, 0, Qt.AlignTop)
        text = QVBoxLayout()
        title = QLabel(APP_NAME, self.body)
        title.setObjectName("heading")
        text.addWidget(title)
        text.addWidget(pixel_label(f"Version {__version__}", color="pixel_blue", parent=self.body))
        info = QLabel(
            "Ein kleines Pixeltier für deinen Desktop.<br>"
            "Alle Grafiken und Sounds sind selbst erstellt.<br>"
            "Pixelschrift: Silkscreen (SIL Open Font License).", self.body)
        info.setWordWrap(True)
        text.addWidget(info)
        text.addStretch(1)
        row.addLayout(text, 1)
        lay.addLayout(row)
        btns = QHBoxLayout()
        btns.addStretch(1)
        ok = QPushButton("OK", self.body)
        ok.clicked.connect(self.close)
        btns.addWidget(ok)
        lay.addLayout(btns)
        self.resize(380, 200)
