---
name: project-nvidia-ml-py-import-pynvml
description: "nvidia-ml-py 13.6+ PyPI 包主动 ship pynvml.py 作为 module 文件, import 路径仍是 pynvml"
metadata: 
  node_type: memory
  type: project
  originSessionId: 298dc759-254d-43ee-a841-71ccb0b25682
---

nvidia-ml-py 13.610.43 (官方 NVML Python 绑定) **主动 ship** 一个叫 `pynvml.py` 的 module 文件. PyPI 包名是 `nvidia-ml-py`, 但 import 路径是 `import pynvml` (跟旧的 deprecated `pynvml` PyPI shim 一样).

**Why:** 用户 2026-06-15 反复怀疑 "是不是只删 pyproject 没真卸 pynvml", 实际上 pynvml shim 已卸 (`pynvml-13.0.1.dist-info/` 已不存在), 现在的 `pynvml.py` 是 nvidia-ml-py 提供的. 记下来避免再被怀疑.

**How to apply:**
- 验证 nvidia-ml-py 装上后: `ls .venv/Lib/site-packages/ | grep pynvml` 应该只看到 `pynvml.py` (没 `pynvml-*.dist-info`); `ls .venv/Lib/site-packages/ | grep nvidia_ml_py` 应该看到 `nvidia_ml_py-13.610.43.dist-info`
- 确认 ownership: `cat .venv/Lib/site-packages/nvidia_ml_py-13.610.43.dist-info/RECORD | grep pynvml` 应该有 `pynvml.py,sha256=...,<size>` 一行
- 改 dep 后必须 `uv lock` + `uv sync`, 看输出有 "Removed pynvml" + "Uninstalled 1 package - pynvml==13.0.1"
- 验证 lock: `grep '^name = "pynvml"' uv.lock` 应该 0 行, `grep '^name = "nvidia-ml-py"' uv.lock` 应该 1 行
- import 用法变化: 旧 pynvml 11.x `nvmlDeviceGetName` 返 bytes; 新 nvidia-ml-py 13.6+ 套了 `@convertStrBytes` 装饰器, 返 str — 调用方需 `isinstance(_name, bytes)` 守卫
- 项目已用重构方案: `from pynvml import nvmlInit, nvmlDeviceGetCount, ...` 具体函数 import 替代 `import pynvml` namespace
