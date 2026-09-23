"""Transcription engine. No prints, no Qt — reports via callbacks only."""
import os
import sys

import torch
from transformers import AutoModel

from . import models, vad
from .events import Segment


class GatedModelError(Exception):
    """Kept for API compat; Silero VAD path needs no gated downloads."""


class Cancelled(Exception):
    def __init__(self, segments):
        super().__init__("cancelled")
        self.segments = segments


def tune_cpu_threads():
    # macOS ARM torch defaults intra-op to 1 thread (measured 9x slowdown
    # on M1: 51 s -> 5.6 s on short.wav with 8 threads). Only repair the
    # broken default; never downgrade a sane one (e.g. 14 on Win x64).
    if torch.get_num_threads() == 1:
        torch.set_num_threads(min(os.cpu_count() or 4, 8))


def load_model(model_id: str, device: str):
    info = models.get(model_id)
    if device == "cpu":
        tune_cpu_threads()
    model = AutoModel.from_pretrained(
        models.REPO, revision=info.id, trust_remote_code=True
    )
    model.eval()
    if device != "cpu":
        model.to(device)
    return model


def transcribe(model, audio_file, *, on_segments=None, on_chunk=None,
               should_cancel=None) -> list[Segment]:
    """Own longform loop: decode -> Silero VAD -> chunk -> ASR per chunk."""
    inner = model.model  # GigaAMASR behind the transformers wrapper
    device, dtype = inner._device, inner._dtype
    # Reuse GigaAM's ffmpeg loader (inner modeling_gigaam module, pinned).
    giga_mod = sys.modules[type(inner).__module__]
    wav = giga_mod.load_audio(audio_file)  # 1-D 16 kHz mono, CPU

    bounds = vad.chunk_spans(vad.speech_spans(wav))
    if on_segments:
        on_segments(len(bounds))

    collected: list[Segment] = []
    sr = vad.SAMPLE_RATE
    try:
        with torch.inference_mode():
            for i, (start, end) in enumerate(bounds, 1):
                if should_cancel is not None and should_cancel():
                    raise Cancelled(collected)
                chunk = wav[int(start * sr):int(end * sr)]
                chunk = chunk.to(device).unsqueeze(0).to(dtype)
                length = torch.full([1], chunk.shape[-1], device=device)
                encoded, encoded_len = inner.forward(chunk, length)
                text = inner.decoding.decode(inner.head, encoded, encoded_len)[0]
                seg = Segment(index=i, start=start, end=end, text=text)
                collected.append(seg)
                if on_chunk:
                    on_chunk(seg, len(bounds))
    except Cancelled as e:
        return e.segments
    return collected
