---
name: project-windows-console-utf8-stdout
description: Windows console 输出 UTF-8 中文乱码的修法 (stdout.reconfigure + SetConsoleOutputCP 65001)
metadata: 
  node_type: memory
  type: project
  originSessionId: 2b43cdde-9008-4f4a-8f71-df2d2a112bb2
---

# Windows console 输出 UTF-8 中文

**症状**: 脚本在 Windows 输出含中文 (中文 print, tabulate 表格, 中文错误信息), 终端显示成 mojibake (例如 "实体清单" → "��ʵ���嵥").

**根因**: Windows console 默认 code page 是 437 (US) 或 936 (GBK), 不是 UTF-8. Python 3 stdout 走 console 的 code page, UTF-8 字节流被错误解码.

**修复** (`scripts/neo4j_import.py` 顶部):
```python
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Python 3.7+
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)  # 强制 console 显示 UTF-8
    except Exception:
        pass
```

两层都做: stdout 写 UTF-8 字节 + console 接收 UTF-8 显示.

**Why**: 跟现有 write-side memory [[feedback-windows-console-corrupts-non-ascii-when-writing-yaml]] 对应, 那个是**写文件** (用 Python 文件 I/O 绕过), 这个是**写 stdout** (用 reconfigure + SetConsoleOutputCP 强制 UTF-8).

**How to apply**:
- 新加 CLI 脚本 (在 Windows 环境会跑): 第一件事就加这块到 sys.path 注入之后
- tabulate 表格 / 中文 log / 中文 print: 都受这个 bug 影响
- 写测试时: subprocess 跑脚本要传 `encoding="utf-8"` (默认是 gbk, 跟脚本 stdout 冲突)
- 真跑 `uv run python scripts/X.py` 前先看输出有没有 mojibake, 有就修

**Related**: [[feedback-windows-console-corrupts-non-ascii-when-writing-yaml]] (写文件), [[feedback-tdd-test-real-behavior-not-just-no-crash]] (用户两次纠错, 这次也算"没真测"暴露的)
