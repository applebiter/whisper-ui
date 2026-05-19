#!/usr/bin/env bash
# Install WhisperUI Nemo actions to ~/.local/share/nemo/actions/
#
# Run from anywhere:  bash /path/to/whisper-ui/nemo-actions/install.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ACTIONS_SRC="$REPO_DIR/nemo-actions"
ACTIONS_DST="$HOME/.local/share/nemo/actions"

echo "Installing Nemo actions from: $ACTIONS_SRC"
echo "                          to: $ACTIONS_DST"
echo ""

mkdir -p "$ACTIONS_DST"

# ── extract-audio ─────────────────────────────────────────────────────────────

# Copy the script and make it executable
install -m 755 "$ACTIONS_SRC/extract-audio.sh" "$ACTIONS_DST/extract-audio.sh"

# Rewrite the .nemo_action with the actual HOME path substituted
sed "s|/home/sysadmin|$HOME|g" \
    "$ACTIONS_SRC/extract-audio.nemo_action" \
    > "$ACTIONS_DST/extract-audio.nemo_action"

echo "  ✓  extract-audio  →  right-click any video file in Nemo"

# ── Dependency hints ──────────────────────────────────────────────────────────

echo ""
MISSING=()
command -v ffmpeg      &>/dev/null || MISSING+=("ffmpeg")
command -v zenity      &>/dev/null || MISSING+=("zenity")
command -v notify-send &>/dev/null || MISSING+=("libnotify-bin")

if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo "  ⚠  Missing dependencies: ${MISSING[*]}"
    echo "     Install with: sudo apt install ${MISSING[*]}"
    echo ""
fi

# ── Reload Nemo ───────────────────────────────────────────────────────────────

if pgrep -x nemo &>/dev/null; then
    nemo -q 2>/dev/null && sleep 1 && nemo &disown 2>/dev/null || true
    echo "  ↺  Nemo restarted to pick up new actions."
else
    echo "  ℹ  Start Nemo (or press F5 in an open window) to see the new actions."
fi

echo ""
echo "Done. Right-click any video file in Nemo to use 'Extract Audio'."
