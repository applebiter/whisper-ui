"""Output panel — displays transcription or LLM-formatted Markdown."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
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

_DISPLAY_ORDER = FORMAT_KEYS


# ── Markdown → HTML helper ────────────────────────────────────────────────────

def _to_html(md_text: str) -> str:
    """Convert Markdown to HTML for QTextEdit rendering.

    Uses Qt's built-in Markdown engine — no extra dependencies needed.
    A throwaway QTextEdit is used just for the conversion.
    """
    tmp = QTextEdit()
    tmp.setMarkdown(md_text)
    return tmp.toHtml()


# ── Fonts ─────────────────────────────────────────────────────────────────────

def _mono_font() -> QFont:
    f = QFont()
    f.setFamilies(["Cascadia Code", "Fira Code", "JetBrains Mono", "Courier New"])
    f.setFixedPitch(True)
    f.setPointSize(12)
    return f


def _prose_font() -> QFont:
    f = QFont()
    f.setFamilies(["Segoe UI", "Ubuntu", "Helvetica Neue", "Arial"])
    f.setFixedPitch(False)
    f.setPointSize(13)
    return f


# ── Widget ────────────────────────────────────────────────────────────────────

class OutputPanel(QGroupBox):
    # Emitted when content changes so LlmPanel can enable/disable its button
    has_text_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__("Output", parent)
        self._result: dict | None = None
        self._raw_text: str = ""        # original whisper plain text
        self._markdown_text: str = ""   # LLM-formatted text (may be empty)
        self._view: str = "source"      # "source" | "rendered"
        self._streaming = False
        self._build_ui()

    # ------------------------------------------------------------------ build

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # ── Info row ──────────────────────────────────────────────────────────
        info_row = QHBoxLayout()
        self._lang_lbl = QLabel()
        self._lang_lbl.setProperty("class", "muted")
        info_row.addWidget(self._lang_lbl)
        info_row.addStretch()
        self._dur_lbl = QLabel()
        self._dur_lbl.setProperty("class", "muted")
        info_row.addWidget(self._dur_lbl)
        root.addLayout(info_row)

        # ── View toggle + format selector row ─────────────────────────────────
        ctrl_row = QHBoxLayout()

        # Source / Rendered radio toggle
        self._view_group = QButtonGroup(self)
        self._rb_source = QRadioButton("Source")
        self._rb_rendered = QRadioButton("✨ Rendered")
        self._rb_source.setChecked(True)
        self._rb_rendered.setEnabled(False)
        self._view_group.addButton(self._rb_source, 0)
        self._view_group.addButton(self._rb_rendered, 1)
        ctrl_row.addWidget(self._rb_source)
        ctrl_row.addWidget(self._rb_rendered)

        # Thin separator
        sep = QLabel("│")
        sep.setProperty("class", "muted")
        ctrl_row.addWidget(sep)

        # Format selector (only meaningful in source view)
        self._fmt_group = QButtonGroup(self)
        for i, key in enumerate(_DISPLAY_ORDER):
            label = FORMATS[key][0]
            rb = QRadioButton(label)
            if i == 0:
                rb.setChecked(True)
            self._fmt_group.addButton(rb, i)
            ctrl_row.addWidget(rb)
            setattr(self, f"_fmt_rb_{key}", rb)  # keep refs for toggling

        ctrl_row.addStretch()
        self._view_group.idClicked.connect(self._on_view_toggled)
        self._fmt_group.idClicked.connect(self._refresh_display)
        root.addLayout(ctrl_row)

        # ── Text area ─────────────────────────────────────────────────────────
        self._editor = QTextEdit()
        self._editor.setReadOnly(True)
        self._editor.setMinimumHeight(240)
        self._editor.setFont(_mono_font())
        self._editor.setPlaceholderText(
            "Transcription output will appear here…"
        )
        root.addWidget(self._editor, 1)

        # ── Action buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        copy_btn = QPushButton("Copy")
        copy_btn.clicked.connect(self._copy)
        btn_row.addWidget(copy_btn)

        save_btn = QPushButton("Save As…")
        save_btn.setProperty("flat", "true")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        self._revert_btn = QPushButton("↩ Revert to Original")
        self._revert_btn.setProperty("flat", "true")
        self._revert_btn.setVisible(False)
        self._revert_btn.clicked.connect(self._revert)
        btn_row.addWidget(self._revert_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setProperty("flat", "true")
        clear_btn.clicked.connect(self.clear)
        btn_row.addWidget(clear_btn)

        btn_row.addStretch()
        root.addLayout(btn_row)

    # ----------------------------------------------------------------- public

    def show_result(self, result: dict):
        """Display the result of a whisper transcription."""
        self._result = result
        self._markdown_text = ""

        lang = result.get("language") or "unknown"
        self._lang_lbl.setText(f"Detected language: {lang.capitalize()}")

        segs = result.get("segments", [])
        if segs:
            m, s = divmod(int(segs[-1]["end"]), 60)
            self._dur_lbl.setText(f"Duration: {m:02d}:{s:02d}")

        self._raw_text = result.get("text", "").strip()

        # Reset to source view
        self._set_view("source")
        self._rb_rendered.setEnabled(False)
        self._revert_btn.setVisible(False)
        self._refresh_display()
        self.has_text_changed.emit(bool(self._raw_text))

    def begin_streaming(self):
        """Called before OllamaWorker starts; prepares the editor for live output."""
        self._streaming = True
        self._markdown_text = ""
        self._set_view("source")
        self._rb_rendered.setEnabled(False)
        self._revert_btn.setVisible(False)
        # Show format selector in plain-text mode during stream
        self._fmt_group.button(0).setChecked(True)
        self._editor.setFont(_mono_font())
        self._editor.setPlainText("")
        self._editor.setPlaceholderText("Formatting…")

    def append_chunk(self, chunk: str):
        """Append a streamed token from OllamaWorker."""
        self._markdown_text += chunk
        self._editor.moveCursor(self._editor.textCursor().MoveOperation.End)
        self._editor.insertPlainText(chunk)

    def finish_streaming(self, full_text: str):
        """Called when OllamaWorker finishes; switches to rendered Markdown."""
        self._streaming = False
        self._markdown_text = full_text
        self._revert_btn.setVisible(True)
        self._rb_rendered.setEnabled(True)
        self._set_view("rendered")

    def raw_text(self) -> str:
        """The original plain transcription (before any LLM formatting)."""
        return self._raw_text

    def clear(self):
        self._result = None
        self._raw_text = ""
        self._markdown_text = ""
        self._editor.clear()
        self._lang_lbl.clear()
        self._dur_lbl.clear()
        self._rb_rendered.setEnabled(False)
        self._revert_btn.setVisible(False)
        self._set_view("source")
        self.has_text_changed.emit(False)

    # --------------------------------------------------------------- private

    def _on_view_toggled(self, view_id: int):
        self._view = "rendered" if view_id == 1 else "source"
        self._refresh_display()

    def _set_view(self, view: str):
        self._view = view
        self._rb_source.setChecked(view == "source")
        self._rb_rendered.setChecked(view == "rendered")
        self._refresh_display()

    def _refresh_display(self):
        if self._streaming:
            return  # live updates via append_chunk

        if self._view == "rendered" and self._markdown_text:
            self._editor.setFont(_prose_font())
            self._editor.setMarkdown(self._markdown_text)
            self._set_format_controls_visible(False)
        else:
            self._editor.setFont(_mono_font())
            self._set_format_controls_visible(True)
            if self._result is None and not self._raw_text:
                self._editor.clear()
                return
            fmt_id = max(0, self._fmt_group.checkedId())
            key = _DISPLAY_ORDER[fmt_id]
            if self._result is not None:
                self._editor.setPlainText(convert(self._result, key))
            else:
                self._editor.setPlainText(self._raw_text)

    def _set_format_controls_visible(self, visible: bool):
        for key in _DISPLAY_ORDER:
            rb = getattr(self, f"_fmt_rb_{key}", None)
            if rb:
                rb.setVisible(visible)

    def _revert(self):
        self._markdown_text = ""
        self._rb_rendered.setEnabled(False)
        self._revert_btn.setVisible(False)
        self._set_view("source")

    def _copy(self):
        text = self._editor.toPlainText()
        if text:
            QApplication.clipboard().setText(text)

    def _save(self):
        if self._view == "rendered" and self._markdown_text:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Markdown", "formatted.md",
                "Markdown Files (*.md);;Text Files (*.txt);;All Files (*)",
            )
            if path:
                Path(path).write_text(self._markdown_text, encoding="utf-8")
            return

        if not self._result:
            return
        fmt_id = max(0, self._fmt_group.checkedId())
        label, ext, converter = FORMATS[_DISPLAY_ORDER[fmt_id]]
        path, _ = QFileDialog.getSaveFileName(
            self, f"Save as {label}", f"transcription.{ext}",
            f"{label} Files (*.{ext});;All Files (*)",
        )
        if path:
            Path(path).write_text(converter(self._result), encoding="utf-8")

    def current_text(self) -> str:
        return self._editor.toPlainText()
