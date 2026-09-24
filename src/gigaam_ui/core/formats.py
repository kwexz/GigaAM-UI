"""Subtitle writers. All take list[Segment], write UTF-8, end file with newline."""
import json

from .events import Segment


def srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    h, rem = divmod(total_ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def vtt_timestamp(seconds: float) -> str:
    return srt_timestamp(seconds).replace(",", ".")


def write_srt(segments: list[Segment], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for seg in segments:
            text = seg.text.strip()
            if seg.speaker:
                text = f"{seg.speaker}: {text}"
            f.write(
                f"{seg.index}\n"
                f"{srt_timestamp(seg.start)} --> {srt_timestamp(seg.end)}\n"
                f"{text}\n\n"
            )


def write_vtt(segments: list[Segment], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for seg in segments:
            text = seg.text.strip()
            if seg.speaker:
                text = f"{seg.speaker}: {text}"
            f.write(
                f"{vtt_timestamp(seg.start)} --> {vtt_timestamp(seg.end)}\n"
                f"{text}\n\n"
            )


def write_txt(segments: list[Segment], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for seg in segments:
            text = seg.text.strip()
            if seg.speaker:
                text = f"{seg.speaker}: {text}"
            f.write(f"[{srt_timestamp(seg.start)} --> {srt_timestamp(seg.end)}] {text}\n")


def write_json(segments: list[Segment], path: str) -> None:
    payload = [
        {
            "index": seg.index,
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text.strip(),
            "speaker": seg.speaker,
        }
        for seg in segments
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


WRITERS = {"srt": write_srt, "vtt": write_vtt, "txt": write_txt, "json": write_json}


def write(segments: list[Segment], fmt: str, path: str) -> None:
    try:
        writer = WRITERS[fmt]
    except KeyError:
        raise SystemExit(f"Unknown format: {fmt} (available: {sorted(WRITERS)})")
    writer(segments, path)
