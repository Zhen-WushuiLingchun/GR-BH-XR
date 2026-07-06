"""WGPU Vulkan adapter selection for Task 4 compute prototypes."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


@dataclass(frozen=True)
class BackendInfo:
    backend: str
    requested_backend: str
    adapter_name: str
    adapter_vendor: str
    adapter_type: str
    backend_type: str
    device_id: int | None
    vendor_id: int | None
    description: str
    ready: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "requested_backend": self.requested_backend,
            "adapter_name": self.adapter_name,
            "adapter_vendor": self.adapter_vendor,
            "adapter_type": self.adapter_type,
            "backend_type": self.backend_type,
            "device_id": self.device_id,
            "vendor_id": self.vendor_id,
            "description": self.description,
            "ready": self.ready,
        }


def require_wgpu():
    try:
        import wgpu  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - dependency-gated path
        raise RuntimeError(
            "Task 4 GPU tools require the optional dependency group: "
            "python -m pip install -e .[gpu]"
        ) from exc
    return wgpu


def _info_dict(adapter) -> dict[str, Any]:
    info = getattr(adapter, "info", {})
    if hasattr(info, "to_dict"):
        return info.to_dict()
    return dict(info)


def enumerate_vulkan_adapters() -> list[tuple[Any, dict[str, Any]]]:
    wgpu = require_wgpu()
    adapters = []
    for adapter in wgpu.gpu.enumerate_adapters_sync():
        info = _info_dict(adapter)
        if str(info.get("backend_type", "")).lower() == "vulkan":
            adapters.append((adapter, info))
    return adapters


def select_vulkan_adapter(prefer_nvidia: bool = True):
    """Return a Vulkan adapter, preferring an NVIDIA discrete GPU."""

    adapters = enumerate_vulkan_adapters()
    if not adapters:
        raise RuntimeError("No WGPU Vulkan adapter was found.")

    def score(item: tuple[Any, dict[str, Any]]) -> tuple[int, int, int]:
        _adapter, info = item
        vendor = str(info.get("vendor", "")).lower()
        device = str(info.get("device", "")).lower()
        adapter_type = str(info.get("adapter_type", "")).lower()
        is_discrete = int(adapter_type == "discretegpu")
        is_nvidia = int("nvidia" in vendor or "nvidia" in device)
        return (is_nvidia if prefer_nvidia else 0, is_discrete, int(adapter_type != "cpu"))

    return sorted(adapters, key=score, reverse=True)[0][0]


def create_vulkan_device():
    adapter = select_vulkan_adapter()
    return adapter, adapter.request_device_sync(label="gr-bh-xr task4 vulkan compute")


def backend_info(adapter=None) -> BackendInfo:
    if adapter is None:
        adapter = select_vulkan_adapter()
    info = _info_dict(adapter)
    return BackendInfo(
        backend="wgpu",
        requested_backend="vulkan",
        adapter_name=str(info.get("device", "")),
        adapter_vendor=str(info.get("vendor", "")),
        adapter_type=str(info.get("adapter_type", "")),
        backend_type=str(info.get("backend_type", "")),
        device_id=_optional_int(info.get("device_id")),
        vendor_id=_optional_int(info.get("vendor_id")),
        description=str(info.get("description", "")),
        ready=str(info.get("backend_type", "")).lower() == "vulkan",
    )


def _optional_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except Exception:
        return None


def main() -> None:
    adapter = select_vulkan_adapter()
    print(json.dumps(backend_info(adapter).as_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
