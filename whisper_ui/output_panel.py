"""Output panel — displays transcription in multiple formats with copy/save."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
)

from .formats import FORMATS, FORMAT_KEYS, convert

# Ordered list for the radio buttons (same order as FORMAT_KEYS)
_DISPLAY_ORDER = FORMAT_KEYS  # ["txt", "srt", "vtt", "tsv", "json"]


class OutputPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Output", parent)
        self._result: dict | None = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # Info row: detected language + audio duration
        info_row = QHBoxLayout()
        self._lang_lbl = QLabel()
        self._lang_lbl.setProperty("class", "muted")
        info_row.addWidget(self._lang_lbl)
        info_row.addStretch()
        self._dur_lbl = QLabel()
        self._dur_lbl.setProperty("class", "muted")
        info_row.addWidget(self._dur_lbl)
        root.addLayout(info_row)

        # Format selector
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self._fmt_group = QButtonGroup(self)
        for i, key in enumerate(_DISPLAY_ORDER):
            label = FORMATS[key][0]
            rb = QRadioButton(label)
            if i == 0:
                rb.setChecked(True)
            self._fmt_group.addButton(rb, i)
            fmt_row.addWidget(rb)
        fmt_row.addStretch()
        self._fmt_group.idClicked.connect(self._refresh)
        root.addLayout(fmt_row)

        # Text area
        self._editor = QTextEdit()
        self._editor.setReadOnly(True)
        self._editor.setMinimumHeight(220)
        self._editor.setPlaceholderText(
            "Transcription output will appear here after processing…"
        )
        root.addWidget(self._editor, 1)

        # Action buttons
        btn_row = QHBoxLayout()
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(self._copy)
        btn_row.addWidget(copy_btn)

        save_btn = QPushButton("Save As…")
        save_btn.setProperty("flat", "true")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setProperty("flat", "true")
        clear_btn.clicked.connect(self.clear)
        btn_row.addWidget(clear_btn)

        btn_row.addStretch()
        root.addLayout(btn_row)

    # ---------------------------------------------------------------- public

    def show_result(self, result: dict):
        self._result = result

        lang = result.get("language") or "unknown"
        self._lang_lbl.setText(f"Detected language: {lang.capitalize()}")

        segs = result.get("segments", [])
        if segs:
            total = segs[-1]["end"]
            m, s = divmod(int(total), 60)
            self._dur_lbl.setText(f"Duration: {m:02d}:{s:02d}")

        self._refresh()

    def clear(self):
        self._result = None
        self._editor.clear()
        self._lang_lbl.clear()
        self._dur_lbl.clear()

    def current_text(self) -> str:
        return self._editor.toPlainText()

    # ---------------------------------------------------------------- private

    def _current_format_key(self) -> str:
        idx = max(0, self._fmt_group.checkedId())
        return _DISPLAY_ORDER[idx]

    def _refresh(self):
        if self._result is None:
            return
        self._editor.setPlainText(convert(self._result, self._current_format_key()))

    def _copy(self):
        text = self._editor.toPlainText()
        if text:
            QApplication.clipboard().setText(text)

    def _save(self):
        if not self._result:
            return
        key = self._current_format_key()
        label, ext, _ = FORMATS[key]
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save as {label}",
            f"transcription.{ext}",
            f"{label} Files (*.{ext});;All Files (*)",
        )
        if path:
            Path(path).write_text(convert(self._result, key), encoding="utf-8")
