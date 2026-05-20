"""LLM formatting panel — Ollama connection, preset picker, and format button."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from . import presets as preset_store
from . import settings as settings_store
from .ollama_client import list_models, test_connection
from .preset_dialog import PresetDialog


class LlmPanel(QGroupBox):
    """Emits format_requested(prompt_with_text_inserted, extra_instruction)
    when the user clicks Format.  The caller is responsible for supplying the
    raw transcription text and building the final prompt."""

    # (preset_prompt_template, extra_instruction)
    # The caller substitutes {text} and appends extra_instruction itself.
    format_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__("Format with Ollama", parent)
        self._presets: list[dict] = preset_store.load()
        self._cfg = settings_store.load()
        self._build_ui()
        self._populate_presets()

    # ------------------------------------------------------------------ build

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ── Connection row ────────────────────────────────────────────────────
        conn_row = QHBoxLayout()

        conn_row.addWidget(QLabel("Host:"))
        self._host_edit = QLineEdit(self._cfg.get("ollama_host", "http://localhost:11434"))
        self._host_edit.setPlaceholderText("http://localhost:11434")
        self._host_edit.setMinimumWidth(220)
        conn_row.addWidget(self._host_edit, 1)

        self._test_btn = QPushButton("Test")
        self._test_btn.setProperty("flat", "true")
        self._test_btn.setFixedWidth(60)
        self._test_btn.clicked.connect(self._test_connection)
        conn_row.addWidget(self._test_btn)

        self._conn_lbl = QLabel("Not tested")
        self._conn_lbl.setProperty("class", "muted")
        self._conn_lbl.setMinimumWidth(200)
        conn_row.addWidget(self._conn_lbl)

        conn_row.addStretch()
        root.addLayout(conn_row)

        # ── Model row ─────────────────────────────────────────────────────────
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model:"))
        self._model_combo = QComboBox()
        self._model_combo.setMinimumWidth(240)
        self._model_combo.setPlaceholderText("Connect to populate…")
        self._model_combo.currentTextChanged.connect(self._save_settings)
        model_row.addWidget(self._model_combo, 1)
        model_row.addStretch()
        root.addLayout(model_row)

        # ── Preset row ────────────────────────────────────────────────────────
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))

        self._preset_combo = QComboBox()
        self._preset_combo.setMinimumWidth(240)
        preset_row.addWidget(self._preset_combo, 1)

        new_btn = QPushButton("＋")
        new_btn.setProperty("flat", "true")
        new_btn.setFixedWidth(32)
        new_btn.setToolTip("New preset")
        new_btn.clicked.connect(self._new_preset)
        preset_row.addWidget(new_btn)

        self._edit_btn = QPushButton("✎")
        self._edit_btn.setProperty("flat", "true")
        self._edit_btn.setFixedWidth(32)
        self._edit_btn.setToolTip("Edit selected preset")
        self._edit_btn.clicked.connect(self._edit_preset)
        preset_row.addWidget(self._edit_btn)

        self._del_btn = QPushButton("✕")
        self._del_btn.setProperty("flat", "true")
        self._del_btn.setFixedWidth(32)
        self._del_btn.setToolTip("Delete selected preset")
        self._del_btn.clicked.connect(self._delete_preset)
        preset_row.addWidget(self._del_btn)

        preset_row.addStretch()
        root.addLayout(preset_row)

        # ── Extra instruction ─────────────────────────────────────────────────
        extra_row = QHBoxLayout()
        extra_row.addWidget(QLabel("Extra instruction:"))
        self._extra_edit = QLineEdit()
        self._extra_edit.setPlaceholderText(
            "Optional — e.g. 'Use British English' or 'Keep it under 200 words'"
        )
        extra_row.addWidget(self._extra_edit, 1)
        root.addLayout(extra_row)

        # ── Format button ─────────────────────────────────────────────────────
        self._format_btn = QPushButton("✨  Format with AI")
        self._format_btn.setMinimumHeight(38)
        self._format_btn.setEnabled(False)
        self._format_btn.clicked.connect(self._on_format_clicked)
        root.addWidget(self._format_btn)

    # --------------------------------------------------------------- presets

    def _populate_presets(self):
        self._preset_combo.blockSignals(True)
        self._preset_combo.clear()
        for p in self._presets:
            self._preset_combo.addItem(p["name"])
        self._preset_combo.blockSignals(False)
        has = bool(self._presets)
        self._edit_btn.setEnabled(has)
        self._del_btn.setEnabled(has)

    def _new_preset(self):
        dlg = PresetDialog(self, title="New Preset")
        if dlg.exec() == PresetDialog.DialogCode.Accepted:
            self._presets.append({"name": dlg.name(), "prompt": dlg.prompt()})
            preset_store.save(self._presets)
            self._populate_presets()
            self._preset_combo.setCurrentIndex(len(self._presets) - 1)

    def _edit_preset(self):
        idx = self._preset_combo.currentIndex()
        if idx < 0:
            return
        p = self._presets[idx]
        dlg = PresetDialog(self, name=p["name"], prompt=p["prompt"], title="Edit Preset")
        if dlg.exec() == PresetDialog.DialogCode.Accepted:
            self._presets[idx] = {"name": dlg.name(), "prompt": dlg.prompt()}
            preset_store.save(self._presets)
            self._populate_presets()
            self._preset_combo.setCurrentIndex(idx)

    def _delete_preset(self):
        idx = self._preset_combo.currentIndex()
        if idx < 0:
            return
        name = self._presets[idx]["name"]
        reply = QMessageBox.question(
            self,
            "Delete Preset",
            f'Delete preset "{name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._presets.pop(idx)
            preset_store.save(self._presets)
            self._populate_presets()

    # --------------------------------------------------------------- connection

    def _test_connection(self):
        host = self._host_edit.text().strip()
        self._conn_lbl.setText("Testing…")
        self._conn_lbl.setProperty("class", "muted")
        self._refresh_label_style(self._conn_lbl)
        self._test_btn.setEnabled(False)

        ok, msg = test_connection(host)

        self._test_btn.setEnabled(True)
        self._conn_lbl.setText(msg)
        self._set_label_class(self._conn_lbl, "success" if ok else "error")

        if ok:
            self._save_settings()
            self._refresh_models(host)

    def _refresh_models(self, host: str):
        try:
            names = list_models(host)
        except Exception as exc:
            self._conn_lbl.setText(f"Connected but couldn't list models: {exc}")
            self._set_label_class(self._conn_lbl, "warning")
            return

        saved_model = self._cfg.get("ollama_model", "")
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        for n in names:
            self._model_combo.addItem(n)
        if saved_model in names:
            self._model_combo.setCurrentText(saved_model)
        elif names:
            self._model_combo.setCurrentIndex(0)
        self._model_combo.blockSignals(False)

        self._update_format_btn()

    def _save_settings(self):
        self._cfg["ollama_host"] = self._host_edit.text().strip()
        self._cfg["ollama_model"] = self._model_combo.currentText()
        settings_store.save(self._cfg)

    # --------------------------------------------------------------- format

    def _on_format_clicked(self):
        idx = self._preset_combo.currentIndex()
        if idx < 0 or not self._presets:
            return
        preset_prompt = self._presets[idx]["prompt"]
        extra = self._extra_edit.text().strip()
        self.format_requested.emit(preset_prompt, extra)

    def _update_format_btn(self):
        ready = bool(self._model_combo.currentText()) and bool(self._presets)
        self._format_btn.setEnabled(ready)

    # --------------------------------------------------------------- public

    def set_ready(self, has_text: bool):
        """Enable/disable the Format button based on whether output text exists."""
        model_ok = bool(self._model_combo.currentText())
        preset_ok = bool(self._presets)
        self._format_btn.setEnabled(has_text and model_ok and preset_ok)

    def set_busy(self, busy: bool):
        self._format_btn.setEnabled(not busy)
        self._format_btn.setText("⏳  Formatting…" if busy else "✨  Format with AI")

    def current_host(self) -> str:
        return self._host_edit.text().strip()

    def current_model(self) -> str:
        return self._model_combo.currentText()

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _set_label_class(label, cls: str):
        label.setProperty("class", cls)
        label.style().unpolish(label)
        label.style().polish(label)

    @staticmethod
    def _refresh_label_style(label):
        label.style().unpolish(label)
        label.style().polish(label)
