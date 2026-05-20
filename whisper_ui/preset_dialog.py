"""Dialog for creating and editing named prompt presets."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
)


class PresetDialog(QDialog):
    """Modal dialog to create or edit a preset.

    Usage::

        dlg = PresetDialog(parent, name="...", prompt="...")
        if dlg.exec() == QDialog.Accepted:
            name, prompt = dlg.name(), dlg.prompt()
    """

    def __init__(
        self,
        parent=None,
        *,
        name: str = "",
        prompt: str = "",
        title: str = "Preset",
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(560)
        self.setMinimumHeight(420)
        self._build_ui(name, prompt)

    def _build_ui(self, name: str, prompt: str):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._name_edit = QLineEdit(name)
        self._name_edit.setPlaceholderText("e.g. Meeting Notes")
        form.addRow("Name:", self._name_edit)
        root.addLayout(form)

        root.addWidget(QLabel("Prompt template:"))

        hint = QLabel(
            "Use <b>{text}</b> where the transcription should be inserted."
        )
        hint.setProperty("class", "muted")
        root.addWidget(hint)

        self._prompt_edit = QTextEdit()
        self._prompt_edit.setPlainText(prompt)
        self._prompt_edit.setPlaceholderText(
            "Format the following transcription…\n\n{text}"
        )
        self._prompt_edit.setAcceptRichText(False)
        root.addWidget(self._prompt_edit, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _validate_and_accept(self):
        if not self._name_edit.text().strip():
            self._name_edit.setFocus()
            self._name_edit.setPlaceholderText("Name is required")
            return
        if not self._prompt_edit.toPlainText().strip():
            self._prompt_edit.setFocus()
            return
        self.accept()

    def name(self) -> str:
        return self._name_edit.text().strip()

    def prompt(self) -> str:
        return self._prompt_edit.toPlainText().strip()
