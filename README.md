# WhisperUI

A desktop GUI and command-line tool for [OpenAI Whisper](https://github.com/openai/whisper) — record or open audio/video, transcribe or translate in 99 languages, choose models, and export to Text, SRT, WebVTT, TSV, or JSON.

## Features

- **Desktop GUI** (PySide6) with a dark theme
- **CLI** with full option parity — no display required
- **Importable Python API** for use in other projects
- Model selector with descriptions, sizes, and in-app download with live progress bar
- Microphone recording with real-time VU meter and elapsed timer
- Open any audio/video format supported by ffmpeg
- Transcription (keeps source language) and translation (always to English)
- Language auto-detection or manual selection across 99 languages
- CUDA GPU acceleration (auto-detected; falls back to CPU)
- Word-level timestamps
- Output formats: plain text, SRT, WebVTT, TSV, JSON

## Requirements

- Python 3.8+
- [ffmpeg](https://ffmpeg.org/) on your system PATH (Whisper uses it for audio decoding)
- A CUDA-capable GPU is optional but strongly recommended for medium/large models

## Installation

```bash
git clone https://github.com/applebiter/whisper-ui.git
cd whisper-ui
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Install ffmpeg if you don't already have it:

```bash
sudo apt install ffmpeg          # Debian / Ubuntu / Mint
brew install ffmpeg              # macOS
winget install ffmpeg            # Windows
```

## Usage

### Desktop GUI

```bash
python main.py
```

Select a model (download it if needed), choose an audio source (file or microphone), configure options, and click **Transcribe**.

### CLI

```
python main.py [--help] {transcribe,models} ...
```

Run without arguments to open the GUI. Pass a subcommand for headless operation.

#### `transcribe` — process an audio/video file

```bash
# Basic — output goes to stdout
python main.py transcribe interview.mp3

# Save as an SRT subtitle file
python main.py transcribe lecture.mp4 --format srt --output lecture.srt

# Translate from French to English, auto-download the model if missing
python main.py transcribe discours.mp3 \
    --model large-v3-turbo \
    --task translate \
    --auto-download \
    --output english.txt

# Quiet mode — only the transcript, nothing else
python main.py transcribe audio.wav --model tiny --quiet > transcript.txt
```

All options for `transcribe`:

| Flag | Default | Description |
|---|---|---|
| `--model`, `-m` | `large-v3-turbo` | Model name (see `models` command) |
| `--task`, `-t` | `transcribe` | `transcribe` or `translate` (→ English) |
| `--language`, `-l` | auto | ISO-639-1 code, e.g. `en`, `fr`, `de` |
| `--device`, `-d` | auto | `cuda` or `cpu` |
| `--format`, `-f` | `txt` | `txt`, `srt`, `vtt`, `tsv`, `json` |
| `--output`, `-o` | stdout | Write to this file instead of stdout |
| `--word-timestamps` | off | Add word-level timing to each segment |
| `--no-condition` | off | Disable conditioning on previous segment (reduces looping) |
| `--initial-prompt` | — | Seed text to guide transcription style or vocabulary |
| `--auto-download` | off | Download the model automatically if not present |
| `--verbose` | off | Print each decoded segment to stderr |
| `--quiet`, `-q` | off | Suppress all status messages |

#### `models` — list and download models

```bash
# Show all models and whether they're downloaded
python main.py models

# Download a specific model
python main.py models --download large-v3-turbo
```

### Python API

`whisper_ui.core` exposes a clean, Qt-free API for use in other applications:

```python
from whisper_ui.core import (
    available_models,       # () → list[str]
    model_info,             # (name) → {"size": str, "description": str}
    is_model_downloaded,    # (name) → bool
    download_model,         # (name, progress_callback=None) → path str
    transcribe,             # (audio_path, model_name, ...) → dict
    format_result,          # (result, fmt) → str
    FORMAT_KEYS,            # ["txt", "srt", "vtt", "tsv", "json"]
)

# Check and download a model
if not is_model_downloaded("base"):
    download_model(
        "base",
        progress_callback=lambda pct, speed: print(f"{pct}%  {speed}")
    )

# Transcribe
result = transcribe(
    "audio.mp3",
    model_name="base",
    device=None,            # None → auto-detect CUDA or CPU
    task="transcribe",
    language=None,          # None → auto-detect
    word_timestamps=False,
    status_callback=print,
)

print(result["text"])       # full transcript
print(result["language"])   # detected language code

# Format the result
from whisper_ui.core import format_result
print(format_result(result, "srt"))
```

Format converters are also importable individually:

```python
from whisper_ui.formats import to_text, to_srt, to_vtt, to_tsv, to_json
```

## Models

| Model | Size | Notes |
|---|---|---|
| `tiny` / `tiny.en` | ~75 MB | Fastest, lowest accuracy |
| `base` / `base.en` | ~142 MB | Fast with reasonable accuracy |
| `small` / `small.en` | ~466 MB | Good speed/quality balance |
| `medium` / `medium.en` | ~1.5 GB | High accuracy, moderate speed |
| `large-v1` / `v2` / `v3` | ~2.9 GB | Highest accuracy |
| **`large-v3-turbo`** | **~1.5 GB** | **★ Recommended — near `large-v3` quality at ~8× the speed** |

`.en` variants are English-only and slightly more accurate for English audio. Models are cached in `~/.cache/whisper/` and shared with the Whisper CLI.

## License

[MIT](LICENSE)
