"""Verified downloads with resume. Stdlib only: the bootstrapper runs
before any third-party dependency exists."""
import hashlib
import os
import urllib.request
from pathlib import Path

CHUNK = 1024 * 256


class DownloadError(Exception):
    pass


class ChecksumError(DownloadError):
    pass


class Cancelled(DownloadError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(CHUNK), b""):
            h.update(blk)
    return h.hexdigest()


def download(url: str, dest: str | Path, *, expected_sha256: str,
             on_progress=None, should_cancel=None) -> Path:
    """Download to dest atomically (via .part + resume + sha256 check)."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.is_file() else 0

    req = urllib.request.Request(url)
    if have:
        req.add_header("Range", f"bytes={have}-")
    try:
        resp = urllib.request.urlopen(req)
    except OSError as e:
        raise DownloadError(f"cannot download {url}: {e}") from e

    if have and resp.status != 206:
        have = 0  # server ignored Range: restart from scratch
    total = resp.getheader("Content-Length")
    total = (int(total) + have) if total is not None else 0

    try:
        with open(part, "ab" if have else "wb") as f:
            received = have
            if on_progress:
                on_progress(received, total)
            while True:
                if should_cancel is not None and should_cancel():
                    raise Cancelled(f"cancelled: {url}")
                blk = resp.read(CHUNK)
                if not blk:
                    break
                f.write(blk)
                received += len(blk)
                if on_progress:
                    on_progress(received, total)
    finally:
        resp.close()

    if _sha256(part) != expected_sha256.lower():
        part.unlink(missing_ok=True)
        raise ChecksumError(f"sha256 mismatch: {url}")
    os.replace(part, dest)
    return dest
