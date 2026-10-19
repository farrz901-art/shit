"""checks.py 单元测试 (2026-06-11) — 5 个 check 函数

项目惯例: 用 asyncio.run() 跑协程, 不用 @pytest.mark.asyncio
(pytest-asyncio 没装, 项目里其他 async 测试都用 asyncio.run)
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from src.health import gpu as _gpu_module
from src.health.checks import (
    check_dify,
    check_neo4j,
    check_pgvector,
    check_python,
    check_system,
)

# ---------- check_python ----------


def test_check_python_returns_uptime():
    """uptime = time.time() - process_start_time, 返 extra.uptime_s + version"""
    r = check_python()
    assert r.status == "ok"
    assert r.latency_ms == 0.0
    assert r.error is None
    assert 0 <= r.extra["uptime_s"] < 60
    assert "version" in r.extra


# ---------- check_dify ----------


def test_check_dify_ok():
    """Dify ping 成功, latency_ms > 0, error=None"""
    fake_response = MagicMock()
    fake_response.status_code = 200
    with (
        patch.dict("os.environ", {"DIFY_DATASET_API_KEY": "dataset-test-key"}),
        patch("src.health.checks._requests.get", return_value=fake_response),
    ):
        r = asyncio.run(check_dify())
    assert r.status == "ok"
    assert r.latency_ms is not None
    assert r.latency_ms is not None and r.latency_ms >= 0
    assert r.error is None


def test_check_dify_connection_error():
    """Dify ping 失败, status=error, error 含异常信息"""
    with (
        patch.dict("os.environ", {"DIFY_DATASET_API_KEY": "dataset-test-key"}),
        patch("src.health.checks._requests.get", side_effect=ConnectionError("timeout")),
    ):
        r = asyncio.run(check_dify())
    assert r.status == "error"
    assert r.latency_ms is None
    assert r.error is not None and "timeout" in r.error


def test_check_dify_http_error():
    """Dify 返 4xx/5xx → status=error, error 含 HTTP 状态码"""
    fake_response = MagicMock()
    fake_response.status_code = 500
    with (
        patch.dict("os.environ", {"DIFY_DATASET_API_KEY": "dataset-test-key"}),
        patch("src.health.checks._requests.get", return_value=fake_response),
    ):
        r = asyncio.run(check_dify())
    assert r.status == "error"
    assert r.error is not None and "500" in r.error


# ---------- check_neo4j ----------


def test_check_neo4j_ok():
    """Neo4j verify_connectivity 成功"""
    fake_store = MagicMock()
    fake_store.verify_connectivity = MagicMock(return_value=None)
    with patch("src.health.checks._get_neo4j_store", return_value=fake_store):
        r = asyncio.run(check_neo4j())
    assert r.status == "ok"
    assert r.latency_ms is not None and r.latency_ms >= 0
    assert r.error is None


def test_check_neo4j_driver_missing():
    """Neo4j driver 不可用 → status=error"""
    with patch("src.health.checks._get_neo4j_store", side_effect=ImportError("no driver")):
        r = asyncio.run(check_neo4j())
    assert r.status == "error"
    assert r.error is not None and ("no driver" in r.error or "driver" in r.error.lower())


# ---------- check_pgvector ----------


def test_check_pgvector_ok():
    """pgvector SELECT 1 成功"""
    fake_engine = MagicMock()
    fake_conn = MagicMock()
    fake_result = MagicMock()
    fake_result.scalar.return_value = 1
    fake_conn.execute.return_value = fake_result
    fake_ctx = MagicMock()
    fake_ctx.__enter__ = MagicMock(return_value=fake_conn)
    fake_ctx.__exit__ = MagicMock(return_value=False)
    fake_engine.connect.return_value = fake_ctx
    with patch("src.health.checks._get_pg_engine", return_value=fake_engine):
        r = asyncio.run(check_pgvector())
    assert r.status == "ok"
    assert r.latency_ms is not None and r.latency_ms >= 0
    assert r.error is None


def test_check_pgvector_connection_refused():
    """pgvector 连接失败 → status=error"""
    with patch("src.health.checks._get_pg_engine", side_effect=ConnectionRefusedError("refused")):
        r = asyncio.run(check_pgvector())
    assert r.status == "error"
    assert r.error is not None


# ---------- check_system ----------


def test_check_system_returns_cpu_mem_gpu():
    """psutil + pynvml 数值正确, gpu 列表非空 (mock PCI 空避免误扫 /sys)"""
    fake_mem = MagicMock()
    fake_mem.percent = 67.2
    fake_mem.used = 12000 * 1024 * 1024  # 12000 MB 原始字节数
    fake_mem.total = 18000 * 1024 * 1024
    with (
        patch("src.health.checks.psutil.cpu_percent", return_value=23.5),
        patch("src.health.checks.psutil.virtual_memory", return_value=fake_mem),
        patch(
            "src.health.checks._sample_gpu",
            return_value=(
                [
                    {
                        "name": "NVIDIA RTX 4090",
                        "util_pct": 45,
                        "mem_used_mb": 8000,
                        "mem_total_mb": 24000,
                    }
                ],
                None,
            ),
        ),
        patch("src.health.checks._sample_pci_gpus", return_value=[]),
    ):
        r = asyncio.run(check_system())
    assert r.status == "ok"
    assert r.extra["cpu_pct"] == 23.5
    assert r.extra["mem_pct"] == 67.2
    assert r.extra["mem_used_mb"] == 12000
    assert r.extra["mem_total_mb"] == 18000
    assert len(r.extra["gpu"]) == 1
    assert r.extra["gpu"][0]["name"] == "NVIDIA RTX 4090"


def test_check_system_no_gpu():
    """_sample_gpu 返 [] → gpu=[], status 仍 ok"""
    fake_mem = MagicMock()
    fake_mem.percent = 50.0
    fake_mem.used = 1024 * 1024
    fake_mem.total = 2048 * 1024
    with (
        patch("src.health.checks.psutil.cpu_percent", return_value=10.0),
        patch("src.health.checks.psutil.virtual_memory", return_value=fake_mem),
        patch("src.health.checks._sample_gpu", return_value=([], None)),
        patch("src.health.checks._sample_pci_gpus", return_value=[]),
    ):
        r = asyncio.run(check_system())
    assert r.status == "ok"
    assert r.extra["gpu"] == []
    assert r.extra["gpu_source"] == "empty"
    assert r.extra["gpu_error"] is None


# ---------- 2026-07-07 新增: NVML 错误暴露 + PCI 兜底 ----------


def test_check_system_nvml_error_exposed():
    """NVML 抛错 → extra.gpu_error 含 message, gpu_source='empty' (PCI 也空)"""
    fake_mem = MagicMock()
    fake_mem.percent = 30.0
    fake_mem.used = 1000 * 1024 * 1024
    fake_mem.total = 2000 * 1024 * 1024
    with (
        patch("src.health.checks.psutil.cpu_percent", return_value=15.0),
        patch("src.health.checks.psutil.virtual_memory", return_value=fake_mem),
        patch(
            "src.health.checks._sample_gpu",
            return_value=([], "NVMLError: Driver Not Loaded"),
        ),
        patch("src.health.checks._sample_pci_gpus", return_value=[]),
    ):
        r = asyncio.run(check_system())
    assert r.status == "ok"
    assert r.extra["gpu"] == []
    assert r.extra["gpu_error"] == "NVMLError: Driver Not Loaded"
    assert r.extra["gpu_source"] == "empty"


def test_check_system_pci_fallback_used():
    """NVML 空 + PCI 返非空 → 用 PCI 数据, source='pci'"""
    fake_mem = MagicMock()
    fake_mem.percent = 40.0
    fake_mem.used = 8000 * 1024 * 1024
    fake_mem.total = 16000 * 1024 * 1024
    pci_entries = [
        {
            "name": "NVIDIA [0x2c05]",
            "util_pct": 0,
            "mem_used_mb": 0,
            "mem_total_mb": 16384,
        }
    ]
    with (
        patch("src.health.checks.psutil.cpu_percent", return_value=20.0),
        patch("src.health.checks.psutil.virtual_memory", return_value=fake_mem),
        patch("src.health.checks._sample_gpu", return_value=([], "NVMLError: Driver Not Loaded")),
        patch("src.health.checks._sample_pci_gpus", return_value=pci_entries),
    ):
        r = asyncio.run(check_system())
    assert r.status == "ok"
    assert r.extra["gpu_source"] == "pci"
    assert len(r.extra["gpu"]) == 1
    assert r.extra["gpu"][0]["name"] == "NVIDIA [0x2c05]"
    assert r.extra["gpu"][0]["mem_total_mb"] == 16384
    # NVML 错误仍暴露, 让 admin 知道是驱动问题
    assert r.extra["gpu_error"] == "NVMLError: Driver Not Loaded"


def test_check_system_merges_nvml_and_pci_non_nvidia():
    """NVML 只能看 NVIDIA, PCI 兜底能看非 NVIDIA (AMD/Intel 集显).

    合并策略: NVML NVIDIA 数据优先, PCI 中非 NVIDIA 的条目追加进去.
    这样 NVML 工作但机器有 AMD 集显时, 两个都能看到.
    """
    fake_mem = MagicMock()
    fake_mem.percent = 50.0
    fake_mem.used = 4000 * 1024 * 1024
    fake_mem.total = 8000 * 1024 * 1024
    nvml_entries = [
        {
            "name": "NVIDIA GeForce RTX 5070 Ti",
            "util_pct": 75,
            "mem_used_mb": 12000,
            "mem_total_mb": 16303,
        }
    ]
    # PCI 列出 1 个 NVIDIA (跟 NVML 重, 应去重) + 1 个 AMD 集显 (应保留)
    pci_entries = [
        {"name": "NVIDIA [0x2c05]", "util_pct": 0, "mem_used_mb": 0, "mem_total_mb": 16384},
        {"name": "AMD [0x13c0]", "util_pct": 0, "mem_used_mb": 0, "mem_total_mb": 258},
    ]
    with (
        patch("src.health.checks.psutil.cpu_percent", return_value=25.0),
        patch("src.health.checks.psutil.virtual_memory", return_value=fake_mem),
        patch("src.health.checks._sample_gpu", return_value=(nvml_entries, None)),
        patch("src.health.checks._sample_pci_gpus", return_value=pci_entries),
    ):
        r = asyncio.run(check_system())
    assert r.status == "ok"
    # 合并结果: NVML 的 NVIDIA + PCI 的 AMD (NVIDIA 重名去重)
    assert r.extra["gpu_source"] == "nvml+pci"
    assert len(r.extra["gpu"]) == 2
    names = [g["name"] for g in r.extra["gpu"]]
    assert "NVIDIA GeForce RTX 5070 Ti" in names
    assert "AMD [0x13c0]" in names
    # NVML 的数据 (util/mem_used) 应保留, 不被 PCI 的 0 覆盖
    nvidia_gpu = next(g for g in r.extra["gpu"] if "NVIDIA" in g["name"])
    assert nvidia_gpu["util_pct"] == 75
    assert nvidia_gpu["mem_used_mb"] == 12000
    assert r.extra["gpu_error"] is None


def test_check_system_pci_only_no_nvml():
    """NVML 错 + PCI 含 NVIDIA + AMD → 全用 PCI, source='pci'"""
    fake_mem = MagicMock()
    fake_mem.percent = 50.0
    fake_mem.used = 4000 * 1024 * 1024
    fake_mem.total = 8000 * 1024 * 1024
    pci_entries = [
        {"name": "NVIDIA [0x2c05]", "util_pct": 0, "mem_used_mb": 0, "mem_total_mb": 16384},
        {"name": "AMD [0x13c0]", "util_pct": 0, "mem_used_mb": 0, "mem_total_mb": 258},
    ]
    with (
        patch("src.health.checks.psutil.cpu_percent", return_value=25.0),
        patch("src.health.checks.psutil.virtual_memory", return_value=fake_mem),
        patch("src.health.checks._sample_gpu", return_value=([], "NVMLError: Driver Not Loaded")),
        patch("src.health.checks._sample_pci_gpus", return_value=pci_entries),
    ):
        r = asyncio.run(check_system())
    assert r.status == "ok"
    assert r.extra["gpu_source"] == "pci"
    assert len(r.extra["gpu"]) == 2
    assert r.extra["gpu_error"] == "NVMLError: Driver Not Loaded"


def test_sample_pci_gpus_smoke(tmp_path):
    """伪造 sysfs 树: 1 个 VGA NVIDIA + 1 个 host bridge (应被过滤) + 1 个 zero-BAR 设备 (应被过滤).

    验证: 过滤非 display class / 过滤 mem_total_mb=0 / 解析 64-bit prefetchable BAR.
    """
    # 1) NVIDIA VGA: 64-bit prefetchable BAR = 0x1000000000 - 0x13ffffffff (16384 MiB)
    nvidia_dir = tmp_path / "0000:01:00.0"
    nvidia_dir.mkdir()
    (nvidia_dir / "vendor").write_text("0x10de")
    (nvidia_dir / "device").write_text("0x2c05")
    (nvidia_dir / "class").write_text("0x030000")  # VGA
    (nvidia_dir / "resource").write_text(
        "0x0000000000000000 0x000000000000ffff 0x0000000000040200\n"  # MMIO (flags & 0x04 = 0, 跳过)
        "0x0000000000000000 0x00000003ffffffff 0x000000000014220c\n"  # prefetchable mem (16384 MiB)
    )
    # 2) AMD host bridge: class 0x0600, 应被过滤
    amd_dir = tmp_path / "0000:00:00.0"
    amd_dir.mkdir()
    (amd_dir / "vendor").write_text("0x1022")
    (amd_dir / "device").write_text("0x1480")
    (amd_dir / "class").write_text("0x060000")  # Host bridge
    # 3) 集成显卡 AMD VGA 但 resource 不可读 → mem_total_mb=0 → 应被过滤
    igpu_dir = tmp_path / "0000:79:00.0"
    igpu_dir.mkdir()
    (igpu_dir / "vendor").write_text("0x1002")
    (igpu_dir / "device").write_text("0x13c0")
    (igpu_dir / "class").write_text("0x030000")
    # 没有 resource 文件 → BAR=0 → 过滤掉

    # monkeypatch sysfs base
    with patch.object(_gpu_module, "_PCI_SYSFS_BASE", str(tmp_path)):
        gpus = _gpu_module._sample_pci_gpus()

    assert len(gpus) == 1
    assert gpus[0]["name"] == "NVIDIA [0x2c05]"
    assert gpus[0]["util_pct"] == 0
    assert gpus[0]["mem_used_mb"] == 0
    assert gpus[0]["mem_total_mb"] == 16384
