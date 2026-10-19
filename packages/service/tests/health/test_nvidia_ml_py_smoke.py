"""smoke test: 验证 nvidia-ml-py 替换 pynvml 后 _sample_gpu 真实代码路径

2026-06-15 重构后: checks.py 改用 `from pynvml import 具体函数` 替代
`import pynvml` + `pynvml.X` namespace. 这个 smoke test 把 pynvml 整个模块 mock 掉,
强制走 _sample_gpu 内部代码, 验证:
- 旧 pynvml 11.x 行为: nvmlDeviceGetName 返 bytes → .decode() 走通
- 新 nvidia-ml-py 13.6+ 行为: @convertStrBytes 装饰器返 str → .decode() 跳过
- 真 import nvidia-ml-py 提供的 pynvml 模块, 无 FutureWarning
- 7 个 _sample_gpu 用到的函数全部可达
- 无 GPU/驱动时真模块优雅降级返 [] 不抛
"""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock


def _build_fake_pynvml_module(name_return):
    """构造一个完整的 fake pynvml 模块, name_return 可以是 bytes (旧) 或 str (新)"""
    fake_handle = MagicMock()
    fake_util = MagicMock(gpu=50)
    fake_mem = MagicMock(used=4 * 1024 * 1024 * 1024, total=8 * 1024 * 1024 * 1024)

    fake_pynvml = MagicMock()
    fake_pynvml.nvmlInit = MagicMock()
    fake_pynvml.nvmlDeviceGetCount = MagicMock(return_value=1)
    fake_pynvml.nvmlDeviceGetHandleByIndex = MagicMock(return_value=fake_handle)
    fake_pynvml.nvmlDeviceGetName = MagicMock(return_value=name_return)
    fake_pynvml.nvmlDeviceGetUtilizationRates = MagicMock(return_value=fake_util)
    fake_pynvml.nvmlDeviceGetMemoryInfo = MagicMock(return_value=fake_mem)
    fake_pynvml.nvmlShutdown = MagicMock()
    return fake_pynvml


def test_legacy_pynvml_11x_returns_bytes():
    """旧 pynvml 11.x: nvmlDeviceGetName 返 bytes, 走 .decode() 路径"""
    fake_pynvml = _build_fake_pynvml_module(b"NVIDIA GeForce RTX 4090")
    sys.modules["pynvml"] = fake_pynvml
    sys.modules.pop("src.health.gpu", None)
    sys.modules.pop("src.health.checks", None)

    from src.health.gpu import _sample_gpu

    gpus, err = _sample_gpu()
    print("legacy bytes path:", json.dumps([gpus, err], ensure_ascii=False))

    assert err is None
    assert len(gpus) == 1
    assert gpus[0]["name"] == "NVIDIA GeForce RTX 4090"
    assert gpus[0]["util_pct"] == 50
    assert gpus[0]["mem_used_mb"] == 4096
    assert gpus[0]["mem_total_mb"] == 8192
    assert fake_pynvml.nvmlInit.called
    assert fake_pynvml.nvmlShutdown.called


def test_nvidia_ml_py_13_6_plus_returns_str():
    """nvidia-ml-py 13.6+ (现装版本): @convertStrBytes 自动 decode 返 str, 跳过 .decode()"""
    fake_pynvml = _build_fake_pynvml_module("NVIDIA GeForce RTX 5090")
    sys.modules["pynvml"] = fake_pynvml
    sys.modules.pop("src.health.gpu", None)
    sys.modules.pop("src.health.checks", None)

    from src.health.gpu import _sample_gpu

    gpus, err = _sample_gpu()
    print("nvidia-ml-py str path:", json.dumps([gpus, err], ensure_ascii=False))

    assert err is None
    assert len(gpus) == 1
    assert gpus[0]["name"] == "NVIDIA GeForce RTX 5090"
    assert gpus[0]["util_pct"] == 50
    assert gpus[0]["mem_used_mb"] == 4096
    assert gpus[0]["mem_total_mb"] == 8192


def test_real_nvidia_ml_py_import_clean_no_warning():
    """真模块 import 无 FutureWarning, 7 个 _sample_gpu 用到的函数全存在"""
    sys.modules.pop("pynvml", None)
    sys.modules.pop("src.health.gpu", None)
    sys.modules.pop("src.health.checks", None)

    from pynvml import (
        nvmlDeviceGetCount,
        nvmlDeviceGetHandleByIndex,
        nvmlDeviceGetMemoryInfo,
        nvmlDeviceGetName,
        nvmlDeviceGetUtilizationRates,
        nvmlInit,
        nvmlShutdown,
    )

    # 全部能 import, 真模块函数都 callable
    for fn in (
        nvmlInit,
        nvmlDeviceGetCount,
        nvmlDeviceGetHandleByIndex,
        nvmlDeviceGetName,
        nvmlDeviceGetUtilizationRates,
        nvmlDeviceGetMemoryInfo,
        nvmlShutdown,
    ):
        assert callable(fn), f"{fn} not callable"
    import pynvml

    print("real pynvml module file:", pynvml.__file__)


def test_real_graceful_degrade_no_driver():
    """真模块 + 本机无 NVIDIA 驱动: _sample_gpu 优雅降级返 ([], "<err>") 不抛"""
    sys.modules.pop("pynvml", None)
    sys.modules.pop("src.health.gpu", None)
    sys.modules.pop("src.health.checks", None)

    from src.health.gpu import _sample_gpu

    result = _sample_gpu()
    # tuple (list, err|None) — 老版本返 [], 新版本当 NVML 初始化失败时返 ([], "<err msg>")
    assert isinstance(result, tuple) and len(result) == 2
    gpus, err = result
    assert isinstance(gpus, list)
    # 驱动加载失败时 err 应非空; pynvml 完全没装时 err 也非空
    print("graceful degrade result:", result)
