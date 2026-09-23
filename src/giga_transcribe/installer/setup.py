"""First-run setup orchestration: what is missing, how much, fetch it."""
import json
from dataclasses import dataclass
from pathlib import Path

from . import downloads, state
from .manifest import Component, Manifest

MARKER = "installed.json"


@dataclass
class SetupStatus:
    component: Component
    done: bool  # already present and verified


def dest_for(target: Path, component: Component) -> Path:
    return target / component.id / Path(component.url.split("?")[0]).name


def status(manifest: Manifest, target: Path | None = None) -> list[SetupStatus]:
    target = target or state.data_dir()
    return [SetupStatus(c, downloads.verify(dest_for(target, c), c.sha256))
            for c in manifest.components]


def missing(manifest: Manifest, target: Path | None = None) -> list[Component]:
    return [s.component for s in status(manifest, target) if not s.done]


def total_bytes(components: list[Component]) -> int:
    return sum(c.size for c in components)


def format_bytes(n: int) -> str:
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if n < 1024 or unit == "ГБ":
            return f"{n:.0f} {unit}" if unit == "Б" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} ГБ"


def write_marker(target: Path, manifest: Manifest) -> None:
    payload = {"version": manifest.version,
               "components": [c.id for c in manifest.components]}
    target.mkdir(parents=True, exist_ok=True)
    (target / MARKER).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def is_installed(target: Path | None = None) -> bool:
    target = target or state.data_dir()
    marker = target / MARKER
    if not marker.is_file():
        return False
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return bool(data.get("components"))


def ensure(manifest: Manifest, target: Path | None = None, *,
           on_component=None, on_progress=None,
           should_cancel=None) -> list[Component]:
    """Download missing components. Returns what was fetched (empty = all had)."""
    target = target or state.data_dir()
    fetched: list[Component] = []
    pending = missing(manifest, target)
    for i, comp in enumerate(pending):
        if should_cancel is not None and should_cancel():
            raise downloads.Cancelled("setup cancelled")
        if on_component:
            on_component(comp, i, len(pending))
        dest = dest_for(target, comp)
        downloads.download(comp.url, dest, expected_sha256=comp.sha256,
                           on_progress=(lambda r, t, c=comp: on_progress(c, r, t)
                                        if on_progress else None),
                           should_cancel=should_cancel)
        fetched.append(comp)
    write_marker(target, manifest)
    return fetched
