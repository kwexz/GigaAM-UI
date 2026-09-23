"""QProcess worker over a downloaded engine bundle (giga-worker exe).

Same signals as TranscribeWorker, so MainWindow treats both identically.
stdout must be pure JSONL (worker protocol v1); anything else is an error.
"""
import json
import os
import tempfile

from PySide6.QtCore import QObject, QProcess, Signal, Slot

from giga_transcribe.core.events import JobResult, Progress, Segment


class EngineProcessWorker(QObject):
    stage = Signal(str)
    segments_total = Signal(int)
    chunk = Signal(object, object)  # Segment, Progress
    finished = Signal(object)       # JobResult

    def __init__(self, job, engine_exe: str):
        super().__init__()
        self._job = job
        self._exe = engine_exe
        self._proc: QProcess | None = None
        self._buf = ""
        self._tmpdir = ""
        self._cancel_file = ""
        self._done = False

    @Slot()
    def run(self):
        self._tmpdir = tempfile.mkdtemp(prefix="giga-job-")
        spec = os.path.join(self._tmpdir, "job.json")
        with open(spec, "w", encoding="utf-8") as f:
            json.dump({"input": self._job.input, "output": self._job.output,
                       "format": self._job.fmt, "model": self._job.model_id,
                       "device": self._job.device}, f)
        self._cancel_file = os.path.join(self._tmpdir, "cancel")
        self._proc = QProcess(self)
        self._proc.readyReadStandardOutput.connect(self._drain)
        self._proc.finished.connect(self._exited)
        self._proc.errorOccurred.connect(self._proc_error)
        self._proc.start(self._exe, ["--job", spec, "--cancel-file",
                                     self._cancel_file])

    def cancel(self):
        if self._cancel_file and not os.path.exists(self._cancel_file):
            open(self._cancel_file, "w").close()

    @Slot()
    def _drain(self):
        self._buf += bytes(self._proc.readAllStandardOutput()).decode(
            "utf-8", errors="replace")
        *lines, self._buf = self._buf.split("\n")
        for line in lines:
            line = line.strip()
            if line:
                self._handle(line)

    def _handle(self, line: str):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            self._fail(f"worker sent non-JSON: {line[:120]}")
            return
        kind = obj.get("type")
        if kind == "stage":
            self.stage.emit(obj.get("name", ""))
        elif kind == "segments":
            self.segments_total.emit(int(obj.get("total", 0)))
        elif kind == "segment":
            seg = Segment(index=obj.get("index", 0), start=obj.get("start", 0.0),
                          end=obj.get("end", 0.0), text=obj.get("text", ""),
                          speaker=obj.get("speaker"))
            self.chunk.emit(seg, Progress(obj.get("current", 0),
                                          obj.get("total", 0)))
        elif kind == "finished":
            self._emit_finished(JobResult(
                "done", obj.get("output", ""), float(obj.get("elapsed", 0.0)),
                int(obj.get("segments", 0))))
        elif kind == "cancelled":
            self._emit_finished(JobResult("cancelled", obj.get("partial", ""),
                                          0.0, 0))
        elif kind == "error":
            self._fail(obj.get("message", "unknown worker error"))
        # unknown types ignored (forward-compat)

    def _emit_finished(self, result: JobResult):
        if self._done:
            return
        self._done = True
        self.finished.emit(result)

    def _fail(self, message: str):
        self._cleanup()
        self._emit_finished(JobResult("error", self._job.output, 0.0, 0,
                                      message))

    @Slot(int, object)
    def _exited(self, code: int, status):
        if not self._done:
            tail = ""
            if self._proc is not None:
                try:
                    tail = bytes(
                        self._proc.readAllStandardError()).decode(
                            "utf-8", errors="replace")[-500:]
                except RuntimeError:
                    pass
            self._fail(f"engine exited with code {code}. {tail}".strip())

    @Slot(object)
    def _proc_error(self, _error):
        if self._proc is not None:
            self._fail(f"cannot start engine: {self._exe}")

    def _cleanup(self):
        import shutil
        if self._proc is not None:
            self._proc.deleteLater()
            self._proc = None
        if self._tmpdir:
            shutil.rmtree(self._tmpdir, ignore_errors=True)
            self._tmpdir = ""
