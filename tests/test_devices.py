"""Devices: detection, resolve, fit guard. CUDA parts conditional on hardware."""
import torch

from gigaam_ui.core import devices
from gigaam_ui.core.devices import DeviceInfo


def test_cpu_always_present():
    ids = devices.available()
    assert "cpu" in ids and len(ids) == len(set(ids))
    cpu = next(d for d in devices.describe() if d.id == "cpu")
    assert cpu.cores and cpu.cores > 0


def test_resolve_cpu_and_auto():
    assert devices.resolve("cpu") == "cpu"
    assert devices.resolve("auto") in devices.available()
    if not torch.cuda.is_available():
        import pytest
        with pytest.raises(SystemExit):
            devices.resolve("cuda")
        with pytest.raises(SystemExit):
            devices.resolve("bogus")


def test_check_fit():
    big = DeviceInfo(id="cuda:0", kind="cuda", total_memory=int(8e9), name="T")
    assert devices.check_fit(big, int(1e9)) is None
    msg = devices.check_fit(big, int(9e9))
    assert msg and "8.0" in msg
    cpu = DeviceInfo(id="cpu", kind="cpu")
    assert devices.check_fit(cpu, int(1e12)) is None  # RAM assumed plentiful


def test_param_bytes():
    t = torch.zeros(10, dtype=torch.float32)

    class M:
        def parameters(self):
            return iter([t])

    assert devices.param_bytes(M()) == 40
