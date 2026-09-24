"""QThread worker over installer.setup (same pattern as TranscribeWorker)."""
import threading
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal, Slot


@dataclass
class SetupResult:
    status: str  # done | cancelled | error
    fetched: list = None
    error: str = ""


class SetupWorker(QObject):
    component = Signal(object, int, int)  # Component, index, total
    progress = Signal(object, int, int)   # Component, received, total
    finished = Signal(object)             # SetupResult

    def __init__(self, manifest, target):
        super().__init__()
        self._manifest = manifest
        self._target = target
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    @Slot()
    def run(self):
        from gigaam_ui.installer import setup
        from gigaam_ui.installer.downloads import Cancelled, DownloadError
        try:
            fetched = setup.ensure(
                self._manifest, self._target,
                on_component=lambda c, i, n: self.component.emit(c, i, n),
                on_progress=lambda c, r, t: self.progress.emit(c, r, t),
                should_cancel=self._cancel.is_set,
            )
        except Cancelled:
            self.finished.emit(SetupResult("cancelled"))
        except DownloadError as e:
            self.finished.emit(SetupResult("error", error=str(e)))
        else:
            self.finished.emit(SetupResult("done", fetched=fetched))
