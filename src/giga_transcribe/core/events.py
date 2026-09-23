"""Events and data types shared by engine, worker, desktop and CLI."""
from dataclasses import dataclass, field


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
