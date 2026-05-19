"""Pure-Python format converters for whisper result dicts.

Each function accepts a whisper result dict (as returned by whisper.transcribe)
and returns a formatted string.  No Qt dependency — safe to import from CLI or
other apps.
"""
from __future__ import annotations

import json


# ──────────────────────────────────────────────────── helpers ────────────────

def _ts_srt(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ts_vtt(sec: float) -> str:
    return _ts_srt(sec).replace(",", ".")


# ──────────────────────────────────────────────── converters ─────────────────

def to_text(result: dict) -> str:
    """Plain text — the full transcript."""
    return result.get("text", "").strip()


def to_srt(result: dict) -> str:
    """SubRip subtitle format."""
    parts: list[str] = []
    for i, seg in enumerate(result.get("segments", []), 1):
        parts.append(
            f"{i}\n"
            f"{_ts_srt(seg['start'])} --> {_ts_srt(seg['end'])}\n"
            f"{seg['text'].strip()}"
        )
    return "\n\n".join(parts)


def to_vtt(result: dict) -> str:
    """WebVTT subtitle format."""
    parts = ["WEBVTT\n"]
    for seg in result.get("segments", []):
        parts.append(
            f"{_ts_vtt(seg['start'])} --> {_ts_vtt(seg['end'])}\n"
            f"{seg['text'].strip()}"
        )
    return "\n\n".join(parts)


def to_tsv(result: dict) -> str:
    """Tab-separated values: start, end, text."""
    rows = ["start\tend\ttext"]
    for seg in result.get("segments", []):
        rows.append(
            f"{seg['start']:.3f}\t{seg['end']:.3f}\t{seg['text'].strip()}"
        )
    return "\n".join(rows)


def to_json(result: dict) -> str:
    """Full whisper result as JSON (includes segments, language, etc.)."""
    return json.dumps(result, indent=2, ensure_ascii=False, default=str)


# ─────────────────────────────────────────── lookup helpers ──────────────────

#: Maps format key → (display label, file extension, converter function)
FORMATS: dict[str, tuple[str, str, "FormatFn"]] = {
    "txt":  ("Text", "txt", to_text),
    "srt":  ("SRT",  "srt", to_srt),
    "vtt":  ("VTT",  "vtt", to_vtt),
    "tsv":  ("TSV",  "tsv", to_tsv),
    "json": ("JSON", "json", to_json),
}

FORMAT_KEYS = list(FORMATS.keys())


def convert(result: dict, fmt: str) -> str:
    """Convert result to the named format.  Raises KeyError for unknown fmt."""
    return FORMATS[fmt][2](result)
