"""Events and data types shared by engine, worker, desktop and CLI."""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Segment:
    index: int
    start: float
    end: float
    text: str
    speaker: str | None = None  # reserved for diarization, unused in MVP


@dataclass
class Progress:
    done: int
    total: int

    @property
    def percent(self) -> float:
        return (self.done / self.total * 100.0) if self.total else 0.0


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
