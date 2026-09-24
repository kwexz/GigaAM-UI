import pytest

from gigaam_ui.core import formats
from gigaam_ui.core.events import Segment


def segs():
    return [
        Segment(1, 0.0, 17.277, "  Hello world.  "),
        Segment(2, 17.969, 61.5, "Second line.", speaker="Ann"),
    ]


def test_srt_timestamp_rollover():
    assert formats.srt_timestamp(59.9995) == "00:01:00,000"
    assert formats.srt_timestamp(0.0) == "00:00:00,000"
    assert formats.srt_timestamp(3723.456) == "01:02:03,456"
    assert formats.srt_timestamp(-5) == "00:00:00,000"


def test_write_srt(tmp_path):
    out = tmp_path / "a.srt"
    formats.write(segs(), "srt", str(out))
    assert out.read_text(encoding="utf-8") == (
        "1\n00:00:00,000 --> 00:00:17,277\nHello world.\n\n"
        "2\n00:00:17,969 --> 00:01:01,500\nAnn: Second line.\n\n"
    )


def test_write_vtt(tmp_path):
    out = tmp_path / "a.vtt"
    formats.write(segs(), "vtt", str(out))
    text = out.read_text(encoding="utf-8")
    assert text.startswith("WEBVTT\n\n")
    assert "00:00:17.969 --> 00:01:01.500\nAnn: Second line." in text


def test_write_txt_and_json(tmp_path):
    out = tmp_path / "a.txt"
    formats.write(segs(), "txt", str(out))
    assert "[00:00:00,000 --> 00:00:17,277] Hello world." in out.read_text(
        encoding="utf-8")
    out = tmp_path / "a.json"
    formats.write(segs(), "json", str(out))
    import json
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload[1] == {"index": 2, "start": 17.969, "end": 61.5,
                          "text": "Second line.", "speaker": "Ann"}


def test_unknown_format():
    with pytest.raises(SystemExit):
        formats.write(segs(), "ass", "x")
