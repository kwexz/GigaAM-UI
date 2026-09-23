"""Desktop entry point: setup page on first run, main window otherwise."""
import sys

from PySide6.QtWidgets import QApplication

from giga_transcribe.core import compat
from giga_transcribe.desktop.main_window import MainWindow
from giga_transcribe.desktop.setup_page import SetupPage
from giga_transcribe.installer import builtin, setup
from giga_transcribe.installer.state import data_dir


def main(argv=None) -> int:
    compat.load_dotenv()
    app = QApplication(argv or sys.argv)
    manifest = builtin.default_manifest()

    if setup.is_installed():
        compat.ensure_ffmpeg()
        win = MainWindow()
        win.show()
    else:
        page = SetupPage(manifest, data_dir())
        holder = {}

        def go_main():
            compat.ensure_ffmpeg()
            holder["win"] = MainWindow()
            holder["win"].show()
            page.close()

        page.done.connect(go_main)
        page.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
