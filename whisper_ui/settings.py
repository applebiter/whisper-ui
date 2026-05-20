"""Persistent application settings stored in ~/.config/whisper-ui/settings.json."""
from __future__ import annotations

import json
import os

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "whisper-ui")
_FILE = os.path.join(CONFIG_DIR, "settings.json")

_DEFAULTS: dict = {
    "ollama_host": "http://localhost:11434",
    "ollama_model": "",
}


def load() -> dict:
    try:
        with open(_FILE, encoding="utf-8") as f:
            return {**_DEFAULTS, **json.load(f)}
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(_DEFAULTS)


def save(settings: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
