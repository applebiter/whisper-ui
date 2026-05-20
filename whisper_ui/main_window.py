"""Main application window."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .audio_panel import AudioPanel
from .llm_panel import LlmPanel
from .model_panel import ModelPanel
from .ollama_client import OllamaWorker
from .options_panel import OptionsPanel
from .output_panel import OutputPanel
from .workers import TranscribeWorker, is_model_downloaded

# ─────────────────────────────────────────── dark stylesheet ─────────────────

_STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #cccccc;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #3e3e42;
    border-radius: 6px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #9cdcfe;
    font-weight: bold;
}
QComboBox {
    background: #2d2d2d;
    border: 1px solid #3e3e42;
    border-radius: 4px;
    padding: 4px 8px;
    color: #cccccc;
    min-height: 26px;
}
QComboBox:hover { border-color: #007acc; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: #252526;
    border: 1px solid #007acc;
    color: #cccccc;
    selection-background-color: #094771;
    selection-color: #ffffff;
    outline: none;
}
QLineEdit {
    background: #2d2d2d;
    border: 1px solid #3e3e42;
    border-radius: 4px;
    padding: 4px 8px;
    color: #cccccc;
    min-height: 26px;
}
QLineEdit:focus { border-color: #007acc; }
QTextEdit {
    background: #1a1a1a;
    border: 1px solid #3e3e42;
    border-radius: 4px;
    color: #d4d4d4;
    font-size: 13px;
}
QPushButton {
    background: #0078d4;
    border: none;
    border-radius: 4px;
    padding: 6px 18px;
    color: white;
    font-weight: 600;
    min-height: 28px;
}
QPushButton:hover { background: #1086e8; }
QPushButton:pressed { background: #006abc; }
QPushButton:disabled { background: #333333; color: #555555; }
QPushButton[flat="true"] {
    background: transparent;
    border: 1px solid #3e3e42;
    color: #cccccc;
    font-weight: normal;
}
QPushButton[flat="true"]:hover { background: #2a2d2e; border-color: #007acc; }
QPushButton[flat="true"]:disabled { background: transparent; border-color: #333; color: #444; }
QRadioButton, QCheckBox { spacing: 6px; color: #cccccc; }
QRadioButton::indicator, QCheckBox::indicator { width: 14px; height: 14px; }
QProgressBar {
    border: none;
    border-radius: 3px;
    background: #2d2d2d;
    min-height: 8px;
    max-height: 8px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #007acc, stop:1 #00b4d8);
    border-radius: 3px;
}
QLabel { color: #cccccc; }
QLabel[class="muted"] { color: #858585; }
QLabel[class="success"] { color: #4ec9b0; }
QLabel[class="warning"] { color: #ffcc00; }
QLabel[class="error"] { color: #f44747; }
QStatusBar {
    background: #007acc;
    color: white;
    font-weight: 600;
    padding: 2px 8px;
    min-height: 26px;
}
QStatusBar::item { border: none; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    background: #1e1e1e;
    width: 10px;
    border: none;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #424242;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #555555; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QDialog {
    background-color: #1e1e1e;
    color: #cccccc;
}
QDialogButtonBox QPushButton { min-width: 80px; }
"""


# ─────────────────────────────────────────────────── main window ──────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._audio_path = ""
        self._model_name = ""
        self._transcribe_worker: TranscribeWorker | None = None
        self._ollama_worker: OllamaWorker | None = None
        self._build_ui()
        self.setStyleSheet(_STYLE)

    def _build_ui(self):
        self.setWindowTitle("WhisperUI")
        self.setMinimumSize(800, 900)
        self.resize(960, 1060)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setCentralWidget(scroll)

        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(body)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        # ── Model ──────────────────────────────────────────────────────────────
        self._model_panel = ModelPanel()
        self._model_panel.model_changed.connect(self._on_model_changed)
        self._model_panel.model_downloaded.connect(self._on_model_changed)
        root.addWidget(self._model_panel)

        # ── Audio + Options ────────────────────────────────────────────────────
        mid = QHBoxLayout()
        mid.setSpacing(10)

        self._audio_panel = AudioPanel()
        self._audio_panel.audio_ready.connect(self._on_audio_ready)
        self._audio_panel.audio_cleared.connect(self._on_audio_cleared)
        mid.addWidget(self._audio_panel, 3)

        self._options_panel = OptionsPanel()
        mid.addWidget(self._options_panel, 2)

        root.addLayout(mid)

        # ── Transcribe action bar ──────────────────────────────────────────────
        action = QHBoxLayout()

        self._transcribe_btn = QPushButton("▶   Transcribe")
        self._transcribe_btn.setEnabled(False)
        self._transcribe_btn.setMinimumHeight(42)
        sp = self._transcribe_btn.sizePolicy()
        sp.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
        self._transcribe_btn.setSizePolicy(sp)
        self._transcribe_btn.clicked.connect(self._start_transcription)
        action.addWidget(self._transcribe_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setProperty("flat", "true")
        self._cancel_btn.setMinimumHeight(42)
        self._cancel_btn.setFixedWidth(100)
        self._cancel_btn.hide()
        self._cancel_btn.clicked.connect(self._cancel_transcription)
        action.addWidget(self._cancel_btn)

        root.addLayout(action)

        # ── Output ────────────────────────────────────────────────────────────
        self._output_panel = OutputPanel()
        self._output_panel.has_text_changed.connect(self._on_output_text_changed)
        root.addWidget(self._output_panel, 1)

        # ── LLM formatting ────────────────────────────────────────────────────
        self._llm_panel = LlmPanel()
        self._llm_panel.format_requested.connect(self._start_llm_format)
        root.addWidget(self._llm_panel)

        # ── Status bar ────────────────────────────────────────────────────────
        self._status_lbl = QLabel("Ready")
        self.statusBar().addWidget(self._status_lbl, 1)

        self._model_name = self._model_panel.current_model()
        self._update_transcribe_btn()

    # ───────────────────────────────────────────── transcription flow ─────────

    def _on_model_changed(self, name: str):
        self._model_name = name
        self._update_transcribe_btn()

    def _on_audio_ready(self, path: str):
        self._audio_path = path
        self._update_transcribe_btn()

    def _on_audio_cleared(self):
        self._audio_path = ""
        self._update_transcribe_btn()

    def _on_output_text_changed(self, has_text: bool):
        self._llm_panel.set_ready(has_text)

    def _update_transcribe_btn(self):
        has_audio = bool(self._audio_path)
        has_model = bool(self._model_name) and is_model_downloaded(self._model_name)
        self._transcribe_btn.setEnabled(has_audio and has_model)

        if self._model_name and not is_model_downloaded(self._model_name):
            self._set_status(
                f"Model '{self._model_name}' is not downloaded — click Download above."
            )
        elif not has_audio:
            self._set_status("Select an audio file or record audio to get started.")
        else:
            self._set_status("Ready to transcribe.")

    def _start_transcription(self):
        if not self._audio_path or not self._model_name:
            return
        if not is_model_downloaded(self._model_name):
            QMessageBox.warning(
                self,
                "Model Not Downloaded",
                f"The model '{self._model_name}' hasn't been downloaded yet.\n"
                "Use the Download button in the Model section.",
            )
            return

        device = self._options_panel.get_device()
        kwargs = self._options_panel.get_transcribe_kwargs()

        self._transcribe_btn.setEnabled(False)
        self._cancel_btn.show()
        self._output_panel.clear()
        self._set_status("Starting…")

        self._transcribe_worker = TranscribeWorker(
            self._model_name, self._audio_path, device, kwargs, self
        )
        self._transcribe_worker.status.connect(self._set_status)
        self._transcribe_worker.finished.connect(self._on_transcribe_done)
        self._transcribe_worker.error.connect(self._on_transcribe_error)
        self._transcribe_worker.start()

    def _cancel_transcription(self):
        if self._transcribe_worker and self._transcribe_worker.isRunning():
            self._transcribe_worker.terminate()
            self._transcribe_worker.wait(3000)
        self._transcribe_finish_up()
        self._set_status("Cancelled.")

    def _on_transcribe_done(self, result: dict):
        self._output_panel.show_result(result)
        self._transcribe_finish_up()
        self._set_status("Transcription complete.")

    def _on_transcribe_error(self, msg: str):
        QMessageBox.critical(self, "Transcription Error", msg)
        self._transcribe_finish_up()
        self._set_status(f"Error: {msg[:80]}")

    def _transcribe_finish_up(self):
        self._cancel_btn.hide()
        self._update_transcribe_btn()

    # ──────────────────────────────────────────────── LLM format flow ─────────

    def _start_llm_format(self, preset_prompt: str, extra_instruction: str):
        raw = self._output_panel.raw_text()
        if not raw:
            return

        # Build the final prompt
        prompt = preset_prompt.replace("{text}", raw)
        if extra_instruction:
            prompt += f"\n\nAdditional instruction: {extra_instruction}"

        host = self._llm_panel.current_host()
        model = self._llm_panel.current_model()
        if not model:
            QMessageBox.warning(
                self,
                "No Model Selected",
                "Connect to Ollama and select a model first.",
            )
            return

        self._output_panel.begin_streaming()
        self._llm_panel.set_busy(True)
        self._set_status(f"Formatting with {model}…")

        self._ollama_worker = OllamaWorker(host, model, prompt, self)
        self._ollama_worker.chunk_received.connect(self._output_panel.append_chunk)
        self._ollama_worker.finished.connect(self._on_llm_done)
        self._ollama_worker.error.connect(self._on_llm_error)
        self._ollama_worker.start()

    def _on_llm_done(self, full_text: str):
        self._output_panel.finish_streaming(full_text)
        self._llm_panel.set_busy(False)
        self._set_status("Formatting complete.")

    def _on_llm_error(self, msg: str):
        QMessageBox.critical(self, "Ollama Error", msg)
        self._llm_panel.set_busy(False)
        self._set_status(f"Ollama error: {msg[:80]}")
        # Restore output to original transcription
        self._output_panel.finish_streaming("")

    # ─────────────────────────────────────────────────────── helpers ──────────

    def _set_status(self, msg: str):
        self._status_lbl.setText(msg)
