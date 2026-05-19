"""Pure-Python API for WhisperUI — no Qt, safe to import from any app.

Public surface
──────────────
    available_models()          → list[str]
    model_info(name)            → dict
    is_model_downloaded(name)   → bool
    download_model(name, cb)    → str   (path to .pt file)
    transcribe(audio_path, ...) → dict  (whisper result)
    format_result(result, fmt)  → str   (see formats.FORMAT_KEYS)

The transcribe() function caches loaded models in-process so repeated calls
with the same (model_name, device) don't reload from disk.
"""
from __future__ import annotations

import os
import threading
from typing import Callable

from .formats import convert, FORMAT_KEYS  # re-export convenience

__all__ = [
    "MODEL_INFO",
    "WHISPER_CACHE_DIR",
    "available_models",
    "model_info",
    "is_model_downloaded",
    "download_model",
    "transcribe",
    "format_result",
    "FORMAT_KEYS",
]

WHISPER_CACHE_DIR: str = os.path.join(os.path.expanduser("~"), ".cache", "whisper")

# ── per-model metadata ─────────────────────────────────────────────────────

MODEL_INFO: dict[str, dict] = {
    "tiny.en":         {"size": "~75 MB",   "description": "English-only. Fastest model — great for testing or very limited hardware."},
    "tiny":            {"size": "~75 MB",   "description": "Multilingual. Fastest model. Good for quick tests; lower accuracy."},
    "base.en":         {"size": "~142 MB",  "description": "English-only. Fast with reasonable accuracy."},
    "base":            {"size": "~142 MB",  "description": "Multilingual. Fast with reasonable accuracy. A solid first choice."},
    "small.en":        {"size": "~466 MB",  "description": "English-only. Good speed/quality balance."},
    "small":           {"size": "~466 MB",  "description": "Multilingual. Good speed/quality balance for everyday use."},
    "medium.en":       {"size": "~1.5 GB",  "description": "English-only. High accuracy at moderate speed."},
    "medium":          {"size": "~1.5 GB",  "description": "Multilingual. High accuracy, slower. Needs ~5 GB RAM."},
    "large-v1":        {"size": "~2.9 GB",  "description": "Original large model. Very high accuracy across all languages."},
    "large-v2":        {"size": "~2.9 GB",  "description": "Improved large. Better than v1, especially for non-English."},
    "large-v3":        {"size": "~2.9 GB",  "description": "Latest large model. Best overall accuracy in all 99 supported languages."},
    "large":           {"size": "~2.9 GB",  "description": "Alias for large-v3. Best overall accuracy."},
    "large-v3-turbo":  {"size": "~1.5 GB",  "description": "★ Recommended — near large-v3 accuracy at ~8× the speed. Best quality-to-speed ratio."},
    "turbo":           {"size": "~1.5 GB",  "description": "Alias for large-v3-turbo. Near large-v3 quality at ~8× the speed."},
}

# ── in-process model cache ─────────────────────────────────────────────────
_model_cache: dict = {}
_model_lock = threading.Lock()

# ── model helpers ──────────────────────────────────────────────────────────

def available_models() -> list[str]:
    """Return all model names whisper recognises."""
    import whisper
    return list(whisper.available_models())


def model_info(model_name: str) -> dict:
    """Return size/description dict for *model_name* (empty dict if unknown)."""
    return dict(MODEL_INFO.get(model_name, {}))


def is_model_downloaded(model_name: str) -> bool:
    """Return True if the model file is present in the whisper cache."""
    try:
        import whisper
        url = whisper._MODELS.get(model_name, "")
        if not url:
            return False
        path = os.path.join(WHISPER_CACHE_DIR, os.path.basename(url))
        return os.path.isfile(path)
    except Exception:
        return False


def download_model(
    model_name: str,
    progress_callback: Callable[[int, str], None] | None = None,
) -> str:
    """Download *model_name* to the whisper cache directory.

    *progress_callback*, if provided, is called as ``callback(pct, speed_str)``
    where *pct* is 0–100 and *speed_str* is a human-readable rate like
    ``"4.2 MB/s"``.

    Returns the local path to the downloaded ``.pt`` file.
    Raises on network or I/O errors (partial file is removed).
    """
    import time

    import requests
    import whisper

    os.makedirs(WHISPER_CACHE_DIR, exist_ok=True)
    url = whisper._MODELS[model_name]
    dest = os.path.join(WHISPER_CACHE_DIR, os.path.basename(url))

    try:
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        start = time.monotonic()

        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=65_536):
                fh.write(chunk)
                downloaded += len(chunk)
                if progress_callback is not None:
                    elapsed = max(time.monotonic() - start, 1e-9)
                    pct = int(downloaded * 100 / total) if total else 0
                    bps = downloaded / elapsed
                    if bps >= 1_048_576:
                        speed = f"{bps / 1_048_576:.1f} MB/s"
                    else:
                        speed = f"{bps / 1024:.0f} KB/s"
                    progress_callback(pct, speed)

        return dest

    except Exception:
        if os.path.exists(dest):
            try:
                os.remove(dest)
            except OSError:
                pass
        raise


# ── transcription ──────────────────────────────────────────────────────────

def _auto_device() -> str:
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def transcribe(
    audio_path: str,
    model_name: str = "large-v3-turbo",
    device: str | None = None,
    *,
    task: str = "transcribe",
    language: str | None = None,
    word_timestamps: bool = False,
    condition_on_previous_text: bool = True,
    initial_prompt: str | None = None,
    verbose: bool = False,
    status_callback: Callable[[str], None] | None = None,
) -> dict:
    """Load model (cached) and transcribe *audio_path*.

    Parameters
    ----------
    audio_path:
        Path to any audio/video file that ffmpeg can read.
    model_name:
        One of whisper's model names (e.g. ``"large-v3-turbo"``).
    device:
        ``"cuda"``, ``"cpu"``, or ``None`` for auto-detect.
    task:
        ``"transcribe"`` or ``"translate"`` (translate always produces English).
    language:
        ISO-639-1 code (e.g. ``"en"``) or ``None`` for auto-detect.
    word_timestamps:
        Include word-level timing in each segment's ``"words"`` list.
    condition_on_previous_text:
        Feed previous segment's text as context.  Disable to reduce looping.
    initial_prompt:
        Text to prepend as context (vocabulary hints, style guide, etc.).
    verbose:
        Pass ``True`` to print segment text to stdout as it's processed.
    status_callback:
        Optional ``callback(message)`` called with "Loading model…" /
        "Transcribing…" status strings.

    Returns
    -------
    dict
        The whisper result: ``{"text": str, "segments": [...], "language": str}``.
    """
    import whisper

    if device is None:
        device = _auto_device()

    cache_key = (model_name, device)
    with _model_lock:
        if cache_key not in _model_cache:
            if status_callback:
                status_callback(f"Loading model '{model_name}'…")
            _model_cache[cache_key] = whisper.load_model(model_name, device=device)

    model = _model_cache[cache_key]

    if status_callback:
        status_callback("Transcribing…")

    kwargs: dict = dict(
        task=task,
        language=language,
        word_timestamps=word_timestamps,
        condition_on_previous_text=condition_on_previous_text,
        verbose=verbose,
    )
    if initial_prompt:
        kwargs["initial_prompt"] = initial_prompt

    return dict(model.transcribe(audio_path, **kwargs))


def format_result(result: dict, fmt: str) -> str:
    """Convert *result* to the named output format.

    *fmt* must be one of :data:`FORMAT_KEYS` (``"txt"``, ``"srt"``, etc.).
    """
    return convert(result, fmt)
