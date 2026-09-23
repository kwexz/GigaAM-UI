"""Engine bundle discovery inside the data dir (platform-filtered)."""
from pathlib import Path

from .setup import current_platform
from .state import data_dir


def _exe_name() -> str:
    import sys
    return "giga-worker.exe" if sys.platform == "win32" else "giga-worker"


def find_engine(target: Path | None = None) -> str | None:
    """Path to a downloaded engine executable for this platform, or None."""
    base = Path(target or data_dir())
    if not base.is_dir():
        return None
    plat = current_platform()
    name = _exe_name()
    for c in sorted(base.glob("engine-*/giga-worker/giga-worker*")):
        if plat in c.parent.parent.name and c.name == name and c.is_file():
            return str(c)
    return None
