# 产品订货号解析器：通用化重构 + outer main.py 接入

**日期**: 2026-06-04
**状态**: 待批准

## Context

`src/server/decoder/` 是项目里新加进来的产品订货号解析服务（基于 FastAPI + YAML 配置驱动），用于把 "1LE0001-1AA42-1AA4" 这类工业产品型号解构成结构化字段，给 Dify 工作流的下游 LLM 节点用。

当前实现（[src/server/decoder/parser.py](../../../src/server/decoder/parser.py)、[src/server/decoder/main.py](../../../src/server/decoder/main.py)）是**单厂商（西门子 1LE0）+ 临时目录结构**的 PoC，**没有整合进项目统一入口**。具体 3 个问题：

1. **相对路径 bug**：`MotorDecoder(config_dir="configs")` 是相对 CWD 的。README 写的启动方式是 `cd decoder && python -m uvicorn main:app`，CWD 此时在 `src/server/decoder/`，会找不到实际位于 `src/server/configs/` 的 YAML。
2. **测试 CWD 依赖**：`src/server/tests/test_decoder.py` 的 `MotorDecoder(config_dir="configs")` 同样依赖 CWD，必须从 `src/server/` 目录运行才能加载到 configs。
3. **YAML 纯字符串 value 不出 `_zh` / `_en`**：现有解析器对 `values` 是 dict 时会展开 `_zh/_en` 字段，但 YAML 里 `mounting`、`winding_protection`、`box_location` 等位的 value 是纯字符串（如 `A: "IM B3"`），结果里就不会有这些后缀字段，与 README schema 示例不符。

**用户 2026-06-04 同步更新了 server 下的代码**（大致逻辑没变）：
- [src/server/configs/siemens/1le0_low_voltage.yaml](../../../src/server/configs/siemens/1le0_low_voltage.yaml)：
  - 删了 `display_separators` 字段（v1.2）
  - 删了 `special_code_1` / `special_code_2` 两位（idx 15, 16）
  - `total_chars: 16`（原 18），positions 减到 9 个
  - 模型字符串从 `1LE0001-1AA4-21AA-4AB` 改为 `1LE0001-1AA42-1AA4`
- [src/server/tests/test_decoder.py](../../../src/server/tests/test_decoder.py)：同步换测试数据为 16 字符
- [src/server/README.md](../../../src/server/README.md)：同步换为 16 字符示例

**附带问题**：
- `src/server/main.py` 是 "Hello, FastAPI!" 占位文件，跟 `src/server/decoder/main.py` 双入口并存，混淆项目主入口。
- `src/server/README.md` 是从别的项目拷过来的 "motor-decoder-template" 模板文档，描述的"项目结构"和"启动方式"全过时。
- 项目外层 `main.py`（[main.py](../../../main.py)）当前只暴露 `process_files()`，没有服务启动模式。

**用户决策**（2026-06-04 brainstorming）：
1. 包名从 `src/server/decoder` 改成 `src/product_decoders`，核心类从 `MotorDecoder` 改成 `ProductDecoder`（因为产品不一定是电机）
2. FastAPI 路由不挂产品名（不出现 `/motor/...`），保持根路径 `/decode`、`/series`、`/health`，加新产品时**只加 YAML 不动 URL**
3. Bug 3 修复走"YAML 全部改成 `{code, zh, en}` dict 形式"路线，**不**走解析器降级路线
4. outer `main.py` 默认走 `serve`（启动产品解析服务），`ingest`（跑 PDF 流水线）改成显式子命令
5. 顺手实现 `format_display()`：按 position 的 `group` 字段把 `1LE00011AA421AA4` 还原成 4 段分组的 `1LE0001-1AA42-1AA4`，在响应里加 `display` 字段
6. `src/server/README.md` 的内容**全部吸收**进仓库根 `README.md`

**已知分歧**：当前 test_decoder.py 的 display 是 `1LE0001-1AA42-1AA4`（3 段，**把 vlt 切成 2+1**），不是 4 段。本 spec 走 4 段不切 vlt 方案，重构时一并修复 test。

## 关键设计

### 1. 目录结构

```text
src/
├── product_decoders/                # 通用产品订货号解析
│   ├── __init__.py                  # 暴露 create_app, ProductDecoder, ConfigLoader
│   ├── app.py                       # FastAPI 工厂 create_app()
│   ├── engine.py                    # ProductDecoder 核心引擎
│   ├── config_loader.py             # ConfigLoader
│   └── configs/
│       └── motor/
│           └── siemens/
│               └── 1le0_low_voltage.yaml   # ← 原文件内容改造
├── rag_ingest/                      # 不动
└── ...

main.py                              # 重写: 默认 serve, 子命令 ingest
README.md                            # 项目根, 合并 src/server/README.md 内容
tests/
└── test_product_decoder.py          # 从 src/server/tests/ 迁过来, 改 pytest 风格
```

**删除**：
- `src/server/main.py`（"Hello, FastAPI!" 占位）
- `src/server/README.md`（与本项目无关的模板文档）
- `src/server/` 整个目录（包括 `decoder/`、`tests/`、`configs/`、`__pycache__/`）

**新增/覆盖**：
- 仓库根 `README.md`（覆盖现有 pyproject 默认生成的 "Add your description here" 占位）

### 2. 核心类重命名 + 拆分

| 旧 | 新 | 说明 |
|---|---|---|
| `MotorDecoder` ([src/server/decoder/parser.py](../../../src/server/decoder/parser.py)) | `ProductDecoder` (src/product_decoders/engine.py) | 类内部已经是通用的（`route()` 按前缀路由），名字直接泛化 |
| `ConfigLoader` ([src/server/decoder/parser.py](../../../src/server/decoder/parser.py)) | `ConfigLoader` (src/product_decoders/config_loader.py) | 不动逻辑，拆到独立文件便于维护 |
| `__init__.py` 暴露 `MotorDecoder, ConfigLoader` | `__init__.py` 暴露 `create_app, ProductDecoder, ConfigLoader` | 公共 API 收敛到工厂模式入口 |

### 3. FastAPI 应用（src/product_decoders/app.py）

```python
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List

from .config_loader import ConfigLoader
from .engine import ProductDecoder

# 锁定绝对路径, 不依赖 CWD
CONFIGS_DIR = Path(__file__).resolve().parent / "configs"


class DecodeRequest(BaseModel):
    model: str = Field(..., description="完整订货号")


class SeriesInfo(BaseModel):
    series: str
    manufacturer: str
    name: str
    prefix: str


def create_app() -> FastAPI:
    """FastAPI 工厂: 测试可用 monkeypatch 注入 CONFIGS_DIR"""
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
        try:
            return decoder.decode(req.model)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"内部错误: {e}")

    @app.get("/series", response_model=List[SeriesInfo])
    async def list_series():
        return decoder.list_series()

    @app.get("/health")
    async def health():
        return {"status": "ok", "series_count": len(decoder.list_series())}

    return app


# 可选: python -m src.product_decoders.app 直接跑（开发用）
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_app(), host="0.0.0.0", port=8000)
```

**关键点**：
- 工厂模式 `create_app()`：测试时可以传不同的 `CONFIGS_DIR`，不必 mock 整个 loader
- 路由不挂产品名：未来加 ABB / 汇川 / 传感器等不同产品类型，**URL 不变**，内部 `ProductDecoder.route()` 按模型前缀选配置
- CORS `allow_origins=["*"]`：**保留**（Dify 跨域调用场景需要；收紧放到未来如果上生产再处理）

### 4. ProductDecoder 引擎（src/product_decoders/engine.py）

逻辑基本从 [src/server/decoder/parser.py](../../../src/server/decoder/parser.py) 平移，**改动 4 处**：

1. **类名** `MotorDecoder` → `ProductDecoder`
2. **构造函数** 接受外部注入的 `ConfigLoader`（不再内部 `self.loader = ConfigLoader(config_dir)`），便于测试
3. **新增 `format_display()`**：按 YAML 里 position 的 `group` 字段做"视觉分组"插横线
4. **`decode()` 末尾** 多写一个 `display` 字段

```python
class ProductDecoder:
    def __init__(self, loader: ConfigLoader):
        self.loader = loader
        self._routing_table: Optional[List[dict]] = None

    # ... route() / _normalize() / decode() 不变, 内部 dict 解析逻辑保持

    def format_display(self, normalized: str, positions: List[dict]) -> str:
        """按 position.group 字段对 normalized 字符串做视觉分组.

        输入: "1LE00011AA421AA4" (16 字符, 标准化后无横线)
        positions 顺序: prefix(g1,6) + eff(g1,1) + frm(g2,2) + pl(g2,1) +
                        ln(g2,1) + vlt(g3,2) + mnt(g4,1) + wnd(g4,1) +
                        box(g4,1)
        → 按 group 边界插横线:
          group1 累计 7 字符后插 → "1LE0001-"
          group2 累计 11 字符后插 → "1LE0001-1AA4-"
          group3 累计 13 字符后插 → "1LE0001-1AA4-21-"
          group4 累计 16 字符 (结尾) 不插
        → "1LE0001-1AA42-1AA4"

        注意: 跟 src/server/tests/test_decoder.py 当前的 display "1LE0001-1AA42-1AA4"
              (3 段, 把 vlt 切成 2+1) 不一致. 本设计走 4 段, 不切电压位.
              重构时一并修复 test_decoder.py 的 display 期望值.

        如果所有 position 都缺 group 字段, 走降级路径: 不插横线, 直接返回 normalized.
        """
        if not any(pos.get("group") for pos in positions):
            return normalized

        # 计算每个 group 累计字符数
        group_boundaries: dict[int, int] = {}  # group 号 → 累计字符数
        cursor = 0
        for pos in positions:
            cursor += pos.get("char_count", 1)
            g = pos.get("group")
            if g is not None and g not in group_boundaries:
                group_boundaries[g] = cursor

        # 在 group 边界 (除最后) 之后插 "-"
        max_g = max(group_boundaries)
        boundaries = sorted(
            pos for g, pos in group_boundaries.items() if pos < len(normalized) and g < max_g
        )
        chars = list(normalized)
        for b in reversed(boundaries):
            chars.insert(b, "-")
        return "".join(chars)
```

**YAML 兼容性**：
- 原有 `display_separators: [6, 8, 10, 11, 13, 14, 15]` 字段**从 YAML 里删掉**（改用 position 级 `group` 字段，更灵活）
- 删掉此字段是**无副作用**的——解析器根本不读 `display_separators` 字段

### 5. Bug 修复映射

| Bug | 修复点 | 修复方式 |
|---|---|---|
| **#1 decoder/main.py 相对路径** | app.py | `CONFIGS_DIR = Path(__file__).resolve().parent / "configs"`，工厂模式构造时传绝对路径 |
| **#2 测试 CWD 依赖** | tests/ | 改为 pytest；`pyproject.toml` 的 `[tool.pytest.ini_options]` 加 `pythonpath = ["src"]` |
| **#3 YAML 纯字符串 value 不出 _zh/_en** | YAML | 把 `1le0_low_voltage.yaml` 所有 enum value 改成 `{code, zh, en}` 形式（详见 §6） |
| **#4 占位 main.py 死代码** | 删除 | 删 `src/server/main.py` |
| **#5 README 模板文档** | 合并 | 吸收到仓库根 `README.md`，详见 §8 |

### 6. YAML 改造：所有 enum value 统一为 `{code, zh, en}` 形式 + position 加 `group` 字段

#### 6.0 position 级 `group` 字段（新增）

每个 position 加 `group: <int>`，从 1 开始递增。**视觉分组相同**的 position 标同一个 group 号。`format_display()` 在 group 累计字符数边界插横线。

Siemens 1LE0 4 段分组示例（**同步用户 2026-06-04 删 special_code 后的 16 字符 / 9 位版本**）：

```yaml
positions:
  # group 1: 1LE0001 (prefix + eff, 7 字符)
  - idx: 1
    name: prefix
    char_count: 6
    type: fixed
    group: 1

  - idx: 7
    name: efficiency_grade
    char_count: 1
    type: enum
    group: 1

  # group 2: 1AA4 (frame + poles + length, 4 字符)
  - idx: 8
    name: frame_size
    char_count: 2
    type: enum
    group: 2

  - idx: 10
    name: poles
    char_count: 1
    type: enum
    group: 2

  - idx: 11
    name: frame_length
    char_count: 1
    type: enum
    group: 2

  # group 3: 21 (voltage, 2 字符)
  - idx: 12
    name: voltage
    char_count: 2
    type: enum
    group: 3

  # group 4: AA4 (mounting + winding + box, 3 字符)
  - idx: 14
    name: mounting
    char_count: 1
    type: enum
    group: 4

  - idx: 15
    name: winding_protection
    char_count: 1
    type: enum
    group: 4

  - idx: 16
    name: box_location
    char_count: 1
    type: enum
    group: 4
```

**group 字段约定**：
- 同一 group 内的 position 必须在 `positions` 列表中**连续**（中间不能有不同 group 插队）
- group 号从 1 开始连续递增
- **不强制**每段字符数对齐——不同产品分组规则可能不同
- **缺 `group` 字段**：`format_display()` 走降级路径，直接返回 normalized 字符串

#### 6.1 `efficiency_grade`（当前 value 已经是 dict，保持不动）

```yaml
"1":
  zh: "高效电动机，中国能效等级 3 级"
  en: "High Efficiency, China Energy Efficiency Grade 3"
```

**问题**：缺 `code`。按用户决策"全部改成 `{code, zh, en}`"，需要补：

```yaml
"1":
  code: "EFF3"
  zh: "高效电动机，中国能效等级 3 级"
  en: "High Efficiency, China Energy Efficiency Grade 3"
```

#### 6.2 `frame_size`（value 是纯数字，不是 dict）

```yaml
# 现状
"1A": 100
"1B": 112

# 改为
"1A":
  code: 100
  zh: "100mm 机座"
  en: "100mm frame"
"1B":
  code: 112
  zh: "112mm 机座"
  en: "112mm frame"
```

**批量生成**：13 个机座号都改。如果某些值用同样的 zh/en 字符串太啰嗦，可以只给 `code` 让解析器把 `code` 同步写到 `zh/en`（YAGNI——一次性改完 13 个不重复也行，参见 §6.5 兜底）

#### 6.3 `poles`（同上）

```yaml
A:
  code: 2
  zh: "2 极"
  en: "2 poles"
B:
  code: 4
  zh: "4 极"
  en: "4 poles"
# ...
```

#### 6.4 `frame_length`（当前 value 已经是 dict，补 `code` 即可）

```yaml
"0":
  code: "S"
  zh: "短机座"
  en: "short"
# ...
```

#### 6.5 `voltage`（当前 value 是纯字符串）

```yaml
"21":
  code: "220△/380Y/50"
  zh: "220V△/380VY 50Hz"
  en: "220V△/380VY 50Hz"
"22":
  code: "230△/400Y/50"
  zh: "230V△/400VY 50Hz"
  en: "230V△/400VY 50Hz"
# ... 共 8 条
```

#### 6.6 `mounting`（纯字符串 → dict，16 条）

```yaml
A:
  code: "IM B3"
  zh: "IM B3 (卧式, 底脚安装)"
  en: "IM B3"
T:
  code: "IM B6"
  zh: "IM B6"
  en: "IM B6"
# ... 共 16 条
```

**取舍**：为了工作量，可只写 `code: "IM B3"`，**不**补 zh/en。`_zh/_en` 字段会缺失但不报错，由调用方按 `code` 字段兜底展示。

#### 6.7 `winding_protection`（纯字符串 → dict，6 条）

```yaml
A:
  code: "NONE"
  zh: "无绕组保护 / without winding protection"
  en: "without winding protection"
# ... 共 6 条
```

#### 6.8 `box_location`（纯字符串 → dict，3 条）

```yaml
"4":
  code: "TOP"
  zh: "置顶 / on top"
  en: "on top"
# ... 共 3 条
```

#### 6.9 解析器对 `{code, zh, en}` 的兼容

现有解析器在 [src/server/decoder/parser.py:148-161](../../../src/server/decoder/parser.py#L148-L161) 已经有 dict 分支：

```python
decoded_val = values[segment]
if isinstance(decoded_val, dict):
    result[pos_name] = (
        decoded_val.get("code")
        or decoded_val.get("zh")
        or decoded_val
    )
    if "zh" in decoded_val:
        result[f"{pos_name}_zh"] = decoded_val["zh"]
    if "en" in decoded_val:
        result[f"{pos_name}_en"] = decoded_val["en"]
```

**完全够用**，**不动**。YAML 改完 value 都是 dict，`code` / `zh` / `en` 三个键都会进 result。

### 7. outer main.py 接口

```python
# main.py
"""RAG 项目统一入口
  uv run python main.py            → 启动产品订货号解析服务 (默认, 端口 8000)
  uv run python main.py ingest     → 跑 PDF 离线流水线
"""
import argparse
import uvicorn

from src.rag_ingest.pipeline import process_files
from src.product_decoders import create_app

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000


def cmd_serve(host: str, port: int, reload: bool) -> None:
    app = create_app()
    uvicorn.run(app, host=host, port=port, reload=reload)


def cmd_ingest() -> None:
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
        # 默认走 serve
        args = parser.parse_args(["serve"])

    kwargs = {k: v for k, v in vars(args).items() if k not in ("mode", "_handler")}
    args._handler(**kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

调用方式：
```bash
uv run python main.py                       # 默认 serve
uv run python main.py serve --port 9000     # 自定义端口
uv run python main.py serve --reload        # 开发模式
uv run python main.py ingest                # PDF 流水线
```

### 8. README 合并策略

仓库根 `README.md` 当前是 `pyproject.toml` 默认创建的占位文件。合并后大致结构：

```markdown
# RAG 项目

## 1. 项目结构
[树状图: rag_ingest/, product_decoders/, configs/, tests/]

## 2. 快速启动
### 2.1 启动产品订货号解析服务（默认）
    uv sync
    uv run python main.py
    curl -X POST http://localhost:8000/decode \
      -H "Content-Type: application/json" \
      -d '{"model": "1LE0001-1AA42-1AA4"}'

### 2.2 跑 PDF 离线流水线
    uv run python main.py ingest

## 3. 产品订货号解析服务
### 3.1 添加新系列
    在 src/product_decoders/configs/<category>/<vendor>/ 下加 YAML
    零代码改动
### 3.2 统一输出 Schema
    (从原 src/server/README.md 搬 JSON 示例)
### 3.3 API 接口
    | POST /decode | GET /series | GET /health |
### 3.4 Dify 接入示例
    (从原 src/server/README.md 搬 Dify 流程图, URL 改 /decode)

## 4. 测试
    uv run pytest tests/

## 5. 开发者规范
    (中文注释, 中文日志, TDD)
```

**原 `src/server/README.md` 内容去向**：
- §快速启动、§运行测试 → 合并到 §2 / §4
- §添加新系列、§API 接口、§Dify 工作流接入、§统一输出 Schema、§解码示例表 → 合并到 §3
- §项目结构 → 合并到 §1
- 旧 README 提到的 `cd decoder && python -m uvicorn main:app` 启动方式 → **删掉**，替换为 `uv run python main.py`

### 9. 测试迁移与扩展

`src/server/tests/test_decoder.py` → `tests/test_product_decoder.py`：

1. 改为 pytest 风格：去掉 `if __name__ == "__main__"`，每个 `def test_xxx` 都是 pytest case
2. 在 `pyproject.toml` 的 `[tool.pytest.ini_options]` 加 `pythonpath = ["src"]`，让 `from src.product_decoders import ...` 工作
3. 新增 / 补充测试用例：
   - **回归 Bug #1**：`create_app()` 在任意 CWD 下都能加载到 configs（测试用 `os.chdir` 到临时目录后实例化）
   - **回归 Bug #3**：每个 enum 位都出 `_zh` / `_en`（覆盖 `efficiency_grade_zh`、`mounting_zh`、`winding_protection_zh` 等）
   - **新增 `format_display`**：`assert result["display"] == "1LE0001-1AA42-1AA4"`（按 YAML 中 `group` 字段做视觉分组，**4 段不切 vlt**；这跟当前 test_decoder.py 的 3 段 display "1LE0001-1AA42-1AA4" 不一致，重构时一并修复）
   - **新增 `display` 在响应顶层**：`POST /decode` 响应 JSON 包含 `display` 字段
4. 现有 6 个测试用例（`test_decode_siemens_1le0` 等）平移过来，**测试数据换成 16 字符 / 9 位的 `1LE0001-1AA42-1AA4`**（同步用户 2026-06-04 删 special_code 后的新模型），断言从字符串改成对应 `code` 字段（如 `assert result["mounting"] == "IM B3"` 对应 `code: "IM B3"`）

### 10. 错误处理

| 场景 | 行为 | HTTP 状态 |
|---|---|---|
| 路由不到任何系列（型号前缀未知） | `ValueError("无法识别型号所属系列")` | 400 |
| 长度不符（标准化后字符数与配置 total_chars 不匹配） | `ValueError("型号长度错误")` | 400 |
| 未知 enum value | 写入 `_warnings`，HTTP 200，Dify LLM 节点兜底解释 | 200 |
| YAML 文件不存在 / 语法错 / 缺 `series` 字段 | `create_app()` 调用时（= uvicorn 启动时） `raise` + uvicorn exit 非零 | — |
| FastAPI 内部未捕获异常 | `Exception` → 500 | 500 |

**`_warnings` 行为保留**：跟现状一致，LLM 节点看到 `_warnings` 时知道是部分已知部分未知，不要硬卡。

## 不在本次范围（YAGNI）

- Pydantic schema 校验 YAML（保持 lenient，未来加）
- CORS 收紧到具体域名（Dify 跨域场景需要 `*`）
- 多语言扩展（zh-CN / en-US 之外的语言）
- 持久化路由缓存（每次 `route()` 都 `load_all()`，单进程够用）
- 鉴权 / API key（Dify 内部网络调用先不加）
- 多次重试 / 熔断 / 限流
- 单独 docker 化

## 实施步骤（详情到 writing-plans 阶段展开）

1. 写 pytest 配置（`pyproject.toml` 加 `pythonpath`） + `tests/test_product_decoder.py` 骨架（先复制粘贴现有 6 个 case 改名）
2. 删 `src/server/`（保留 git reflog 找回）
3. 建 `src/product_decoders/`：`config_loader.py`（平移）+ `engine.py`（重命名 + `format_display` + `display` 字段）
4. 改 `1le0_low_voltage.yaml`（§6 全量改造）
5. 跑 pytest，确认 6 个原 case 仍过（验证平移不破坏行为）
6. 加新 case（§9 第 3 条 4 个新断言），跑 pytest
7. 写 `app.py`（§3 工厂）
8. 写 `main.py`（§7 重写）
9. 手测：`uv run python main.py`，curl `/decode`、`/series`、`/health`
10. 写仓库根 `README.md`（§8 合并）
11. `git commit`

## 风险

- **YAML 改 47 条 value 出错**：用 yaml 解析器 + 现有测试断言兜底；建议写一个一次性的"打印所有 result keys"的调试脚本跑一遍，对照 README schema 示例
- **`group` 字段在 positions 列表里顺序错位**：会导致分段错乱。约定**同 group 必须连续**，在测试 `test_format_display` 里加 `assert all consecutive` 检查（YAGNI——人眼 review YAML 即可，必要时再加校验）
- **`display_separators` 删除后旧 YAML 不识别字段不会报错**（因为解析器不读这个 key），但如果未来有人根据旧 README 复制粘贴配置，会缺失分组逻辑——在 `app.py` 的工厂里加 startup 校验：如果 `display_separators` 出现，log warning（不抛错）

## 测试设计

### 单元测试（快，无外部依赖，进 CI）

按 [feedback-no-mock-for-external-systems](../../../../../.claude/projects/c--Users-abcuc-Desktop-rag/memory/feedback-no-mock-for-external-systems.md) **不 mock 文件系统**：

| 测试函数 | 输入 | 期望 |
|---|---|---|
| `test_decode_siemens_1le0_full` | `1LE0001-1AA42-1AA4` (16 字符) | series=siemens_1le0, manufacturer=Siemens, frame_size.code=100, poles.code=2, frame_length.code=L, voltage.code="220△/380Y/50", mounting.code="IM B3", winding_protection.code="NONE", box_location.code="TOP", display="1LE0001-1AA42-1AA4" |
| `test_decode_with_unknown_value` | `1LE0001-1AA4-99-AA4` | `_warnings` 含 `voltage` 警告, HTTP 200, voltage 字段是 raw "99" |
| `test_unknown_series` | `XYZ12345678901234` | ValueError, HTTP 400 |
| `test_length_error` | `1LE0001-1A` | ValueError, HTTP 400 |
| `test_list_series` | GET /series | 至少 1 条 (siemens_1le0_low_voltage) |
| `test_normalization_3_forms` | `1le0001-1aa4-21-aa4` / `1LE00011AA421AA4` / `  1LE0001 1AA4 21 AA4  ` | 3 个 result 的 `frame_size.code` 都 == 100 |
| `test_format_display` | normalized="1LE00011AA421AA4", positions 含 group 1-4 | display="1LE0001-1AA42-1AA4" |
| `test_format_display_no_group` | normalized="1LE00011AA421AA4", positions 缺 group 字段 | display="1LE00011AA421AA4"（降级路径, 不插横线） |
| `test_create_app_loads_configs_from_any_cwd` | `os.chdir("/tmp")` 后调 `create_app()` | 不抛异常，loader 找到 1 个配置 |
| `test_every_enum_position_emits_zh_en` | 解析 `1LE0001-1AA42-1AA4` | `result["efficiency_grade_zh"]`、`result["mounting_zh"]`、`result["winding_protection_zh"]`、`result["box_location_zh"]`、`result["voltage_zh"]`、`result["frame_size_zh"]`、`result["poles_zh"]`、`result["frame_length_zh"]` 全部非空 |

### 集成测试（可选，本设计范围内不做 e2e）

不需要——服务只解析本地 YAML + 内存计算，无外部系统依赖。FastAPI 路由层的 curl 手测覆盖即可。
