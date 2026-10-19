# ARCH-004: 迁移 src/ingest/config.py + config_legacy.py 到 settings.py 计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `src/ingest/config.py` 和 `src/config_legacy.py` 两个重复的"旧 config.toml 加载器"全部迁到 `src/config/settings.py`, 业务代码全走 `settings.paths / settings.cad_config / settings.archive_config`, 然后删掉 2 个旧模块 + 2 个旧 test + 旧 re-export.

**Architecture:**
- `settings.py` 加 3 个嵌套 dataclass (`Paths` / `CadConfig` / `ArchiveConfig`) + 6 个新 env 字段 (`INGEST_INPUT_DIR` / `INGEST_OUTPUT_DIR` / `ARCHIVE_MAX_DEPTH` / `ARCHIVE_MAX_TOTAL_SIZE` / `ARCHIVE_MAX_FILE_COUNT` / `ODA_WIN_PATH` / `ODA_UNIX_PATH`)
- `src/ingest/pipeline.py` 5 处 `get_paths() / get_archive_config()` 改 `settings.paths / settings.archive_config`
- `src/ingest/converters/cad.py` 删 `_read_oda_path_from_env_or_config` 的 config.toml fallback (只留 env 路径, 跟 `defaults.py` 已有 `DEFAULT_ODA_*_PATH` 对齐)
- `src/product_decoders/output_api.py:30` 改 `settings.paths.output_dir`
- 删 `src/config_legacy.py` (已删, 跳过) + `src/ingest/config.py` + `tests/test_config.py` (已删) + `tests/ingest/test_config.py` + `tests/ingest/test_cad_oda.py` (4 个 test 改 env 路径)
- 清 re-export (`src/__init__.py:90, 205-207` + `src/config/__init__.py:8-15`)

**Tech Stack:** Python 3.14, dataclass, os.getenv, pytest + monkeypatch

---

## 任务边界

| 现有 | 状态 |
|---|---|
| `src/config_legacy.py` | **已删 (working tree `D`)** |
| `tests/test_config.py` | **已删 (working tree `D`)** |
| `src/config/__init__.py` | user 已恢复成 re-export, 需清理 |
| `src/__init__.py:90, 205-207` | 还 re-export 旧 API, 需清理 |
| `src/ingest/config.py` (131 行) | 业务在用, 不能直接删 — 必须先迁 |
| `src/ingest/pipeline.py` (5+ 处) | 业务在用, 必须迁 |
| `src/ingest/converters/cad.py` | 业务在用, 改 env-only |
| `src/product_decoders/output_api.py:30` | 业务在用, 改 settings |
| `tests/ingest/test_config.py` (120 行) | 测旧 API, 删 |
| `tests/ingest/test_cad_oda.py` (4 个 test) | mock `CONFIG_FILE`, 改 env |
| `tests/ingest/test_cad_converter.py:202` | 1 处 mock `CONFIG_FILE`, 改 env |
| `tests/ingest/test_web_apis.py` | mock `get_paths`, 改 mock `settings.paths` |

---

## Task 1: 在 settings.py 加 Paths / CadConfig / ArchiveConfig + 7 个 env 字段

**Files:**
- Modify: `packages/service/src/config/settings.py:26-33` (在 `class Settings:` 之前加 3 个 dataclass)
- Modify: `packages/service/src/config/settings.py:37-44` (在 env 段之后加 3 个 section: paths / cad / archive)

- [ ] **Step 1: 在 `class Settings:` 之前加 3 个 dataclass**

在 `src/config/settings.py:24` (空行, `from src.common import defaults` 之后, `@dataclass class Settings:` 之前) 加:

```python
# ═══════════════════════════════════
# Ingest (Paths / CadConfig / ArchiveConfig) — ARCH-004 迁移
# 旧 src/ingest/config.py + src/config_legacy.py 走 config.toml
# 迁到 env, 业务代码全走 settings.paths / settings.cad_config / settings.archive_config
# ═══════════════════════════════════
from pathlib import Path  # noqa: E402  # 在 dataclass 之后 import 不影响运行, 但 pyright 喜欢顶部 import. 这里跟在第一个 import 区下面.


@dataclass(frozen=True)
class Paths:
    """路径配置 (ARCH-004: 原 [paths] 段迁到 env)"""

    input_dir: Path
    output_dir: Path


@dataclass(frozen=True)
class CadConfig:
    """CAD 相关配置 (ARCH-004: 原 [cad] 段 + env ODA_WIN_PATH / ODA_UNIX_PATH)

    oda_win_path / oda_unix_path 是用户显式配置的 ODA File Converter 路径.
    空 = 走 ezdxf 系统默认.
    """

    oda_win_path: str
    oda_unix_path: str


@dataclass(frozen=True)
class ArchiveConfig:
    """压缩包解压配置 (ARCH-004: 原 [archive] 段迁到 env)

    max_depth: 嵌套解压深度 (1 = 不递归)
    max_total_size: 解压总大小上限 (字节, 防 zip bomb)
    max_file_count: 解压文件总数上限 (防 zip bomb)
    """

    max_depth: int
    max_total_size: int
    max_file_count: int
```

⚠️ `Path` 必须 `from pathlib import Path` 顶部 import. 把 `from pathlib import Path` 加到文件顶部 `import` 区 (在 `from dataclasses import dataclass, field` 后面).

- [ ] **Step 2: 在 `Settings` 加 3 个嵌套 dataclass 字段**

在 `class Settings:` 内部, "CORS" section 之后 (即 `cors_allow_origins` 字段后, `redis_host` 字段前) 加:

```python
    # ═══════════════════════════════════
    # Ingest (ARCH-004 迁移)
    # ═══════════════════════════════════
    paths: Paths = field(
        default_factory=lambda: Paths(
            input_dir=Path(os.getenv("INGEST_INPUT_DIR", "./ingest_inputs")),
            output_dir=Path(os.getenv("INGEST_OUTPUT_DIR", "./ingest_outputs")),
        ),
    )
    cad_config: CadConfig = field(
        default_factory=lambda: CadConfig(
            oda_win_path=os.getenv("ODA_WIN_PATH", defaults.DEFAULT_ODA_WIN_PATH).strip(),
            oda_unix_path=os.getenv("ODA_UNIX_PATH", defaults.DEFAULT_ODA_UNIX_PATH).strip(),
        ),
    )
    archive_config: ArchiveConfig = field(
        default_factory=lambda: ArchiveConfig(
            max_depth=int(os.getenv("ARCHIVE_MAX_DEPTH", "1")),
            max_total_size=int(os.getenv("ARCHIVE_MAX_TOTAL_SIZE", str(1 << 30))),
            max_file_count=int(os.getenv("ARCHIVE_MAX_FILE_COUNT", "10000")),
        ),
    )
```

⚠️ 这 3 个字段**必须在 `redis_host` 之前** (即 env section 之内), 因为 dataclass 字段有顺序, 后面 `__init__` 顺序也如此 — 测试用 `Settings(...)` 构造时位置敏感.

- [ ] **Step 3: 验证 import + 字段访问**

跑: `cd packages/service && uv run python -c "from src.config.settings import settings, Paths, CadConfig, ArchiveConfig; print(type(settings.paths).__name__, type(settings.cad_config).__name__, type(settings.archive_config).__name__); print(settings.paths.input_dir, settings.archive_config.max_depth)"`

期望输出: `Paths CadConfig ArchiveConfig` 跟着 `Path(...)` 跟 `1`.

- [ ] **Step 4: Commit**

```bash
git add packages/service/src/config/settings.py
git commit -m "feat(config): ARCH-004 — settings.py 加 Paths/CadConfig/ArchiveConfig + 7 env 字段"
```

---

## Task 2: 改 `src/ingest/pipeline.py` 5 处 `get_paths() / get_archive_config()` → `settings.paths / settings.archive_config`

**Files:**
- Modify: `packages/service/src/ingest/pipeline.py:18` (顶部 import 改)
- Modify: `packages/service/src/ingest/pipeline.py:108, 140, 143, 256, 358, 421` (5 个函数体改)
- Modify: `packages/service/src/ingest/pipeline.py:254, 419` (2 个函数内 lazy import 删)

- [ ] **Step 1: 顶部 import 改**

`src/ingest/pipeline.py:18`:

```python
# 旧:
from .config import get_archive_config, get_paths

# 新:
from src.config.settings import settings
```

- [ ] **Step 2: 改 5 个函数体**

每个 `get_paths()` → `settings.paths`, 每个 `get_archive_config()` → `settings.archive_config`:

| 位置 | 旧 | 新 |
|---|---|---|
| `:108` | `str(get_paths().output_dir)` | `str(settings.paths.output_dir)` |
| `:140-143` | `paths = get_paths()` + `archive_cfg = get_archive_config()` | `paths = settings.paths` + `archive_cfg = settings.archive_config` |
| `:254` (lazy import) | `from .config import get_paths` | (删, 顶部 import 已有) |
| `:256` | `paths = get_paths()` | `paths = settings.paths` |
| `:358` | `paths = get_paths()` | `paths = settings.paths` |
| `:419` (lazy import) | `from .config import get_paths` | (删) |
| `:421` | `paths = get_paths()` | `paths = settings.paths` |

- [ ] **Step 3: 跑 import 冒烟**

```bash
cd packages/service && uv run python -c "from src.ingest.pipeline import process_files, process_documents, process_cad_files, process_passthrough; print('imports OK')"
```

期望: `imports OK` (无 ImportError / ModuleNotFoundError).

- [ ] **Step 4: Commit**

```bash
git add packages/service/src/ingest/pipeline.py
git commit -m "refactor(ingest): ARCH-004 — pipeline.py 5 处 get_paths/get_archive_config 改 settings.paths/archive_config"
```

---

## Task 3: 改 `src/ingest/converters/cad.py` `_read_oda_path_from_env_or_config` 删 config.toml fallback

**Files:**
- Modify: `packages/service/src/ingest/converters/cad.py:50-65` (`_read_oda_path_from_env_or_config` 函数体简化)

- [ ] **Step 1: 改 `_read_oda_path_from_env_or_config`**

旧:
```python
def _read_oda_path_from_env_or_config(key_env: str, key_config: str) -> str:
    """从 env 读 ODA 路径, env 没设则退到 config.toml

    优先级: env (ODA_WIN_PATH) > config ([cad].oda_win_path) > defaults ("")
    空字符串 = 让 ezdxf 走系统默认路径
    """
    # env 没设时, 兜底值从 defaults 拿 (避免 os.getenv(..., "") 这种字面量)
    fallback = defaults.DEFAULT_ODA_WIN_PATH if key_env == "ODA_WIN_PATH" else defaults.DEFAULT_ODA_UNIX_PATH
    env_val = os.getenv(key_env, fallback).strip()
    if env_val:
        return env_val
    # env 缺就退到 config.toml
    from ..config import get_cad_config

    cad_cfg = get_cad_config()
    return str(getattr(cad_cfg, key_config)).strip()
```

新:
```python
def _read_oda_path_from_env_or_config(key_env: str, key_config: str) -> str:
    """从 env 读 ODA 路径 (ARCH-004: 不再退到 config.toml)

    优先级: env (ODA_WIN_PATH) > defaults ("")
    空字符串 = 让 ezdxf 走系统默认路径

    key_config 参数保留是 API 兼容 (测试用), 业务走 settings.cad_config.
    """
    # env 没设时, 兜底值从 defaults 拿 (避免 os.getenv(..., "") 这种字面量)
    fallback = defaults.DEFAULT_ODA_WIN_PATH if key_env == "ODA_WIN_PATH" else defaults.DEFAULT_ODA_UNIX_PATH
    return os.getenv(key_env, fallback).strip()
```

⚠️ 业务代码 8 行 → 5 行. 删了 `from ..config import get_cad_config` lazy import.

- [ ] **Step 2: 跑 import 冒烟**

```bash
cd packages/service && uv run python -c "from src.ingest.converters.cad import _read_oda_path_from_env_or_config, read_cad_with_oda; print('imports OK')"
```

- [ ] **Step 3: Commit**

```bash
git add packages/service/src/ingest/converters/cad.py
git commit -m "refactor(ingest): ARCH-004 — cad.py 删 config.toml fallback, ODA 路径纯 env"
```

---

## Task 4: 改 `src/product_decoders/output_api.py:30` `_output_dir` 用 `settings.paths.output_dir`

**Files:**
- Modify: `packages/service/src/product_decoders/output_api.py:25-30`

- [ ] **Step 1: 改 `_output_dir`**

旧:
```python
def _output_dir():
    """延迟查 output_dir, 方便测试 monkeypatch"""
    # 跟其他业务代码一致, 延迟 import 防循环
    from src.ingest import config as _config

    return _config.get_paths().output_dir
```

新:
```python
def _output_dir():
    """读 output_dir (ARCH-004: 改走 settings.paths.output_dir)"""
    return settings.paths.output_dir
```

⚠️ 顶部加 `from src.config.settings import settings` (在 `from src.storage.object_store import get_object_store` 后面).

- [ ] **Step 2: 跑 import 冒烟**

```bash
cd packages/service && uv run python -c "from src.product_decoders.output_api import _output_dir, list_files, read_file; print(_output_dir())"
```

- [ ] **Step 3: Commit**

```bash
git add packages/service/src/product_decoders/output_api.py
git commit -m "refactor(api): ARCH-004 — output_api 改 settings.paths.output_dir"
```

---

## Task 5: 改 4 个 ingest test 文件 (删 mock CONFIG_FILE, 改 mock env / settings)

**Files:**
- Modify: `packages/service/tests/ingest/test_cad_oda.py` (4 个 test 改 env-only)
- Modify: `packages/service/tests/ingest/test_cad_converter.py:202` (1 处改 env-only)
- Modify: `packages/service/tests/ingest/test_web_apis.py:19` (mock `get_paths` 改 mock `settings.paths`)
- Delete: `packages/service/tests/ingest/test_config.py` (整个文件测旧 API, 删)

- [ ] **Step 1: 改 `tests/ingest/test_cad_oda.py` 4 个 test 删 `fake_config` 写盘 + `monkeypatch.setattr(cfg_mod, "CONFIG_FILE", ...)`**

`tests/ingest/test_cad_oda.py` 是 ARCH-004 改造最多的文件. 4 个 test:
- `test_env_wins_over_config` (line 27): 旧 — 写 fake_config + monkeypatch CONFIG_FILE + 设 env 验证 env 赢. 新 — 直接设 env, 验证 env 赢 (config.toml 路径删了).
- `test_falls_back_to_config_when_env_unset` (line 59): 旧 — 写 fake_config + monkeypatch CONFIG_FILE + delenv + 验证 config 兜底. **新 — 改名为 `test_falls_back_to_default_when_env_unset`, delenv + 验证 defaults 空串** (因为 config.toml 路径删了).
- `test_falls_back_to_empty_when_neither_set` (line 82): 旧 — 写 fake_config + monkeypatch + delenv + 验证 "". 新 — delenv + 验证 "" (config 步骤删).
- `test_strips_whitespace` (line 95): 旧 — 只设 env. 不动.

完整新文件 `tests/ingest/test_cad_oda.py`:

```python
"""cad_oda DWG 读取包装测试 (ARCH-004 改造: config.toml 路径删了, 全 env)"""

import pytest
from ezdxf.addons import odafc

from src.ingest.converters.cad import (
    OdaNotInstalledError,
    _read_oda_path_from_env_or_config,
    read_cad_with_oda,
)


def test_missing_dwg_file_raises_filenotfound(tmp_path):
    """DWG 文件本身不存在时，read_cad_with_oda 必须抛 FileNotFoundError"""
    nonexistent = tmp_path / "nonexistent.dwg"
    with pytest.raises(FileNotFoundError):
        read_cad_with_oda(str(nonexistent))


class TestOdaPathPriority:
    """_read_oda_path_from_env_or_config 优先级: env > defaults ("")"""

    def test_env_wins_over_default(self, monkeypatch):
        """env 配了 → 用 env, 不走 defaults 空串"""
        monkeypatch.setenv("ODA_WIN_PATH", "D:/from-env")
        result = _read_oda_path_from_env_or_config("ODA_WIN_PATH", "oda_win_path")
        assert result == "D:/from-env"

        monkeypatch.setenv("ODA_UNIX_PATH", "/from-env")
        result = _read_oda_path_from_env_or_config("ODA_UNIX_PATH", "oda_unix_path")
        assert result == "/from-env"

    def test_falls_back_to_default_when_env_unset(self, monkeypatch):
        """env 没设 → 走 defaults 空串 (ARCH-004: 不再退到 config.toml)"""
        monkeypatch.delenv("ODA_WIN_PATH", raising=False)
        result = _read_oda_path_from_env_or_config("ODA_WIN_PATH", "oda_win_path")
        assert result == ""

    def test_strips_whitespace(self, monkeypatch):
        """env 值带前后空格要去掉"""
        monkeypatch.setenv("ODA_WIN_PATH", "  D:/with-spaces  ")
        result = _read_oda_path_from_env_or_config("ODA_WIN_PATH", "oda_win_path")
        assert result == "D:/with-spaces"


@pytest.mark.skipif(
    odafc.is_installed(),
    reason="本机已装 ODA，跳过'未装 ODA 时友好错误'场景的测试",
)
class TestReadCadWithOda:
    """read_cad_with_oda 行为测试 (不依赖真实 ODA)"""

    def test_dwg_raises_friendly_error_when_oda_missing(self, tmp_path):
        """未装 ODA 时, read_cad_with_oda 必须抛 OdaNotInstalledError 而非 ezdxf 原生异常"""
        fake_dwg = tmp_path / "fake.dwg"
        fake_dwg.write_bytes(b"AC1032\x00" * 10)

        with pytest.raises(OdaNotInstalledError) as exc_info:
            read_cad_with_oda(str(fake_dwg))

        msg = str(exc_info.value)
        assert "ODA" in msg
        assert "opendesign.com" in msg or "下载" in msg
        assert str(fake_dwg) in msg
```

- [ ] **Step 2: 改 `tests/ingest/test_cad_converter.py:202` 1 处**

`tests/ingest/test_cad_converter.py:189-202` (`TestOdaPathConfigErrorPropagation.test_returns_empty_when_cad_segment_missing`):

旧:
```python
        from src.ingest import config as cfg_module
        from src.ingest.converters.cad import _read_oda_path_from_env_or_config

        monkeypatch.delenv("ODA_WIN_PATH", raising=False)
        monkeypatch.delenv("ODA_UNIX_PATH", raising=False)

        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(
            '[paths]\ninput_dir = "a"\noutput_dir = "b"\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(cfg_module, "CONFIG_FILE", cfg_file)
```

新:
```python
        from src.ingest.converters.cad import _read_oda_path_from_env_or_config

        monkeypatch.delenv("ODA_WIN_PATH", raising=False)
        monkeypatch.delenv("ODA_UNIX_PATH", raising=False)
```

(整个 test 重命名为 `test_returns_empty_when_env_unset`, 但保留 test 名也 OK — 旧 test 名 `test_returns_empty_when_cad_segment_missing` 改成 `test_returns_empty_when_env_unset` 更准确).

- [ ] **Step 3: 改 `tests/ingest/test_web_apis.py:19` mock `get_paths` 改 mock `settings.paths`**

`tests/ingest/test_web_apis.py`:

旧 (line 18-19):
```python
    fake_paths = Paths(input_dir=tmp_path, output_dir=tmp_path)
    monkeypatch.setattr("src.ingest.config.get_paths", lambda: fake_paths)
```

新:
```python
    from src.config.settings import settings as _settings
    monkeypatch.setattr(_settings, "paths", Paths(input_dir=tmp_path, output_dir=tmp_path))
```

(其他 6 处 `from src.ingest.config import get_paths` 调用保留, monkeypatch 改了后这些调用会走 `settings.paths` ... **等等**, 业务代码 `output_api.py:30` 已经改 `settings.paths.output_dir` 了, 那 `from src.ingest.config import get_paths` 在 test 里就拿不到东西.

需要把 6 处 `from src.ingest.config import get_paths` + `get_paths().output_dir` 改成:
```python
    from src.config.settings import settings
    out = settings.paths.output_dir
```

**或者更简单**: 在 test 文件顶部加 `from src.config.settings import settings`, 然后 6 处 `get_paths().output_dir` 改成 `settings.paths.output_dir`.

`test_web_apis.py` 完整改造:

```python
"""Web 后端 API 契约测试 (2026-06-05 frontend-monorepo) (ARCH-004: 改 mock settings.paths)"""

import pytest
from fastapi.testclient import TestClient

from src.config.settings import Paths, settings
from src.core.app_factory import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """把 output_dir 临时改成 tmp_path, 创建干净 app"""
    monkeypatch.setattr(settings, "paths", Paths(input_dir=tmp_path, output_dir=tmp_path))
    return TestClient(create_app())


class TestListFiles:
    """GET /api/output/files"""

    def test_list_files_returns_empty_when_dir_empty(self, client):
        r = client.get("/api/output/files")
        assert r.status_code == 200
        assert r.json() == {"files": []}

    def test_list_files_returns_md_and_json_only(self, client):
        out = settings.paths.output_dir
        (out / "doc1.md").write_text("# A", encoding="utf-8")
        (out / "doc2.json").write_text("{}", encoding="utf-8")
        (out / "skip.pdf").write_bytes(b"%PDF")
        (out / "skip.txt").write_text("hi", encoding="utf-8")
        (out / ".hidden").write_text("hidden", encoding="utf-8")

        r = client.get("/api/output/files")
        assert r.status_code == 200
        names = sorted(f["name"] for f in r.json()["files"])
        assert "doc1.md" in names
        assert "doc2.json" in names
        assert "skip.pdf" not in names
        assert "skip.txt" not in names
        assert ".hidden" not in names

    def test_list_file_includes_size_and_mtime(self, client):
        out = settings.paths.output_dir
        (out / "x.md").write_text("hello", encoding="utf-8")
        r = client.get("/api/output/files")
        assert r.status_code == 200
        files = r.json()["files"]
        assert len(files) == 1
        f = files[0]
        assert f["name"] == "x.md"
        assert f["size"] == 5
        assert isinstance(f["mtime"], (int, float))
        assert f["mtime"] > 0


class TestReadFile:
    """GET /api/output/files/{name}"""

    def test_read_md_returns_content(self, client):
        out = settings.paths.output_dir
        (out / "doc.md").write_text("# Title\n\nbody", encoding="utf-8")
        r = client.get("/api/output/files/doc.md")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "doc.md"
        assert body["content"] == "# Title\n\nbody"
        assert body["mime"] == "text/markdown"

    def test_read_json_returns_content(self, client):
        out = settings.paths.output_dir
        (out / "data.json").write_text('{"k": 1}', encoding="utf-8")
        r = client.get("/api/output/files/data.json")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "data.json"
        assert body["content"] == '{"k": 1}'
        assert body["mime"] == "application/json"

    def test_read_missing_file_returns_404(self, client):
        r = client.get("/api/output/files/nope.md")
        assert r.status_code == 404
        assert "不存在" in r.json()["detail"]

    def test_path_traversal_returns_400(self, client):
        r = client.get("/api/output/files/bad%20name.md")
        assert r.status_code == 400
        assert "非法" in r.json()["detail"]

    def test_invalid_chars_in_name_returns_400(self, client):
        r = client.get("/api/output/files/bad~name.md")
        assert r.status_code == 400
        assert "非法" in r.json()["detail"]

    def test_oversized_file_returns_413(self, client):
        out = settings.paths.output_dir
        (out / "big.md").write_bytes(b"x" * (11 * 1024 * 1024))
        r = client.get("/api/output/files/big.md")
        assert r.status_code == 413
        assert "10 MB" in r.json()["detail"] or "太大" in r.json()["detail"]
```

- [ ] **Step 4: 删 `tests/ingest/test_config.py`**

```bash
git rm packages/service/tests/ingest/test_config.py
```

- [ ] **Step 5: 跑 3 个 test 文件验证**

```bash
cd packages/service && uv run pytest tests/ingest/test_cad_oda.py tests/ingest/test_cad_converter.py tests/ingest/test_web_apis.py -v
```

期望: 所有 test 通过. **特别注意**: 之前这些 test 测的是 `config.toml` 路径, 跑过表示新 settings 路径能覆盖原行为.

- [ ] **Step 6: Commit**

```bash
git add packages/service/tests/ingest/test_cad_oda.py packages/service/tests/ingest/test_cad_converter.py packages/service/tests/ingest/test_web_apis.py packages/service/tests/ingest/test_config.py
git commit -m "test(ingest): ARCH-004 — 3 个 test 改 mock settings/env, 删 test_config.py"
```

---

## Task 6: 清 re-export (src/__init__.py + src/config/__init__.py) + 删 src/ingest/config.py

**Files:**
- Modify: `packages/service/src/__init__.py:90` (删 `from .config import get_archive_config, get_cad_config, get_paths`)
- Modify: `packages/service/src/__init__.py:205-207` (删 `__all__` 里的 3 个)
- Modify: `packages/service/src/config/__init__.py:1-15` (删 re-export, 只留 `from src.config.settings import settings`)
- Delete: `packages/service/src/ingest/config.py` (131 行)

- [ ] **Step 1: 清 `src/__init__.py:90`**

旧:
```python
# Config
from .config import get_archive_config, get_cad_config, get_paths
```

新: **整段删**. 业务代码不走 `src.get_paths` 这条路.

- [ ] **Step 2: 清 `src/__init__.py:205-207`**

旧:
```python
    # config
    "get_paths",
    "get_cad_config",
    "get_archive_config",
```

新: 整段 `# config` section 删 (连同 3 个 entry).

- [ ] **Step 3: 改 `src/config/__init__.py`**

新内容 (整个文件替换):

```python
"""config 包 — 配置集中管理

包含:
- settings.py: env 变量集中管理 (ARCH-003 + ARCH-004)
  - 普通字段: env > settings > defaults 三级 fallback
  - 嵌套 dataclass: paths (input_dir / output_dir), cad_config (ODA 路径), archive_config (解压限制)
  - 业务代码: from src.config.settings import settings; settings.paths.output_dir

2026-06-29 ARCH-004 迁移: 删 config_legacy.py 跟 src/ingest/config.py 的 config.toml 加载器,
全部改走 env (settings.py). 唯一引用方 tests/test_config.py 同步删除.
"""

from src.config.settings import settings  # noqa: F401
```

- [ ] **Step 4: 删 `src/ingest/config.py`**

```bash
git rm packages/service/src/ingest/config.py
```

⚠️ 删之前确认所有 import 已迁:
- `src/ingest/pipeline.py:18` 已改 `from src.config.settings import settings` (Task 2)
- `src/ingest/converters/cad.py:62` 已删 `from ..config import get_cad_config` (Task 3)
- `src/ingest/__init__.py` 看是否 export 旧 API: `cd packages/service && grep -n "get_paths\|get_cad_config\|get_archive_config\|CONFIG_FILE" src/ingest/__init__.py` 必须 0 命中

- [ ] **Step 5: 跑 import 冒烟 + pytest**

```bash
cd packages/service && uv run python -c "import src; print('src import OK'); from src.ingest import pipeline, config  # noqa: F401" 2>&1 | grep -v "ModuleNotFoundError" || echo "imports clean"
cd packages/service && uv run pytest -q --co 2>&1 | tail -5
```

期望: 第一个命令报 `src import OK` (没 import error). 第二个命令 collect 0 errors.

- [ ] **Step 6: Commit**

```bash
git add packages/service/src/__init__.py packages/service/src/config/__init__.py packages/service/src/ingest/config.py
git commit -m "refactor: ARCH-004 — 删 src/ingest/config.py + 清 src/__init__.py + src/config/__init__.py re-export"
```

---

## Task 7: 删 `tests/test_config.py` (已删, working tree `D`) + 验证 grep 0 命中 + 跑全量测试

**Files:**
- (working tree 状态) `tests/test_config.py` 已经是 `D` 状态, **已经在前一个 commit 删了 (commit message "T0 ...")** — 实际查看 `git log --diff-filter=D --name-only -- tests/test_config.py` 确认.
- 同样 `src/config_legacy.py` 已经在前一次 commit 删了.

- [ ] **Step 1: 验证 working tree 状态**

```bash
cd c:/Users/abcuc/Desktop/rag && git status --short
```

期望: 之前的 ARCH-004 6 个 commit 已清掉 `src/config_legacy.py` + `tests/test_config.py` + 所有 `get_paths/get_cad_config/get_archive_config/CONFIG_FILE` 引用.

- [ ] **Step 2: 全量 grep 0 命中**

```bash
cd c:/Users/abcuc/Desktop/rag && grep -rn "get_paths\|get_cad_config\|get_archive_config\|CONFIG_FILE\|config_legacy" packages/service/src packages/service/tests 2>&1 | grep -v __pycache__ | head -20
```

期望: 0 命中 (或仅 `__pycache__` 缓存).

- [ ] **Step 3: 跑 ruff + pyright**

```bash
cd c:/Users/abcuc/Desktop/rag/packages/service && uv run ruff format && uv run ruff check --fix && uv run pyright
```

期望: ruff 0 error, pyright 0 error. (pyright 22 pre-existing errors 应该不变, 这次不该引入新 error)

- [ ] **Step 4: 跑全量 pytest**

```bash
cd c:/Users/abcuc/Desktop/rag/packages/service && uv run pytest -q 2>&1 | tail -5
```

期望: fail 数 ≤ T0 baseline (50 fail) − 5 (test_config.py 5 个 test 删) + 0 (其他). **预期 fail 数 45**.

- [ ] **Step 5: Commit (如果有 stash 残留清理)**

如果 Step 4 跑出意外, 先 git status 看, 再决定是否需要 amend. 正常情况无 commit.

---

## 总结

| 文件 | 操作 | 净行数 |
|---|---|---|
| `src/config/settings.py` | 加 3 dataclass + 7 env 字段 | +45 |
| `src/ingest/pipeline.py` | 改 5 处调用 | −3 |
| `src/ingest/converters/cad.py` | 删 config fallback | −5 |
| `src/product_decoders/output_api.py` | 改 1 处 | −1 |
| `src/ingest/config.py` | 删 | −119 |
| `src/config_legacy.py` | (已删) | (71) |
| `src/__init__.py` | 删 re-export | −4 |
| `src/config/__init__.py` | 改 docstring + 删 re-export | −7 |
| `tests/ingest/test_config.py` | 删 | −120 |
| `tests/ingest/test_cad_oda.py` | 4 个 test 改 env-only | −25 |
| `tests/ingest/test_cad_converter.py` | 1 个 test 改 env-only | −5 |
| `tests/ingest/test_web_apis.py` | 1 个 fixture + 6 处改 | +5 |
| `tests/test_config.py` | (已删) | (75) |
| **合计** | | **净 −237 行** |

**pytest fail 减少预期**: 50 → 45 (test_config.py 5 个 fail 删了). 其他 fail 保持 baseline.
