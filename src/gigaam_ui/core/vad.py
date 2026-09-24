"""Voice activity segmentation with Silero VAD (no gated repos, no HF token)."""
import torch
from silero_vad import get_speech_timestamps, load_silero_vad

SAMPLE_RATE = 16000

_model = None


def get_model():
    global _model
    if _model is None:
        _model = load_silero_vad()
    return _model


def speech_spans(wav: torch.Tensor) -> list[tuple[float, float]]:
    """Speech spans in seconds for 16 kHz mono waveform."""
    found = get_speech_timestamps(wav, get_model(), sampling_rate=SAMPLE_RATE,
                                  return_seconds=True)
    return [(t["start"], t["end"]) for t in found]


def chunk_spans(spans: list[tuple[float, float]], max_duration: float = 22.0,
                min_duration: float = 15.0, strict_limit: float = 30.0,
                new_chunk_threshold: float = 0.2) -> list[tuple[float, float]]:
    """Merge speech spans into ASR chunks, cutting at silences past min_duration
    and hard-splitting anything over strict_limit."""

    def flush(chunks, start, end):
        if end - start > strict_limit:
            n = int((end - start) / strict_limit) + 1
            step = (end - start) / n
            for k in range(n):
                chunks.append((start + k * step, start + (k + 1) * step))
        else:
            chunks.append((start, end))

    chunks: list[tuple[float, float]] = []
    if not spans:
        return chunks
    cur_start, cur_end = spans[0]
    for start, end in spans[1:]:
        cur_dur = cur_end - cur_start
        if cur_dur > new_chunk_threshold and (
                cur_dur + (end - cur_end) > max_duration
                or cur_dur > min_duration):
            flush(chunks, cur_start, cur_end)
            cur_start = start
        cur_end = end
    if cur_end - cur_start > new_chunk_threshold:
        flush(chunks, cur_start, cur_end)
    return chunks
