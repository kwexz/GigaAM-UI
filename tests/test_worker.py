"""Worker protocol: stdout is pure JSONL, errors/cancel map to exit codes."""
import json

import pytest

import giga_transcribe.core.jobs as jobs_mod
from giga_transcribe.core.events import Progress, Segment
from giga_transcribe.worker.__main__ import main


def write_job(tmp_path, **over):
    job = {"input": str(tmp_path / "in.wav"),
           "output": str(tmp_path / "out.srt"), "format": "srt",
           "model": "e2e_rnnt", "device": "cpu"}
    job.update(over)
    spec = tmp_path / "job.json"
    spec.write_text(json.dumps(job), encoding="utf-8")
    return str(spec)


def run_main(argv, capsys):
    code = main(argv)
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()
             if line.strip()]
    return code, lines


@pytest.fixture()
def fake_engine(monkeypatch):
    def fake_run(job, *, on_stage=None, on_segments=None, on_chunk=None,
                 should_cancel=None):
        from giga_transcribe.core.jobs import JobResult
        on_stage("loading_model")
        on_stage("transcribing")
        on_segments(2)
        for i, text in ((1, "one"), (2, "two")):
            if should_cancel is not None and should_cancel():
                return JobResult("cancelled", job.output + ".partial", 0.1, i - 1)
            on_chunk(Segment(i, float(i - 1), float(i), text), Progress(i, 2))
        return JobResult("done", job.output, 0.2, 2)

    monkeypatch.setattr(jobs_mod, "run", fake_run)


def test_protocol_happy_path(tmp_path, fake_engine, capsys, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda *a: "ffmpeg")
    (tmp_path / "in.wav").write_bytes(b"x")
    code, lines = run_main(["--job", write_job(tmp_path)], capsys)
    assert code == 0
    assert [l["type"] for l in lines] == ["stage", "stage", "segments",
                                          "segment", "segment", "finished"]
    assert lines[-1]["segments"] == 2
    assert lines[3]["text"] == "one" and lines[3]["current"] == 1


def test_bad_job_file(tmp_path, capsys):
    code, lines = run_main(["--job", str(tmp_path / "nope.json")], capsys)
    assert code == 1 and lines[-1]["type"] == "error"


def test_missing_key(tmp_path, capsys):
    spec = tmp_path / "job.json"
    spec.write_text("{}", encoding="utf-8")
    code, lines = run_main(["--job", str(spec)], capsys)
    assert code == 1 and "missing key" in lines[-1]["message"]


def test_cancel_file(tmp_path, fake_engine, capsys, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda *a: "ffmpeg")
    (tmp_path / "in.wav").write_bytes(b"x")
    cancel = tmp_path / "cancel"
    cancel.write_text("stop")
    code, lines = run_main(["--job", write_job(tmp_path), "--cancel-file",
                            str(cancel)], capsys)
    assert code == 130 and lines[-1]["type"] == "cancelled"
