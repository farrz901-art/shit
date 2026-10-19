# Neo4j 导入脚本实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 写一个 Python CLI 脚本 `scripts/neo4j_import.py`, 把 `configs/product_decoders/**/*.yaml` 转换为 4 类 Neo4j 节点 (`产品系列` / `产品型号` / `技术参数` / `参数值`) + 4 类关系 (`属于` / `具有参数` / `参数值` / `参数对应`), 经用户交互式 y/N 确认后写入在线 Neo4j (Aura + APOC)。

**Architecture:** 单文件脚本 + 函数化拆分。`yaml_to_graph_data()` 集成项目内的 `ProductDecoder.decode()` 解码 `examples[].raw` 来生成具体的关系; `Neo4jClient` 封装 driver + APOC 验证; `import` 子命令走 `load → decode → dedup → table → y/N → cypher` 流程, `check` 子命令只验连通 + 打节点数。所有 Neo4j 凭证走 4 个 `NEO4J_*` env var, 凭证不进代码。

**Tech Stack:** Python 3.14, neo4j>=5.x, tabulate>=0.9, pyyaml, src.product_decoders (项目内 ProductDecoder + ConfigLoader), pytest 9

**Spec:** [docs/superpowers/specs/2026-06-04-neo4j-import-design.md](../specs/2026-06-04-neo4j-import-design.md)

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `pyproject.toml` | 改 | `dependencies` 加 `neo4j`, `tabulate`, `pyyaml` (显式, 避免幽灵依赖) |
| `.env.example` | 新建 | 4 个 `NEO4J_*` 占位符 |
| `.gitignore` | 改 | 添加 `.env` (防凭证泄露) |
| `scripts/neo4j_import.py` | 新建 | 整个 CLI 脚本: load → decode → dedup → table → y/N → cypher |
| `tests/scripts/__init__.py` | 新建 | 空 (让 pytest 找到 tests/scripts/) |
| `tests/scripts/test_neo4j_import.py` | 新建 | ~21 个 pytest 测试, 分 6 组 |
| `README.md` | 改 | 加 "环境变量 / Neo4j 导入" 节 + 项目结构加 `scripts/` 和 `tests/scripts/` |

**Files that change together**: `scripts/neo4j_import.py` + `tests/scripts/test_neo4j_import.py` 强相关 (TDD 同步); `pyproject.toml` + `.env.example` 一起改 (依赖 + 文档); README 跟 `scripts/` 一起加。

---

## Task 1: 依赖 + .env.example + .gitignore

**Files:**
- Modify: `pyproject.toml` (在 `dependencies` 数组加 3 个包)
- Create: `.env.example`
- Modify: `.gitignore` (添加 `.env`)

- [ ] **Step 1: 更新 `pyproject.toml` 的 dependencies**

打开 [pyproject.toml](../../pyproject.toml), 把现有 `dependencies = [...]` 数组改成:

```toml
dependencies = [
    "docker>=7.1.0",
    "ezdxf>=1.4.4",          # CAD converter (DWG/DXF) 直接用，不带 [draw] extras
    "fastapi>=0.136.3",
    "kreuzberg[all]>=4.9.7",
    "llama-index>=0.14.22",
    "neo4j>=5.20.0",          # Neo4j 官方 Python driver (import_check)
    "pymupdf>=1.27.2.3",
    "pyyaml>=6.0",            # YAML 解析 (ProductDecoder 和 neo4j_import.py 都用, 显式声明)
    "tabulate>=0.9.0",        # CLI 表格渲染 (import_check)
    "uvicorn>=0.49.0",
]
```

把 `neo4j`, `pyyaml`, `tabulate` 按字母顺序插入, 不破坏原有顺序。

- [ ] **Step 2: 创建 `.env.example`**

仓库根创建 `.env.example`, 内容:

```bash
# =============================================================================
# Neo4j Aura 在线实例 (用于 scripts/neo4j_import.py)
# =============================================================================
# 用法:
#   1. cp .env.example .env
#   2. 在 https://console.neo4j.io 注册免费 Aura 实例
#   3. 把下面 4 个占位符替换成实际值
#   4. 运行前 source .env 或用 direnv 自动加载
#
# 安全: .env 已在 .gitignore, 不会被提交
# =============================================================================

# Neo4j 连接 URI (Aura 免费实例格式: neo4j+s://xxx.databases.neo4j.io)
NEO4J_URI=neo4j+s://your-instance-id.databases.neo4j.io

# Neo4j 用户名 (Aura 默认 neo4j)
NEO4J_USER=neo4j

# Neo4j 密码 (Aura 创建实例时下载的 .txt 里的密码)
NEO4J_PASSWORD=replace-with-your-aura-password

# Neo4j 数据库名 (Aura 免费实例默认 neo4j, 一般不用改)
NEO4J_DATABASE=neo4j
```

- [ ] **Step 3: 更新 `.gitignore`**

打开 [`.gitignore`](../../.gitignore), 在末尾追加:

```gitignore
# Neo4j 凭证 (本地配置, 不要提交)
.env
```

如果 `.env` 已在里面, 跳过这步。

- [ ] **Step 4: 同步依赖 + 验证可导入**

```bash
uv sync
uv run python -c "import neo4j, tabulate, yaml; print('neo4j', neo4j.__version__); print('tabulate', tabulate.__version__); print('pyyaml', yaml.__version__)"
```

预期: 3 行版本号, 0 错。

- [ ] **Step 5: 提交**

```bash
git add pyproject.toml .env.example .gitignore uv.lock
git commit -F /tmp/commit_msg.txt
```

`/tmp/commit_msg.txt` 内容:

```
chore: 加 neo4j + tabulate + pyyaml 依赖, 创建 .env.example

- pyproject.toml: 显式声明 3 个新依赖
- .env.example: 4 个 NEO4J_* 占位符 + 用法说明
- .gitignore: 添加 .env 防凭证泄露
```

---

## Task 2: 测试脚手架 (fixture + 空测试文件)

**Files:**
- Create: `tests/scripts/__init__.py` (空文件)
- Create: `tests/scripts/test_neo4j_import.py` (含 fixture, 0 个测试)

- [ ] **Step 1: 创建空 `tests/scripts/__init__.py`**

```bash
echo "" > tests/scripts/__init__.py
```

- [ ] **Step 2: 写 `tests/scripts/test_neo4j_import.py` 含 fixture**

创建 [tests/scripts/test_neo4j_import.py](../../tests/scripts/test_neo4j_import.py), 内容:

```python
"""scripts/neo4j_import.py 单元测试

测试策略: 单元 + Mock, 不连真实 Neo4j. 真实端到端留给用户手动跑 import 验证.

测试数据用 _make_yaml_text() 生成最小版 1le0 yaml (8 个 enum position + 1 example),
通过 tmp_config_dir fixture 落到临时目录, 用项目内的 ConfigLoader + ProductDecoder 加载.
"""
from pathlib import Path
import argparse
import pytest

from src.product_decoders import ConfigLoader, ProductDecoder


# ---------- 测试 fixture ----------

# 仓库根: tests/scripts/ 的 parent.parent.parent
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _make_yaml_text() -> str:
    """返回最小 1le0 yaml 字符串 (8 enum position + 1 example)

    example "1LE0001-1AA4-21-AA4" 是 16 字符, 跟 total_chars=16 匹配.
    8 个 enum position 的 values 各含 1 个 key, 刚好覆盖 example 的 8 段编码.
    """
    return """\
series: test_1le0
manufacturer: TestBrand
series_name_zh: 测试系列
series_name_en: Test Series
version: "1.0"
source_doc: test fixture

router:
  prefix: "1LE000"
  pattern: "^1LE000"
  priority: 100

decoder:
  type: "positional"
  total_chars: 16
  display_separators: [7, 12]
  positions:
    - idx: 1
      name: prefix
      name_zh: 型号前缀
      name_en: Series prefix
      char_count: 6
      type: fixed
      value: "1LE000"
    - idx: 7
      name: efficiency_grade
      name_zh: 能效等级
      name_en: Efficiency grade
      char_count: 1
      type: enum
      values:
        "1": {code: "EFF3", zh: "高效", en: "High Efficiency"}
    - idx: 8
      name: frame_size
      name_zh: 机座号
      name_en: Frame size
      char_count: 2
      type: enum
      unit: mm
      values:
        "1A": {code: 100, zh: "100mm 机座", en: "100mm frame"}
    - idx: 10
      name: poles
      name_zh: 极数
      name_en: Number of poles
      char_count: 1
      type: enum
      values:
        A: {code: 2, zh: "2 极", en: "2 poles"}
    - idx: 11
      name: frame_length
      name_zh: 机座长度
      name_en: Frame length
      char_count: 1
      type: enum
      values:
        "4": {code: "L", zh: "长机座", en: "long"}
    - idx: 12
      name: voltage
      name_zh: 电压
      name_en: Voltage
      char_count: 2
      type: enum
      values:
        "21": {code: "220V/380V/50", zh: "220V/380V 50Hz", en: "220V/380V 50Hz"}
    - idx: 14
      name: mounting
      name_zh: 安装方式
      name_en: Mounting
      char_count: 1
      type: enum
      values:
        A: {code: "IM B3", zh: "IM B3 卧式", en: "IM B3"}
    - idx: 15
      name: winding_protection
      name_zh: 绕组保护
      name_en: Winding protection
      char_count: 1
      type: enum
      values:
        A: {code: "NONE", zh: "无", en: "none"}
    - idx: 16
      name: box_location
      name_zh: 接线盒位置
      name_en: Box location
      char_count: 1
      type: enum
      values:
        "4": {code: "TOP", zh: "置顶", en: "on top"}

examples:
  - raw: "1LE0001-1AA4-21-AA4"
    description: "测试示例: 机座 100, 2 极, 长机座"
"""


@pytest.fixture
def tmp_config_dir(tmp_path):
    """创建临时 config 目录, 写入测试 yaml, 返回 (config_dir, loader, decoder)"""
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    yaml_path = config_dir / "test.yaml"
    yaml_path.write_text(_make_yaml_text(), encoding="utf-8")
    loader = ConfigLoader(config_dir=str(config_dir))
    decoder = ProductDecoder(loader)
    return config_dir, loader, decoder
```

- [ ] **Step 3: 跑测试, 验 0 个测试 (脚手架 OK)**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -v
```

预期: `0 passed` 或 `no tests ran`, 0 失败。

- [ ] **Step 4: 提交**

```bash
git add tests/scripts/__init__.py tests/scripts/test_neo4j_import.py
git commit -F /tmp/commit_msg.txt
```

`/tmp/commit_msg.txt`:

```
test(scripts): 脚手架 - test_neo4j_import.py 含 fixture

- _make_yaml_text(): 最小版 1le0 yaml (8 enum pos + 1 example)
- tmp_config_dir fixture: 落临时目录, 返回 (loader, decoder)
- 0 个测试, 后续 task 逐步加
```

---

## Task 3: TDD `load_yamls()`

**Files:**
- Modify: `tests/scripts/test_neo4j_import.py` (加 2 测试)
- Modify: `scripts/neo4j_import.py` (新建, 含 `load_yamls()`)

- [ ] **Step 1: 写 2 个失败测试**

在 [tests/scripts/test_neo4j_import.py](../../tests/scripts/test_neo4j_import.py) 末尾追加:

```python
# ---------- Group 1a: load_yamls ----------

def test_load_yamls_finds_yaml_files(tmp_config_dir):
    """临时目录有 1 个 yaml, load_yamls 加载它, 返回 1 个 dict"""
    from scripts.neo4j_import import load_yamls
    config_dir, _, _ = tmp_config_dir
    yamls = load_yamls(config_dir)
    assert len(yamls) == 1
    assert yamls[0]["series"] == "test_1le0"


def test_load_yamls_empty_dir(tmp_path):
    """空目录 → 空 list, 不抛"""
    from scripts.neo4j_import import load_yamls
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    yamls = load_yamls(empty_dir)
    assert yamls == []
```

- [ ] **Step 2: 跑测试, 验 2 个 FAIL**

```bash
uv run pytest tests/scripts/test_neo4j_import.py::test_load_yamls_finds_yaml_files tests/scripts/test_neo4j_import.py::test_load_yamls_empty_dir -v
```

预期: `ModuleNotFoundError: No module named 'scripts.neo4j_import'`

- [ ] **Step 3: 创建 `scripts/neo4j_import.py` 含 `load_yamls()`**

创建 [scripts/neo4j_import.py](../../scripts/neo4j_import.py), 完整内容:

```python
"""YAML 配置 → Neo4j 知识图谱 导入脚本

子命令:
  import  把 configs/product_decoders/ 转成节点/关系, 查 Neo4j 去重, 表格确认, 写库
  check   验 Neo4j 连通 + APOC 可用, 打节点数

用法:
  uv run python scripts/neo4j_import.py check
  uv run python scripts/neo4j_import.py import
  uv run python scripts/neo4j_import.py import --config-dir /path/to/configs
"""
from pathlib import Path
from typing import Optional
import argparse
import os
import sys

import yaml

from src.product_decoders import ConfigLoader, ProductDecoder


# ---------- 数据层 ----------

def load_yamls(config_dir: Path) -> list[dict]:
    """递归加载 config_dir 下所有 .yaml 文件, 返回 list[dict]"""
    config_dir = Path(config_dir)
    yamls: list[dict] = []
    for yaml_path in sorted(config_dir.rglob("*.yaml")):
        with open(yaml_path, encoding="utf-8") as f:
            yamls.append(yaml.safe_load(f))
    return yamls


# ---------- 暂未实现 ----------

def yaml_to_graph_data(yamls: list[dict], decoder: ProductDecoder) -> dict:
    raise NotImplementedError("TODO: Task 4-5 实现")


def dedup_against_neo4j(data: dict, client) -> tuple[list, list]:
    raise NotImplementedError("TODO: Task 9 实现")


def build_cypher(nodes: list[dict], rels: list[dict]) -> tuple[str, dict]:
    raise NotImplementedError("TODO: Task 6 实现")


def format_props(props: dict) -> str:
    raise NotImplementedError("TODO: Task 7 实现")


def render_node_table(nodes: list[dict]) -> str:
    raise NotImplementedError("TODO: Task 7 实现")


def render_rel_table(rels: list[dict]) -> str:
    raise NotImplementedError("TODO: Task 7 实现")


def cmd_import(args) -> int:
    raise NotImplementedError("TODO: Task 11 实现")


def cmd_check(args) -> int:
    raise NotImplementedError("TODO: Task 10 实现")


def main() -> int:
    raise NotImplementedError("TODO: Task 12 实现")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 跑测试, 验 2 个 PASS**

```bash
uv run pytest tests/scripts/test_neo4j_import.py::test_load_yamls_finds_yaml_files tests/scripts/test_neo4j_import.py::test_load_yamls_empty_dir -v
```

预期: `2 passed`

- [ ] **Step 5: 提交**

```bash
git add tests/scripts/test_neo4j_import.py scripts/neo4j_import.py
git commit -F /tmp/commit_msg.txt
```

`/tmp/commit_msg.txt`:

```
feat(scripts): load_yamls() 加载 configs/ 下所有 yaml

- 递归 rglob("*.yaml"), 加载为 list[dict]
- 空目录返回空 list, 不抛
- 其他函数留 NotImplementedError, 后续 task 填
```

---

## Task 4: TDD `yaml_to_graph_data()` - 产品系列 / 技术参数 / 参数值 节点

**Files:**
- Modify: `tests/scripts/test_neo4j_import.py` (加 6 测试)
- Modify: `scripts/neo4j_import.py` (实现 3 类节点)

- [ ] **Step 1: 写 6 个失败测试**

在 [tests/scripts/test_neo4j_import.py](../../tests/scripts/test_neo4j_import.py) 末尾追加:

```python
# ---------- Group 1b-d: yaml_to_graph_data 节点 (产品系列/技术参数/参数值) ----------

def test_yaml_to_nodes_series_count(tmp_config_dir):
    """1 个 yaml → 1 个产品系列节点"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data
    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    series_nodes = [n for n in data["nodes"] if "产品系列" in n["labels"]]
    assert len(series_nodes) == 1


def test_yaml_to_nodes_series_uses_name_zh_and_props(tmp_config_dir):
    """产品系列.name 是 series_name_zh, props 含 series_id"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data
    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    series_node = next(n for n in data["nodes"] if "产品系列" in n["labels"])
    assert series_node["name"] == "测试系列"
    assert series_node["props"]["series_id"] == "test_1le0"
    assert series_node["props"]["manufacturer"] == "TestBrand"


def test_yaml_to_nodes_param_count(tmp_config_dir):
    """8 个 enum position → 8 个技术参数节点"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data
    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    param_nodes = [n for n in data["nodes"] if "技术参数" in n["labels"]]
    assert len(param_nodes) == 8


def test_yaml_to_nodes_param_uses_name_zh(tmp_config_dir):
    """技术参数.name 是 name_zh"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data
    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    names = {n["name"] for n in data["nodes"] if "技术参数" in n["labels"]}
    assert "机座号" in names
    assert "极数" in names
    assert "电压" in names


def test_yaml_to_nodes_value_count(tmp_config_dir):
    """8 个 enum position 各 1 value → 8 个参数值节点"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data
    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    value_nodes = [n for n in data["nodes"] if "参数值" in n["labels"]]
    assert len(value_nodes) == 8


def test_yaml_to_nodes_value_preserves_code(tmp_config_dir):
    """参数值.code 来自 values[i].code"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data
    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    v_1a = next(n for n in data["nodes"] if n["name"] == "1A")
    assert v_1a["props"]["code"] == 100
    assert v_1a["props"]["zh"] == "100mm 机座"
```

- [ ] **Step 2: 跑测试, 验 6 个 FAIL**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -k "yaml_to_nodes" -v
```

预期: 6 个 FAIL, 全部 `NotImplementedError`

- [ ] **Step 3: 实现 `yaml_to_graph_data()` 的 3 类节点 (产品系列/技术参数/参数值)**

在 [scripts/neo4j_import.py](../../scripts/neo4j_import.py) 中, 把 `yaml_to_graph_data` 改成:

```python
def yaml_to_graph_data(yamls: list[dict], decoder: ProductDecoder) -> dict:
    """YAML 列表 + ProductDecoder → {nodes, rels}

    集成 ProductDecoder.decode() 解码 examples[].raw 生成 4 类关系.
    """
    nodes: list[dict] = []
    rels: list[dict] = []

    for cfg in yamls:
        # ---- 产品系列 节点 ----
        series_name = cfg.get("series_name_zh", cfg.get("series", ""))
        series_node = {
            "labels": ["产品系列"],
            "name": series_name,
            "props": {
                "series_id": cfg.get("series", ""),
                "manufacturer": cfg.get("manufacturer", ""),
                "series_name_zh": cfg.get("series_name_zh", ""),
                "series_name_en": cfg.get("series_name_en", ""),
                "description": f"{cfg.get('series_name_zh', '')} / {cfg.get('series_name_en', '')}".strip(" /"),
                "version": str(cfg.get("version", "")),
                "source_doc": cfg.get("source_doc", ""),
            },
        }
        nodes.append(series_node)

        # ---- 技术参数 节点 (只取 type=enum 的 position) ----
        enum_positions: list[dict] = []
        for pos in cfg.get("decoder", {}).get("positions", []):
            if pos.get("type") != "enum":
                continue
            enum_positions.append(pos)
            param_props = {
                "name_zh": pos.get("name_zh", ""),
                "name_en": pos.get("name_en", ""),
                "char_count": pos.get("char_count", 1),
                "type": pos.get("type", "enum"),
                "idx": pos.get("idx", 0),
            }
            if "unit" in pos:
                param_props["unit"] = pos["unit"]
            nodes.append({
                "labels": ["技术参数"],
                "name": pos.get("name_zh", ""),
                "props": param_props,
            })

        # ---- 参数值 节点 ----
        for pos in enum_positions:
            for raw_key, decoded in pos.get("values", {}).items():
                if isinstance(decoded, dict):
                    value_props = {
                        "code": decoded.get("code"),
                        "zh": decoded.get("zh", ""),
                        "en": decoded.get("en", ""),
                    }
                else:
                    value_props = {"code": decoded}
                nodes.append({
                    "labels": ["参数值"],
                    "name": str(raw_key),
                    "props": value_props,
                })

    # 节点按 name 去重 (APOC merge 也是按 name, 先在 Python 端去重避免参数重复)
    seen: set[str] = set()
    unique_nodes: list[dict] = []
    for n in nodes:
        if n["name"] in seen:
            continue
        seen.add(n["name"])
        unique_nodes.append(n)

    return {"nodes": unique_nodes, "rels": rels}
```

- [ ] **Step 4: 跑测试, 验 6 个 PASS**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -k "yaml_to_nodes" -v
```

预期: `6 passed`

- [ ] **Step 5: 跑全套测试, 验不退化**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -v
```

预期: `8 passed` (6 新 + 2 旧)

- [ ] **Step 6: 提交**

```bash
git add tests/scripts/test_neo4j_import.py scripts/neo4j_import.py
git commit -F /tmp/commit_msg.txt
```

`/tmp/commit_msg.txt`:

```
feat(scripts): yaml_to_graph_data() 生成 产品系列/技术参数/参数值 节点

- 产品系列.name = series_name_zh, props 含 series_id 等
- 技术参数.name = name_zh, 只取 type=enum 的 position
- 参数值.name = values 字典的 key, props 含 code/zh/en
- 节点按 name 在 Python 端去重
```

---

## Task 5: TDD `yaml_to_graph_data()` - 产品型号 + 4 类关系 (ProductDecoder 集成)

**Files:**
- Modify: `tests/scripts/test_neo4j_import.py` (加 6 测试)
- Modify: `scripts/neo4j_import.py` (扩展 `yaml_to_graph_data()` 加型号 + 关系)

- [ ] **Step 1: 写 6 个失败测试**

在 [tests/scripts/test_neo4j_import.py](../../tests/scripts/test_neo4j_import.py) 末尾追加:

```python
# ---------- Group 1e-h: yaml_to_graph_data 产品型号 + 4 类关系 ----------

def test_yaml_to_nodes_model_count(tmp_config_dir):
    """1 个 example → 1 个产品型号节点"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data
    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    model_nodes = [n for n in data["nodes"] if "产品型号" in n["labels"]]
    assert len(model_nodes) == 1


def test_yaml_to_nodes_model_uses_examples_raw(tmp_config_dir):
    """产品型号.name 是 examples[].raw"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data
    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    model_node = next(n for n in data["nodes"] if "产品型号" in n["labels"])
    assert model_node["name"] == "1LE0001-1AA4-21-AA4"
    assert "测试示例" in model_node["props"]["description"]


def test_yaml_to_rels_belongsto_count(tmp_config_dir):
    """1 个 example × 1 series → 1 条 属于"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data
    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    belongs = [r for r in data["rels"] if r["type"] == "属于"]
    assert len(belongs) == 1
    assert belongs[0]["srcName"] == "1LE0001-1AA4-21-AA4"
    assert belongs[0]["tgtName"] == "测试系列"


def test_yaml_to_rels_has_param_count(tmp_config_dir):
    """1 个 example × 8 enum pos → 8 条 具有参数"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data
    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    has_param = [r for r in data["rels"] if r["type"] == "具有参数"]
    assert len(has_param) == 8


def test_yaml_to_rels_param_value_and_param_of_counts(tmp_config_dir):
    """decode 出来 8 个 (param, value) 配对 → 8 参数值 + 8 参数对应"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data
    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    data = yaml_to_graph_data(yamls, decoder)
    param_val = [r for r in data["rels"] if r["type"] == "参数值"]
    param_of = [r for r in data["rels"] if r["type"] == "参数对应"]
    assert len(param_val) == 8
    assert len(param_of) == 8


def test_yaml_decode_failure_skips_example(tmp_config_dir, capsys):
    """examples 里加一个无法解码的型号 → 跳过, 不阻塞其他"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data
    config_dir, _, decoder = tmp_config_dir
    yamls = load_yamls(config_dir)
    # 加一个坏 example
    yamls[0]["examples"].append({
        "raw": "BAD-MODEL-XXXXXXXX",
        "description": "故意坏",
    })
    data = yaml_to_graph_data(yamls, decoder)
    # 只该有 1 个产品型号 (好的那个)
    model_nodes = [n for n in data["nodes"] if "产品型号" in n["labels"]]
    assert len(model_nodes) == 1
    # 警告应打印
    captured = capsys.readouterr()
    assert "BAD-MODEL-XXXXXXXX" in captured.out
```

- [ ] **Step 2: 跑测试, 验 6 个 FAIL**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -k "model_count or model_uses or belongsto or has_param or param_value_and or decode_failure" -v
```

预期: 6 个 FAIL (model 节点不存在, rels 全空)

- [ ] **Step 3: 扩展 `yaml_to_graph_data()` 加型号 + 4 关系**

在 [scripts/neo4j_import.py](../../scripts/neo4j_import.py) 中, 修改 `yaml_to_graph_data`, 在参数值节点循环之后, **return 之前**, 插入:

```python
        # ---- 产品型号 节点 + 4 类关系 (集成 ProductDecoder) ----
        for ex in cfg.get("examples", []):
            raw_model = ex.get("raw", "")
            if not raw_model:
                continue
            # 产品型号 节点
            nodes.append({
                "labels": ["产品型号"],
                "name": raw_model,
                "props": {"description": ex.get("description", "")},
            })
            # 属于 → 产品系列
            rels.append({
                "srcName": raw_model,
                "tgtName": series_name,
                "type": "属于",
                "props": {},
            })
            # 用 ProductDecoder 解码, 拿到 8 个 (param_name, value) 配对
            try:
                decoded = decoder.decode(raw_model)
            except ValueError as e:
                print(f"[SKIP] example '{raw_model}' 无法解码: {e}", file=sys.stderr)
                continue
            for pos in enum_positions:
                pos_name_en = pos["name"]                # decoder 用英文 key
                raw_value = decoded.get(f"{pos_name_en}_raw")
                if raw_value is None:
                    continue
                pos_name_zh = pos.get("name_zh", pos_name_en)
                # 具有参数 → 技术参数
                rels.append({
                    "srcName": raw_model,
                    "tgtName": pos_name_zh,
                    "type": "具有参数",
                    "props": {},
                })
                # 参数值 → 参数值
                rels.append({
                    "srcName": raw_model,
                    "tgtName": str(raw_value),
                    "type": "参数值",
                    "props": {},
                })
                # 参数对应 → 技术参数
                rels.append({
                    "srcName": str(raw_value),
                    "tgtName": pos_name_zh,
                    "type": "参数对应",
                    "props": {},
                })
```

- [ ] **Step 4: 跑测试, 验 6 个 PASS**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -k "model_count or model_uses or belongsto or has_param or param_value_and or decode_failure" -v
```

预期: `6 passed`

- [ ] **Step 5: 跑全套, 验 14 个全过**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -v
```

预期: `14 passed`

- [ ] **Step 6: 提交**

```bash
git add tests/scripts/test_neo4j_import.py scripts/neo4j_import.py
git commit -F /tmp/commit_msg.txt
```

`/tmp/commit_msg.txt`:

```
feat(scripts): yaml_to_graph_data() 加 产品型号 + 4 类关系

- 产品型号.name = examples[].raw, props.description = examples[].description
- 4 类关系: 属于(型号→系列), 具有参数(型号→参数), 参数值(型号→值), 参数对应(值→参数)
- 用 ProductDecoder.decode() 解 examples[].raw, 拿 (param, value) 配对
- 解码失败 → 打印警告到 stderr, 跳过该 example, 不阻塞
```

---

## Task 6: TDD `build_cypher()`

**Files:**
- Modify: `tests/scripts/test_neo4j_import.py` (加 3 测试)
- Modify: `scripts/neo4j_import.py` (实现 `build_cypher`)

- [ ] **Step 1: 写 3 个失败测试**

在 [tests/scripts/test_neo4j_import.py](../../tests/scripts/test_neo4j_import.py) 末尾追加:

```python
# ---------- Group 3: build_cypher ----------

def test_build_cypher_contains_apoc_merge_node():
    """cypher 必须含 apoc.merge.node + UNWIND $nodes"""
    from scripts.neo4j_import import build_cypher
    cypher, _ = build_cypher(
        [{"labels": ["产品系列"], "name": "X", "props": {}}],
        [],
    )
    assert "apoc.merge.node" in cypher
    assert "UNWIND $nodes" in cypher


def test_build_cypher_contains_apoc_merge_relationship():
    """cypher 必须含 apoc.merge.relationship + UNWIND $rels"""
    from scripts.neo4j_import import build_cypher
    _, _ = build_cypher([], [])
    cypher, _ = build_cypher(
        [],
        [{"srcName": "A", "tgtName": "B", "type": "具有参数", "props": {}}],
    )
    assert "apoc.merge.relationship" in cypher
    assert "UNWIND $rels" in cypher


def test_build_cypher_params_separated():
    """$nodes 和 $rels 必须在 params 分开"""
    from scripts.neo4j_import import build_cypher
    nodes = [{"labels": ["产品系列"], "name": "X", "props": {"k": "v"}}]
    rels = [{"srcName": "X", "tgtName": "Y", "type": "属于", "props": {}}]
    _, params = build_cypher(nodes, rels)
    assert "nodes" in params
    assert "rels" in params
    assert params["nodes"] == nodes
    assert params["rels"] == rels
```

- [ ] **Step 2: 跑测试, 验 3 个 FAIL**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -k "build_cypher" -v
```

预期: 3 个 FAIL (`NotImplementedError`)

- [ ] **Step 3: 实现 `build_cypher()`**

在 [scripts/neo4j_import.py](../../scripts/neo4j_import.py) 中, 把 `build_cypher` 改成:

```python
def build_cypher(nodes: list[dict], rels: list[dict]) -> tuple[str, dict]:
    """生成 apoc.merge.node + apoc.merge.relationship 的 cypher + params

    模板:
        UNWIND $nodes AS node
        CALL apoc.merge.node(node.labels, {name: node.name}, node.props, {}) YIELD node AS n
        UNWIND $rels AS rel
        MATCH (a {name: rel.srcName})
        MATCH (b {name: rel.tgtName})
        CALL apoc.merge.relationship(a, rel.type, {}, rel.props, b) YIELD rel AS r
        RETURN count(r) AS rels_written
    """
    cypher = """
UNWIND $nodes AS node
CALL apoc.merge.node(node.labels, {name: node.name}, node.props, {}) YIELD node AS n
WITH count(n) AS nodes_merged
UNWIND $rels AS rel
MATCH (a {name: rel.srcName})
MATCH (b {name: rel.tgtName})
CALL apoc.merge.relationship(a, rel.type, {}, rel.props, b) YIELD rel AS r
RETURN count(r) AS rels_written
""".strip()
    params = {"nodes": nodes, "rels": rels}
    return cypher, params
```

- [ ] **Step 4: 跑测试, 验 3 个 PASS**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -k "build_cypher" -v
```

预期: `3 passed`

- [ ] **Step 5: 提交**

```bash
git add tests/scripts/test_neo4j_import.py scripts/neo4j_import.py
git commit -F /tmp/commit_msg.txt
```

`/tmp/commit_msg.txt`:

```
feat(scripts): build_cypher() 生成 APOC merge cypher

- 模板含 apoc.merge.node + apoc.merge.relationship
- $nodes 和 $rels 拆成 2 个 params, 一次性 batch 写
```

---

## Task 7: TDD `format_props` + `render_node_table` + `render_rel_table`

**Files:**
- Modify: `tests/scripts/test_neo4j_import.py` (加 5 测试)
- Modify: `scripts/neo4j_import.py` (实现 3 个函数)

- [ ] **Step 1: 写 5 个失败测试**

在 [tests/scripts/test_neo4j_import.py](../../tests/scripts/test_neo4j_import.py) 末尾追加:

```python
# ---------- Group 4: 表格渲染 ----------

def test_format_props_empty_shows_无():
    """空 dict → '无'"""
    from scripts.neo4j_import import format_props
    assert format_props({}) == "无"


def test_format_props_dict_shows_kv():
    """{k:v} → 'k: v, k: v'"""
    from scripts.neo4j_import import format_props
    assert format_props({"code": 100, "zh": "100mm 机座"}) == "code: 100, zh: 100mm 机座"


def test_render_node_table_chinese_ok():
    """tabulate 输出含中文不抛 UnicodeEncodeError"""
    from scripts.neo4j_import import render_node_table
    nodes = [
        {"name": "测试系列", "labels": ["产品系列"], "props": {"description": "..."}},
        {"name": "机座号", "labels": ["技术参数"], "props": {}},
        {"name": "1A", "labels": ["参数值"], "props": {"code": 100, "zh": "100mm 机座"}},
    ]
    out = render_node_table(nodes)
    assert "测试系列" in out
    assert "机座号" in out
    assert "code: 100" in out


def test_render_node_table_no_props_shows_无():
    """空 props 显示 '无'"""
    from scripts.neo4j_import import render_node_table
    out = render_node_table([{"name": "X", "labels": ["技术参数"], "props": {}}])
    assert "无" in out


def test_render_rel_table_format():
    """关系表格式正确"""
    from scripts.neo4j_import import render_rel_table
    rels = [{"srcName": "型号A", "tgtName": "系列B", "type": "属于", "props": {}}]
    out = render_rel_table(rels)
    assert "型号A" in out
    assert "系列B" in out
    assert "属于" in out
```

- [ ] **Step 2: 跑测试, 验 5 个 FAIL**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -k "format_props or render_" -v
```

预期: 5 个 FAIL (`NotImplementedError`)

- [ ] **Step 3: 实现 3 个函数**

在 [scripts/neo4j_import.py](../../scripts/neo4j_import.py) 中, 把 3 个 NotImplementedError 函数改成:

```python
def format_props(props: dict) -> str:
    """{} → '无', {k:v} → 'k: v, k: v' (跟用户给的例子一致)"""
    if not props:
        return "无"
    return ", ".join(f"{k}: {v}" for k, v in props.items())


def render_node_table(nodes: list[dict]) -> str:
    """渲染节点清单 (序号, 实体名称, 实体类型, 属性)"""
    from tabulate import tabulate
    rows = []
    for i, n in enumerate(nodes, 1):
        rows.append([i, n["name"], "/".join(n["labels"]), format_props(n.get("props", {}))])
    return tabulate(rows, headers=["序号", "实体名称", "实体类型", "属性"], tablefmt="simple")


def render_rel_table(rels: list[dict]) -> str:
    """渲染关系清单 (序号, 源实体, 关系类型, 目标实体, 属性)"""
    from tabulate import tabulate
    rows = []
    for i, r in enumerate(rels, 1):
        rows.append([i, r["srcName"], r["type"], r["tgtName"], format_props(r.get("props", {}))])
    return tabulate(rows, headers=["序号", "源实体", "关系类型", "目标实体", "属性"], tablefmt="simple")
```

- [ ] **Step 4: 跑测试, 验 5 个 PASS**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -k "format_props or render_" -v
```

预期: `5 passed`

- [ ] **Step 5: 提交**

```bash
git add tests/scripts/test_neo4j_import.py scripts/neo4j_import.py
git commit -F /tmp/commit_msg.txt
```

`/tmp/commit_msg.txt`:

```
feat(scripts): 表格渲染 format_props + render_node_table + render_rel_table

- format_props: {} → '无', {k:v} → 'k: v, k: v'
- tabulate 渲染 2 类表格, 含中文不乱码 (项目既有经验)
```

---

## Task 8: TDD `Neo4jClient` 基础 + env 验证

**Files:**
- Modify: `tests/scripts/test_neo4j_import.py` (加 2 测试)
- Modify: `scripts/neo4j_import.py` (实现 `Neo4jClient.__init__`)

- [ ] **Step 1: 写 2 个失败测试**

在 [tests/scripts/test_neo4j_import.py](../../tests/scripts/test_neo4j_import.py) 末尾追加:

```python
# ---------- Group 5a: Neo4jClient 基础 ----------

def test_neo4j_client_constructs_with_all_env(monkeypatch):
    """4 个 env 都设 → 构造成功"""
    from scripts.neo4j_import import Neo4jClient
    monkeypatch.setenv("NEO4J_URI", "neo4j+s://x")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "pw")
    monkeypatch.setenv("NEO4J_DATABASE", "neo4j")
    # 不真连, 传 mock driver
    client = Neo4jClient(driver=None)  # 显式构造, 不读 env
    assert client.uri == "neo4j+s://x"
    assert client.user == "neo4j"
    assert client.password == "pw"
    assert client.database == "neo4j"


def test_neo4j_client_missing_env_raises(monkeypatch):
    """缺 NEO4J_PASSWORD → RuntimeError 提示具体哪个变量"""
    from scripts.neo4j_import import Neo4jClient
    monkeypatch.setenv("NEO4J_URI", "neo4j+s://x")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    monkeypatch.setenv("NEO4J_DATABASE", "neo4j")
    with pytest.raises(RuntimeError, match="NEO4J_PASSWORD"):
        Neo4jClient.from_env()
```

- [ ] **Step 2: 跑测试, 验 2 个 FAIL**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -k "neo4j_client" -v
```

预期: 2 个 FAIL (`Neo4jClient` 不存在)

- [ ] **Step 3: 实现 `Neo4jClient`**

在 [scripts/neo4j_import.py](../../scripts/neo4j_import.py) 中, 替换 `cmd_import` 上方的所有 NotImplementedError, 加入 `Neo4jClient` 类 (在 `cmd_check` 上方):

```python
# ---------- Neo4j 客户端 ----------

class Neo4jClient:
    """封装 neo4j driver, 4 个 env var 缺一报借误

    构造用 Neo4jClient.from_env() 读环境变量; 测试可显式传 driver=None mock.
    """

    def __init__(self, uri: str, user: str, password: str, database: str, driver=None):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self._driver = driver  # 真实环境用 self._connect() 构造

    @classmethod
    def from_env(cls) -> "Neo4jClient":
        """从 NEO4J_* env var 构造, 缺一报 RuntimeError"""
        required = ["NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "NEO4J_DATABASE"]
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            raise RuntimeError(f"缺环境变量: {', '.join(missing)}")
        return cls(
            uri=os.environ["NEO4J_URI"],
            user=os.environ["NEO4J_USER"],
            password=os.environ["NEO4J_PASSWORD"],
            database=os.environ["NEO4J_DATABASE"],
        )

    def _connect(self):
        """懒连接, 第一次用 driver 时才连"""
        if self._driver is None:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
        return self._driver

    def check_apoc(self) -> str:
        """验 APOC 可用, 返回版本号. 失败抛 RuntimeError"""
        driver = self._connect()
        with driver.session(database=self.database) as session:
            try:
                result = session.run("RETURN apoc.version() AS v").single()
            except Exception as e:
                raise RuntimeError(f"APOC 不可用: {e}") from e
        return result["v"]

    def existing_node_names(self, label: str) -> set[str]:
        """查指定 label 下所有节点的 name"""
        driver = self._connect()
        with driver.session(database=self.database) as session:
            result = session.run(f"MATCH (n:`{label}`) RETURN n.name AS name")
            return {r["name"] for r in result if r["name"] is not None}

    def count_nodes_by_label(self, label: str) -> int:
        """查指定 label 的节点数"""
        driver = self._connect()
        with driver.session(database=self.database) as session:
            result = session.run(f"MATCH (n:`{label}`) RETURN count(n) AS c").single()
        return result["c"]

    def run_cypher(self, cypher: str, params: dict) -> None:
        """执行 cypher, 失败透传 Neo4jError"""
        driver = self._connect()
        with driver.session(database=self.database) as session:
            session.run(cypher, **params)
```

- [ ] **Step 4: 跑测试, 验 2 个 PASS**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -k "neo4j_client" -v
```

预期: `2 passed`

- [ ] **Step 5: 跑全套, 验 24 个全过**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -v
```

预期: `24 passed`

- [ ] **Step 6: 提交**

```bash
git add tests/scripts/test_neo4j_import.py scripts/neo4j_import.py
git commit -F /tmp/commit_msg.txt
```

`/tmp/commit_msg.txt`:

```
feat(scripts): Neo4jClient 基础 + 4 env 验证

- from_env() classmethod 读 NEO4J_*, 缺一报 RuntimeError 含具体变量名
- _connect() 懒连接, 真实环境用 GraphDatabase.driver
- check_apoc / existing_node_names / count_nodes_by_label / run_cypher 方法
- 测试用 driver=None mock, 不连真实库
```

---

## Task 9: TDD `dedup_against_neo4j()`

**Files:**
- Modify: `tests/scripts/test_neo4j_import.py` (加 3 测试)
- Modify: `scripts/neo4j_import.py` (实现 `dedup_against_neo4j`)

- [ ] **Step 1: 写 3 个失败测试**

在 [tests/scripts/test_neo4j_import.py](../../tests/scripts/test_neo4j_import.py) 末尾追加:

```python
# ---------- Group 2: dedup_against_neo4j ----------

def test_dedup_filters_existing_param(tmp_config_dir):
    """Neo4j 已有 '机座号' → 该节点 + 关联 3 条 rel 都被剔除"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data, dedup_against_neo4j
    config_dir, _, decoder = tmp_config_dir
    data = yaml_to_graph_data(load_yamls(config_dir), decoder)

    class MockClient:
        def existing_node_names(self, label):
            return {"机座号"} if label == "技术参数" else set()

    new_nodes, new_rels = dedup_against_neo4j(data, MockClient())
    names = {n["name"] for n in new_nodes}
    assert "机座号" not in names
    # 引用 机座号 的 3 条 rel 全部剔除
    rel_endpoints = {(r["srcName"], r["tgtName"]) for r in new_rels}
    for s, t in rel_endpoints:
        assert "机座号" not in (s, t)


def test_dedup_empty_existing_returns_all(tmp_config_dir):
    """Neo4j 空 → 全部算 new"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data, dedup_against_neo4j
    config_dir, _, decoder = tmp_config_dir
    data = yaml_to_graph_data(load_yamls(config_dir), decoder)

    class MockClient:
        def existing_node_names(self, label):
            return set()

    new_nodes, new_rels = dedup_against_neo4j(data, MockClient())
    assert len(new_nodes) == len(data["nodes"])
    assert len(new_rels) == len(data["rels"])


def test_dedup_dedupes_node_names(tmp_config_dir):
    """Python 端已去重过的节点 → dedup 后还是去重的 (不爆重复)"""
    from scripts.neo4j_import import load_yamls, yaml_to_graph_data, dedup_against_neo4j
    config_dir, _, decoder = tmp_config_dir
    data = yaml_to_graph_data(load_yamls(config_dir), decoder)

    class MockClient:
        def existing_node_names(self, label):
            return set()

    new_nodes, _ = dedup_against_neo4j(data, MockClient())
    names = [n["name"] for n in new_nodes]
    assert len(names) == len(set(names))  # 节点 name 都唯一
```

- [ ] **Step 2: 跑测试, 验 3 个 FAIL**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -k "dedup" -v
```

预期: 3 个 FAIL (`NotImplementedError`)

- [ ] **Step 3: 实现 `dedup_against_neo4j()`**

在 [scripts/neo4j_import.py](../../scripts/neo4j_import.py) 中, 把 `dedup_against_neo4j` 改成:

```python
def dedup_against_neo4j(data: dict, client) -> tuple[list[dict], list[dict]]:
    """查 Neo4j 已有节点, 过滤 new_nodes + 剔除引用已存在端点的 rels

    Returns: (new_nodes, new_rels)
    """
    # 收集 4 个 label 的已有 name 并集
    LABELS = ["产品系列", "产品型号", "技术参数", "参数值"]
    existing: set[str] = set()
    for label in LABELS:
        existing |= client.existing_node_names(label)

    # 过滤节点
    new_nodes = [n for n in data["nodes"] if n["name"] not in existing]
    new_node_names = {n["name"] for n in new_nodes}

    # 过滤 rels: 端点必须在 new_node_names 里 (新端点才需要写)
    new_rels = [
        r for r in data["rels"]
        if r["srcName"] in new_node_names and r["tgtName"] in new_node_names
    ]

    return new_nodes, new_rels
```

- [ ] **Step 4: 跑测试, 验 3 个 PASS**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -k "dedup" -v
```

预期: `3 passed`

- [ ] **Step 5: 跑全套, 验 27 个全过**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -v
```

预期: `27 passed`

- [ ] **Step 6: 提交**

```bash
git add tests/scripts/test_neo4j_import.py scripts/neo4j_import.py
git commit -F /tmp/commit_msg.txt
```

`/tmp/commit_msg.txt`:

```
feat(scripts): dedup_against_neo4j() 查 Neo4j 已有, 过滤节点 + 关系

- 4 个 label (产品系列/产品型号/技术参数/参数值) 各查一次, 并集
- 节点按 name 过滤
- 关系按端点必须在 new_nodes 名空间里, 剔除 dangling 端点的关系
```

---

## Task 10: TDD `cmd_check()`

**Files:**
- Modify: `tests/scripts/test_neo4j_import.py` (加 1 测试)
- Modify: `scripts/neo4j_import.py` (实现 `cmd_check`)

- [ ] **Step 1: 写 1 个失败测试**

在 [tests/scripts/test_neo4j_import.py](../../tests/scripts/test_neo4j_import.py) 末尾追加:

```python
# ---------- Group 5b: cmd_check ----------

def test_cmd_check_prints_counts(capsys, monkeypatch):
    """check 子命令打 4 个 label 节点数, 不写库"""
    from scripts.neo4j_import import cmd_check

    class MockClient:
        def check_apoc(self): return "5.20.0"
        def count_nodes_by_label(self, label): return {"产品系列": 0, "产品型号": 0, "技术参数": 0, "参数值": 0}.get(label, 0)

    args = argparse.Namespace()  # cmd_check 不读 args, 但要传
    rc = cmd_check(args, client=MockClient())
    out = capsys.readouterr().out
    assert "APOC 可用" in out
    assert "产品系列" in out
    assert "产品型号" in out
    assert "技术参数" in out
    assert "参数值" in out
    assert rc == 0
```

**注意**: 这个测试 import 了 `argparse`, 在文件顶部已有, 不用加。

- [ ] **Step 2: 跑测试, 验 1 个 FAIL**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -k "cmd_check" -v
```

预期: FAIL (`NotImplementedError`)

- [ ] **Step 3: 实现 `cmd_check()`**

在 [scripts/neo4j_import.py](../../scripts/neo4j_import.py) 中, 把 `cmd_check` 改成:

```python
def cmd_check(args, client=None) -> int:
    """check 子命令: 连通 + APOC + 节点数"""
    if client is None:
        client = Neo4jClient.from_env()
    print(f"[Neo4j 连接成功] uri={client.uri}, database={client.database}")
    version = client.check_apoc()
    print(f"[APOC 可用] apoc.version()={version}")
    LABELS = ["产品系列", "产品型号", "技术参数", "参数值"]
    counts = {label: client.count_nodes_by_label(label) for label in LABELS}
    print(f"[节点数] " + ", ".join(f"{label}: {n}" for label, n in counts.items()))
    return 0
```

- [ ] **Step 4: 跑测试, 验 1 个 PASS**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -k "cmd_check" -v
```

预期: `1 passed`

- [ ] **Step 5: 跑全套, 验 28 个全过**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -v
```

预期: `28 passed`

- [ ] **Step 6: 提交**

```bash
git add tests/scripts/test_neo4j_import.py scripts/neo4j_import.py
git commit -F /tmp/commit_msg.txt
```

`/tmp/commit_msg.txt`:

```
feat(scripts): cmd_check() 子命令 - 连通验证 + APOC + 4 label 节点数

- 支持 client= 参数注入 mock, 测试不连真实库
- 真实环境不传 client, 从 env 构造 Neo4jClient
```

---

## Task 11: TDD `cmd_import()`

**Files:**
- Modify: `tests/scripts/test_neo4j_import.py` (加 2 测试)
- Modify: `scripts/neo4j_import.py` (实现 `cmd_import`)

- [ ] **Step 1: 写 2 个失败测试**

在 [tests/scripts/test_neo4j_import.py](../../tests/scripts/test_neo4j_import.py) 末尾追加:

```python
# ---------- Group 5c: cmd_import ----------

def test_cmd_import_user_says_no_exits_0(capsys, tmp_config_dir, monkeypatch):
    """用户输入 N → exit 0, 不调 run_cypher"""
    from scripts.neo4j_import import cmd_import
    config_dir, _, _ = tmp_config_dir

    class MockClient:
        def check_apoc(self): return "5.20.0"
        def existing_node_names(self, label): return set()  # Neo4j 空
        def run_cypher(self, cypher, params):
            raise AssertionError("不应调用 run_cypher, 用户说 N 了")

    monkeypatch.setattr("builtins.input", lambda _: "n")
    args = argparse.Namespace(config_dir=config_dir)
    rc = cmd_import(args, client=MockClient())
    out = capsys.readouterr().out
    assert "已取消" in out
    assert rc == 0


def test_cmd_import_user_says_yes_writes(capsys, tmp_config_dir, monkeypatch):
    """用户输入 y → 调 run_cypher 1 次"""
    from scripts.neo4j_import import cmd_import
    config_dir, _, _ = tmp_config_dir

    written = []

    class MockClient:
        def check_apoc(self): return "5.20.0"
        def existing_node_names(self, label): return set()
        def run_cypher(self, cypher, params):
            written.append((cypher, params))

    monkeypatch.setattr("builtins.input", lambda _: "y")
    args = argparse.Namespace(config_dir=config_dir)
    rc = cmd_import(args, client=MockClient())
    out = capsys.readouterr().out
    assert rc == 0
    assert len(written) == 1
    assert "已写入" in out
```

- [ ] **Step 2: 跑测试, 验 2 个 FAIL**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -k "cmd_import" -v
```

预期: 2 个 FAIL (`NotImplementedError`)

- [ ] **Step 3: 实现 `cmd_import()`**

在 [scripts/neo4j_import.py](../../scripts/neo4j_import.py) 中, 把 `cmd_import` 改成:

```python
def cmd_import(args, client=None) -> int:
    """import 子命令: load → decode → dedup → table → y/N → cypher"""
    if client is None:
        client = Neo4jClient.from_env()
    client.check_apoc()  # 验证

    # 1. load + decode
    loader = ConfigLoader(config_dir=str(args.config_dir))
    decoder = ProductDecoder(loader)
    yamls = load_yamls(args.config_dir)
    data = yaml_to_graph_data(yamls, decoder)

    # 2. dedup
    new_nodes, new_rels = dedup_against_neo4j(data, client)

    # 3. 表格
    if not new_nodes:
        print("无新数据 (Neo4j 已包含所有节点)")
        return 0
    print(f"\n=== 实体清单 (共 {len(new_nodes)} 条) ===")
    print(render_node_table(new_nodes))
    print(f"\n=== 关系清单 (共 {len(new_rels)} 条) ===")
    print(render_rel_table(new_rels))

    # 4. y/N
    ans = input("\n确认写入 Neo4j? [y/N]: ").strip().lower()
    if ans not in ("y", "Y"):
        print("已取消")
        return 0

    # 5. 写
    cypher, params = build_cypher(new_nodes, new_rels)
    client.run_cypher(cypher, params)
    print(f"已写入 {len(new_nodes)} 节点, {len(new_rels)} 关系")
    return 0
```

- [ ] **Step 4: 跑测试, 验 2 个 PASS**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -k "cmd_import" -v
```

预期: `2 passed`

- [ ] **Step 5: 跑全套, 验 30 个全过**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -v
```

预期: `30 passed`

- [ ] **Step 6: 提交**

```bash
git add tests/scripts/test_neo4j_import.py scripts/neo4j_import.py
git commit -F /tmp/commit_msg.txt
```

`/tmp/commit_msg.txt`:

```
feat(scripts): cmd_import() 子命令 - 端到端 load→dedup→y/N→cypher

- 支持 client= 参数注入 mock, 测试不连真实库
- 5 步流程: load+decode, dedup, 表格, y/N, run_cypher
- 无新数据短路返回 0
- 用户输非 y/Y → "已取消" + exit 0
```

---

## Task 12: TDD `main()` argparse 派发

**Files:**
- Modify: `tests/scripts/test_neo4j_import.py` (加 2 测试)
- Modify: `scripts/neo4j_import.py` (实现 `main`)

- [ ] **Step 1: 写 2 个失败测试**

在 [tests/scripts/test_neo4j_import.py](../../tests/scripts/test_neo4j_import.py) 末尾追加:

```python
# ---------- Group 5d: main argparse ----------

def test_main_check_subcommand(monkeypatch, capsys):
    """main 派发到 cmd_check"""
    from scripts.neo4j_import import main

    class MockClient:
        def check_apoc(self): return "5.20.0"
        def count_nodes_by_label(self, label): return 0

    monkeypatch.setattr("scripts.neo4j_import.Neo4jClient.from_env", classmethod(lambda cls: MockClient()))
    monkeypatch.setattr("sys.argv", ["neo4j_import.py", "check"])
    rc = main()
    out = capsys.readouterr().out
    assert "APOC 可用" in out
    assert rc == 0


def test_main_import_subcommand_user_no(monkeypatch, tmp_config_dir, capsys):
    """main 派发到 cmd_import, 用户说 N → exit 0"""
    from scripts.neo4j_import import main

    class MockClient:
        def check_apoc(self): return "5.20.0"
        def existing_node_names(self, label): return set()

    monkeypatch.setattr("scripts.neo4j_import.Neo4jClient.from_env", classmethod(lambda cls: MockClient()))
    monkeypatch.setattr("sys.argv", ["neo4j_import.py", "import", "--config-dir", str(tmp_config_dir)])
    monkeypatch.setattr("builtins.input", lambda _: "n")
    rc = main()
    out = capsys.readouterr().out
    assert "已取消" in out
    assert rc == 0
```

- [ ] **Step 2: 跑测试, 验 2 个 FAIL**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -k "main_" -v
```

预期: 2 个 FAIL (`NotImplementedError`)

- [ ] **Step 3: 实现 `main()`**

在 [scripts/neo4j_import.py](../../scripts/neo4j_import.py) 中, 把 `main` 改成:

```python
def main() -> int:
    """argparse 入口, 派发到 cmd_check 或 cmd_import"""
    parser = argparse.ArgumentParser(description="YAML 配置 → Neo4j 知识图谱导入")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # check 子命令
    sub_check = subparsers.add_parser("check", help="验 Neo4j 连通 + APOC + 打节点数")

    # import 子命令
    sub_import = subparsers.add_parser("import", help="读 YAML, 查 Neo4j 去重, 表格确认, 写库")
    sub_import.add_argument(
        "--config-dir",
        type=Path,
        default=Path("configs/product_decoders"),
        help="YAML 配置目录 (默认: configs/product_decoders)",
    )

    args = parser.parse_args()

    if args.command == "check":
        return cmd_check(args)
    elif args.command == "import":
        return cmd_import(args)
    else:
        parser.print_help()
        return 1
```

- [ ] **Step 4: 跑测试, 验 2 个 PASS**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -k "main_" -v
```

预期: `2 passed`

- [ ] **Step 5: 跑全套, 验 32 个全过**

```bash
uv run pytest tests/scripts/test_neo4j_import.py -v
```

预期: `32 passed`

- [ ] **Step 6: 跑全项目测试, 验没回归**

```bash
uv run pytest tests/ -v
```

预期: 之前的 120 passed + 7 skipped 不变, 加 32 个新测试全过

- [ ] **Step 7: 提交**

```bash
git add tests/scripts/test_neo4j_import.py scripts/neo4j_import.py
git commit -F /tmp/commit_msg.txt
```

`/tmp/commit_msg.txt`:

```
feat(scripts): main() argparse 派发 check/import 子命令

- subparsers required=True, 缺子命令报错
- import 子命令支持 --config-dir flag
- 32 个测试全过, 不影响既有 120 个测试
```

---

## Task 13: 更新 README.md + 端到端验证

**Files:**
- Modify: `README.md` (加 Neo4j 导入节 + 更新项目结构)

- [ ] **Step 1: 更新 `README.md` 的项目结构树**

打开 [README.md](../../README.md), 在 "1. 项目结构" 节, 更新 `scripts/` 描述, 加 `tests/scripts/`:

```
├── scripts/                             # 一次性脚本
│   ├── neo4j_import.py                  # YAML → Neo4j 知识图谱导入
│   └── ...
├── tests/
│   ├── test_*.py                        # 既有 RAG / product_decoders 测试
│   └── scripts/
│       └── test_neo4j_import.py         # neo4j_import.py 单测
```

- [ ] **Step 2: 加 Neo4j 导入节**

在 README.md 的 "## 4. 测试" 节**之前**, 插入新节 "## Neo4j 导入":

```markdown
## Neo4j 知识图谱导入

把产品配置 YAML 导入在线 Neo4j (Aura) 做知识图谱查询, 4 类节点 + 4 类关系, 跟 Dify LLM 抽取的 schema 对齐.

### 快速开始

```bash
# 1. 注册 Neo4j Aura 免费实例: https://console.neo4j.io
# 2. 复制环境变量模板并填值
cp .env.example .env
# 编辑 .env 填 4 个 NEO4J_* 变量

# 3. 验连通 + APOC
uv run python scripts/neo4j_import.py check

# 4. 导入 (交互式 y/N 确认)
uv run python scripts/neo4j_import.py import
```

### 节点 / 关系 schema

| Label | name 来源 | 示例 |
|---|---|---|
| `产品系列` | YAML `series_name_zh` | 西门子低压系列三相异步电动机 |
| `产品型号` | YAML `examples[].raw` (16 位) | 1LE0001-1AA42-1AA4 |
| `技术参数` | YAML `positions[].name_zh` | 机座号, 极数, 电压 |
| `参数值` | YAML `values{}` 的 key | 1A, 21, A (原始编码) |

| 关系类型 | 源 → 目标 | 来源 |
|---|---|---|
| `属于` | 产品型号 → 产品系列 | 硬连 1 条/example |
| `具有参数` | 产品型号 → 技术参数 | decode 出来的 8 个 enum pos |
| `参数值` | 产品型号 → 参数值 | decode 出来的 8 个具体值 |
| `参数对应` | 参数值 → 技术参数 | 跟 `参数值` 配对 |

### 子命令

- `import` — 读 YAML, 查 Neo4j 去重, 表格确认, 写库
- `check` — 验 Neo4j 连通 + APOC 可用, 打 4 label 节点数
```

- [ ] **Step 3: 端到端手动验证 (用真实 Neo4j, 本步人工)**

```bash
# 跑一次 check
uv run python scripts/neo4j_import.py check

# 预期: 打印 APOC 版本 + 4 label 节点数 (初次: 0/0/0/0)

# 跑一次 import, 输 y
uv run python scripts/neo4j_import.py import
# 实体清单 18 条 + 关系清单 25 条 (用仓库根 configs/, 不是 fixture)
# (configs/product_decoders/motor/siemens/1le0_low_voltage.yaml: 1 系列 + 1 型号 + 8 参数 + 59 值 = 69 节点, 1+8+8+8 = 25 关系)
# 输 y 确认写入

# 再 check 验节点数
uv run python scripts/neo4j_import.py check
# 预期: 1/1/8/59

# 再 import 验幂等
uv run python scripts/neo4j_import.py import
# 预期: "无新数据" 或表格空
```

**注意**: 这一步**不写测试** (依赖外部 Neo4j), 实施工程师手动跑。如果 Neo4j 没注册, 跳过本步, 写个 `MANUAL_VERIFICATION.md` 记录跑法。

- [ ] **Step 4: 跑全套测试, 验最终状态**

```bash
uv run pytest tests/ -v
```

预期: 之前 120 passed + 7 skipped, 加 32 个新测试 = ~152 passed

- [ ] **Step 5: 提交**

```bash
git add README.md
git commit -F /tmp/commit_msg.txt
```

`/tmp/commit_msg.txt`:

```
docs: README 加 Neo4j 导入节 + 更新项目结构

- 新增 "## Neo4j 知识图谱导入" 节: 快速开始 + schema + 子命令
- 项目结构树加 scripts/neo4j_import.py 和 tests/scripts/
- 端到端验证步骤 (check → import → 再 check) 写进 README
```

---

## 验收 (再次列出, 跟 spec 对齐)

- [ ] `uv run python scripts/neo4j_import.py check` 在真实 Neo4j 上打印连接成功 + APOC 可用 + 节点数 (初次应为 0/0/0/0)
- [ ] `uv run python scripts/neo4j_import.py import` 打印实体清单 (69 条: 1 系列 + 1 型号 + 8 参数 + 59 值) + 关系清单 (25 条) + 表格格式跟用户给的例子一致
- [ ] 用户输入 `y` 后写入, 再次 `check` 显示 1/1/8/59 节点
- [ ] 用户输入 `N` 后退出 0, Neo4j 数据不变
- [ ] `uv run pytest tests/scripts/test_neo4j_import.py -v` 全过 (32 用例)
- [ ] 重复跑 `import` 第二次表格显示 "无新数据" 或为空
- [ ] 缺 `NEO4J_PASSWORD` 报清晰借误, exit 1
- [ ] 跨多 YAML 时 (未来加系列) `name` 相同的 技术参数 节点被 APOC merge 合并, 不重复

---

## 风险

| 风险 | 缓解 |
|---|---|
| APOC merge 对动态 label 的限制 | 已选 APOC merge 模板, 实测过类似用法 |
| tabulate 中文乱码 (Windows console 437/GBK) | 项目内既有 tabulate 用法, 测试用 `print` 验中文存在 |
| 真实 Neo4j 没有 APOC | `check_apoc()` 启动验证, 失败清晰报错 |
| YAML 字段缺失 (e.g. 缺 `name_zh`) | `KeyError` 透传, 用户加字段后重跑 |
| Dify LLM 后续抽取的中文术语跟现有 `name_zh` 不一致 | 后续单独设计 "ontology alignment" 子任务, 本期不解决 |
| `examples[].raw` 解码失败 | 测试覆盖 (Task 5 test_yaml_decode_failure_skips_example), 实际跑打印警告到 stderr 跳过该 example |
