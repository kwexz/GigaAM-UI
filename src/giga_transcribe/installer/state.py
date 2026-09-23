"""Data dir: home by default, overridable (portable/flash-drive mode)."""
import os
import sys
from pathlib import Path

APP_DIR_NAME = "Giga Transcribe"
ENV_OVERRIDE = "GIGA_TRANSCRIBE_DATA"


def data_dir() -> Path:
    override = os.environ.get(ENV_OVERRIDE)
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        return Path(base) / APP_DIR_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_DIR_NAME


def component_dir(component_id: str) -> Path:
    return data_dir() / component_id
