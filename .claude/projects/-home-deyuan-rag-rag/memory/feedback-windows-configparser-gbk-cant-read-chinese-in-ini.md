---
name: feedback-windows-configparser-gbk-cant-read-chinese-in-ini
description: "Windows Python configparser 读 .ini 用 gbk 默认编码, .ini 里的中文/非 ASCII 注释会让 alembic/ConfigParser 整体解析失败"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f3b59aa7-7450-417f-8f57-0c46614e5cfc
---

Python `configparser` 在 Windows 上读 `.ini` 默认用 `gbk` codec. 如果 `.ini` 文件里有中文/emoji/非 ASCII 字符, **整个文件解析会爆** `UnicodeDecodeError: 'gbk' codec can't decode byte 0xa8`.

**症状链** (2026-06-12 修 `packages/service/alembic.ini` 时栽过):
1. 改 `alembic.ini` 加中文注释解释 `%(here)s` 用意
2. 跑 `alembic current` 爆 `UnicodeDecodeError: 'gbk' codec can't decode byte 0xa8 in position 249`
3. `tests/rag/storage/test_migrations.py` 调 `alembic upgrade head` 子进程, 也跟着爆
4. 排查花了 5 分钟, 一度以为是 `script_location` 改坏了

**根因**: `configparser.RawConfigParser.read()` 在 Windows 上没指定 `encoding=` 参数时, 走 `locale.getpreferredencoding(False)`, Windows 上是 `gbk` (cp936). ini 文件哪怕你用 UTF-8 写的, gbk 解码照样爆.

**Why:** 跟 [feedback-windows-console-corrupts-non-ascii-when-writing-yaml](feedback-windows-console-corrupts-non-ascii-when-writing-yaml.md) 同根 — Windows 默认编码不是 UTF-8, 任何"配置文件含非 ASCII"都得显式处理.

**How to apply:**
- **写 .ini 文件别用中文注释**, 用英文. (`pyproject.toml` / `setup.cfg` 同理)
- 如果非要用中文: 用 `Write` 工具写并显式 `encoding="utf-8-sig"` (BOM 头让 configparser 认 UTF-8)
- 验证: 改完 .ini 跑一次实际读取方 (alembic / configparser / setuptools), 别光 `cat` 看着对就 commit
- grep 自查: `git diff -- '*.ini' | grep -P "[^\x00-\x7F]"` 找非 ASCII 字符
- 同类配置文件高危: `*.ini` / `*.cfg` / `setup.cfg` / `pyproject.toml` (tomli 读, Windows 上同样问题)
