"""Transcription options panel — language, task, device, timestamps, etc."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
)

# (display name, whisper language code or None for auto)
_LANGUAGES: list[tuple[str, str | None]] = [
    ("Auto-detect", None),
    ("Afrikaans", "af"),
    ("Arabic", "ar"),
    ("Armenian", "hy"),
    ("Azerbaijani", "az"),
    ("Belarusian", "be"),
    ("Bosnian", "bs"),
    ("Bulgarian", "bg"),
    ("Catalan", "ca"),
    ("Chinese", "zh"),
    ("Croatian", "hr"),
    ("Czech", "cs"),
    ("Danish", "da"),
    ("Dutch", "nl"),
    ("English", "en"),
    ("Estonian", "et"),
    ("Finnish", "fi"),
    ("French", "fr"),
    ("Galician", "gl"),
    ("German", "de"),
    ("Greek", "el"),
    ("Hebrew", "he"),
    ("Hindi", "hi"),
    ("Hungarian", "hu"),
    ("Icelandic", "is"),
    ("Indonesian", "id"),
    ("Italian", "it"),
    ("Japanese", "ja"),
    ("Kannada", "kn"),
    ("Kazakh", "kk"),
    ("Korean", "ko"),
    ("Latvian", "lv"),
    ("Lithuanian", "lt"),
    ("Macedonian", "mk"),
    ("Malay", "ms"),
    ("Marathi", "mr"),
    ("Maori", "mi"),
    ("Nepali", "ne"),
    ("Norwegian", "no"),
    ("Persian", "fa"),
    ("Polish", "pl"),
    ("Portuguese", "pt"),
    ("Romanian", "ro"),
    ("Russian", "ru"),
    ("Serbian", "sr"),
    ("Slovak", "sk"),
    ("Slovenian", "sl"),
    ("Spanish", "es"),
    ("Swahili", "sw"),
    ("Swedish", "sv"),
    ("Tagalog", "tl"),
    ("Tamil", "ta"),
    ("Thai", "th"),
    ("Turkish", "tr"),
    ("Ukrainian", "uk"),
    ("Urdu", "ur"),
    ("Vietnamese", "vi"),
    ("Welsh", "cy"),
]


class OptionsPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Transcription Options", parent)
        self._build_ui()

    def _build_ui(self):
        form = QFormLayout(self)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Language
        self._lang_combo = QComboBox()
        for name, code in _LANGUAGES:
            self._lang_combo.addItem(name, userData=code)
        form.addRow("Language:", self._lang_combo)

        # Task
        task_row = QHBoxLayout()
        self._task_group = QButtonGroup(self)
        self._rb_transcribe = QRadioButton("Transcribe")
        self._rb_translate = QRadioButton("Translate → English")
        self._rb_transcribe.setChecked(True)
        self._task_group.addButton(self._rb_transcribe, 0)
        self._task_group.addButton(self._rb_translate, 1)
        task_row.addWidget(self._rb_transcribe)
        task_row.addWidget(self._rb_translate)
        task_row.addStretch()
        form.addRow("Task:", task_row)

        # Device
        self._device_combo = QComboBox()
        try:
            import torch
            if torch.cuda.is_available():
                name = torch.cuda.get_device_name(0)
                self._device_combo.addItem(f"CUDA  ({name})", userData="cuda")
        except Exception:
            pass
        self._device_combo.addItem("CPU", userData="cpu")
        form.addRow("Device:", self._device_combo)

        # Timestamps
        self._ts_combo = QComboBox()
        self._ts_combo.addItem("None", userData="none")
        self._ts_combo.addItem("Segment-level", userData="segment")
        self._ts_combo.addItem("Word-level", userData="word")
        form.addRow("Timestamps:", self._ts_combo)

        # VAD filter
        self._vad_check = QCheckBox("Apply voice-activity filter (skip silence)")
        self._vad_check.setToolTip(
            "Filters non-speech segments before transcription. "
            "Reduces hallucination on silent audio."
        )
        form.addRow("", self._vad_check)

        # Condition on previous text
        self._condition_check = QCheckBox("Condition on previous segment")
        self._condition_check.setChecked(True)
        self._condition_check.setToolTip(
            "Each segment is conditioned on the previous transcription. "
            "Disable if you notice looping or hallucination."
        )
        form.addRow("", self._condition_check)

        # Initial prompt
        self._prompt_edit = QLineEdit()
        self._prompt_edit.setPlaceholderText(
            "Optional — guide style, vocabulary, or provide context…"
        )
        form.addRow("Initial prompt:", self._prompt_edit)

    # ---------------------------------------------------------------- getters

    def get_device(self) -> str:
        return self._device_combo.currentData() or "cpu"

    def get_transcribe_kwargs(self) -> dict:
        kwargs: dict = {}

        kwargs["language"] = self._lang_combo.currentData()  # None = auto

        kwargs["task"] = (
            "translate" if self._task_group.checkedId() == 1 else "transcribe"
        )

        ts = self._ts_combo.currentData()
        kwargs["word_timestamps"] = ts == "word"

        kwargs["condition_on_previous_text"] = self._condition_check.isChecked()

        if self._vad_check.isChecked():
            kwargs["vad_filter"] = True  # supported by faster-whisper; silently ignored by openai-whisper

        prompt = self._prompt_edit.text().strip()
        if prompt:
            kwargs["initial_prompt"] = prompt

        kwargs["verbose"] = False
        return kwargs
