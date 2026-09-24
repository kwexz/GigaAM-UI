"""tune_cpu_threads: repair broken single-thread default, keep sane ones."""
import sys

from gigaam_ui.core import engine


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


def test_pyannote_stub_satisfies_import():
    import importlib
    saved = {k: v for k, v in sys.modules.items()
             if k == "pyannote" or k.startswith("pyannote.")}
    for k in saved:
        del sys.modules[k]
    try:
        engine._stub_unused_pyannote()
        assert importlib.import_module("pyannote") is sys.modules["pyannote"]
    finally:
        sys.modules.update(saved)
