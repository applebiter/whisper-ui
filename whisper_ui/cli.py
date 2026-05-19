"""Command-line interface for WhisperUI.

Usage
─────
    python main.py transcribe FILE [options]
    python main.py models [--download MODEL]

Run ``python main.py <command> --help`` for full option docs.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import (
    available_models,
    download_model,
    format_result,
    is_model_downloaded,
    model_info,
    transcribe,
    WHISPER_CACHE_DIR,
)
from .formats import FORMAT_KEYS

# ─────────────────────────────────────────────── subcommand: models ──────────

def _cmd_models(args: argparse.Namespace) -> int:
    if args.download:
        return _download_model(args.download)

    models = available_models()
    col_w = max(len(m) for m in models) + 2

    print(f"\n{'Model':<{col_w}}  {'Size':<10}  Status")
    print("─" * (col_w + 26))
    for name in models:
        info = model_info(name)
        size = info.get("size", "—")
        status = "✓  downloaded" if is_model_downloaded(name) else "✗  not downloaded"
        print(f"  {name:<{col_w}}  {size:<10}  {status}")
    print()
    print(f"Cache directory: {WHISPER_CACHE_DIR}")
    print()
    return 0


def _download_model(name: str) -> int:
    models = available_models()
    if name not in models:
        print(f"error: unknown model '{name}'.  "
              f"Choose from: {', '.join(models)}", file=sys.stderr)
        return 1

    if is_model_downloaded(name):
        print(f"Model '{name}' is already downloaded.")
        return 0

    info = model_info(name)
    size = info.get("size", "")
    label = f"'{name}' ({size})" if size else f"'{name}'"
    print(f"Downloading model {label}…")

    _last_pct = [-1]

    def _progress(pct: int, speed: str):
        if pct == _last_pct[0]:
            return
        _last_pct[0] = pct
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        print(f"\r  [{bar}] {pct:3d}%  {speed:<12}", end="", flush=True)

    try:
        download_model(name, progress_callback=_progress)
        print(f"\r  [{'█' * 20}] 100%  Done.          ")
        print(f"Model '{name}' saved to {WHISPER_CACHE_DIR}")
        return 0
    except Exception as exc:
        print(f"\nDownload failed: {exc}", file=sys.stderr)
        return 1


# ───────────────────────────────────────────── subcommand: transcribe ────────

def _cmd_transcribe(args: argparse.Namespace) -> int:
    audio = str(args.audio)
    model_name = args.model

    # Auto-download if requested
    if not is_model_downloaded(model_name):
        if args.auto_download:
            rc = _download_model(model_name)
            if rc != 0:
                return rc
        else:
            print(
                f"error: model '{model_name}' is not downloaded.\n"
                "  Run:  python main.py models --download " + model_name + "\n"
                "  Or add --auto-download to this command.",
                file=sys.stderr,
            )
            return 1

    def _status(msg: str):
        if not args.quiet:
            print(msg, file=sys.stderr)

    try:
        result = transcribe(
            audio,
            model_name=model_name,
            device=args.device,
            task=args.task,
            language=args.language,
            word_timestamps=args.word_timestamps,
            condition_on_previous_text=not args.no_condition,
            initial_prompt=args.initial_prompt or None,
            verbose=args.verbose,
            status_callback=_status,
        )
    except FileNotFoundError:
        print(f"error: audio file not found: {audio}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        lang = result.get("language", "unknown")
        segs = result.get("segments", [])
        dur = f"{segs[-1]['end']:.1f}s" if segs else "?"
        print(f"Language: {lang}  |  Duration: {dur}", file=sys.stderr)

    text = format_result(result, args.format)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(text, encoding="utf-8")
        if not args.quiet:
            print(f"Saved → {out_path}", file=sys.stderr)
    else:
        print(text)

    return 0


# ─────────────────────────────────────────────────── parser + entry ──────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="whisper-ui",
        description="WhisperUI — transcribe or translate audio/video files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python main.py transcribe interview.mp3\n"
            "  python main.py transcribe lecture.mp4 --model large-v3 --format srt\n"
            "  python main.py transcribe audio.wav --task translate --output english.txt\n"
            "  python main.py models\n"
            "  python main.py models --download large-v3-turbo\n"
        ),
    )

    sub = parser.add_subparsers(dest="command")

    # ── models ────────────────────────────────────────────────────────────────
    p_models = sub.add_parser("models", help="List available models and their download status.")
    p_models.add_argument(
        "--download",
        metavar="MODEL",
        help="Download the named model to the whisper cache.",
    )

    # ── transcribe ────────────────────────────────────────────────────────────
    p_tr = sub.add_parser(
        "transcribe",
        help="Transcribe (or translate) an audio/video file.",
    )
    p_tr.add_argument("audio", type=Path, help="Path to the audio/video file.")
    p_tr.add_argument(
        "--model", "-m",
        default="large-v3-turbo",
        metavar="NAME",
        help="Whisper model to use (default: large-v3-turbo). "
             "Run 'models' to see all options.",
    )
    p_tr.add_argument(
        "--task", "-t",
        choices=["transcribe", "translate"],
        default="transcribe",
        help="'transcribe' keeps the source language; "
             "'translate' always produces English (default: transcribe).",
    )
    p_tr.add_argument(
        "--language", "-l",
        default=None,
        metavar="CODE",
        help="ISO-639-1 language code of the audio (e.g. 'fr'). "
             "Omit for auto-detect.",
    )
    p_tr.add_argument(
        "--device", "-d",
        default=None,
        choices=["cuda", "cpu"],
        help="Compute device.  Omit to auto-detect (CUDA if available).",
    )
    p_tr.add_argument(
        "--format", "-f",
        choices=FORMAT_KEYS,
        default="txt",
        help="Output format: txt (default), srt, vtt, tsv, or json.",
    )
    p_tr.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Write output to FILE instead of stdout.",
    )
    p_tr.add_argument(
        "--word-timestamps",
        action="store_true",
        help="Include word-level timestamps in the result.",
    )
    p_tr.add_argument(
        "--no-condition",
        action="store_true",
        help="Disable conditioning on previous segment text. "
             "Can reduce looping/hallucination.",
    )
    p_tr.add_argument(
        "--initial-prompt",
        metavar="TEXT",
        help="Provide context or vocabulary hints to guide transcription style.",
    )
    p_tr.add_argument(
        "--auto-download",
        action="store_true",
        help="Download the model automatically if it is not already present.",
    )
    p_tr.add_argument(
        "--verbose",
        action="store_true",
        help="Print each segment to stderr as it is decoded.",
    )
    p_tr.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress all status messages; only output the transcript.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "models":
        return _cmd_models(args)
    if args.command == "transcribe":
        return _cmd_transcribe(args)

    # No subcommand — print help (caller should then launch GUI)
    parser.print_help()
    return 0
