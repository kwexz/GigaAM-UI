"""Desktop entry point: setup page on first run, main window otherwise."""
import sys

from PySide6.QtWidgets import QApplication

from gigaam_ui.core import compat
from gigaam_ui.desktop.main_window import MainWindow
from gigaam_ui.desktop.setup_page import SetupPage
from gigaam_ui.installer import builtin, setup
from gigaam_ui.installer.state import data_dir


def main(argv=None) -> int:
    compat.load_dotenv()
    app = QApplication(argv or sys.argv)
    holder = {}

    def show_setup():
        manifest, err = builtin.default_manifest()
        page = SetupPage(manifest, data_dir(), fetch_error=err)
        holder["page"] = page
        page.done.connect(lambda: go_main(page))
        page.retry_requested.connect(lambda: (page.close(), show_setup()))
        page.show()

    def go_main(page=None):
        if page is not None:
            page.close()
        compat.ensure_ffmpeg()
        win = MainWindow()
        holder["win"] = win
        win.need_setup.connect(lambda: (win.close(), show_setup()))
        win.show()

    if setup.is_installed():
        go_main()
    else:
        show_setup()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
