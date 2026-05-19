"""Background QThread workers: recording, model download, and transcription."""
from __future__ import annotations

import os
import tempfile
import threading

from PySide6.QtCore import QThread, Signal

WHISPER_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "whisper")

_model_cache: dict = {}
_model_lock = threading.Lock()


def is_model_downloaded(model_name: str) -> bool:
    """Return True if the model file exists in the whisper cache."""
    try:
        import whisper
        url = whisper._MODELS.get(model_name, "")
        if not url:
            return False
        return os.path.isfile(os.path.join(WHISPER_CACHE_DIR, os.path.basename(url)))
    except Exception:
        return False


class RecordWorker(QThread):
    """Records from the default microphone until stop() is called."""

    audio_level = Signal(float)   # 0.0–1.0 RMS level for VU meter
    finished = Signal(str)        # path to saved WAV file
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop_event = threading.Event()

    def run(self):
        try:
            import sounddevice as sd
            import soundfile as sf
            import numpy as np
        except ImportError as exc:
            self.error.emit(
                f"Missing dependency: {exc}\n"
                "Run: pip install sounddevice soundfile numpy"
            )
            return

        self._stop_event.clear()
        sample_rate = 16_000
        chunks: list = []

        def _callback(indata, frames, time, status):
            data = indata.copy()
            chunks.append(data)
            rms = float(np.sqrt(np.mean(data ** 2)))
            self.audio_level.emit(min(rms * 20.0, 1.0))

        try:
            with sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                callback=_callback,
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
    """Downloads a whisper model file with streaming progress."""

    progress = Signal(int)       # 0–100 percentage
    speed_label = Signal(str)    # human-readable speed string
    finished = Signal()
    error = Signal(str)

    def __init__(self, model_name: str, parent=None):
        super().__init__(parent)
        self.model_name = model_name

    def run(self):
        import time

        dest = ""
        try:
            import whisper
            import requests

            os.makedirs(WHISPER_CACHE_DIR, exist_ok=True)
            url = whisper._MODELS[self.model_name]
            dest = os.path.join(WHISPER_CACHE_DIR, os.path.basename(url))

            resp = requests.get(url, stream=True, timeout=60)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            start = time.monotonic()

            with open(dest, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=65_536):
                    fh.write(chunk)
                    downloaded += len(chunk)
                    elapsed = max(time.monotonic() - start, 1e-6)
                    if total:
                        self.progress.emit(int(downloaded * 100 / total))
                    bps = downloaded / elapsed
                    if bps >= 1_048_576:
                        self.speed_label.emit(f"{bps / 1_048_576:.1f} MB/s")
                    else:
                        self.speed_label.emit(f"{bps / 1024:.0f} KB/s")

            self.finished.emit()

        except Exception as exc:
            if dest and os.path.exists(dest):
                try:
                    os.remove(dest)
                except OSError:
                    pass
            self.error.emit(str(exc))


class TranscribeWorker(QThread):
    """Loads a whisper model (cached) and runs transcription in a thread."""

    status = Signal(str)     # status messages for the UI
    finished = Signal(dict)  # whisper result dict
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
        self.transcribe_kwargs = dict(transcribe_kwargs)

    def run(self):
        try:
            import whisper

            cache_key = (self.model_name, self.device)
            with _model_lock:
                if cache_key not in _model_cache:
                    self.status.emit(f"Loading model '{self.model_name}'…")
                    _model_cache[cache_key] = whisper.load_model(
                        self.model_name, device=self.device
                    )

            model = _model_cache[cache_key]
            self.status.emit("Transcribing…")
            result = model.transcribe(self.audio_path, **self.transcribe_kwargs)
            self.finished.emit(dict(result))

        except Exception as exc:
            self.error.emit(str(exc))
