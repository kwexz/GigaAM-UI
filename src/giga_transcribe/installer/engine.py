"""Engine bundle discovery inside the data dir."""
from pathlib import Path

from .state import data_dir


def _exe_name() -> str:
    import sys
    return "giga-worker.exe" if sys.platform == "win32" else "giga-worker"


def find_engine(target: Path | None = None) -> str | None:
    """Path to a downloaded engine executable, or None."""
    base = Path(target or data_dir())
    if not base.is_dir():
        return None
    cands = sorted(base.glob("engine-*/giga-worker/giga-worker*"))
    name = _exe_name()
    for c in cands:
        if c.name == name and c.is_file():
            return str(c)
    return None
