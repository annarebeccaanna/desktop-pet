"""„Erkennung testen …“: zeigt live, ob eine Bildschirmfreigabe erkannt wird.

Gelistet werden die sichtbaren Fenster der bekannten Meeting-Programme und
Browser. Passt keine Regel, obwohl gerade geteilt wird, lässt sich die Liste
kopieren und eine eigene Regel in ``share_signatures.json`` ergänzen.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..core import paths
from ..win import IS_WINDOWS
from ..win.share_detect import ShareDetector, find_sharing
from .retro import RetroWindow, pixel_label

if TYPE_CHECKING:  # pragma: no cover
    from ..core.app import PetApp

REFRESH_MS = 2000
USER_TEMPLATE = {
    "_info": "Eigene Regeln zur Freigabe-Erkennung. Eine Regel passt, wenn alle Felder passen. "
             "Beispiel unten: Fenstertitel aus „Erkennung testen …“ übernehmen.",
    "rules": [
        {"app": "Beispiel", "process": ["programm.exe"], "title": "(?i)freigabe beenden"},
    ],
}


class ShareTestDialog(RetroWindow):
    def __init__(self, app: "PetApp", parent: QWidget | None = None) -> None:
        super().__init__("Freigabe-Erkennung testen", app.icon_pixmap(16), minimizable=False, parent=parent)
        self.setWindowFlag(Qt.Tool, True)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.app = app
        feature = app.features.get("share_autopause")
        self.detector: ShareDetector = feature.detector if feature is not None else ShareDetector(
            user_file=paths.user_data_dir() / "share_signatures.json")
        self.detector.reload()

        lay = QVBoxLayout(self.body)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)
        head = QLabel("Wird gerade geteilt?", self.body)
        head.setObjectName("heading")
        lay.addWidget(head)
        info = QLabel("Starte eine Freigabe in Teams, Zoom, Webex oder im Browser – die Anzeige aktualisiert "
                      "sich alle 2 Sekunden. Unten stehen die Fenster der bekannten Meeting-Programme und Browser; "
                      "die erkannten sind markiert.", self.body)
        info.setWordWrap(True)
        lay.addWidget(info)
        self.status = pixel_label("", size_px=16, parent=self.body)
        lay.addWidget(self.status)

        self.table = QTableWidget(0, 3, self.body)
        self.table.setHorizontalHeaderLabels(["Programm", "Fensterklasse", "Fenstertitel"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        lay.addWidget(self.table, 1)
        if not IS_WINDOWS:
            note = QLabel("Hinweis: Die Erkennung funktioniert nur unter Windows.", self.body)
            note.setObjectName("muted")
            lay.addWidget(note)

        btns = QHBoxLayout()
        b_copy = QPushButton("Kopieren", self.body)
        b_copy.setToolTip("Liste in die Zwischenablage – z. B. um eine Regel zu ergänzen")
        b_copy.clicked.connect(self.copy)
        btns.addWidget(b_copy)
        b_rules = QPushButton("Eigene Regeln …", self.body)
        b_rules.setToolTip(str(paths.user_data_dir() / "share_signatures.json"))
        b_rules.clicked.connect(self.open_user_rules)
        btns.addWidget(b_rules)
        btns.addStretch(1)
        b_close = QPushButton("Schließen", self.body)
        b_close.clicked.connect(self.close)
        btns.addWidget(b_close)
        lay.addLayout(btns)

        self._rows: list = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(REFRESH_MS)
        self.resize(720, 420)
        self.refresh()

    def refresh(self) -> None:
        windows = self.detector.diagnose()
        hits = {id(w): app for app, w in find_sharing(windows, self.detector.rules)}
        matched_apps = sorted(set(hits.values()))
        if matched_apps:
            self.status.setText(("Freigabe erkannt: " + ", ".join(matched_apps)).upper())
            self.status.setStyleSheet("color: #2E8B2E; background: transparent;")
        else:
            self.status.setText("KEINE FREIGABE ERKANNT")
            self.status.setStyleSheet("color: #B22222; background: transparent;")
        self._rows = windows
        self.table.setRowCount(len(windows))
        for r, w in enumerate(windows):
            cells = [w.process, w.class_name, w.title or "(ohne Titel)"]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if id(w) in hits:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setForeground(Qt.darkGreen)
                    if c == 2:
                        item.setText(f"✓ {text}   ← {hits[id(w)]}")
                self.table.setItem(r, c, item)

    def copy(self) -> None:
        lines = [f"{w.process}\t{w.class_name}\t{w.title}" for w in self._rows]
        QGuiApplication.clipboard().setText("\n".join(lines) or "(keine Fenster)")

    def open_user_rules(self) -> None:
        path = paths.user_data_dir() / "share_signatures.json"
        if not path.exists():
            path.write_text(json.dumps(USER_TEMPLATE, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        self.detector.reload()

    def closeEvent(self, e) -> None:  # noqa: N802
        self._timer.stop()
        super().closeEvent(e)
