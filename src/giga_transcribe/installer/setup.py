"""First-run setup orchestration: what is missing, how much, fetch it."""
import json
import shutil
import tarfile
import tempfile
import zipfile
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
    name = Path(component.url.split("?")[0]).name
    if component.extract:
        return target / component.id / name
    return target / component.id / name


def _installed_files(target: Path, component: Component) -> bool:
    if not component.files:
        return downloads.verify(dest_for(target, component), component.sha256)
    base = target / component.id
    return all((base / f).is_file() for f in component.files)


def status(manifest: Manifest, target: Path | None = None) -> list[SetupStatus]:
    target = target or state.data_dir()
    return [SetupStatus(c, _installed_files(target, c))
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


def _safe_join(base: Path, *parts: str) -> Path | None:
    out = base.joinpath(*parts)
    try:
        out.relative_to(base)
    except ValueError:
        return None  # absolute path or .. escape
    return out


def _strip(name: str, strip_top: bool) -> str | None:
    parts = Path(name).parts
    if not strip_top or len(parts) <= 1:
        return name
    return str(Path(*parts[1:]))


def _unpack(archive: Path, into: Path, strip_top: bool) -> None:
    into.mkdir(parents=True, exist_ok=True)
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                target = _strip(info.filename, strip_top)
                out = _safe_join(into, target) if target else None
                if out is None:
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    elif archive.name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(archive, "r:gz") as t:
            for member in t.getmembers():
                if not member.isfile():
                    continue
                target = _strip(member.name, strip_top)
                if target is None:
                    continue
                member.name = target
                out = _safe_join(into, target)
                if out is None:
                    continue
                t.extract(member, into, filter="data")
    else:
        raise downloads.DownloadError(f"cannot unpack: {archive.name}")


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
        if comp.extract:
            tmp = Path(tempfile.mkdtemp(prefix="giga-dl-")) / dest.name
            try:
                downloads.download(comp.url, tmp, expected_sha256=comp.sha256,
                                   on_progress=(lambda r, t: on_progress(comp, r, t)
                                                if on_progress else None),
                                   should_cancel=should_cancel)
                shutil.rmtree(target / comp.id, ignore_errors=True)
                _unpack(tmp, target / comp.id, comp.strip_top)
            finally:
                tmp.unlink(missing_ok=True)
                try:
                    tmp.parent.rmdir()
                except OSError:
                    pass
            if not _installed_files(target, comp):
                raise downloads.DownloadError(
                    f"archive missing expected files: {comp.id} {comp.files}")
        else:
            downloads.download(comp.url, dest, expected_sha256=comp.sha256,
                               on_progress=(lambda r, t, c=comp: on_progress(c, r, t)
                                            if on_progress else None),
                               should_cancel=should_cancel)
        fetched.append(comp)
    write_marker(target, manifest)
    return fetched
