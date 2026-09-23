"""QThread worker over core.jobs. torch is touched only inside run().

NOTE: 0.2 runs inference in-process (separate thread). The QProcess +
JSONL subprocess split lands with packaging (0.4), where crash isolation
and separate engine packs matter.
"""
import threading

from PySide6.QtCore import QObject, Signal, Slot


class TranscribeWorker(QObject):
    stage = Signal(str)          # loading_model | transcribing
    segments_total = Signal(int)
    chunk = Signal(object, object)  # Segment, Progress
    finished = Signal(object)    # JobResult

    def __init__(self, job):
        super().__init__()
        self._job = job
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    @Slot()
    def run(self):
        from giga_transcribe.core import jobs  # lazy: keep UI import light
        result = jobs.run(
            self._job,
            on_stage=self.stage.emit,
            on_segments=self.segments_total.emit,
            on_chunk=lambda seg, prog: self.chunk.emit(seg, prog),
            should_cancel=self._cancel.is_set,
        )
        self.finished.emit(result)
