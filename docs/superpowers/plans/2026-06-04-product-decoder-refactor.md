# Product Decoder 重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `src/server/decoder/`（Motor decoder PoC）重构为 `src/product_decoders/`（通用产品解析器，类名 `ProductDecoder`），修 3 个 bug（相对路径 / 测试 CWD 依赖 / YAML 纯字符串 value 缺 `_zh/_en`），并在 outer `main.py` 加 `serve` / `ingest` 子命令，合并 `src/server/README.md` 到仓库根 `README.md`。

**Architecture:** 用 FastAPI 工厂模式 `create_app()` 解耦"创建 app"和"配置加载"，避免模块级副作用。`ProductDecoder` 引擎按模型前缀路由到不同 YAML 配置，URL 保持根路径（不挂产品名）。`format_display()` 按 YAML position 的 `group` 字段做视觉分组插横线，保留 README 4 段形式。

**Tech Stack:** Python 3.14, FastAPI 0.136+, Pydantic, PyYAML, pytest 9, uvicorn 0.49+

**Spec:** [docs/superpowers/specs/2026-06-04-product-decoder-refactor-design.md](../specs/2026-06-04-product-decoder-refactor-design.md)

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `pyproject.toml` | 改 | `[tool.pytest.ini_options]` 加 `pythonpath = ["src"]` |
| `src/product_decoders/__init__.py` | 新建 | 暴露 `create_app, ProductDecoder, ConfigLoader` |
| `src/product_decoders/config_loader.py` | 新建 | `ConfigLoader` 类（按需加载 + 缓存） |
| `src/product_decoders/engine.py` | 新建 | `ProductDecoder` 类 + `format_display()` 静态方法 |
| `src/product_decoders/app.py` | 新建 | FastAPI 工厂 `create_app()`，路由 `/decode` `/series` `/health` |
| `src/product_decoders/configs/motor/siemens/1le0_low_voltage.yaml` | 新建 | 9 位 + 4 group + 所有 value 是 `{code, zh, en}` dict |
| `tests/test_product_decoder.py` | 新建 | 10 个 pytest 测试（覆盖 spec §测试设计） |
| `main.py` | 改 | 加 `serve` / `ingest` 子命令，默认 `serve` |
| `README.md` | 改 | 合并 `src/server/README.md` 内容（项目结构、快速启动、API、Dify 接入、Schema） |
| `src/server/`（含 `main.py` `README.md` `decoder/` `tests/` `configs/`） | 删 | 整个目录 |

**Files that change together**：`src/product_decoders/` 4 个新文件 + 1 个 YAML 强相关；测试和 main.py 跟它们一起构建；README 跟 src/server 删除一起收尾。

---

## Task 1: Pytest 配置 + 10 个测试骨架（TDD 红）

**Files:**
- Modify: `pyproject.toml`（在 `[tool.pytest.ini_options]` 块加 `pythonpath`）
- Create: `tests/test_product_decoder.py`

**目标**：先把 pytest 跑通，10 个新测试写出来，**全红**（`ImportError: No module named 'src.product_decoders'`）。后续 task 逐步让它们变绿。

- [ ] **Step 1: 改 `pyproject.toml` 加 `pythonpath`**

打开 [pyproject.toml](../../../pyproject.toml)，把现有的：

```toml
[tool.pytest.ini_options]
markers = [
    "slow: 慢测试（>2 分钟，跑真实 docker / GPU）",
]
```

改成：

```toml
[tool.pytest.ini_options]
markers = [
    "slow: 慢测试（>2 分钟，跑真实 docker / GPU）",
]
pythonpath = ["src"]
```

- [ ] **Step 2: 创建 `tests/test_product_decoder.py`**

新建 `tests/test_product_decoder.py`，包含全部 10 个测试。注意 16 字符模型 `1LE0001-1AA42-1AA4`（4 段 display），YAML value 全 `{code, zh, en}` dict。

```python
"""ProductDecoder 测试用例

16 字符 Siemens 1LE0 模型: 1LE0001-1AA42-1AA4
4 段 display 分组: prefix+eff / frm+pl+ln / vlt / mnt+wnd+box
YAML value 全部 {code, zh, en} dict 形式
"""
import os
from pathlib import Path

import pytest

from src.product_decoders import ConfigLoader, ProductDecoder, create_app


# 仓库根 = tests/ 的 parent.parent
REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = REPO_ROOT / "src" / "product_decoders" / "configs"


def make_decoder() -> ProductDecoder:
    """构造一个 ProductDecoder, 用绝对路径指向新的 configs 目录"""
    loader = ConfigLoader(config_dir=str(CONFIGS_DIR))
    return ProductDecoder(loader)


# ---------- T1: 完整解码 ----------
def test_decode_siemens_1le0_full():
    """16 字符型号完整解码, 验证所有 code 字段和 display 字段"""
    decoder = make_decoder()
    result = decoder.decode("1LE0001-1AA42-1AA4")

    assert result["series"] == "siemens_1le0_low_voltage"
    assert result["manufacturer"] == "Siemens"
    assert result["prefix"] == "1LE000"
    # efficiency_grade: 唯一值是 "1" (EFF3), 主值取 zh
    assert "高效" in result["efficiency_grade"]
    # frame_size: 1A -> code=100
    assert result["frame_size"] == 100
    assert result["frame_size_raw"] == "1A"
    # poles: A -> code=2
    assert result["poles"] == 2
    assert result["poles_raw"] == "A"
    # frame_length: 4 -> code=L
    assert result["frame_length"] == "L"
    # voltage: 21 -> code="220△/380Y/50" (spec §6.5 提议, 待用户确认)
    assert result["voltage"] == "220△/380Y/50"
    # mounting: A -> code="IM B3"
    assert result["mounting"] == "IM B3"
    # winding_protection: A -> code="NONE"
    assert result["winding_protection"] == "NONE"
    # box_location: 4 -> code="TOP"
    assert result["box_location"] == "TOP"
    # display: 4 段分组 (spec §6.0 group 字段)
    assert result["display"] == "1LE0001-1AA42-1AA4"


# ---------- T2: 未知 enum value ----------
def test_decode_with_unknown_value():
    """电压位 99 未知 -> 进 _warnings, HTTP 200, voltage 字段是 raw '99'"""
    decoder = make_decoder()
    result = decoder.decode("1LE0001-1AA4-99-AA4")

    assert "_warnings" in result
    assert any(w.get("name") == "voltage" for w in result["_warnings"])
    assert result["voltage_raw"] == "99"


# ---------- T3: 未知系列 ----------
def test_unknown_series():
    """完全无匹配前缀 -> ValueError"""
    decoder = make_decoder()
    with pytest.raises(ValueError, match="无法识别"):
        decoder.decode("XYZ12345678901234")


# ---------- T4: 长度错误 ----------
def test_length_error():
    """太短的型号 -> ValueError"""
    decoder = make_decoder()
    with pytest.raises(ValueError, match="长度"):
        decoder.decode("1LE0001-1A")


# ---------- T5: 列出所有系列 ----------
def test_list_series():
    """至少 1 个系列"""
    decoder = make_decoder()
    series_list = decoder.list_series()
    assert len(series_list) >= 1
    siemens = next(s for s in series_list if s["series"] == "siemens_1le0_low_voltage")
    assert siemens["manufacturer"] == "Siemens"
    assert siemens["prefix"] == "1LE000"


# ---------- T6: 输入标准化 ----------
def test_normalization_3_forms():
    """不同书写方式解析出相同 frame_size"""
    decoder = make_decoder()
    r1 = decoder.decode("1le0001-1aa4-21-aa4")
    r2 = decoder.decode("1LE00011AA421AA4")
    r3 = decoder.decode("  1LE0001 1AA4 21 AA4  ")
    assert r1["frame_size"] == r2["frame_size"] == r3["frame_size"] == 100


# ---------- T7: format_display 正常路径 ----------
def test_format_display_with_group():
    """positions 含 group 1-4 -> 按 group 边界插横线"""
    positions = [
        {"char_count": 6, "group": 1},
        {"char_count": 1, "group": 1},
        {"char_count": 2, "group": 2},
        {"char_count": 1, "group": 2},
        {"char_count": 1, "group": 2},
        {"char_count": 2, "group": 3},
        {"char_count": 1, "group": 4},
        {"char_count": 1, "group": 4},
        {"char_count": 1, "group": 4},
    ]
    result = ProductDecoder.format_display("1LE00011AA421AA4", positions)
    assert result == "1LE0001-1AA42-1AA4"


# ---------- T8: format_display 降级路径 ----------
def test_format_display_no_group():
    """positions 缺 group 字段 -> 不插横线, 直接返回 normalized"""
    positions = [
        {"char_count": 6}, {"char_count": 1}, {"char_count": 2},
        {"char_count": 1}, {"char_count": 1}, {"char_count": 2},
        {"char_count": 1}, {"char_count": 1}, {"char_count": 1},
    ]
    result = ProductDecoder.format_display("1LE00011AA421AA4", positions)
    assert result == "1LE00011AA421AA4"


# ---------- T9: create_app 在任意 CWD 下能找到 configs ----------
def test_create_app_loads_configs_from_any_cwd(tmp_path, monkeypatch):
    """切到临时目录后调 create_app() 不能因为相对路径失败"""
    monkeypatch.chdir(tmp_path)
    app = create_app()  # 不抛异常 = 通过
    assert app is not None
    # 顺便测一下健康检查能拿到 series_count >= 1
    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["series_count"] >= 1


# ---------- T10: 每个 enum 位都出 _zh / _en ----------
def test_every_enum_position_emits_zh_en():
    """Bug #3 回归: 解析 1LE0001-1AA42-1AA4, 所有 enum 位的 _zh / _en 都非空"""
    decoder = make_decoder()
    result = decoder.decode("1LE0001-1AA42-1AA4")

    for field in [
        "efficiency_grade", "frame_size", "poles", "frame_length",
        "voltage", "mounting", "winding_protection", "box_location",
    ]:
        assert f"{field}_zh" in result, f"缺 {field}_zh 字段"
        assert f"{field}_en" in result, f"缺 {field}_en 字段"
        assert result[f"{field}_zh"], f"{field}_zh 是空字符串"
        assert result[f"{field}_en"], f"{field}_en 是空字符串"
```

- [ ] **Step 3: 跑测试看全红**

```bash
uv run pytest tests/test_product_decoder.py -v 2>&1 | head -30
```

期望：10 个测试**全 FAIL**，错误是 `ModuleNotFoundError: No module named 'src.product_decoders'` 或 `ImportError`。

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml tests/test_product_decoder.py
git commit -m "test(product_decoder): pytest 配置 + 10 个测试骨架 (TDD 红)"
```

---

## Task 2: 实现 `ConfigLoader`（让 1 个测试能 import）

**Files:**
- Create: `src/product_decoders/__init__.py`
- Create: `src/product_decoders/config_loader.py`

**目标**：`ConfigLoader` 是个纯文件加载类，独立于解析器。先实现它，让"import 不挂"。

- [ ] **Step 1: 创建 `src/product_decoders/__init__.py`**

```python
"""product_decoders package

通用产品订货号解析 (FastAPI 服务 + 配置驱动).
"""
from .app import create_app
from .config_loader import ConfigLoader
from .engine import ProductDecoder

__all__ = ["create_app", "ConfigLoader", "ProductDecoder"]
```

- [ ] **Step 2: 创建 `src/product_decoders/config_loader.py`**

```python
"""配置加载器: 按需加载 + 缓存"""
from pathlib import Path
from typing import Dict, List


class ConfigLoader:
    """配置加载器, 支持按需加载和缓存

    用法:
        loader = ConfigLoader(config_dir="configs")
        cfg = loader.load("siemens_1le0_low_voltage")
    """

    def __init__(self, config_dir: str):
        self.config_dir = Path(config_dir)
        self._cache: Dict[str, dict] = {}

    def load(self, series_id: str) -> dict:
        """按 series_id 加载单个配置 (缓存)"""
        if series_id in self._cache:
            return self._cache[series_id]
        for yaml_file in self.config_dir.rglob("*.yaml"):
            with open(yaml_file, "r", encoding="utf-8") as f:
                cfg = _safe_yaml_load(f)
            if cfg and cfg.get("series") == series_id:
                self._cache[series_id] = cfg
                return cfg
        raise ValueError(f"未找到系列配置: {series_id}")

    def load_all(self) -> List[dict]:
        """加载目录下所有 yaml 配置"""
        configs: List[dict] = []
        for yaml_file in self.config_dir.rglob("*.yaml"):
            with open(yaml_file, "r", encoding="utf-8") as f:
                cfg = _safe_yaml_load(f)
            if cfg:
                configs.append(cfg)
        return configs


def _safe_yaml_load(f) -> dict:
    """读 yaml 时容错: 空文件 / 注释-only 文件返回 None"""
    import yaml
    cfg = yaml.safe_load(f)
    return cfg or {}
```

- [ ] **Step 3: 跑测试看 import 错误变了**

```bash
uv run pytest tests/test_product_decoder.py -v 2>&1 | head -30
```

期望：import 错误变化（从 `ModuleNotFoundError` 变成 `AttributeError: module 'src.product_decoders' has no attribute 'engine'` 或类似），但**测试还是红**，因为 `ProductDecoder` 还不存在。

- [ ] **Step 4: Commit**

```bash
git add src/product_decoders/__init__.py src/product_decoders/config_loader.py
git commit -m "feat(product_decoders): ConfigLoader 抽到独立模块"
```

---

## Task 3: 实现 `ProductDecoder`（让 T1-T6 变绿）

**Files:**
- Create: `src/product_decoders/engine.py`

**目标**：从 [src/server/decoder/parser.py](../../../src/server/decoder/parser.py) 平移 `MotorDecoder` 逻辑，改类名为 `ProductDecoder`，构造函数改**接受外部注入**的 `ConfigLoader`（不再内部创建）。这一步让 T1-T6 变绿；T7-T10 还红。

注意：当前 Task 3 **还不实现** `format_display()`，所以 T7 仍红。`decode()` 也**还不写** `display` 字段，所以 T1 里的 `result["display"]` 断言会挂（T1 整体红）。这没关系——Task 4 才解决。

- [ ] **Step 1: 创建 `src/product_decoders/engine.py`**

```python
"""产品订货号解析引擎

按 model 前缀路由到不同 YAML 配置, 按 char_count 顺序消耗字符.
"""
from pathlib import Path
from typing import Optional, Dict, List, Any
import re

from .config_loader import ConfigLoader


class ProductDecoder:
    """产品型号解码器核心

    关键设计: 每个 position 有 char_count, 解析器按 char_count 顺序消耗字符.
    加新系列只需写 YAML, 零代码改动.

    用法:
        loader = ConfigLoader(config_dir="configs")
        decoder = ProductDecoder(loader)
        result = decoder.decode("1LE0001-1AA42-1AA4")
    """

    def __init__(self, loader: ConfigLoader):
        self.loader = loader
        self._routing_table: Optional[List[dict]] = None

    # ------------------------------------------------------------------
    # 路由器
    # ------------------------------------------------------------------
    def _build_routing_table(self) -> List[dict]:
        if self._routing_table is not None:
            return self._routing_table
        configs = self.loader.load_all()
        table = []
        for cfg in configs:
            router = cfg.get("router", {})
            table.append({
                "series": cfg["series"],
                "prefix": router.get("prefix", ""),
                "pattern": router.get("pattern", ""),
                "priority": router.get("priority", 0),
            })
        table.sort(key=lambda x: (-x["priority"], -len(x["prefix"])))
        self._routing_table = table
        return table

    def route(self, model: str) -> str:
        normalized = self._normalize(model)
        for entry in self._build_routing_table():
            pattern = entry["pattern"] or f"^{entry['prefix']}"
            if re.match(pattern, normalized):
                return entry["series"]
        raise ValueError(f"无法识别型号所属系列: {model}")

    # ------------------------------------------------------------------
    # 标准化
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize(model: str) -> str:
        return model.replace("-", "").replace(" ", "").upper()

    # ------------------------------------------------------------------
    # 核心解码 (变长位置支持)
    # ------------------------------------------------------------------
    def decode(self, model: str) -> dict:
        series_id = self.route(model)
        cfg = self.loader.load(series_id)

        raw = self._normalize(model)
        expected_len = cfg["decoder"]["total_chars"]
        if len(raw) != expected_len:
            raise ValueError(
                f"型号长度错误: {model} → 标准化后 {len(raw)} 位, "
                f"期望 {expected_len} 位 (系列: {series_id})"
            )

        result = {
            "series": series_id,
            "series_name": cfg.get("series_name_zh", ""),
            "manufacturer": cfg.get("manufacturer", ""),
            "raw_input": model,
            "normalized": raw,
        }

        # 按 char_count 顺序消耗字符
        cursor = 0
        warnings: List[dict] = []

        for pos in cfg["decoder"]["positions"]:
            char_count = pos.get("char_count", 1)
            segment = raw[cursor:cursor + char_count]
            cursor += char_count

            pos_name = pos["name"]
            pos_type = pos.get("type", "enum")

            # ----- 固定值前缀位 (如 1LE000) -----
            if pos_type == "fixed":
                expected = pos.get("value", "")
                if segment != expected:
                    warnings.append({
                        "position": pos["idx"],
                        "name": pos_name,
                        "expected": expected,
                        "got": segment,
                        "message": f"前缀不匹配: 期望 '{expected}', 得到 '{segment}'",
                    })
                result[pos_name] = segment
                continue

            # ----- 透传位 -----
            if pos_type == "passthrough":
                result[pos_name] = segment
                continue

            # ----- 枚举解码 -----
            values = pos.get("values", {})
            if segment in values:
                decoded_val = values[segment]
                if isinstance(decoded_val, dict):
                    # 主值: 优先 code (短代号, 便于程序处理)
                    # 补充: _zh, _en 作为展示用
                    result[pos_name] = (
                        decoded_val.get("code")
                        or decoded_val.get("zh")
                        or decoded_val
                    )
                    if "zh" in decoded_val:
                        result[f"{pos_name}_zh"] = decoded_val["zh"]
                    if "en" in decoded_val:
                        result[f"{pos_name}_en"] = decoded_val["en"]
                else:
                    result[pos_name] = decoded_val
                result[f"{pos_name}_raw"] = segment
            else:
                result[pos_name] = segment
                result[f"{pos_name}_raw"] = segment
                warnings.append({
                    "position": pos["idx"],
                    "name": pos_name,
                    "name_zh": pos.get("name_zh", ""),
                    "value": segment,
                    "message": f"值 '{segment}' 不在已知编码表中",
                })

        if cursor != len(raw):
            warnings.append({
                "position": -1,
                "name": "trailing",
                "message": f"解析后剩余 {len(raw) - cursor} 字符未消费: '{raw[cursor:]}'",
            })

        if warnings:
            result["_warnings"] = warnings

        return result

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------
    def list_series(self) -> List[dict]:
        return [
            {
                "series": cfg["series"],
                "manufacturer": cfg.get("manufacturer", ""),
                "name": cfg.get("series_name_zh", ""),
                "prefix": cfg.get("router", {}).get("prefix", ""),
            }
            for cfg in self.loader.load_all()
        ]
```

- [ ] **Step 2: 跑测试看进展**

```bash
uv run pytest tests/test_product_decoder.py -v 2>&1 | tail -40
```

期望：T1-T6 仍**大部分红**（因为 YAML 还是 src/server/ 那份 18 字符的，T1 解析 16 字符会挂；T2 也是；T3-T6 应该过）。T7-T10 仍红。

- [ ] **Step 3: Commit**

```bash
git add src/product_decoders/engine.py
git commit -m "feat(product_decoders): ProductDecoder 平移 + 构造函数改注入式"
```

---

## Task 4: 实现 `format_display()` + `display` 字段（T7/T8 变绿）

**Files:**
- Modify: `src/product_decoders/engine.py`（加 `format_display` 静态方法 + `decode()` 末尾加 `display`）

**目标**：让 T7/T8 变绿。同时给 `decode()` 末尾加 `display` 字段，让 T1 的 `display` 断言也变绿（前提是 YAML 改完——Task 5 解决）。

- [ ] **Step 1: 在 `ProductDecoder` 类**内**添加 `format_display` 静态方法**

打开 `src/product_decoders/engine.py`，在 `ProductDecoder` 类的 `list_series` 方法**下方**（即类内最后一个方法之后）追加：

```python
    # ------------------------------------------------------------------
    # 展示: 按 position.group 做视觉分组
    # ------------------------------------------------------------------
    @staticmethod
    def format_display(normalized: str, positions: List[dict]) -> str:
        """按 position.group 字段对 normalized 字符串做视觉分组.

        输入: "1LE00011AA421AA4" (16 字符, 标准化后无横线)
        positions 含 group 字段 (1, 1, 2, 2, 2, 3, 4, 4, 4)
        → 按 group 累计字符数边界插 "-", 得到 "1LE0001-1AA42-1AA4"

        降级路径: 如果所有 position 都缺 group 字段, 不插横线, 直接返回 normalized.
        """
        if not any(pos.get("group") for pos in positions):
            return normalized

        # 计算每个 group 累计字符数 (取该 group 第一次出现的累计值)
        group_boundaries: Dict[int, int] = {}
        cursor = 0
        for pos in positions:
            cursor += pos.get("char_count", 1)
            g = pos.get("group")
            if g is not None and g not in group_boundaries:
                group_boundaries[g] = cursor

        # 在 group 边界 (除最后一个 group) 之后插 "-"
        max_g = max(group_boundaries)
        boundaries = sorted(
            pos for g, pos in group_boundaries.items()
            if pos < len(normalized) and g < max_g
        )
        chars = list(normalized)
        for b in reversed(boundaries):
            chars.insert(b, "-")
        return "".join(chars)
```

- [ ] **Step 2: 在 `ProductDecoder.decode()` 末尾加 `display` 字段**

打开 `src/product_decoders/engine.py`，找到 `decode()` 方法里的：

```python
        if warnings:
            result["_warnings"] = warnings

        return result
```

把它**之前**插入一行（在 `if warnings:` 之前）：

```python
        # 按 position.group 视觉分组还原 display
        result["display"] = self.format_display(raw, cfg["decoder"]["positions"])
```

完整的 `decode()` 方法尾巴应该是：

```python
        if cursor != len(raw):
            warnings.append({
                "position": -1,
                "name": "trailing",
                "message": f"解析后剩余 {len(raw) - cursor} 字符未消费: '{raw[cursor:]}'",
            })

        # 按 position.group 视觉分组还原 display
        result["display"] = self.format_display(raw, cfg["decoder"]["positions"])

        if warnings:
            result["_warnings"] = warnings

        return result
```

- [ ] **Step 3: 跑 T7/T8 看绿**

```bash
uv run pytest tests/test_product_decoder.py::test_format_display_with_group tests/test_product_decoder.py::test_format_display_no_group -v
```

期望：T7/T8 **PASS**。

- [ ] **Step 4: 跑全套看进展**

```bash
uv run pytest tests/test_product_decoder.py -v 2>&1 | tail -30
```

期望：T7/T8 PASS。其他仍红（YAML 还没改 → T1/T2/T10 挂）。

- [ ] **Step 5: Commit**

```bash
git add src/product_decoders/engine.py
git commit -m "feat(product_decoders): format_display 按 position.group 分组 + decode 写 display 字段"
```

---

## Task 5: 改造 YAML（group 字段 + value 改 dict）让 T1/T2/T10 变绿

**Files:**
- Create: `src/product_decoders/configs/motor/siemens/1le0_low_voltage.yaml`

**目标**：从 [src/server/configs/siemens/1le0_low_voltage.yaml](../../../src/server/configs/siemens/1le0_low_voltage.yaml) 平移 + 改造：去掉 `display_separators` 字段（Task 1 已经在新 YAML 里没写）+ 给每个 position 加 `group` 字段 + 把所有 enum value 改成 `{code, zh, en}` dict 形式。

- [ ] **Step 1: 创建 YAML 目录**

```bash
mkdir -p src/product_decoders/configs/motor/siemens
```

- [ ] **Step 2: 创建 `1le0_low_voltage.yaml`**

新建 `src/product_decoders/configs/motor/siemens/1le0_low_voltage.yaml`：

```yaml
# =============================================================================
# 西门子 1LE0 低压系列三相异步电动机 - 订货号配置
# Siemens 1LE0 Low-voltage Motor Series - Order No. Configuration
# =============================================================================
# 9 个 position / 16 字符 / 4 个 group
# group 1 (1LE0001, 7 字符): prefix + efficiency_grade
# group 2 (1AA4,     4 字符): frame_size + poles + frame_length
# group 3 (21,       2 字符): voltage
# group 4 (AA4,      3 字符): mounting + winding_protection + box_location
# =============================================================================

series: siemens_1le0_low_voltage
manufacturer: Siemens
series_name_zh: 西门子低压系列三相异步电动机
series_name_en: Siemens 1LE0 Low-voltage Motor Series
version: "2.0"
source_doc: 西门子电机型号4.png (用户校正版) + product_decoders 重构

# ---------- 路由配置 ----------
router:
  match_type: "prefix"
  prefix: "1LE000"
  pattern: "^1LE000"
  priority: 100
  description: 前缀 1LE000 + 1 位能效等级码

# ---------- 解析器配置 ----------
decoder:
  type: "positional"
  total_chars: 16

  positions:

    # ---------- group 1: 1LE0001 ----------
    - idx: 1
      name: prefix
      name_zh: 型号前缀
      name_en: Series prefix
      char_count: 6
      type: fixed
      group: 1
      value: "1LE000"

    - idx: 7
      name: efficiency_grade
      name_zh: 能效等级
      name_en: Efficiency grade
      char_count: 1
      type: enum
      group: 1
      required: true
      values:
        "1":
          code: "EFF3"
          zh: "高效电动机，中国能效等级 3 级"
          en: "High Efficiency, China Energy Efficiency Grade 3"

    # ---------- group 2: 1AA4 ----------
    - idx: 8
      name: frame_size
      name_zh: 机座号
      name_en: Frame size
      char_count: 2
      type: enum
      group: 2
      required: true
      unit: mm
      values:
        "0D": {code: 80,  zh: "80mm 机座",  en: "80mm frame"}
        "0E": {code: 90,  zh: "90mm 机座",  en: "90mm frame"}
        "1A": {code: 100, zh: "100mm 机座", en: "100mm frame"}
        "1B": {code: 112, zh: "112mm 机座", en: "112mm frame"}
        "1C": {code: 132, zh: "132mm 机座", en: "132mm frame"}
        "1D": {code: 160, zh: "160mm 机座", en: "160mm frame"}
        "1E": {code: 180, zh: "180mm 机座", en: "180mm frame"}
        "2A": {code: 200, zh: "200mm 机座", en: "200mm frame"}
        "2B": {code: 225, zh: "225mm 机座", en: "225mm frame"}
        "2C": {code: 250, zh: "250mm 机座", en: "250mm frame"}
        "2D": {code: 280, zh: "280mm 机座", en: "280mm frame"}
        "3A": {code: 315, zh: "315mm 机座", en: "315mm frame"}
        "3B": {code: 355, zh: "355mm 机座", en: "355mm frame"}

    - idx: 10
      name: poles
      name_zh: 极数
      name_en: Number of poles
      char_count: 1
      type: enum
      group: 2
      required: true
      unit: 极
      values:
        A: {code: 2, zh: "2 极", en: "2 poles"}
        B: {code: 4, zh: "4 极", en: "4 poles"}
        C: {code: 6, zh: "6 极", en: "6 poles"}
        D: {code: 8, zh: "8 极", en: "8 poles"}

    - idx: 11
      name: frame_length
      name_zh: 机座长度
      name_en: Frame length
      char_count: 1
      type: enum
      group: 2
      required: true
      values:
        "0": {code: "S", zh: "短机座", en: "short"}
        "1": {code: "S", zh: "短机座", en: "short"}
        "2": {code: "M", zh: "中机座", en: "medium"}
        "3": {code: "M", zh: "中机座", en: "medium"}
        "4": {code: "L", zh: "长机座", en: "long"}
        "5": {code: "L", zh: "长机座", en: "long"}
        "6": {code: "L", zh: "长机座", en: "long"}
        "7": {code: "L", zh: "长机座", en: "long"}

    # ---------- group 3: 21 ----------
    - idx: 12
      name: voltage
      name_zh: 电压、连接方式、频率
      name_en: Voltage, connections and frequency
      char_count: 2
      type: enum
      group: 3
      required: true
      values:
        "21": {code: "220△/380Y/50", zh: "220V△/380VY 50Hz", en: "220V△/380VY 50Hz"}
        "22": {code: "230△/400Y/50", zh: "230V△/400VY 50Hz", en: "230V△/400VY 50Hz"}
        "23": {code: "240△/415Y/50", zh: "240V△/415VY 50Hz", en: "240V△/415VY 50Hz"}
        "33": {code: "380△/660Y/50", zh: "380V△/660VY 50Hz", en: "380V△/660VY 50Hz"}
        "34": {code: "400△/690Y/50", zh: "400V△/690VY 50Hz", en: "400V△/690VY 50Hz"}
        "35": {code: "415△/50",      zh: "415V△ 50Hz",      en: "415V△ 50Hz"}
        "04": {code: "400△/50",      zh: "400V△ 50Hz",      en: "400V△ 50Hz"}
        "90": {code: "SPECIAL",      zh: "特殊电压与频率 / special voltage & frequency", en: "special voltage & frequency"}

    # ---------- group 4: AA4 ----------
    - idx: 14
      name: mounting
      name_zh: 安装方式
      name_en: Construction and mounting type
      char_count: 1
      type: enum
      group: 4
      required: true
      values:
        A: {code: "IM B3",  zh: "IM B3 卧式底脚安装",  en: "IM B3"}
        T: {code: "IM B6",  zh: "IM B6 卧式底脚安装",  en: "IM B6"}
        U: {code: "IM B7",  zh: "IM B7 卧式底脚安装",  en: "IM B7"}
        V: {code: "IM B8",  zh: "IM B8 卧式底脚安装",  en: "IM B8"}
        J: {code: "IM B35", zh: "IM B35 卧式底脚+法兰", en: "IM B35"}
        C: {code: "IM V5",  zh: "IM V5 立式轴向下",    en: "IM V5"}
        W: {code: "IM V15", zh: "IM V15 立式轴向下",   en: "IM V15"}
        G: {code: "IM V1",  zh: "IM V1 立式轴向上",    en: "IM V1"}
        M: {code: "IM V18", zh: "IM V18 立式轴向下",   en: "IM V18"}
        K: {code: "IM B14", zh: "IM B14 法兰安装",     en: "IM B14"}
        D: {code: "IM V6",  zh: "IM V6 立式轴向上",    en: "IM V6"}
        Y: {code: "IM V35", zh: "IM V35 立式带法兰",   en: "IM V35"}
        H: {code: "IM V3",  zh: "IM V3 立式轴向上",    en: "IM V3"}
        L: {code: "IM V19", zh: "IM V19 立式轴向下",   en: "IM V19"}
        N: {code: "IM B34", zh: "IM B34 底脚+法兰",    en: "IM B34"}
        F: {code: "IM B5",  zh: "IM B5 法兰安装",      en: "IM B5"}

    - idx: 15
      name: winding_protection
      name_zh: 绕组保护
      name_en: Winding protection
      char_count: 1
      type: enum
      group: 4
      required: true
      values:
        A: {code: "NONE", zh: "无绕组保护 / without winding protection", en: "without winding protection"}
        B: {code: "PTC3_TRIP", zh: "3 个 PTC 热敏电阻（跳闸）/ 3 PTC thermistors for tripping", en: "3 PTC thermistors for tripping"}
        C: {code: "PTC6_TRIP_ALARM", zh: "6 个 PTC 热敏电阻（报警+跳闸）/ 6 PTC thermistors for alarm and tripping", en: "6 PTC thermistors for alarm and tripping"}
        F: {code: "KTY84", zh: "1 个 KTY 84-130 温度传感器 / 1 temperature sensor KTY 84-130", en: "1 temperature sensor KTY 84-130"}
        H: {code: "PT100_3", zh: "3 个 Pt100 测温元件 / 3 resistance thermometers Pt100", en: "3 resistance thermometers Pt100"}
        J: {code: "PT100_6", zh: "6 个 Pt100 测温元件 / 6 resistance thermometers Pt100", en: "6 resistance thermometers Pt100"}

    - idx: 16
      name: box_location
      name_zh: 接线盒位置
      name_en: Connection box location
      char_count: 1
      type: enum
      group: 4
      required: true
      description: 从驱动端看
      values:
        "4": {code: "TOP",  zh: "置顶 / on top",  en: "on top"}
        "5": {code: "RIGHT", zh: "右侧 / on RHS",  en: "on RHS"}
        "6": {code: "LEFT",  zh: "左侧 / on LHS",  en: "on LHS"}

# ---------- 校验规则 ----------
validation:
  normalize:
    strip_chars: ["-", " "]
    upper: true
  strict_length: true

# ---------- 示例 ----------
examples:
  - raw: "1LE0001-1AA42-1AA4"
    description: "示例: 机座 100, 2 极, 长机座, 220V/380V 50Hz, IM B3, 无保护, 接线盒置顶"
```

- [ ] **Step 3: 跑 T1/T2/T10 看绿**

```bash
uv run pytest tests/test_product_decoder.py -v 2>&1 | tail -20
```

期望：T1 / T2 / T10 **PASS**（前提是 T7/T8 之前已绿）。T3-T6 之前已绿。

- [ ] **Step 4: 跑全套看进展**

```bash
uv run pytest tests/test_product_decoder.py -v 2>&1 | tail -20
```

期望：T1, T2, T3, T4, T5, T6, T7, T8, T10 = 9 PASS。仅 T9 仍红（`create_app` 还不存在）。

- [ ] **Step 5: Commit**

```bash
git add src/product_decoders/configs/
git commit -m "feat(product_decoders): 1le0 YAML 9 位/4 group + value 全部 {code,zh,en} dict"
```

---

## Task 6: 实现 FastAPI `app.py` 工厂（T9 变绿）

**Files:**
- Create: `src/product_decoders/app.py`

**目标**：用工厂模式 `create_app()` 创建 FastAPI 实例，路由 `/decode` `/series` `/health`。让 T9 变绿。

- [ ] **Step 1: 创建 `src/product_decoders/app.py`**

```python
"""Product Decoder FastAPI Service

提供 HTTP 接口给 Dify 工作流调用:
  POST /decode   - 解码一个产品型号
  GET  /series   - 列出所有支持的系列
  GET  /health   - 健康检查
"""
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config_loader import ConfigLoader
from .engine import ProductDecoder

# 锁定绝对路径, 不依赖 CWD
CONFIGS_DIR = Path(__file__).resolve().parent / "configs"


class DecodeRequest(BaseModel):
    """解码请求"""
    model: str = Field(..., description="完整订货号, 如 1LE0001-1AA42-1AA4")


class SeriesInfo(BaseModel):
    """系列信息"""
    series: str
    manufacturer: str
    name: str
    prefix: str


def create_app() -> FastAPI:
    """FastAPI 工厂: 测试可以 monkeypatch CONFIGS_DIR 后再调本函数"""
    loader = ConfigLoader(config_dir=str(CONFIGS_DIR))
    decoder = ProductDecoder(loader)

    app = FastAPI(
        title="Product Order No. Decoder",
        description="产品订货号通用解析服务 - 配置驱动, 多厂商",
        version="1.0.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/decode")
    async def decode(req: DecodeRequest):
        """解码一个产品型号, 返回结构化结果"""
        try:
            return decoder.decode(req.model)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"内部错误: {e}")

    @app.get("/series", response_model=List[SeriesInfo])
    async def list_series():
        """列出所有支持的产品系列"""
        return decoder.list_series()

    @app.get("/health")
    async def health():
        """健康检查"""
        return {
            "status": "ok",
            "series_count": len(decoder.list_series()),
        }

    return app


# 开发用: python -m src.product_decoders.app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_app(), host="0.0.0.0", port=8000)
```

- [ ] **Step 2: 跑 T9 看绿**

```bash
uv run pytest tests/test_product_decoder.py::test_create_app_loads_configs_from_any_cwd -v
```

期望：T9 **PASS**。

- [ ] **Step 3: 跑全套 10 个测试全绿**

```bash
uv run pytest tests/test_product_decoder.py -v
```

期望：**10/10 PASS**。

- [ ] **Step 4: Commit**

```bash
git add src/product_decoders/app.py
git commit -m "feat(product_decoders): FastAPI 工厂 create_app() + /decode /series /health 路由"
```

---

## Task 7: 重写 outer `main.py` 加 `serve` / `ingest` 子命令

**Files:**
- Modify: [main.py](../../../main.py)

**目标**：默认走 `serve`（启动 FastAPI），`ingest` 显式子命令跑 PDF 流水线。

- [ ] **Step 1: 整段替换 `main.py`**

打开 [main.py](../../../main.py)，**整段替换**为：

```python
"""RAG 项目统一入口

  uv run python main.py            → 启动产品订货号解析服务 (默认, 端口 8000)
  uv run python main.py ingest     → 跑 PDF 离线流水线
"""
import argparse

import uvicorn

from src.product_decoders import create_app
from src.rag_ingest.pipeline import process_files

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000


def cmd_serve(host: str, port: int, reload: bool) -> None:
    """启动 FastAPI 产品解析服务"""
    app = create_app()
    uvicorn.run(app, host=host, port=port, reload=reload)


def cmd_ingest() -> None:
    """跑 PDF 离线流水线"""
    process_files()


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG 入口")
    sub = parser.add_subparsers(dest="mode")

    p_ingest = sub.add_parser("ingest", help="跑 PDF 离线流水线")
    p_ingest.set_defaults(_handler=cmd_ingest)

    p_serve = sub.add_parser("serve", help="启动产品订货号解析服务")
    p_serve.add_argument("--host", default=DEFAULT_HOST)
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_serve.add_argument("--reload", action="store_true")
    p_serve.set_defaults(_handler=cmd_serve)

    args = parser.parse_args()
    if not getattr(args, "_handler", None):
        # 没指定子命令 → 默认走 serve
        args = parser.parse_args(["serve"])

    kwargs = {k: v for k, v in vars(args).items() if k not in ("mode", "_handler")}
    args._handler(**kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 验证 CLI 行为**

```bash
# 默认走 serve
uv run python main.py --help
```

期望：输出 argparse help（跟直接 `serve` 子命令的 help 接近，但少了 ingest 描述）。

```bash
# 显示 serve 子命令
uv run python main.py serve --help
```

期望：显示 `--host` / `--port` / `--reload` 3 个参数。

```bash
# 显示 ingest 子命令
uv run python main.py ingest --help
```

期望：显示 "跑 PDF 离线流水线" 描述，**没有** host/port 参数。

- [ ] **Step 3: 跑全套测试看没回归**

```bash
uv run pytest tests/ -m "not slow" -v 2>&1 | tail -30
```

期望：所有非 slow 测试 PASS（包括 Task 1-6 加的 10 个 product decoder 测试 + 仓库原有的所有测试）。

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat(main): 加 serve / ingest 子命令, 默认 serve 启动 FastAPI"
```

---

## Task 8: 删 `src/server/` 整个目录

**Files:**
- Delete: 整个 `src/server/` 目录（含 `main.py` `README.md` `decoder/` `tests/` `configs/` `__pycache__/`）

**目标**：新模块已在 `src/product_decoders/`，旧 `src/server/` 彻底删掉避免混淆。

- [ ] **Step 1: 确认要删除**

```bash
ls -la src/server/
```

期望：看到 `main.py` `README.md` `decoder/` `tests/` `configs/` `__pycache__/`。

- [ ] **Step 2: 删除整个目录**

**Windows PowerShell**:
```bash
Remove-Item -Recurse -Force src/server
```

**Git Bash / WSL**:
```bash
rm -rf src/server
```

- [ ] **Step 3: 验证 Python 还能 import**

```bash
uv run python -c "from src.product_decoders import create_app; print('OK')"
```

期望：输出 `OK`。

- [ ] **Step 4: 跑全套测试**

```bash
uv run pytest tests/ -m "not slow" -v 2>&1 | tail -30
```

期望：所有非 slow 测试 PASS（特别是 `tests/test_product_decoder.py` 10 个测试）。

- [ ] **Step 5: Commit**

```bash
git add -A src/
git commit -m "chore: 删 src/server/ 整个目录, 由 src/product_decoders/ 取代"
```

---

## Task 9: 写仓库根 `README.md`（合并旧 src/server/README.md）

**Files:**
- Modify: [README.md](../../../README.md)（覆盖 pyproject 占位文件）

**目标**：把 `src/server/README.md` 的内容（项目结构 / 快速启动 / API / Dify 接入 / Schema / 解码示例）全部吸收进仓库根 README，新增产品解析服务章节。

- [ ] **Step 1: 整段替换 `README.md`**

打开 [README.md](../../../README.md)（**如果不存在就新建**），**整段替换**为：

```markdown
# RAG 项目

RAG 离线流水线 + 产品订货号解析 HTTP 服务。

## 1. 项目结构

```
rag/
├── main.py                              # 统一入口: 默认 serve, 子命令 ingest
├── src/
│   ├── product_decoders/                # 产品订货号解析 (FastAPI)
│   │   ├── __init__.py
│   │   ├── app.py                       # FastAPI 工厂
│   │   ├── engine.py                    # ProductDecoder 核心引擎
│   │   ├── config_loader.py             # ConfigLoader
│   │   └── configs/
│   │       └── motor/
│   │           └── siemens/
│   │               └── 1le0_low_voltage.yaml
│   └── rag_ingest/                      # RAG PDF 处理流水线
│       ├── pipeline.py
│       ├── analyzer.py
│       └── ...
├── tests/
│   ├── test_product_decoder.py
│   ├── test_*.py                        # RAG 流水线测试
│   └── integration/
│       └── test_*.py                    # 集成测试 (slow marker)
├── docs/
│   └── superpowers/                     # 设计文档 + 实施计划
└── pyproject.toml
```

## 2. 快速启动

### 2.1 启动产品订货号解析服务（默认）

```bash
uv sync
uv run python main.py                    # 默认 serve, 端口 8000
```

调用测试：

```bash
curl -X POST http://localhost:8000/decode \
  -H "Content-Type: application/json" \
  -d '{"model": "1LE0001-1AA42-1AA4"}'
```

### 2.2 跑 PDF 离线流水线

```bash
uv run python main.py ingest
```

## 3. 产品订货号解析服务

### 3.1 添加新系列

1. 在 `src/product_decoders/configs/<category>/<vendor>/` 下新建 YAML
2. 复制 `motor/siemens/1le0_low_voltage.yaml` 的结构，按实际编码规则修改
3. 填好 `router.prefix` 和 `router.pattern`
4. 重启服务即可

**零代码改动**。模型前缀路由 (`ProductDecoder.route()`) 自动选配置。

### 3.2 统一输出 Schema

```json
{
  "series": "siemens_1le0_low_voltage",
  "manufacturer": "Siemens",
  "raw_input": "1LE0001-1AA42-1AA4",
  "normalized": "1LE00011AA421AA4",
  "display": "1LE0001-1AA42-1AA4",
  "prefix": "1LE000",
  "efficiency_grade": "高效电动机，中国能效等级 3 级",
  "efficiency_grade_zh": "高效电动机，中国能效等级 3 级",
  "efficiency_grade_en": "High Efficiency, China Energy Efficiency Grade 3",
  "frame_size": 100,
  "frame_size_zh": "100mm 机座",
  "frame_size_en": "100mm frame",
  "frame_size_raw": "1A",
  "poles": 2,
  "poles_zh": "2 极",
  "poles_en": "2 poles",
  "poles_raw": "A",
  "frame_length": "L",
  "frame_length_zh": "长机座",
  "frame_length_en": "long",
  "frame_length_raw": "4",
  "voltage": "220△/380Y/50",
  "voltage_zh": "220V△/380VY 50Hz",
  "voltage_en": "220V△/380VY 50Hz",
  "voltage_raw": "21",
  "mounting": "IM B3",
  "mounting_zh": "IM B3 卧式底脚安装",
  "mounting_en": "IM B3",
  "mounting_raw": "A",
  "winding_protection": "NONE",
  "winding_protection_zh": "无绕组保护 / without winding protection",
  "winding_protection_en": "without winding protection",
  "winding_protection_raw": "A",
  "box_location": "TOP",
  "box_location_zh": "置顶 / on top",
  "box_location_en": "on top",
  "box_location_raw": "4"
}
```

**设计要点**：
- 主值用 `code` 或简短中文（如 `"L"`、`"IM B3"`），方便程序处理
- `_zh` / `_en` 后缀字段提供完整中文/英文说明
- `_raw` 后缀字段保留原始编码，方便追溯
- `display` 字段是按 YAML `position.group` 视觉分组还原的展示形式

### 3.3 API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/decode` | 解码一个型号，body: `{"model": "..."}` |
| `GET`  | `/series` | 列出所有支持系列 |
| `GET`  | `/health` | 健康检查，返回 `series_count` |

### 3.4 Dify 工作流接入

```
[开始] 用户输入: "1LE0001-1AA42-1AA4"
   ↓
[HTTP 请求节点]
   POST http://localhost:8000/decode
   Body: {"model": "{{sys.query}}"}
   ↓
[LLM 节点] 格式化输出
   Prompt: "你是产品选型助手，根据解码结果用中文分点解释。
            {{#http_response.body#}}"
   ↓
[直接回复]
```

### 3.5 解码示例

输入：`1LE0001-1AA42-1AA4`（16 字符，标准化后 `1LE00011AA421AA4`，4 段 display）

| 位置 | 编码 | group | 含义 |
|---|---|---|---|
| 1-6 | `1LE000` | 1 | 型号前缀（低压系列） |
| 7 | `1` | 1 | 能效等级 3 级 |
| 8-9 | `1A` | 2 | 机座号 100 |
| 10 | `A` | 2 | 2 极 |
| 11 | `4` | 2 | 长机座 L |
| 12-13 | `21` | 3 | 220V△/380VY 50Hz |
| 14 | `A` | 4 | IM B3 安装 |
| 15 | `A` | 4 | 无绕组保护 |
| 16 | `4` | 4 | 接线盒置顶 |

## 4. 测试

```bash
uv run pytest tests/                      # 跑全部
uv run pytest tests/ -m "not slow"        # 跑非 slow 测试
uv run pytest tests/test_product_decoder.py  # 跑产品解析器单测
```

## 5. 开发者规范

- 中文注释、中文日志（`print(...)` / `logging.info(...)` 都用中文）
- TDD 流程：先红 → 绿 → 重构
- 用 `uv run` 跑 Python（确保依赖一致）
- 设计文档放 `docs/superpowers/specs/`，实施计划放 `docs/superpowers/plans/`
```

- [ ] **Step 2: 跑全套测试看没回归**

```bash
uv run pytest tests/ -m "not slow" -v 2>&1 | tail -10
```

期望：所有非 slow 测试 PASS。

- [ ] **Step 3: 手动 curl 验收 `main.py serve`**

开一个 terminal：

```bash
uv run python main.py serve --port 8765
```

期望：日志看到 `Uvicorn running on http://0.0.0.0:8765`。

另一个 terminal：

```bash
curl -X POST http://localhost:8765/decode \
  -H "Content-Type: application/json" \
  -d '{"model": "1LE0001-1AA42-1AA4"}'
```

期望：返回 JSON 包含 `"display": "1LE0001-1AA42-1AA4"`、`"frame_size": 100`、`"mounting": "IM B3"` 等字段。

```bash
curl http://localhost:8765/series
```

期望：返回 JSON 数组，至少 1 条 `siemens_1le0_low_voltage`。

```bash
curl http://localhost:8765/health
```

期望：`{"status": "ok", "series_count": 1}`。

按 `Ctrl+C` 停服务。

- [ ] **Step 4: 手动验证 `main.py ingest` 不挂**

```bash
uv run python main.py ingest --help
```

期望：显示 "跑 PDF 离线流水线" 描述，**不**真跑（help 不触发实际处理）。

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: 仓库根 README, 合并旧 src/server/README.md 内容 (项目结构/快速启动/API/Dify/Schema)"
```

---

## Task 10: 完成检查 + 跑全套

**Files:** 无

- [ ] **Step 1: 跑全套非 slow 测试**

```bash
uv run pytest tests/ -m "not slow" -v 2>&1 | tail -20
```

期望：**所有 PASS**。包括：
- `tests/test_product_decoder.py`（10 个）
- `tests/test_*.py`（RAG 流水线原有所有）
- `tests/integration/test_*.py`（如果有非 slow 的）

- [ ] **Step 2: 跑全套含 slow**

```bash
uv run pytest tests/ -v 2>&1 | tail -20
```

期望：除 slow 标记的之外全 PASS（slow 测试需要 GPU / 真实 docker，本地不一定能跑）。

- [ ] **Step 3: 确认 git log 干净**

```bash
git status --short
```

期望：没有 untracked 改动（除可能的 `__pycache__`）。

```bash
git log --oneline -10
```

期望看到（按时间倒序）：

- `docs: 仓库根 README, 合并旧 src/server/README.md 内容 (项目结构/快速启动/API/Dify/Schema)`
- `chore: 删 src/server/ 整个目录, 由 src/product_decoders/ 取代`
- `feat(main): 加 serve / ingest 子命令, 默认 serve 启动 FastAPI`
- `feat(product_decoders): FastAPI 工厂 create_app() + /decode /series /health 路由`
- `feat(product_decoders): 1le0 YAML 9 位/4 group + value 全部 {code,zh,en} dict`
- `feat(product_decoders): format_display 按 position.group 分组 + decode 写 display 字段`
- `feat(product_decoders): ProductDecoder 平移 + 构造函数改注入式`
- `feat(product_decoders): ConfigLoader 抽到独立模块`
- `test(product_decoder): pytest 配置 + 10 个测试骨架 (TDD 红)`
- (spec 的 4 个 commit 在更早)

- [ ] **Step 4: 验证 src/server/ 没了**

```bash
ls src/server/ 2>&1
```

期望：`No such file or directory` (或 PowerShell 等价错误)。

- [ ] **Step 5: 验证 outer main.py 启动能跑**

```bash
uv run python main.py --help
```

期望：argparse help 输出。

---

## 完成标准

实施完全部 10 个 task 后：

1. ✅ `src/product_decoders/` 包含 5 个文件（`__init__.py` `app.py` `engine.py` `config_loader.py` `configs/motor/siemens/1le0_low_voltage.yaml`）
2. ✅ `tests/test_product_decoder.py` 10 个测试全 PASS
3. ✅ `main.py` 默认 `serve`，`ingest` 是显式子命令
4. ✅ `src/server/` 已删
5. ✅ `README.md` 在仓库根，覆盖了旧 src/server/README.md 的所有内容
6. ✅ `git log` 有 8 个新增 commit（不含 spec 的 4 个早期 commit）
7. ✅ 手动 curl `/decode` `/series` `/health` 都能正常返回
