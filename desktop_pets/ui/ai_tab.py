"""Tab „KI“ im Einstellungsdialog: Anbieter, API-Key, Modell, Verbindung testen,
Tastenkürzel und Persönlichkeit (Spezifikation Abschnitt 5.3).

Prinzip „ein Feld“: Key einfügen → Anbieter wird am Präfix erkannt. Keys landen im
Windows-Anmeldeinformationsspeicher und werden nur maskiert angezeigt.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from ..features.ai.detect import detect_provider, mask
from ..features.ai.providers import KEY_OPTIONAL, PROVIDERS, AIError
from ..win import IS_WINDOWS

if TYPE_CHECKING:  # pragma: no cover
    from ..core.app import PetApp

AUTO = "auto"


class _TestBridge(QObject):
    done = Signal(int, bool, str)


class AITab(QWidget):
    def __init__(self, app: "PetApp", parent: QWidget | None = None) -> None:
        from .settings_dialog import HotkeyEdit

        super().__init__(parent)
        self.app = app
        self.settings = app.settings
        self._building = False
        self._test_no = 0
        self._bridge = _TestBridge()
        self._bridge.done.connect(self._on_test_done)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        # ---------- Anbieter & Key ----------
        box = QGroupBox("Anbieter && API-Key", self)
        g = QGridLayout(box)
        g.setHorizontalSpacing(8)
        g.addWidget(QLabel("Anbieter:", box), 0, 0)
        self.combo = QComboBox(box)
        ids = list(PROVIDERS)
        # OneAI ganz oben, dann „Automatisch erkennen“, dann der Rest
        self.combo.addItem(PROVIDERS["oneai"].name, "oneai")
        self.combo.addItem("Automatisch erkennen", AUTO)
        for pid in ids:
            if pid != "oneai":
                self.combo.addItem(PROVIDERS[pid].name, pid)
        self.combo.currentIndexChanged.connect(self._on_provider)
        g.addWidget(self.combo, 0, 1, 1, 3)

        g.addWidget(QLabel("API-Key:", box), 1, 0)
        self.key = QLineEdit(box)
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setMinimumWidth(240)
        self.key.returnPressed.connect(self._save_key)
        self.key.textChanged.connect(self._on_key_typed)
        g.addWidget(self.key, 1, 1)
        self.btn_paste = QPushButton("Einfügen", box)
        self.btn_paste.clicked.connect(self._paste)
        g.addWidget(self.btn_paste, 1, 2)
        self.btn_save = QPushButton("Speichern", box)
        self.btn_save.setObjectName("primary")
        self.btn_save.clicked.connect(self._save_key)
        g.addWidget(self.btn_save, 1, 3)

        self.status = QLabel("", box)
        self.status.setWordWrap(True)
        g.addWidget(self.status, 2, 1, 1, 2)
        self.btn_delete = QPushButton("Key löschen", box)
        self.btn_delete.clicked.connect(self._delete_key)
        g.addWidget(self.btn_delete, 2, 3)

        self.btn_more = QPushButton("Erweitert ▸", box)
        self.btn_more.setCheckable(True)
        self.btn_more.toggled.connect(self._toggle_more)
        g.addWidget(self.btn_more, 3, 0)
        self.more = QWidget(box)
        mg = QGridLayout(self.more)
        mg.setContentsMargins(0, 0, 0, 0)
        mg.addWidget(QLabel("Modell:", self.more), 0, 0)
        self.model = QComboBox(self.more)
        self.model.setEditable(True)
        self.model.setMinimumWidth(240)
        self.model.editTextChanged.connect(self._on_model)
        mg.addWidget(self.model, 0, 1)
        mg.addWidget(QLabel("Basis-URL:", self.more), 1, 0)
        self.url = QLineEdit(self.more)
        self.url.editingFinished.connect(self._on_url)
        mg.addWidget(self.url, 1, 1)
        g.addWidget(self.more, 4, 0, 1, 4)

        row = QHBoxLayout()
        self.btn_test = QPushButton("Verbindung testen", box)
        self.btn_test.clicked.connect(self._test)
        row.addWidget(self.btn_test)
        self.test_result = QLabel("", box)
        self.test_result.setWordWrap(True)
        row.addWidget(self.test_result, 1)
        g.addLayout(row, 5, 0, 1, 4)
        g.setColumnStretch(1, 1)
        lay.addWidget(box)

        # ---------- Chat ----------
        chat = QGroupBox("Chat", self)
        cg = QGridLayout(chat)
        self.cb_enabled = QCheckBox("KI-Chat einschalten", chat)
        self.cb_enabled.toggled.connect(self._on_enabled)
        cg.addWidget(self.cb_enabled, 0, 0, 1, 3)
        self.cb_copilot = QCheckBox("Copilot-Taste öffnet den Chat  (Alt + Copilot: Spracheingabe)", chat)
        self.cb_copilot.toggled.connect(self._on_copilot)
        self.cb_copilot.setEnabled(IS_WINDOWS)
        cg.addWidget(self.cb_copilot, 1, 0, 1, 3)
        self.hotkey_edits: dict[str, HotkeyEdit] = {}
        for i, (name, label) in enumerate((("ai_chat", "Chat öffnen:"), ("ai_voice", "Mit Spracheingabe:"))):
            cg.addWidget(QLabel(label, chat), 2 + i, 0)
            edit = HotkeyEdit(chat)
            edit.setFixedWidth(190)
            edit.captured.connect(lambda combo, n=name: self.settings.set(f"hotkeys.{n}", combo))
            self.hotkey_edits[name] = edit
            cg.addWidget(edit, 2 + i, 1)
            change = QPushButton("Ändern …", chat)
            change.clicked.connect(edit.start)
            cg.addWidget(change, 2 + i, 2)
        cg.setColumnStretch(3, 1)
        note = QLabel("Gesendet wird nur, was du eintippst oder sagst – nie Fenstertitel oder Screenshots. "
                      "Der Chat wird nicht gespeichert und ist im Pause-Modus aus. Die Spracheingabe nutzt "
                      "die Windows-Spracheingabe (Win + H).", chat)
        note.setObjectName("muted")
        note.setWordWrap(True)
        cg.addWidget(note, 4, 0, 1, 4)
        lay.addWidget(chat)

        # ---------- Persönlichkeit ----------
        self.pers_box = QGroupBox("Persönlichkeit", self)
        pl = QVBoxLayout(self.pers_box)
        self.personality = QPlainTextEdit(self.pers_box)
        self.personality.setFixedHeight(64)
        self.personality.textChanged.connect(self._on_personality)
        pl.addWidget(self.personality)
        prow = QHBoxLayout()
        hint = QLabel("Wie das Tier antwortet – gilt für die gerade gewählte Tierart.", self.pers_box)
        hint.setObjectName("muted")
        prow.addWidget(hint, 1)
        btn_default = QPushButton("Standard", self.pers_box)
        btn_default.clicked.connect(self._default_personality)
        prow.addWidget(btn_default)
        pl.addLayout(prow)
        lay.addWidget(self.pers_box)
        lay.addStretch(1)
        self.more.setVisible(False)

    # ------------------------------------------------------------------ #
    @property
    def feature(self):
        return self.app.features.get("ai_chat")

    def _selected(self) -> str:
        return self.combo.currentData() or AUTO

    def refresh(self) -> None:
        self._building = True
        try:
            pid = self.feature.provider_id if self.feature else ""
            idx = self.combo.findData(pid or AUTO)
            self.combo.setCurrentIndex(max(0, idx))
            self._fill_provider_fields()
            for name, edit in self.hotkey_edits.items():
                edit.set_value(self.settings.get(f"hotkeys.{name}", ""))
            self.cb_copilot.setChecked(bool(self.settings.get("general.copilot_key"))
                                       and self.settings.get("general.copilot_action") == "ai_chat")
            self.pers_box.setTitle(f"Persönlichkeit von {self.app.pet_name}")
            self.personality.setPlainText(self.feature.personality() if self.feature else "")
        finally:
            self._building = False
        self._update_state()

    def _fill_provider_fields(self) -> None:
        pid = self._selected()
        info = PROVIDERS.get(pid)
        f = self.feature
        self.model.blockSignals(True)
        self.model.clear()
        if info is not None:
            self.model.addItems(list(info.models))
            self.model.setEditText(f.model_for(pid) if f else info.default_model)
        self.model.blockSignals(False)
        self.url.setText(f.base_url_for(pid) if (f and info) else "")
        self.url.setEnabled(bool(info and info.url_editable))
        self.model.setEnabled(info is not None)
        needs_more = info is not None and info.url_editable and not self.url.text()
        if needs_more:
            self.btn_more.setChecked(True)

    def _update_state(self) -> None:
        pid = self._selected()
        f = self.feature
        info = PROVIDERS.get(pid)
        stored = f.keys.get(pid) if (f and info) else ""
        self.key.setPlaceholderText(f"Gespeichert: {mask(stored)}" if stored
                                    else ("Optional – lokale Modelle brauchen meist keinen Key"
                                          if pid in KEY_OPTIONAL else "API-Key hier einfügen"))
        self.btn_delete.setEnabled(bool(stored))
        typed = self.key.text().strip()
        if typed:
            found = detect_provider(typed)
            if pid == AUTO:
                self.status.setText(f"Erkannt: {PROVIDERS[found].name} ✓" if found
                                    else "Anbieter nicht erkannt, bitte auswählen.")
            else:
                self.status.setText("Mit „Speichern“ oder Enter übernehmen.")
        elif info is None:
            self.status.setText("Key einfügen – der Anbieter wird automatisch erkannt.")
        elif f and f.is_ready(pid):
            self.status.setText(f"Bereit: {info.name} ✓")
        else:
            self.status.setText("Noch kein Key hinterlegt." if pid not in KEY_OPTIONAL
                                else "Basis-URL unter „Erweitert“ eintragen.")
        ready = bool(f and f.is_ready())
        self.cb_enabled.blockSignals(True)
        self.cb_enabled.setChecked(bool(f and f.enabled))
        self.cb_enabled.blockSignals(False)
        self.cb_enabled.setEnabled(ready)
        self.cb_enabled.setToolTip("" if ready else "Erst einen API-Key hinterlegen.")
        self.btn_test.setEnabled(bool(f and info and f.is_ready(pid)))

    # ---------- Ereignisse ----------
    def _on_provider(self, _i: int) -> None:
        if self._building:
            return
        pid = self._selected()
        if pid != AUTO:
            self.settings.set("ai.provider", pid)
        self.test_result.setText("")
        self._fill_provider_fields()
        self._update_state()

    def _on_key_typed(self, _text: str) -> None:
        self._update_state()

    def _paste(self) -> None:
        self.key.setText(QGuiApplication.clipboard().text().strip())
        self._update_state()

    def _save_key(self) -> None:
        f = self.feature
        typed = self.key.text().strip()
        if f is None or not typed:
            return
        pid = self._selected()
        if pid == AUTO:
            found = detect_provider(typed)
            if found is None:
                self.status.setText("Anbieter nicht erkannt, bitte oben auswählen.")
                self.btn_more.setChecked(True)
                return
            pid = found
        if not f.keys.set(pid, typed):
            self.status.setText("Key konnte nicht gespeichert werden (siehe log.txt).")
            return
        self.key.clear()
        self.settings.set("ai.provider", pid)
        self._building = True
        self.combo.setCurrentIndex(max(0, self.combo.findData(pid)))
        self._building = False
        self._fill_provider_fields()
        if f.is_ready() and not f.enabled:
            self.app.features.set_enabled("ai_chat", True)      # Key da → Chat gleich an
        self._update_state()

    def _delete_key(self) -> None:
        f = self.feature
        pid = self._selected()
        if f is None or pid not in PROVIDERS:
            return
        f.keys.delete(pid)
        if f.enabled and not f.is_ready():
            self.app.features.set_enabled("ai_chat", False)
        self.test_result.setText("")
        self._update_state()

    def _toggle_more(self, on: bool) -> None:
        self.more.setVisible(on)
        self.btn_more.setText("Erweitert ▾" if on else "Erweitert ▸")

    def _on_model(self, text: str) -> None:
        pid = self._selected()
        info = PROVIDERS.get(pid)
        if self._building or info is None:
            return
        text = text.strip()
        self.settings.set(f"ai.models.{pid}", "" if text == info.default_model else text)

    def _on_url(self) -> None:
        pid = self._selected()
        info = PROVIDERS.get(pid)
        if self._building or info is None or not info.url_editable:
            return
        url = self.url.text().strip()
        self.settings.set(f"ai.base_urls.{pid}", "" if url == info.base_url else url)
        self._update_state()

    def _on_enabled(self, on: bool) -> None:
        if not self._building:
            self.app.features.set_enabled("ai_chat", on)
            self._update_state()

    def _on_copilot(self, on: bool) -> None:
        if self._building:
            return
        if on:
            self.settings.set("general.copilot_key", True)
            self.settings.set("general.copilot_action", "ai_chat")
        elif self.settings.get("general.copilot_action") == "ai_chat":
            self.settings.set("general.copilot_action", "settings")

    def _on_personality(self) -> None:
        if not self._building:
            self.settings.set(f"ai.personality.{self.app.pack.id}", self.personality.toPlainText())

    def _default_personality(self) -> None:
        self.settings.set(f"ai.personality.{self.app.pack.id}", None)
        self._building = True
        self.personality.setPlainText(self.app.pack.prompt)
        self._building = False

    # ---------- Verbindung testen ----------
    def _test(self) -> None:
        f = self.feature
        pid = self._selected()
        if f is None or pid not in PROVIDERS:
            return
        self._on_url()
        self._test_no += 1
        number = self._test_no
        self.test_result.setText("Teste …")
        self.btn_test.setEnabled(False)
        try:
            provider = f.make(pid)
        except AIError as exc:
            self._on_test_done(number, False, str(exc))
            return

        def work() -> None:
            try:
                self._bridge.done.emit(number, True, provider.test_connection())
            except AIError as exc:
                self._bridge.done.emit(number, False, str(exc))
            except Exception as exc:  # noqa: BLE001
                self._bridge.done.emit(number, False, provider.scrub(f"Unerwarteter Fehler: {exc}"))

        threading.Thread(target=work, name="ai-test", daemon=True).start()

    def _on_test_done(self, number: int, ok: bool, text: str) -> None:
        if number != self._test_no:
            return
        self.test_result.setText(text)
        self.test_result.setStyleSheet("color: #1E7B1E;" if ok else "color: #B00020;")
        self._update_state()
