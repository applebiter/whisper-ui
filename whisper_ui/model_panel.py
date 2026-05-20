"""Model selection panel with download support and per-model descriptions."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QComboBox,
)

from .core import MODEL_INFO, is_model_downloaded
from . import settings as settings_store
from .workers import DownloadWorker

_PREFERRED_DEFAULT = "large-v3-turbo"


class ModelPanel(QGroupBox):
    model_changed = Signal(str)
    model_downloaded = Signal(str)

    def __init__(self, parent=None):
        super().__init__("Model", parent)
        self._download_worker: DownloadWorker | None = None
        self._build_ui()

    # ------------------------------------------------------------------ build

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # Row 1: combo + status + download button
        row1 = QHBoxLayout()

        self._combo = QComboBox()
        self._combo.setMinimumWidth(280)
        self._combo.currentIndexChanged.connect(self._on_selection_changed)
        row1.addWidget(self._combo, 1)

        self._status_lbl = QLabel()
        self._status_lbl.setMinimumWidth(130)
        row1.addWidget(self._status_lbl)

        self._download_btn = QPushButton("⬇  Download")
        self._download_btn.setProperty("flat", "true")
        self._download_btn.setFixedWidth(130)
        self._download_btn.hide()
        self._download_btn.clicked.connect(self._start_download)
        row1.addWidget(self._download_btn)

        root.addLayout(row1)

        # Progress bar (shown only while downloading)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.hide()
        root.addWidget(self._progress_bar)

        # Speed / percentage label
        self._progress_lbl = QLabel()
        self._progress_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._progress_lbl.setProperty("class", "muted")
        self._progress_lbl.hide()
        root.addWidget(self._progress_lbl)

        # Description
        self._desc_lbl = QLabel()
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setProperty("class", "muted")
        root.addWidget(self._desc_lbl)

        self._populate_combo()

    def _populate_combo(self):
        import whisper

        saved = settings_store.load().get("whisper_model", "")

        self._combo.blockSignals(True)
        self._combo.clear()
        default_idx = 0
        for i, name in enumerate(whisper.available_models()):
            info = MODEL_INFO.get(name, {})
            size = info.get("size", "")
            label = f"{name}  ({size})" if size else name
            self._combo.addItem(label, userData=name)
            if name == (saved or _PREFERRED_DEFAULT):
                default_idx = i

        self._combo.blockSignals(False)
        self._combo.setCurrentIndex(default_idx)
        self._on_selection_changed(default_idx)

    # --------------------------------------------------------------- handlers

    def _on_selection_changed(self, index: int):
        name = self._combo.itemData(index)
        if not name:
            return

        info = MODEL_INFO.get(name, {})
        self._desc_lbl.setText(info.get("description", ""))

        cfg = settings_store.load()
        cfg["whisper_model"] = name
        settings_store.save(cfg)

        self._refresh_download_status(name)
        self.model_changed.emit(name)

    def _refresh_download_status(self, name: str):
        if is_model_downloaded(name):
            self._status_lbl.setText("✓  Downloaded")
            self._set_label_class(self._status_lbl, "success")
            self._download_btn.hide()
        else:
            self._status_lbl.setText("↓  Not downloaded")
            self._set_label_class(self._status_lbl, "warning")
            self._download_btn.show()
            self._download_btn.setEnabled(True)

    def _start_download(self):
        name = self.current_model()
        if not name:
            return

        self._download_btn.setEnabled(False)
        self._combo.setEnabled(False)
        self._progress_bar.setValue(0)
        self._progress_bar.show()
        self._progress_lbl.setText("Connecting…")
        self._progress_lbl.show()

        self._download_worker = DownloadWorker(name, self)
        self._download_worker.progress.connect(self._on_progress)
        self._download_worker.speed_label.connect(self._on_speed)
        self._download_worker.finished.connect(self._on_download_finished)
        self._download_worker.error.connect(self._on_download_error)
        self._download_worker.start()

    def _on_progress(self, pct: int):
        self._progress_bar.setValue(pct)

    def _on_speed(self, label: str):
        self._progress_lbl.setText(f"{self._progress_bar.value()}%  ·  {label}")

    def _on_download_finished(self):
        self._progress_bar.hide()
        self._progress_lbl.hide()
        self._combo.setEnabled(True)
        name = self.current_model()
        self._status_lbl.setText("✓  Downloaded")
        self._set_label_class(self._status_lbl, "success")
        self._download_btn.hide()
        self.model_downloaded.emit(name)

    def _on_download_error(self, msg: str):
        self._progress_bar.hide()
        self._combo.setEnabled(True)
        self._download_btn.setEnabled(True)
        self._status_lbl.setText("✗  Download failed")
        self._set_label_class(self._status_lbl, "error")
        self._progress_lbl.setText(f"Error: {msg}")
        self._progress_lbl.show()

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _set_label_class(label: QLabel, cls: str):
        label.setProperty("class", cls)
        label.style().unpolish(label)
        label.style().polish(label)

    def current_model(self) -> str:
        return self._combo.currentData() or ""

    def refresh_status(self):
        self._on_selection_changed(self._combo.currentIndex())
