"""Desktop entry point: python -m giga_transcribe.desktop.app"""
import os
import sys

from PySide6.QtWidgets import QApplication

from giga_transcribe.core import compat
from giga_transcribe.desktop.main_window import MainWindow


def main(argv=None) -> int:
    compat.load_dotenv()
    compat.ensure_ffmpeg()
    app = QApplication(argv or sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
