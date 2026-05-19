"""WhisperUI — entry point."""
import shutil
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from whisper_ui.main_window import MainWindow


def _check_ffmpeg(app: QApplication) -> None:
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


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("WhisperUI")
    app.setOrganizationName("WhisperUI")

    _check_ffmpeg(app)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
