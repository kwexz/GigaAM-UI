"""Release manifest fetch (fallback to empty dev manifest offline)."""
import urllib.request

from .manifest import Manifest

RELEASE_MANIFEST_URL = ("https://github.com/kwexz/GigaAM-UI/releases/latest"
                        "/download/manifest.json")


class ManifestError(Exception):
    """Manifest unreachable (offline, private repo, broken release)."""


def fetch_manifest(url: str = RELEASE_MANIFEST_URL,
                   timeout: int = 20) -> Manifest:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return Manifest.from_json(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 — wrapped with context
        raise ManifestError(
            f"cannot fetch component list from {url}: {e}. "
            f"Check network access."
        ) from e


def dev_manifest() -> Manifest:
    return Manifest(version=1, components=())


def default_manifest() -> tuple[Manifest, str | None]:
    """(manifest, error): release manifest when reachable, else dev + reason."""
    try:
        return fetch_manifest(), None
    except ManifestError as e:
        return dev_manifest(), str(e)
