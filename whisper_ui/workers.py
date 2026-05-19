"""QThread workers that wrap core.py functions for use in the GUI."""
from __future__ import annotations

import os
import tempfile
import threading

from PySide6.QtCore import QThread, Signal

from .core import (
    WHISPER_CACHE_DIR,
    download_model,
    is_model_downloaded,
    transcribe as _core_transcribe,
)

__all__ = ["WHISPER_CACHE_DIR", "is_model_downloaded", "RecordWorker",
           "DownloadWorker", "TranscribeWorker"]


class RecordWorker(QThread):
    """Records from the default microphone until stop() is called."""

    audio_level = Signal(float)   # 0.0–1.0 RMS for VU meter
    finished = Signal(str)        # path to saved WAV file
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop_event = threading.Event()

    def run(self):
        try:
            import numpy as np
            import sounddevice as sd
            import soundfile as sf
        except ImportError as exc:
            self.error.emit(
                f"Missing dependency: {exc}\n"
                "Run: pip install sounddevice soundfile numpy"
            )
            return

        self._stop_event.clear()
        sample_rate = 16_000
        chunks: list = []

        def _cb(indata, frames, time, status):
            data = indata.copy()
            chunks.append(data)
            rms = float(np.sqrt(np.mean(data ** 2)))
            self.audio_level.emit(min(rms * 20.0, 1.0))

        try:
            with sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                callback=_cb,
            ):
                self._stop_event.wait()

            if not chunks:
                self.error.emit("No audio was captured.")
                return

            data = np.concatenate(chunks, axis=0)
            fd, path = tempfile.mkstemp(suffix=".wav", prefix="whisper_rec_")
            os.close(fd)
            sf.write(path, data, sample_rate)
            self.finished.emit(path)

        except Exception as exc:
            self.error.emit(str(exc))

    def stop(self):
        self._stop_event.set()


class DownloadWorker(QThread):
    """Downloads a whisper model, forwarding progress signals to the GUI."""

    progress = Signal(int)      # 0–100
    speed_label = Signal(str)   # e.g. "4.2 MB/s"
    finished = Signal()
    error = Signal(str)

    def __init__(self, model_name: str, parent=None):
        super().__init__(parent)
        self.model_name = model_name

    def run(self):
        def _cb(pct: int, speed: str):
            self.progress.emit(pct)
            self.speed_label.emit(speed)

        try:
            download_model(self.model_name, progress_callback=_cb)
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))


class TranscribeWorker(QThread):
    """Runs core.transcribe() in a thread, forwarding status and results."""

    status = Signal(str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(
        self,
        model_name: str,
        audio_path: str,
        device: str,
        transcribe_kwargs: dict,
        parent=None,
    ):
        super().__init__(parent)
        self.model_name = model_name
        self.audio_path = audio_path
        self.device = device
        # Strip any GUI-only keys that core.transcribe doesn't accept
        kw = dict(transcribe_kwargs)
        kw.pop("verbose", None)       # we set it explicitly
        kw.pop("vad_filter", None)    # faster-whisper only; not in openai-whisper
        self.transcribe_kwargs = kw

    def run(self):
        try:
            result = _core_transcribe(
                self.audio_path,
                model_name=self.model_name,
                device=self.device,
                status_callback=self.status.emit,
                verbose=False,
                **self.transcribe_kwargs,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))
