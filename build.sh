#!/usr/bin/env bash
# Build a self-contained WhisperUI executable using PyInstaller.
#
# Usage:
#   ./build.sh                # full build — includes CUDA libraries
#   ./build.sh --slim         # CPU-only — much smaller, no CUDA
#   ./build.sh --archive      # also produce dist/whisper-ui-linux-x86_64.tar.gz
#   ./build.sh --slim --archive
#
# The output directory is dist/whisper-ui/.
# Run the app with:  dist/whisper-ui/whisper-ui
#
# Requirements:
#   - .venv with requirements.txt installed  (pip install -r requirements.txt)
#   - ffmpeg on PATH  (sudo apt install ffmpeg)
#   - libportaudio2   (sudo apt install libportaudio2)   for microphone recording

set -euo pipefail
cd "$(dirname "$0")"

# ── Parse arguments ───────────────────────────────────────────────────────────
SLIM=0
ARCHIVE=0
for arg in "$@"; do
    case "$arg" in
        --slim)    SLIM=1 ;;
        --archive) ARCHIVE=1 ;;
        *) echo "Unknown option: $arg" >&2; exit 1 ;;
    esac
done

# ── Choose / prepare virtualenv ──────────────────────────────────────────────
if [[ "$SLIM" -eq 1 ]]; then
    # The slim build requires a CPU-only PyTorch install.  A CUDA-enabled torch
    # has hard ELF dependencies on libcublasLt (~517 MB) and libcusparseLt
    # (~224 MB) that cannot be stripped — making binary-level filtering useless.
    # We keep a separate lightweight venv for this purpose.
    CPU_VENV=".venv-cpu"
    if [[ ! -f "$CPU_VENV/bin/activate" ]]; then
        echo "Creating CPU-only build environment ($CPU_VENV) — one-time setup…"
        python -m venv "$CPU_VENV"
        # shellcheck disable=SC1090
        source "$CPU_VENV/bin/activate"
        # Install CPU torch first so nothing pulls in the CUDA wheel
        pip install torch --index-url https://download.pytorch.org/whl/cpu --quiet
        # Install remaining deps (torch is already satisfied, so it won't be upgraded)
        pip install PySide6 openai-whisper sounddevice soundfile numpy requests pyinstaller --quiet
    else
        # shellcheck disable=SC1090
        source "$CPU_VENV/bin/activate"
        pip install pyinstaller --quiet
    fi
else
    if [[ ! -f ".venv/bin/activate" ]]; then
        echo "ERROR: .venv not found." >&2
        echo "  python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
        exit 1
    fi
    # shellcheck disable=SC1091
    source .venv/bin/activate
    pip install pyinstaller --quiet
fi

# ── Build ─────────────────────────────────────────────────────────────────────
BUILD_MODE="full (CUDA-capable)"
[[ "$SLIM" -eq 1 ]] && BUILD_MODE="slim (CPU-only, separate torch)"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  WhisperUI — PyInstaller build                       ║"
echo "╠══════════════════════════════════════════════════════╣"
printf "║  Mode: %-45s║\n" "$BUILD_MODE"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

export WHISPER_UI_SLIM="$SLIM"

pyinstaller whisper-ui.spec --clean --noconfirm

# ── Report ────────────────────────────────────────────────────────────────────
BUNDLE="dist/whisper-ui"
ENTRY="$BUNDLE/whisper-ui"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  Build complete                                      ║"
echo "╠══════════════════════════════════════════════════════╣"
printf "║  Bundle:  %-42s║\n" "$BUNDLE/"
printf "║  Size:    %-42s║\n" "$(du -sh "$BUNDLE" | cut -f1)"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Smoke test:                                         ║"
printf "║    %-49s║\n" "$ENTRY --help"
printf "║    %-49s║\n" "$ENTRY models"
printf "║    %-49s║\n" "$ENTRY  # launches GUI"
echo "╚══════════════════════════════════════════════════════╝"

# ── Optional archive ──────────────────────────────────────────────────────────
if [[ "$ARCHIVE" -eq 1 ]]; then
    SUFFIX=""
    [[ "$SLIM" -eq 1 ]] && SUFFIX="-slim"
    TARBALL="dist/whisper-ui-linux-x86_64${SUFFIX}.tar.gz"
    echo ""
    echo "Creating archive: $TARBALL ..."
    tar -czf "$TARBALL" -C dist whisper-ui
    echo "Archive: $TARBALL  ($(du -sh "$TARBALL" | cut -f1))"
fi
