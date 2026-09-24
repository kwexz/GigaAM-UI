"""QProcess worker parsing + engine discovery + manifest fetch fallback."""
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from giga_transcribe.core.events import Job
from giga_transcribe.desktop.worker_process import EngineProcessWorker
from giga_transcribe.installer import builtin
from giga_transcribe.installer.engine import find_engine


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def make_worker(tmp_path):
    job = Job(input="in.wav", output=str(tmp_path / "o.srt"))
    w = EngineProcessWorker(job, "giga-worker")
    got = {}
    w.stage.connect(lambda s: got.setdefault("stage", s))
    w.segments_total.connect(lambda n: got.setdefault("total", n))
    w.chunk.connect(lambda s, p: got.setdefault("chunk", (s.text, p.done, p.total)))
    w.finished.connect(lambda r: got.setdefault("done", (r.status, r.output)))
    return w, got


def test_handle_all_types(qapp, tmp_path):
    w, got = make_worker(tmp_path)
    w._handle(json.dumps({"type": "stage", "name": "transcribing"}))
    w._handle(json.dumps({"type": "segments", "total": 2}))
    w._handle(json.dumps({"type": "segment", "index": 1, "start": 0.0,
                          "end": 1.0, "text": "hi", "current": 1, "total": 2}))
    assert got == {"stage": "transcribing", "total": 2,
                   "chunk": ("hi", 1, 2)}


def test_handle_finished_and_error(qapp, tmp_path):
    w, got = make_worker(tmp_path)
    w._handle(json.dumps({"type": "finished", "output": "o.srt",
                          "elapsed": 1.5, "segments": 2}))
    assert got["done"] == ("done", "o.srt")
    w2, got2 = make_worker(tmp_path)
    w2._handle(json.dumps({"type": "error", "message": "boom"}))
    assert got2["done"][0] == "error"
    w3, got3 = make_worker(tmp_path)
    w3._handle("not json{{{")
    assert got3["done"][0] == "error"


def test_double_finish_guarded(qapp, tmp_path):
    w, got = make_worker(tmp_path)
    w._handle(json.dumps({"type": "finished", "output": "o.srt",
                          "elapsed": 1.0, "segments": 1}))
    w._handle(json.dumps({"type": "error", "message": "late"}))
    assert got["done"] == ("done", "o.srt")


def test_find_engine(tmp_path):
    from giga_transcribe.installer.engine import find_engine as _find
    assert _find(tmp_path) is None


def test_find_app(tmp_path):
    import sys
    from giga_transcribe.installer.engine import find_app
    name = "giga-gui.exe" if sys.platform == "win32" else "giga-gui"
    plat = "win-x64" if sys.platform == "win32" else "mac-arm64"
    exe = tmp_path / f"ui-{plat}" / "giga-gui" / name
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"x")
    assert find_app(tmp_path).endswith(name)


def test_find_engine_platform(tmp_path, monkeypatch):
    import giga_transcribe.installer.engine as eng_mod
    for d, exe in (("engine-cpu-win-x64", "giga-worker.exe"),
                   ("engine-cpu-mac-arm64", "giga-worker")):
        p = tmp_path / d / "giga-worker" / exe
        p.parent.mkdir(parents=True)
        p.write_bytes(b"x")
    monkeypatch.setattr(eng_mod, "_exe_name", lambda: "giga-worker.exe")
    monkeypatch.setattr(eng_mod, "current_platform", lambda: "win-x64")
    assert "engine-cpu-win-x64" in find_engine(tmp_path)
    monkeypatch.setattr(eng_mod, "current_platform", lambda: "mac-arm64")
    monkeypatch.setattr(eng_mod, "_exe_name", lambda: "giga-worker")
    assert "engine-cpu-mac-arm64" in find_engine(tmp_path)


def test_fetch_manifest_fallback(monkeypatch):
    with pytest.raises(builtin.ManifestError):
        builtin.fetch_manifest("http://127.0.0.1:9/nope", timeout=2)
    monkeypatch.setattr(builtin, "fetch_manifest", lambda *a, **k: (_ for _ in ()).throw(
        builtin.ManifestError("offline")))
    manifest, err = builtin.default_manifest()
    assert manifest.components == () and err == "offline"
