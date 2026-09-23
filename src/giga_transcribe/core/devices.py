"""Device detection and fit guards. torch-free import: UI bundle has no torch.

Only actually-available devices surface. When torch is missing (light UI
bundle before engine setup), this module still imports and reports cpu.
"""
import os
from dataclasses import dataclass


def _torch():
    try:
        import torch
    except ImportError:
        return None
    return torch


def has_torch() -> bool:
    return _torch() is not None


# GigaAM-v3 is ~240M params in fp32; activations on <=22 s chunks are small
# next to weights. Keep a headroom factor for allocator fragmentation.
HEADROOM = 0.85


@dataclass(frozen=True)
class DeviceInfo:
    id: str  # cpu | cuda:0 | mps
    kind: str
    index: int = 0
    cores: int | None = None  # cpu logical threads
    total_memory: int | None = None  # bytes, cuda only
    name: str | None = None  # cuda device name


def describe() -> list[DeviceInfo]:
    torch = _torch()
    out = [DeviceInfo(id="cpu", kind="cpu",
                      cores=os.cpu_count() or 4)]
    if torch is None:
        return out
    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            out.append(DeviceInfo(id=f"cuda:{i}", kind="cuda", index=i,
                                  total_memory=props.total_memory,
                                  name=torch.cuda.get_device_name(i)))
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        out.append(DeviceInfo(id="mps", kind="mps"))
    return out


def available() -> list[str]:
    return [d.id for d in describe()]


def resolve(name: str) -> str:
    name = (name or "cpu").lower()
    if name == "auto":
        ids = available()
        cuda = next((i for i in ids if i.startswith("cuda:")), None)
        return cuda or ("mps" if "mps" in ids else "cpu")
    if name == "cuda":
        name = "cuda:0"
    if name not in available():
        raise SystemExit(f"Unknown/unavailable device: {name} "
                         f"(available: {available()})")
    return name


def param_bytes(model) -> int:
    return sum(p.numel() * p.element_size() for p in model.parameters())


def check_fit(info: DeviceInfo, need_bytes: int) -> str | None:
    """None if fits, else human-readable reason (caller decides how to fail)."""
    if info.kind != "cuda" or info.total_memory is None:
        return None  # cpu/mps: system RAM is plentiful for a 1 GB model
    if need_bytes > info.total_memory * HEADROOM:
        need_gb = need_bytes / 1e9
        have_gb = info.total_memory / 1e9
        return (f"model needs ~{need_gb:.1f} GB, GPU has {have_gb:.1f} GB "
                f"({info.name})")
    return None
