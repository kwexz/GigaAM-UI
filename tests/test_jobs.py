"""Jobs with a fake engine — no model, no network."""
import os

import giga_transcribe.core.jobs as jobs_mod
from giga_transcribe.core import jobs
from giga_transcribe.core.events import Segment


class FakeEngine:
    model_id = None

    @staticmethod
    def load_model(model_id, device):
        FakeEngine.model_id = (model_id, device)

        class FakeModel:
            def parameters(self):
                return iter(())

        return FakeModel()

    @staticmethod
    def transcribe(model, audio_file, *, on_segments=None, on_chunk=None,
                   should_cancel=None):
        made = [Segment(1, 0.0, 1.5, "one"), Segment(2, 1.5, 3.0, "two")]
        if on_segments:
            on_segments(len(made))
        out = []
        for seg in made:
            if should_cancel is not None and should_cancel():
                break
            out.append(seg)
            if on_chunk:
                on_chunk(seg, len(made))
        return out


def _patch(monkeypatch):
    monkeypatch.setattr(jobs_mod, "engine", FakeEngine)


def test_run_done(tmp_path, monkeypatch):
    _patch(monkeypatch)
    src = tmp_path / "in.wav"
    src.write_bytes(b"fake")
    out = str(tmp_path / "in.srt")
    job = jobs.Job(input=str(src), output=out)
    seen = []
    res = jobs.run(job, on_chunk=lambda s, p: seen.append((s.index, p.done, p.total)))
    assert res.status == "done" and res.segments == 2
    assert os.path.isfile(out) and not os.path.exists(out + ".partial")
    assert seen == [(1, 1, 2), (2, 2, 2)]
    assert FakeEngine.model_id == ("e2e_rnnt", "cpu")


def test_run_cancel_keeps_partial(tmp_path, monkeypatch):
    _patch(monkeypatch)
    src = tmp_path / "in.wav"
    src.write_bytes(b"fake")
    out = str(tmp_path / "in.srt")
    job = jobs.Job(input=str(src), output=out)
    calls = {"n": 0}

    def cancel_after_first():
        calls["n"] += 1
        return calls["n"] > 1

    res = jobs.run(job, should_cancel=cancel_after_first)
    assert res.status == "cancelled" and res.segments == 1
    assert os.path.isfile(out + ".partial") and not os.path.exists(out)


def test_run_missing_input(tmp_path):
    job = jobs.Job(input=str(tmp_path / "nope.wav"), output="x.srt")
    res = jobs.run(job)
    assert res.status == "error" and "not found" in res.error


def test_default_output():
    assert jobs.default_output("a/b.wav", "vtt") == str(
        __import__("pathlib").Path("a/b.wav").with_suffix(".vtt"))
