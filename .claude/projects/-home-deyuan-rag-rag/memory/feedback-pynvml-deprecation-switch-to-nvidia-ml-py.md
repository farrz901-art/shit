---
name: feedback-pynvml-deprecation-switch-to-nvidia-ml-py
description: "pynvml PyPI 包是 deprecated shim, 装它会发 FutureWarning, 实际项目应直接装 nvidia-ml-py"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 298dc759-254d-43ee-a841-71ccb0b25682
---

`pynvml` PyPI 包是第三方 deprecation shim, 强制发 `FutureWarning` 提醒用户迁到 `nvidia-ml-py`。官方包是 `nvidia-ml-py` (NVIDIA 维护), 仍提供 `pynvml.py` 模块, import 路径不变。

**Why:** 2026-06-15 用户在 health check 启动日志看到 `FutureWarning: The pynvml package is deprecated`, 排查发现 shim 是第三方维护, 真正的 NVIDIA 官方包叫 `nvidia-ml-py`, 仍然提供 `pynvml.py` 模块, 代码侧零改动。

**How to apply:**
- 看到 pynvml FutureWarning 报错 → 改 `pyproject.toml` 依赖: `pynvml>=X` → `nvidia-ml-py>=X`, `import pynvml` 保持不变
- 验证: `uv run python -W error::FutureWarning -c "import pynvml"` 不抛 + `pynvml.__file__` 路径是 `nvidia_ml_py-*.dist-info` 同目录下的 `pynvml.py`
- 遇到类似 deprecation shim 模式 (PyPI 上有人 fork 老名字发警告) 同样处理: 找上游真实包名, 改 dep 声明, import 不动
- 本项目已修: `packages/service/pyproject.toml:29` `pynvml>=13.0.1` → `nvidia-ml-py>=13.0.0`, commit a914efe
