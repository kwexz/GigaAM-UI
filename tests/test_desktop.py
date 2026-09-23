"""Offscreen GUI tests — no display, no model."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from giga_transcribe.core.events import Progress, Segment
from giga_transcribe.desktop.main_window import MainWindow
from giga_transcribe.desktop.worker import TranscribeWorker


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_window_builds(qapp):
    win = MainWindow()
    assert win.model_cb.count() >= 1
    assert win.device_cb.count() >= 1  # cpu always present
    assert win.format_cb.count() >= 3
    assert win.go_btn.isEnabled()
    assert not win.cancel_btn.isEnabled()
    win.set_file("some.wav")
    assert "some.wav" in win.file_lbl.text()


def test_no_engine_offers_setup(qapp, monkeypatch, tmp_path):
    import giga_transcribe.desktop.main_window as mw_mod
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(mw_mod, "find_engine", lambda: None)
    monkeypatch.setattr(mw_mod.devices, "has_torch", lambda: False)
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    (tmp_path / "a.wav").write_bytes(b"x")
    win = MainWindow()
    got = []
    win.need_setup.connect(lambda: got.append(True))
    win.set_file(str(tmp_path / "a.wav"))
    win._on_start()
    assert got == [True]
    assert not win.cancel_btn.isEnabled()


def test_worker_relays_events(qapp, monkeypatch):
    import giga_transcribe.core.jobs as jobs_mod

    seg = Segment(1, 0.0, 1.5, "hello")

    def fake_run(job, *, on_stage=None, on_segments=None, on_chunk=None,
                 should_cancel=None):
        on_stage("transcribing")
        on_segments(1)
        on_chunk(seg, Progress(1, 1))
        return ("RESULT",)

    monkeypatch.setattr(jobs_mod, "run", fake_run)
    got = {}
    w = TranscribeWorker(object())
    w.stage.connect(lambda s: got.setdefault("stage", s))
    w.segments_total.connect(lambda n: got.setdefault("total", n))
    w.chunk.connect(lambda s, p: got.setdefault("chunk", (s.text, p.done)))
    w.finished.connect(lambda r: got.setdefault("done", r))
    w.run()
    assert got == {"stage": "transcribing", "total": 1,
                   "chunk": ("hello", 1), "done": ("RESULT",)}
