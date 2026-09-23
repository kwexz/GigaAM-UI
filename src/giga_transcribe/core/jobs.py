"""One transcription task: input -> model/device/format -> output file."""
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import devices, engine, formats
from .events import Progress, Segment


@dataclass
class Job:
    input: str
    output: str
    fmt: str = "srt"
    model_id: str = "e2e_rnnt"
    device: str = "cpu"


@dataclass
class JobResult:
    status: str  # done | cancelled | error
    output: str
    elapsed: float
    segments: int
    error: str = ""


def default_output(input_path: str, fmt: str) -> str:
    return str(Path(input_path).with_suffix(f".{fmt}"))


def partial_path(output: str) -> str:
    return output + ".partial"


def run(job: Job, *, on_stage=None, on_segments=None, on_chunk=None,
        should_cancel=None) -> JobResult:
    if not os.path.isfile(job.input):
        return JobResult("error", job.output, 0.0, 0, f"not found: {job.input}")
    started = time.perf_counter()
    collected: list[Segment] = []
    part = partial_path(job.output)

    def emit_stage(name: str):
        if on_stage:
            on_stage(name)

    def emit_segments(total: int):
        if on_segments:
            on_segments(total)

    def emit_chunk(seg: Segment, total: int):
        collected.append(seg)
        formats.write(collected, job.fmt, part)  # rewrite; files are KBs
        if on_chunk:
            on_chunk(seg, Progress(len(collected), total))

    try:
        emit_stage("loading_model")
        model = engine.load_model(job.model_id, job.device)
        info = next(d for d in devices.describe() if d.id == job.device)
        misfit = devices.check_fit(info, devices.param_bytes(model))
        if misfit is not None:
            return JobResult("error", job.output, time.perf_counter() - started,
                             0, f"Not enough GPU memory: {misfit}")
        emit_stage("transcribing")
        engine.transcribe(
            model, job.input,
            on_segments=emit_segments, on_chunk=emit_chunk,
            should_cancel=should_cancel,
        )
    except engine.GatedModelError as e:
        return JobResult("error", job.output, time.perf_counter() - started,
                         len(collected), str(e))
    except KeyboardInterrupt:
        return JobResult("cancelled", part, time.perf_counter() - started,
                         len(collected))
    except Exception as e:  # noqa: BLE001 — surfaced to UI/CLI verbatim
        return JobResult("error", job.output, time.perf_counter() - started,
                         len(collected), f"{type(e).__name__}: {e}")

    if should_cancel is not None and should_cancel():
        return JobResult("cancelled", part, time.perf_counter() - started,
                         len(collected))
    os.replace(part, job.output)
    return JobResult("done", job.output, time.perf_counter() - started,
                     len(collected))
