"""GPU 采样函数 (2026-07-07 拆自 checks.py).

两个独立采样器:
- `_sample_gpu()` 走 NVIDIA NVML (nvidia-ml-py), 数据最准 (含 util / mem_used)
- `_sample_pci_gpus()` 走 /sys/bus/pci/devices sysfs, 不依赖任何驱动

返回 GpuItem shape: {name, util_pct, mem_used_mb, mem_total_mb}
(契约见 packages/web/.../system-resources.tsx GpuItem interface)

callers (合并逻辑见 checks.py::check_system):
- NVML 返非空 → 用 NVML 数据
- 否则 → PCI 兜底 (告诉 admin "硬件在, 驱动坏了")
- 都空 → extra.gpu=[], gpu_source="empty"
"""

from __future__ import annotations

from pathlib import Path

# ---------- NVML (NVIDIA) ----------


def _sample_gpu() -> tuple[list[dict], str | None]:
    """采样所有 NVIDIA GPU. 驱动缺失 → ([], "<error>")

    2026-06-15 重构: 从 `import pynvml` namespace 改成具体函数 import.
    nvidia-ml-py 13.6+ 的 nvmlDeviceGetName 套了 @convertStrBytes, 自动把
    ctypes bytes decode 成 str, 老 pynvml 11.x 返 bytes. isinstance 守卫兼容两者.

    2026-07-07 重构: 签名改 tuple (list, err_msg). 老版本吞所有 Exception 返 [],
    让 admin 误以为"机器没 GPU". 现在把 NVML init/runtime 错误 message 透出去,
    check_system 把它放进 extra.gpu_error, 让 admin 看到是"驱动坏了"还是"真没 GPU".
    """
    try:
        # 重依赖 lazy: pynvml (nvidia-ml-py) 软依赖, 非 GPU 机器 ImportError 兜底
        # pynvml module 由 nvidia-ml-py 包提供 (PyPI 上的 pynvml 是 deprecated shim)
        from pynvml import (  # noqa: E402
            nvmlDeviceGetCount,
            nvmlDeviceGetHandleByIndex,
            nvmlDeviceGetMemoryInfo,
            nvmlDeviceGetName,
            nvmlDeviceGetUtilizationRates,
            nvmlInit,
            nvmlShutdown,
        )

        nvmlInit()
        try:
            count = nvmlDeviceGetCount()
            gpus: list[dict] = []
            for i in range(count):
                h = nvmlDeviceGetHandleByIndex(i)
                # 兼容老 pynvml (bytes) 和新 nvidia-ml-py 13.6+ (str)
                _name = nvmlDeviceGetName(h)
                name = _name.decode("utf-8", errors="replace") if isinstance(_name, bytes) else _name
                util = nvmlDeviceGetUtilizationRates(h).gpu
                mem = nvmlDeviceGetMemoryInfo(h)
                gpus.append(
                    {
                        "name": name,
                        "util_pct": util,
                        "mem_used_mb": int(mem.used) // (1024 * 1024),
                        "mem_total_mb": int(mem.total) // (1024 * 1024),
                    }
                )
            return gpus, None
        finally:
            nvmlShutdown()
    except Exception as e:
        # 截断 200 字符防长 traceback 污染 admin JSON; type 名+msg 足够定位
        return [], f"{type(e).__name__}: {str(e)[:200]}"


# ---------- PCI sysfs 兜底 ----------
# NVML 失败时 (驱动坏了/装错版本/Blackwell 需要 nvidia-open) 仍能从 sysfs 列出 GPU.
# 不依赖任何驱动, 直接读 /sys/bus/pci/devices/*/{vendor,device,class,resource}.
# 模块级常量让测试 monkeypatch 到 tmp_path, 不依赖真 /sys (macOS CI / 沙盒兼容).

_PCI_SYSFS_BASE = "/sys/bus/pci/devices"
# PCI class code 0x03xx = display controller. 0x030000 = VGA, 0x030200 = 3D controller
# 0x030100 = VGA-compatible (老式), 0x038000 = 其他
_PCI_CLASS_DISPLAY_PREFIX = "0x03"
_VENDOR_NAMES: dict[str, str] = {
    "0x10de": "NVIDIA",
    "0x1002": "AMD",
    "0x8086": "Intel",
}


def _pci_bar_size_mb(device_path: Path) -> int:
    """从 sysfs resource 文件算 prefetchable memory BAR 总量 (MB).

    只数 framebuffer (flags & 0x04 prefetchable), 跳过 MMIO/IO 空间.
    显存 BAR 在 Linux kernel 必带 prefetchable 标志; MMIO (寄存器/ROM) 不带.
    resource 文件格式: 每行 "<start> <end> <flags>", 16 进制 64-bit.
    返回 0 表示该设备没显存 BAR (罕见) 或文件不可读.
    """
    resource_file = device_path / "resource"
    if not resource_file.is_file():
        return 0
    total_bytes = 0
    try:
        text = resource_file.read_text()
    except OSError:
        return 0
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            start = int(parts[0], 16)
            end = int(parts[1], 16)
            flags = int(parts[2], 16)
        except ValueError:
            continue
        # flags & 0x04 = prefetchable (显存 BAR 标志). 不再要求 64-bit — 部分显存是 32-bit BAR.
        if flags & 0x04 and end > start:
            total_bytes += end - start + 1
    return total_bytes // (1024 * 1024)


def _sample_pci_gpus() -> list[dict]:
    """穷举 PCI 设备, 找 class 0x03xx (display). 无驱动也能跑.

    返回 GpuItem shape (前端契约) 但 util_pct/mem_used_mb 全 0 (没驱动读不到).
    mem_total_mb 从 resource BAR 推算; 拿不到就 0, 此时该设备会被过滤掉 (避免误报).

    非 Linux / 无权限 → [], 跟 _sample_gpu 行为对齐.
    """
    base = Path(_PCI_SYSFS_BASE)
    if not base.is_dir():
        return []
    out: list[dict] = []
    try:
        entries = list(base.iterdir())
    except OSError:
        return []
    for dev_path in entries:
        try:
            if not dev_path.is_dir():
                continue
            class_text = (dev_path / "class").read_text().strip()
        except OSError:
            continue
        # class 文件是 6 位 hex (高字节 class, 中字节 subclass, 低字节 prog-if)
        # 例 "0x030000" = VGA, "0x030200" = 3D, "0x060000" = host bridge
        if not class_text.startswith(_PCI_CLASS_DISPLAY_PREFIX):
            continue
        try:
            vendor = (dev_path / "vendor").read_text().strip()
            device = (dev_path / "device").read_text().strip()
        except OSError:
            continue
        vendor_name = _VENDOR_NAMES.get(vendor, vendor)
        # device id 是 4 位 hex (例 "0x2c05" = GB203), 拼到 vendor 名后, admin 能定位具体型号
        gpu_name = f"{vendor_name} [{device}]"
        mem_mb = _pci_bar_size_mb(dev_path)
        if mem_mb == 0:
            # BAR 拿不到 → 不返, 避免前端看到 "0 MiB 显存 GPU"
            continue
        out.append(
            {
                "name": gpu_name,
                "util_pct": 0,
                "mem_used_mb": 0,
                "mem_total_mb": mem_mb,
            }
        )
    return out
