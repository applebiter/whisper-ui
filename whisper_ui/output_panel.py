"""Output panel — displays transcription in multiple formats with copy/save."""
from __future__ import annotations

import json

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


# ──────────────────────────────────────────────── format converters ──────────

def _ts_srt(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ts_vtt(sec: float) -> str:
    return _ts_srt(sec).replace(",", ".")


def _to_text(result: dict) -> str:
    return result.get("text", "").strip()


def _to_srt(result: dict) -> str:
    parts = []
    for i, seg in enumerate(result.get("segments", []), 1):
        parts.append(
            f"{i}\n"
            f"{_ts_srt(seg['start'])} --> {_ts_srt(seg['end'])}\n"
            f"{seg['text'].strip()}"
        )
    return "\n\n".join(parts)


def _to_vtt(result: dict) -> str:
    parts = ["WEBVTT\n"]
    for seg in result.get("segments", []):
        parts.append(
            f"{_ts_vtt(seg['start'])} --> {_ts_vtt(seg['end'])}\n"
            f"{seg['text'].strip()}"
        )
    return "\n\n".join(parts)


def _to_tsv(result: dict) -> str:
    rows = ["start\tend\ttext"]
    for seg in result.get("segments", []):
        rows.append(
            f"{seg['start']:.3f}\t{seg['end']:.3f}\t{seg['text'].strip()}"
        )
    return "\n".join(rows)


def _to_json(result: dict) -> str:
    return json.dumps(result, indent=2, ensure_ascii=False, default=str)


_FORMATS = [
    ("Text", "txt", _to_text),
    ("SRT", "srt", _to_srt),
    ("VTT", "vtt", _to_vtt),
    ("TSV", "tsv", _to_tsv),
    ("JSON", "json", _to_json),
]


# ──────────────────────────────────────────────────────────── widget ─────────

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
        for i, (label, _ext, _fn) in enumerate(_FORMATS):
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

    def _refresh(self):
        if self._result is None:
            return
        idx = max(0, self._fmt_group.checkedId())
        _label, _ext, converter = _FORMATS[idx]
        self._editor.setPlainText(converter(self._result))

    def _copy(self):
        text = self._editor.toPlainText()
        if text:
            QApplication.clipboard().setText(text)

    def _save(self):
        if not self._result:
            return
        idx = max(0, self._fmt_group.checkedId())
        label, ext, converter = _FORMATS[idx]
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save as {label}",
            f"transcription.{ext}",
            f"{label} Files (*.{ext});;All Files (*)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(converter(self._result))
