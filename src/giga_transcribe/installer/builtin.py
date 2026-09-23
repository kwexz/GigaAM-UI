"""Release manifest fetch (fallback to empty dev manifest offline)."""
import urllib.request

from .manifest import Manifest

RELEASE_MANIFEST_URL = ("https://github.com/kwexz/isMemory/releases/latest"
                        "/download/manifest.json")


def fetch_manifest(url: str = RELEASE_MANIFEST_URL,
                   timeout: int = 20) -> Manifest | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return Manifest.from_json(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 — offline/broken release => dev mode
        return None


def dev_manifest() -> Manifest:
    return Manifest(version=1, components=())


def default_manifest() -> Manifest:
    """Release manifest when reachable, else empty (dev mode)."""
    return fetch_manifest() or dev_manifest()
