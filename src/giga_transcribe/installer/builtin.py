"""Built-in manifest. Empty until the engine-pack pipeline (CI) publishes
real component archives; the setup UI is fully testable with test manifests."""
from .manifest import Manifest


def dev_manifest() -> Manifest:
    return Manifest(version=1, components=())
