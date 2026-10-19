---
name: project-scripts-syspath-injection
description: scripts/ 子目录下的脚本需要 sys.path 注入才能 import src.* (跟 main.py 不一样)
metadata: 
  node_type: memory
  type: project
  originSessionId: 2b43cdde-9008-4f4a-8f71-df2d2a112bb2
---

# scripts/ 子目录脚本的 sys.path 注入

**问题**: 仓库根的 `main.py` 写 `from src.product_decoders import X` 能跑, 但 `scripts/neo4j_import.py` 同样写法报 `ModuleNotFoundError: No module named 'src'`.

**根因**: Python 启动时把**脚本所在目录**加到 `sys.path`.
- `main.py` 在 `rag/`, → `rag/` 在 sys.path → `src/` 作为子目录可找到
- `scripts/neo4j_import.py` 在 `rag/scripts/`, → `scripts/` 在 sys.path → 找不到 `src/`

**对比 pytest**:
- pytest 用 `pyproject.toml` 的 `pythonpath = ["src", "."]`, 测试里 `import scripts.neo4j_import` 没问题 (隐藏了这个问题)
- 直到用户实际 `uv run python scripts/neo4j_import.py check` 才暴露

**修复** (在 `scripts/neo4j_import.py` 顶部):
```python
import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
```

**Why:** 跟 pytest 的 `pythonpath` 行为对齐, 让脚本能直接 `python scripts/X.py` 跑.

**How to apply**:
- 新加 `scripts/*.py` 时, 第一件事是加这个 sys.path 注入块
- 写完必须用 subprocess 跑一次 `python scripts/X.py --help` 验证 (不是只看 pytest 绿)
- 已经有这个块的: `scripts/neo4j_import.py`
- 不要把 `scripts/` 拆成更深的子目录 (会增加复杂度, 跟 main.py 越差越远)

**回归测试** (`tests/scripts/test_neo4j_import.py`):
```python
def test_script_runs_without_module_not_found_error(tmp_path):
    """脚本 subprocess 跑 --help, 验无 ModuleNotFoundError"""
    import subprocess, sys as _sys
    repo_root = Path(__file__).resolve().parent.parent.parent
    script_path = repo_root / "scripts" / "neo4j_import.py"
    result = subprocess.run([_sys.executable, str(script_path), "--help"], ...)
    assert result.returncode == 0
    assert "ModuleNotFoundError" not in result.stderr
```

**Related**: [[feedback-debug-distinguish-root-causes]] (这次 bug 第一次的猜测 "import 路径写错" 不对, 真正根因是 sys.path), [[feedback-no-mock-for-external-systems]] (pytest 通过 ≠ 脚本能跑, 必须真跑一次)
