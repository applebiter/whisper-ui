#!/usr/bin/env bash
# extract-audio.sh — Nemo action: extract audio from video files.
#
# Invoked by Nemo with one or more file paths as arguments.
# Presents a format picker via zenity, then extracts audio from each file
# using ffmpeg, saving the result alongside the original.

set -euo pipefail

TITLE="Extract Audio"

# ── Dependency checks ─────────────────────────────────────────────────────────

if ! command -v ffmpeg &>/dev/null; then
    zenity --error --title="$TITLE" --no-wrap \
        --text="<b>ffmpeg is not installed.</b>\n\nInstall it with:\n    sudo apt install ffmpeg" \
        2>/dev/null
    exit 1
fi

if [[ $# -eq 0 ]]; then
    exit 0
fi

# ── Format selection ──────────────────────────────────────────────────────────

FORMAT=$(zenity --list \
    --title="$TITLE" \
    --text="Select output format for <b>$#</b> file(s):" \
    --column="Format" --column="Description" \
    --hide-header=false \
    --width=480 --height=320 \
    "MP3"  "MPEG Layer 3 — 320 kbps, widely compatible" \
    "FLAC" "Free Lossless — bit-perfect, larger file" \
    "WAV"  "Waveform Audio — uncompressed PCM" \
    "AAC"  "Advanced Audio Coding — 256 kbps, smaller than MP3" \
    "COPY" "Copy stream — fastest, preserves original codec and quality" \
    2>/dev/null) || exit 0  # user cancelled

# ── Process each file ─────────────────────────────────────────────────────────

DONE=0
FAILED=0
FAILED_NAMES=()

for INPUT in "$@"; do
    STEM="${INPUT%.*}"

    # Determine ffmpeg args and output extension
    case "$FORMAT" in
        MP3)
            EXT="mp3"
            FF_ARGS=(-vn -acodec libmp3lame -q:a 0)
            ;;
        FLAC)
            EXT="flac"
            FF_ARGS=(-vn -acodec flac)
            ;;
        WAV)
            EXT="wav"
            FF_ARGS=(-vn -acodec pcm_s16le)
            ;;
        AAC)
            EXT="m4a"
            FF_ARGS=(-vn -acodec aac -b:a 256k)
            ;;
        COPY)
            # Detect the source audio codec to pick a sensible extension
            CODEC=$(ffprobe -v error -select_streams a:0 \
                -show_entries stream=codec_name \
                -of default=noprint_wrappers=1:nokey=1 \
                "$INPUT" 2>/dev/null | head -1)
            case "$CODEC" in
                aac)    EXT="m4a"  ;;
                mp3)    EXT="mp3"  ;;
                opus)   EXT="opus" ;;
                vorbis) EXT="ogg"  ;;
                flac)   EXT="flac" ;;
                pcm*)   EXT="wav"  ;;
                ac3)    EXT="ac3"  ;;
                eac3)   EXT="eac3" ;;
                dts)    EXT="dts"  ;;
                *)      EXT="mka"  ;;
            esac
            FF_ARGS=(-vn -acodec copy)
            ;;
        *)
            continue
            ;;
    esac

    # Avoid silently overwriting an existing file
    OUTPUT="${STEM}.${EXT}"
    if [[ -f "$OUTPUT" ]]; then
        N=1
        while [[ -f "${STEM}_${N}.${EXT}" ]]; do
            (( N++ ))
        done
        OUTPUT="${STEM}_${N}.${EXT}"
    fi

    if ffmpeg -i "$INPUT" "${FF_ARGS[@]}" "$OUTPUT" -y -loglevel error 2>/dev/null; then
        (( DONE++ ))
    else
        (( FAILED++ ))
        FAILED_NAMES+=("$(basename "$INPUT")")
    fi
done

# ── Completion notification ───────────────────────────────────────────────────

if [[ $FAILED -eq 0 ]]; then
    NOUN="file"; [[ $DONE -ne 1 ]] && NOUN="files"
    notify-send \
        --app-name="$TITLE" \
        --icon=audio-x-generic \
        "✓ Extraction complete" \
        "$DONE $NOUN extracted as $FORMAT."
else
    BODY="$DONE succeeded"
    [[ $FAILED -gt 0 ]] && BODY+="  ·  $FAILED failed: $(IFS=', '; echo "${FAILED_NAMES[*]}")"
    notify-send \
        --app-name="$TITLE" \
        --icon=dialog-warning \
        "⚠ Extraction finished with errors" \
        "$BODY"
fi
