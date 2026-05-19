"""Audio source panel — open a file or record from the microphone."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QRadioButton,
)

from .workers import RecordWorker

_AUDIO_FILTER = (
    "Audio / Video Files "
    "(*.mp3 *.mp4 *.m4a *.wav *.flac *.ogg *.opus *.webm *.mkv "
    "*.aac *.wma *.aiff *.au *.mpeg *.mpga *.mov *.avi *.ts *.mka);;"
    "All Files (*)"
)


class LevelMeter(QWidget):
    """Simple horizontal RMS level bar with green→yellow→red gradient."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._level = 0.0
        self.setFixedHeight(16)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._decay = QTimer(self)
        self._decay.setInterval(40)
        self._decay.timeout.connect(self._tick_decay)

    def set_level(self, level: float):
        self._level = max(0.0, min(1.0, level))
        if not self._decay.isActive():
            self._decay.start()
        self.update()

    def _tick_decay(self):
        if self._level > 0.0:
            self._level = max(0.0, self._level - 0.05)
            self.update()
        else:
            self._decay.stop()

    def reset(self):
        self._level = 0.0
        self._decay.stop()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#2a2a2a"))
        bar_w = int(w * self._level)
        if bar_w > 2:
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0.00, QColor("#4ec9b0"))
            grad.setColorAt(0.65, QColor("#ffcc00"))
            grad.setColorAt(1.00, QColor("#f44747"))
            p.fillRect(2, 2, bar_w - 4, h - 4, grad)


class AudioPanel(QGroupBox):
    audio_ready = Signal(str)    # emits path when audio is available
    audio_cleared = Signal()     # emits when audio source is removed

    def __init__(self, parent=None):
        super().__init__("Audio Source", parent)
        self._audio_path = ""
        self._record_worker: RecordWorker | None = None
        self._elapsed = 0
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._on_tick)
        self._suppress_record_result = False
        self._build_ui()

    # ------------------------------------------------------------------ build

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # Source selector
        src_row = QHBoxLayout()
        self._src_group = QButtonGroup(self)
        self._rb_file = QRadioButton("Open File")
        self._rb_record = QRadioButton("Record Microphone")
        self._rb_file.setChecked(True)
        self._src_group.addButton(self._rb_file, 0)
        self._src_group.addButton(self._rb_record, 1)
        src_row.addWidget(self._rb_file)
        src_row.addWidget(self._rb_record)
        src_row.addStretch()
        root.addLayout(src_row)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_file_page())
        self._stack.addWidget(self._build_record_page())
        root.addWidget(self._stack)

        self._src_group.idClicked.connect(self._on_source_switched)

    def _build_file_page(self) -> QWidget:
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)

        self._file_edit = QLineEdit()
        self._file_edit.setPlaceholderText("No file selected…")
        self._file_edit.setReadOnly(True)
        row.addWidget(self._file_edit, 1)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_file)
        row.addWidget(browse_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setProperty("flat", "true")
        clear_btn.clicked.connect(self._clear_file)
        row.addWidget(clear_btn)
        return page

    def _build_record_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        ctrl = QHBoxLayout()
        self._rec_btn = QPushButton("● Start Recording")
        self._rec_btn.clicked.connect(self._toggle_recording)
        ctrl.addWidget(self._rec_btn)

        self._rec_time = QLabel("00:00")
        self._rec_time.setMinimumWidth(44)
        self._rec_time.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        ctrl.addWidget(self._rec_time)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self._level_meter = LevelMeter()
        layout.addWidget(self._level_meter)

        self._rec_status = QLabel("No recording yet.")
        self._rec_status.setProperty("class", "muted")
        layout.addWidget(self._rec_status)
        return page

    # --------------------------------------------------------------- handlers

    def _on_source_switched(self, source_id: int):
        self._stack.setCurrentIndex(source_id)
        if source_id == 0:
            # Switched to File — stop any active recording silently
            self._suppress_record_result = True
            self._stop_recording_worker()
            self._suppress_record_result = False
        else:
            # Switched to Record — clear file selection
            self._clear_file()

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Audio / Video File", "", _AUDIO_FILTER
        )
        if path:
            self._audio_path = path
            self._file_edit.setText(path)
            self.audio_ready.emit(path)

    def _clear_file(self):
        self._audio_path = ""
        self._file_edit.clear()
        self.audio_cleared.emit()

    def _toggle_recording(self):
        if self._record_worker and self._record_worker.isRunning():
            self._stop_recording_worker()
        else:
            self._start_recording()

    def _start_recording(self):
        self._elapsed = 0
        self._rec_time.setText("00:00")
        self._level_meter.reset()
        self._rec_status.setText("Recording…")
        self._set_label_class(self._rec_status, "")
        self._rec_btn.setText("■  Stop Recording")
        self._audio_path = ""
        self.audio_cleared.emit()

        self._record_worker = RecordWorker(self)
        self._record_worker.audio_level.connect(self._level_meter.set_level)
        self._record_worker.finished.connect(self._on_record_finished)
        self._record_worker.error.connect(self._on_record_error)
        self._record_worker.start()
        self._tick_timer.start()

    def _stop_recording_worker(self):
        self._tick_timer.stop()
        if self._record_worker and self._record_worker.isRunning():
            self._record_worker.stop()
        self._rec_btn.setText("● Start Recording")

    def _on_record_finished(self, path: str):
        self._rec_btn.setText("● Start Recording")
        if self._suppress_record_result:
            return
        duration = self._rec_time.text()
        self._audio_path = path
        self._rec_status.setText(
            f"Saved  ·  {duration}  →  {os.path.basename(path)}"
        )
        self._set_label_class(self._rec_status, "success")
        if self._src_group.checkedId() == 1:
            self.audio_ready.emit(path)

    def _on_record_error(self, msg: str):
        self._rec_btn.setText("● Start Recording")
        self._tick_timer.stop()
        self._rec_status.setText(f"Error: {msg}")
        self._set_label_class(self._rec_status, "error")

    def _on_tick(self):
        self._elapsed += 1
        m, s = divmod(self._elapsed, 60)
        self._rec_time.setText(f"{m:02d}:{s:02d}")

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _set_label_class(label: QLabel, cls: str):
        label.setProperty("class", cls)
        label.style().unpolish(label)
        label.style().polish(label)

    def audio_path(self) -> str:
        return self._audio_path
