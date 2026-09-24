"""chunk_spans: pure logic, no model."""
from gigaam_ui.core.vad import chunk_spans


def test_merges_short_spans():
    spans = [(0.0, 5.0), (5.5, 10.0), (10.5, 14.0)]
    assert chunk_spans(spans) == [(0.0, 14.0)]


def test_cuts_past_min_duration_at_silence():
    spans = [(0.0, 16.0), (17.0, 20.0), (21.0, 24.0)]
    assert chunk_spans(spans) == [(0.0, 16.0), (17.0, 24.0)]


def test_hard_splits_over_strict_limit():
    assert chunk_spans([(0.0, 65.0)], strict_limit=30.0) == [
        (0.0, 65.0 / 3), (65.0 / 3, 65.0 * 2 / 3), (65.0 * 2 / 3, 65.0)]


def test_drops_tiny_blips_and_empties():
    assert chunk_spans([(0.0, 0.1)]) == []
    assert chunk_spans([]) == []


def test_respects_max_duration():
    spans = [(0.0, 10.0), (10.5, 20.0), (20.5, 30.0)]
    out = chunk_spans(spans, max_duration=22.0)
    assert out[0][1] <= 20.0  # flushed before adding the third span
    assert out[-1] == (20.5, 30.0)
