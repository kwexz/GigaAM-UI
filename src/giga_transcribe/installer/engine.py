"""Engine bundle discovery inside the data dir (platform-filtered)."""
import sys
from pathlib import Path

from .setup import current_platform
from .state import data_dir


def _exe_name(kind: str) -> str:
    ext = ".exe" if sys.platform == "win32" else ""
    return f"{kind}{ext}"


def find_engine(target: Path | None = None) -> str | None:
    """Path to a downloaded engine executable for this platform, or None."""
    base = Path(target or data_dir())
    if not base.is_dir():
        return None
    plat = current_platform()
    name = _exe_name("GigaAM-Worker")
    for c in sorted(base.glob("engine-*/GigaAM-Worker/GigaAM-Worker*")):
        if plat in c.parent.parent.name and c.name == name and c.is_file():
            return str(c)
    return None


def find_app(target: Path | None = None) -> str | None:
    """Path to a downloaded full-UI bundle for this platform, or None."""
    base = Path(target or data_dir())
    if not base.is_dir():
        return None
    plat = current_platform()
    name = _exe_name("GigaAM-UI")
    for c in sorted(base.glob("ui-*/GigaAM-UI/GigaAM-UI*")):
        if plat in c.parent.parent.name and c.name == name and c.is_file():
            return str(c)
    return None
