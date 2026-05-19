"""WhisperUI — entry point.

Routing
───────
  python main.py                        → launch the GUI
  python main.py transcribe FILE ...    → CLI transcription (no GUI)
  python main.py models [--download X]  → CLI model management (no GUI)
  python main.py --help                 → CLI help
"""
import sys

_CLI_COMMANDS = {"transcribe", "models"}


def _launch_gui() -> None:
    import shutil
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication(sys.argv)
    app.setApplicationName("WhisperUI")
    app.setOrganizationName("WhisperUI")

    if not shutil.which("ffmpeg"):
        QMessageBox.warning(
            None,
            "ffmpeg Not Found",
            "ffmpeg was not found in your PATH.\n\n"
            "Whisper relies on ffmpeg to read and convert audio/video files. "
            "Without it, transcription will fail for most file types.\n\n"
            "Install it with:\n"
            "    sudo apt install ffmpeg",
        )

    from whisper_ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


def main() -> None:
    # Peek at argv: if the first non-flag argument is a known CLI command,
    # hand off to the CLI without importing any Qt code.
    positional = [a for a in sys.argv[1:] if not a.startswith("-")]
    if positional and positional[0] in _CLI_COMMANDS:
        from whisper_ui.cli import main as cli_main
        sys.exit(cli_main())

    # --help / --version with no command → show CLI help
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h"):
        from whisper_ui.cli import main as cli_main
        sys.exit(cli_main())

    _launch_gui()


if __name__ == "__main__":
    main()
