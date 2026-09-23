"""tune_cpu_threads: repair broken single-thread default, keep sane ones."""
from giga_transcribe.core import engine


def test_bumps_single_thread(monkeypatch):
    calls = []
    monkeypatch.setattr(engine.torch, "get_num_threads", lambda: 1)
    monkeypatch.setattr(engine.torch, "set_num_threads", calls.append)
    monkeypatch.setattr(engine.os, "cpu_count", lambda: 8)
    engine.tune_cpu_threads()
    assert calls == [8]


def test_keeps_sane_default(monkeypatch):
    calls = []
    monkeypatch.setattr(engine.torch, "get_num_threads", lambda: 14)
    monkeypatch.setattr(engine.torch, "set_num_threads", calls.append)
    engine.tune_cpu_threads()
    assert calls == []


def test_caps_at_eight(monkeypatch):
    calls = []
    monkeypatch.setattr(engine.torch, "get_num_threads", lambda: 1)
    monkeypatch.setattr(engine.torch, "set_num_threads", calls.append)
    monkeypatch.setattr(engine.os, "cpu_count", lambda: 32)
    engine.tune_cpu_threads()
    assert calls == [8]
