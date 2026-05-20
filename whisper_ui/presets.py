"""Named prompt presets stored in ~/.config/whisper-ui/presets.json.

Each preset is a dict with "name" and "prompt" keys.
Use {text} in the prompt where the raw transcription should be inserted.
"""
from __future__ import annotations

import json
import os

from .settings import CONFIG_DIR

_FILE = os.path.join(CONFIG_DIR, "presets.json")

DEFAULT_PRESETS: list[dict] = [
    {
        "name": "Format as Prose",
        "prompt": (
            "The following is a raw speech transcription that lacks punctuation "
            "and formatting. Rewrite it as clean, readable prose with proper "
            "punctuation, capitalisation, and paragraph breaks. Preserve every "
            "idea faithfully — do not add, remove, or reorder content.\n\n"
            "Transcription:\n{text}"
        ),
    },
    {
        "name": "Meeting Notes",
        "prompt": (
            "Format the following transcription as structured meeting notes in "
            "Markdown. Include:\n"
            "- A **Summary** heading with a one-paragraph overview\n"
            "- A **Discussion** section with bullet points for each topic\n"
            "- An **Action Items** section listing tasks with owners where mentioned\n\n"
            "Transcription:\n{text}"
        ),
    },
    {
        "name": "Bullet Points",
        "prompt": (
            "Convert the following transcription into a concise bulleted list in "
            "Markdown. Each bullet should capture one distinct idea or topic. "
            "Use nested bullets for sub-points. Be brief but complete.\n\n"
            "Transcription:\n{text}"
        ),
    },
    {
        "name": "Interview / Q&A",
        "prompt": (
            "Format the following transcription as an interview or Q&A dialogue "
            "in Markdown. Identify questions and answers and label them clearly "
            "with **Q:** and **A:** prefixes. Add a blank line between each "
            "exchange. If speakers are named, use their names instead of Q/A.\n\n"
            "Transcription:\n{text}"
        ),
    },
    {
        "name": "Fix Punctuation Only",
        "prompt": (
            "Add proper punctuation and capitalisation to the following "
            "transcription. Make the absolute minimum changes necessary — only "
            "fix punctuation and sentence boundaries. Do not rephrase, reorder, "
            "summarise, or add any content.\n\n"
            "Transcription:\n{text}"
        ),
    },
    {
        "name": "Academic / Formal",
        "prompt": (
            "Rewrite the following transcription in a formal, academic register "
            "using proper grammar, punctuation, and paragraph structure. Maintain "
            "all original ideas but elevate the language to suit a professional "
            "or academic audience. Format the output in Markdown.\n\n"
            "Transcription:\n{text}"
        ),
    },
]


def load() -> list[dict]:
    """Return saved presets, falling back to defaults if none exist."""
    try:
        with open(_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return [dict(p) for p in DEFAULT_PRESETS]


def save(presets: list[dict]) -> None:
    os.makedirs(os.path.dirname(_FILE), exist_ok=True)
    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(presets, f, indent=2, ensure_ascii=False)
