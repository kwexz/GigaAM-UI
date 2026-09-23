"""Environment helpers. pyannote-era shims are gone with Silero VAD."""
import os
import shutil
from pathlib import Path


def load_dotenv(path=".env"):
    # ponytail: naive KEY=VALUE parser, use python-dotenv if quoting/expansion needed
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip("'\"")
        os.environ.setdefault(key, value)


def ensure_ffmpeg() -> str:
    if shutil.which("ffmpeg") is None:
        # WinGet Links may be missing from PATH in stale shells/IDEs
        winget_links = Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links"))
        if (winget_links / "ffmpeg.exe").is_file():
            os.environ["PATH"] = str(winget_links) + os.pathsep + os.environ["PATH"]
    found = shutil.which("ffmpeg")
    if found is None:
        raise SystemExit(
            "ffmpeg not found in PATH. Install it: winget install Gyan.FFmpeg, "
            "then reopen terminal."
        )
    return found
