# PDF 表格提取适配器 spec (v1)

**日期**: 2026-07-06
**状态**: 设计待审
**触发来源**: 原 spec [2026-07-02-pdf-pre-analysis-design.md](./2026-07-02-pdf-pre-analysis-design.md) 调研结论存在事实错误 (Camelot 仍在维护, pdfplumber 有 MIT 优势), user 决策扩展 pre-analysis 提取阶段支持多后端可配置.

---

## Context

原 spec §调研结论 写道 (line 236-237):

> - Camelot 2018 年停更, pymupdf 2020 后内置 `find_tables()` 完全替代
> - pdfplumber 跟 pymupdf 重叠, 仅 pymupdf 即可

经 WebFetch 验证 PyPI 实际发布历史, **这两句话都有事实错误**:

### Camelot 实际状态

| 版本 | 发布日期 |
|---|---|
| 0.6.0 | 2018-12-24 |
| 0.7-0.8 系列 | 2019-2020 |
| 0.9.0-0.10.1 | 2021 |
| 0.11.0 | 2023-02-26 |
| 1.0.0 | 2024-12-30 |
| 1.0.9 | 2025-08-10 |
| **2.0.0** | **2026-06-04** (最新, 5 解析器 + bundled pdfium 后端) |

**Camelot 从未停止维护**, 相反 2024 升 1.0, 2025 升 1.0.9, 2026-06 升 2.0 加 ml (Table Transformer) parser.

### pdfplumber 跟 pymupdf 不是同一东西

两者**底层引擎不同, 许可证不同, 性能差异 10-50 倍**:

| 维度 | pdfplumber | pymupdf |
|---|---|---|
| 底层 | 纯 Python (pdfminer.six) | C 库 MuPDF 的 Python binding |
| 许可证 | MIT (宽松) | AGPL (copyleft, 商用需购买) |
| 性能 | 较慢 | 文本 10-50x 快, 渲染 100x |
| 表格 | lines/lines_strict/text/explicit 策略 | `find_tables()` |
| 独有 | 形状对象访问 (.rects/.lines) + 可视化调试 (`to_image` + `debug_tablefinder`) | PDF 创建/编辑 + OCR |

### spec 调研结论错在哪

1. **"Camelot 2018 年停更"** 错 → 误判不需要引入
2. **"pdfplumber 重叠"** 半对 → 但忽视 pdfplumber 独有 shape 对象 + 可视化调试能力
3. **"完全替代"** 强语气 → 但 Camelot 在弱表格线 / 多页表 (`stack_contiguous`) 场景仍有优势
4. **"仅 pymupdf 即可"** 强约束 → 限制 admin 不能针对不同 PDF 选最合适的后端

### 本 spec 目标

**在不破坏现有 pymupdf default 行为的前提下**, 让 admin 在上传 PDF 时**可选地**选择表格提取后端 + 调参, 适应不同 PDF 场景 (机器生成 vs 扫描 vs 弱表格线).

---

## 目标

实现一个 **PDF 表格提取适配器 (Strategy Pattern)**, 让 pre-analysis 的 extract_tables 阶段:

- ✅ 默认仍走 `pymupdf` (0 回归)
- ✅ admin 上传 PDF 时**可选地**选 Camelot / pdfplumber / pymupdf 后端
- ✅ 每个后端有可调参数 (Camelot flavor / edge_tol / row_tol, pdfplumber vertical_strategy / horizontal_strategy / snap_tolerance) — **(2026-07-06 修订) 每个字段配一个问号图标 `?`, 鼠标悬浮显示该字段作用 (走项目 `<AppTooltip>` 封装, 不拼原生 shadcn Tooltip 4 子件)**
- ✅ (2026-07-06 修订) 不持久化到 DB — 默认配置在 yaml, 每次执行按前端发送的 config 跑
- ✅ 任务 summary 记录 `table_backend_used` (admin 详情页能看到本次跑用了哪个后端)
- ✅ 后端未安装 → 清晰错误 (HTTP 503 + 安装指引), 不 500
- ✅ 默认值跟着 yaml 走, admin 不选 → pymupdf + 空参数
- ✅ **(2026-07-06 修订) 阶段化产物渐增可下载** — 每个 stage 跑完立即写自己产物到 ObjectStore + 同步更新 DB `output_files_json`. Admin 详情页能实时看到该阶段已落地部分产物 (chapter / table CSV / flagged paragraphs), 不必等所有阶段跑完. Zip 下载仍仅 completed 状态可用; task 失败时已写部分保留

**非目标 (本期不做)**:
- ❌ 表格 A/B 提取 + 对比 — 后端存哪个用哪个, 不并跑 2 后端对比
- ❌ 用户级默认 — 仅 per-task config, 不存用户偏好
- ❌ 跨页表合并 — 沿用原 spec 限制
- ❌ OCR 后端 — 跟 kreuzberg/mineru 解耦
- ❌ 实时返回 — 沿用 BackgroundTasks 异步
- ❌ 抽 `<AppPdfConfigDialog>` — 高级选项仅 pre-analysis 1 处用, 不满 ≥2 次门槛, 在 upload dialog 内部折叠区即可
- ❌ **(2026-07-06 修订) 不做 Zip 中途下载** — zip 流式组装 + ObjectStore 实盘拼装复杂度高 (CL 了), task running 时 Zip 按钮 disabled, 仅 completed 可下载. 详情页单个产物文件 (chapter_structure.json / page-N-table-M.csv / flagged_paragraphs.csv) 可中途下载
- ❌ **(2026-07-06 修订) 不走 Redis 缓存产物列表** — 每 stage 跑完同步 update DB `output_files_json` (append 1 项), 详情页 query DB 取最新列表. 纯 DB source of truth, 0 cache invalidation. 项目所有 redis 用法 (embed_cache / permission_cache / token_cache) 历来都是 fail-open cache 不是单信息源, 这里同理

---

## 阶段化产物渐增写入 (Stage-by-Stage Streaming Write)

**(2026-07-06 新增需求)**: User 原话 "我希望 pdf 预分析，每个阶段分批生成产物，实时可以点进详情看到部分产物，而不是最后所有阶段分析完一次生成".

### 现状痛点

现行 `_run_pre_analysis` 5 个 stage 串行 (load_config → extract_chapters → extract_tables → extract_flagged → write_outputs), `write_outputs` 是聚合阶段, 直到跑完才把所有 CSV/JSON 一次性写进 ObjectStore. 50 页 D81 PDF 跑 30+ 秒, 期间 admin 进详情页 只能看到 `running` + `current_stage`, **0 产物可下载**, 体验差.

### 新设计 (核心改动)

**关键决策**: 取消聚合 `write_outputs` 阶段对**业务产物**的写入职责, 把每个**业务产物**的写入下沉到对应 stage 完成时:
- `extract_chapters` 跑完 → 立即写 `chapter_structure.json`
- `extract_tables` 跑完 → 立即写 `tables/page-N-table-M.csv` (逐个)
- `extract_flagged` 跑完 → 立即写 `flagged_paragraphs.csv`
- `write_outputs` 阶段**只负责**:`index.json` (1 次) + `summary_json` (1 次) + 跑完通知

每个产物写完立即同步 update DB `output_files_json` (append 1 项), admin 详情页点"刷新"按钮 → GET 端点查 DB → 看到该 stage 已落地产物 + 单文件下载 URL (走现有 `downloadZip` 架构, 加重定向到具体产物 URI).

### 5 Stage 改造前后对比

| Stage | 现状 | 新设计 |
|---|---|---|
| `load_config` | 无产物 | 不变 |
| `extract_chapters` | 不写, 留给 write_outputs | **立即写 `chapter_structure.json`** + append 到 DB output_files_json |
| `extract_tables` | 不写, 留给 write_outputs | **逐表写 `tables/page-N-table-M.csv`** + 每张表 append 1 项到 DB |
| `extract_flagged` | 不写, 留给 write_outputs | **立即写 `flagged_paragraphs.csv`** + append 到 DB |
| `write_outputs` | 聚合 4 个 write 步骤 | **只剩 `index.json` + `summary_json` + update `task_config_json` + mark_completed** |

### DB Schema 影响

**0 schema 改动**: `output_files_json: Text` 已存在, 复用. Stage 跑完 → 增量 append 该 stage 产物项. 详情页 query 整个 DB 列, 看到所有已落地产物.

### 详情页 UI 改动

`/admin/pre-analysis/[task_id]` 页面表格 (`output_files`):

- **现状**: task running 时表格全空 (DB output_files_json 只有空)
- **新**: task running 时表格**已落地的部分** (chapter / 已写 tables / flagged), 每项独立"下载"按钮指向该文件 URI
- 增加 1 个"刷新"按钮 (不轮询, 用户手动点, 跟现有"刷新任务列表"按钮一致风格)
- "下载 ZIP" 按钮: task state=completed 时 enabled; running 时 disabled, hover 提示"任务未完成, 请等待或下载已落地部分产物"

### 中途失败处理 (用户决策 2026-07-06)

- **task state=failed**, **部分产物保留**: stage N 失败时, 前面 stage 1..N-1 已写产物**保留在 ObjectStore**, DB `output_files_json` 保留已 append 项. Admin UI 明标 "部分产物 (做到 stage X 失败) X / Y"
- 重试按钮 (现有): 重跑整个 task, 当前 `state=failed` → pending. 老的 failed task 不删, admin 启动新 retry task
- ObjectStore 不自动删已写产物 (admin 手动 / 任务过期清理 cron), 跟现有 ingest_tasks 失败保留逻辑一致

### Index.json 写入时机 (用户决策 2026-07-06)

**index.json 仅任务结束后写 1 次** (final snapshot 含全部产物清单). 详情页 running 状态头部提示"index.json 将在任务完成后生成". index 是 final manifest 语义, 渐增写会导致 UI 多次重画同一处不一致.

### Zip 下载时机 (用户决策 2026-07-06)

**zip 仅 task=completed 可下载**. running 状态按钮 disabled. 不做"打包部分产物 zip" streaming 复杂度.

### 不轮询策略 (用户决策 2026-07-06)

- **前端不轮询**, 详情页只接受手动刷新按钮
- 后端不主动 push (无 WebSocket)
- 每次刷新 = 1 次 DB 读 (走现有 `load_task` 路径), 不烧 IO

### Stage 内产物 append 写入事务考虑

**风险**: stage N 跑完, put_object_store 成功 + DB UPDATE 失败 (极端 crash 中间) → DB output_files_json 缺该项, 但 ObjectStore 多一个孤儿文件.

**取舍** (用户原话隐含): 本期不加事务包裹 (CLAUDE.md 禁止复杂兜底, shim) — 接受这个 0.01% 级孤儿风险; admin 手测如果发现 DB/ObjectStore 不一致, 跑 ObjectStore list_prefix 对照 DB 即可. 未来 spec 加 reconciliation cron.

### 此需求对本 spec 文件影响清单

影响以下章节需改:

1. §架构设计 - 加 `streaming write` 数据流段
2. § 阶段化产物渐增写入 - **新增整段** (本节即此)
3. § 数据模型 - 已 0 schema 改动, 加 1 段说明 append 语义
4. § API 协议 - 加 `POST /api/pre-analysis/tasks/{id}/artifacts/refresh` 或直接复用 GET /tasks/{id} 不变 (DB 是单源)
5. § 前端 UI - 详情页加"刷新"按钮 + 每产物独立下载 URL
6. § 错误处理 - 新增"中途失败保留部分产物"行
7. § 测试隔离 - 新增 stage 写产物即时性测试
8. § 实施拆分 - 拆分到具体 milestone
9. § 不要做的事 - 加 2 条 (无 Redis cache / 无 Zip streaming)
10. § Goals - 加 1 条 stage-by-stage 渐增可下载 ✓ 已加

---

## 架构设计 (Strategy Pattern)

### 后端目录布局 (增量)

**(2026-07-06 修订) `pre_analysis` 模块子包化**: 不再把 `pre_analysis_*` 文件散在 `src/ingest/` 顶层, 改为独立 `src/ingest/pre_analysis/` 子包. 原因:
- 现有 `src/ingest/` 顶层有 `analyzers/` `converters/` 子包 (CLAUDE.md §业务模块拆分原则), `pre_analysis_*` 5 文件夹在顶层混在 `api.py` / `store.py` 等不同模块之间不易扫
- sub-package 后命名统一: `pre_analysis/` 内文件不再带前缀 (`pre_analysis_models.py` → `models.py` 等), 由子包名承担命名空间
- 测试同步移到 `tests/ingest/pre_analysis/` 子目录, 跟 src/ 镜像

迁移规则:
- `pre_analysis_models.py` → `pre_analysis/models.py`
- `pre_analysis_store.py` → `pre_analysis/store.py`
- `pre_analysis_runner.py` → `pre_analysis/runner.py`
- `pre_analysis_stage_models.py` → `pre_analysis/stage_models.py`
- `pre_analysis_stage_store.py` → `pre_analysis/stage_store.py`
- 新增 `pre_analysis/__init__.py` (重导出 PreAnalysisTask / PreAnalysisTaskStore / PreAnalysisRunner / PreAnalysisStage / PreAnalysisStageStore 给 `src/ingest/api.py` 用)
- 包内 import 全部简化: `from .pre_analysis_models import PreAnalysisTask` → `from .models import PreAnalysisTask`
- `src/ingest/api.py` import 改: `from .pre_analysis import PreAnalysisRunner, PreAnalysisTaskStore, ...`
- `tests/ingest/test_pre_analysis_*.py` 移到 `tests/ingest/pre_analysis/test_*.py`, import 改 `from src.ingest.pre_analysis import ...`
- **alembic metadata 反射不影响**: 现有 migration 文件名 (`20260702_000000_pre_analysis_tasks.py`) 不动, 重命名 migration 是独立 spec (避免引入新 revision 跟现有漂移); 新 migration (`20260706_000000_pre_analysis_task_config.py`) 同样位置不动
- 改动**纯重命名 + 路径调整**, 0 业务改动, 1 个独立 commit 走 `refactor(service): move pre_analysis_* to subpackage pre_analysis/`

```
packages/service/
├── configs/
│   └── pre_analysis/
│       ├── rule_keywords.yaml                          # [现有] 关键词白名单
│       └── table_extraction.yaml                      # [新] 表格后端配置 + 默认 params
├── src/
│   ├── ingest/
│   │   ├── pre_analysis/                               # [新子包] pre_analysis 模块独立化 (2026-07-06 修订)
│   │   │   ├── __init__.py                            #     [新] 重导出 PreAnalysisTask + PreAnalysisTaskStore + PreAnalysisRunner + PreAnalysisStage + PreAnalysisStageStore
│   │   │   ├── models.py                               #     [改/移] 原 pre_analysis_models.py 加 task_config_json 列
│   │   │   ├── store.py                                #     [改/移] 原 pre_analysis_store.py _to_dict 透传 + mark_completed 写 task_config_json
│   │   │   ├── runner.py                               #     [改/移] 原 pre_analysis_runner.py 注入 TableExtractor + 跑完回写 task_config_json
│   │   │   ├── stage_models.py                         #     [移] 原 pre_analysis_stage_models.py (5-stage ORM)
│   │   │   ├── stage_store.py                          #     [移] 原 pre_analysis_stage_store.py (5-stage state machine facade)
│   │   │   └── table_extractors/                      #     [新] Strategy Pattern 文件夹
│   │   │       ├── __init__.py                         #         [新] factory 重导出
│   │   │       ├── base.py                             #         [新] TableExtractor ABC + TableData + BackendNotInstalledError
│   │   │       ├── pymupdf_extractor.py                #         [新] pymupdf 适配器 (复用已打开 doc 优化)
│   │   │       ├── camelot_extractor.py                #         [新] camelot 适配器 (lazy import, BackendNotInstalledError)
│   │   │       ├── pdfplumber_extractor.py             #         [新] pdfplumber 适配器 (lazy import, BackendNotInstalledError)
│   │   │       └── factory.py                          #         [新] get_table_extractor 工厂
│   │   ├── api.py                                      # [改] upload 接受 table_backend + table_params form, 内 import 改 from .pre_analysis import ...
│   │   ├── store.py                                    # [不动] ingest task store, 跟 pre_analysis 解耦
│   │   ├── models.py                                   # [不动] IngestTask ORM, 跟 pre_analysis 解耦
│   │   ├── pipeline.py                                 # [不动] 主流水线
│   │   └── analyzers/ converters/ ...                  # [不动] 其他子包
│   └── storage/
│       └── migrations/
│           └── versions/
│               ├── 20260702_000000_pre_analysis_tasks.py            # [不动] 已有 migration (迁移名跟表名一致, 不动)
│               ├── 20260703_000000_pre_analysis_task_stages.py      # [不动] 已有 migration
│               └── 20260706_000000_pre_analysis_task_config.py      # [新] 加 task_config_json 列 migration
└── tests/
    └── ingest/
        └── pre_analysis/                               # [新子目录] 镜像 src/ingest/pre_analysis/
            ├── __init__.py                             #     [新] (可选) 包标记
            ├── test_models.py                          #     [移] 原 tests/ingest/test_pre_analysis_models.py
            ├── test_store.py                           #     [移] 原 tests/ingest/test_pre_analysis_stage_store.py (对齐 src 文件名)
            ├── test_runner.py                          #     [移] 原 tests/ingest/test_pre_analysis_runner.py 加 2 测试: 指定 backend + cross_page 拆分
            ├── test_api.py                             #     [移] 原 tests/ingest/test_pre_analysis_api.py 加 4 测试: form 字段 + 校验
            └── table_extractors/                       #     [新] 5 测试文件, 镜像 src/.../table_extractors/ 结构
                ├── __init__.py                         #         [新] (可选)
                ├── test_base.py                        #         [新] TableData + TableExtractor ABC 接口契约
                ├── test_pymupdf_extractor.py           #         [新] 2 测试: 复用 doc + 自身开 doc
                ├── test_camelot_extractor.py           #         [新] 2 测试: 真实 PDF 调用 + lazy import 缺包抛 BackendNotInstalledError
                ├── test_pdfplumber_extractor.py        #         [新] 2 测试: 真实 PDF 调用 + lazy import 缺包抛 BackendNotInstalledError
                └── test_factory.py                     #         [新] 4 测试: 3 backend 路由 + 未知 backend ValueError
```

**子包独立化 commit 在 M0** (跟现有 5 commits 之前, 单独 1 commit):
- 文件 git mv (rename detection 准确), import 路径全量替换
- 跑 `uv run pytest` 0 新 fail (0 业务改动, 改名而已)
- 不动 alembic migration (改名是 ORM 反射无关)

**为什么不合并到 M1**: 子包化是 infra 重构, 跟 task_config_json 新列两件事; 分 2 commit 减少 review surface + 容易 bisect 回滚.

### 前端目录布局 (增量)

```
packages/web/
└── app/[locale]/admin/pre-analysis/
    └── _components/
        ├── pre-analysis-upload-dialog.tsx             # [改] 加 "高级选项" 折叠区 + AppSelect 后端选择 + 动态参数 UI
        └── pre-analysis-upload-dialog.test.tsx        # [改] 4 旧测试更新 + 3 新测试

```

### TableExtractor 接口 (Strategy)

**目录布局 (2026-07-06 修订)**: 不再 `table_extractors.py` 单一文件, 改 `table_extractors/` 文件夹, 3 适配器各自一个文件, ABC + factory 拆开:

```
src/ingest/table_extractors/
├── __init__.py                # 重导出: from .base import TableExtractor, TableData
│                              #        from .pymupdf_extractor import PymupdfTableExtractor
│                              #        from .camelot_extractor import CamelotTableExtractor
│                              #        from .pdfplumber_extractor import PdfplumberTableExtractor
│                              # 重导出 factory: from .factory import get_table_extractor
├── base.py                    # TableData + TableExtractor ABC + NotInstalledError
├── pymupdf_extractor.py       # PymupdfTableExtractor 实现
├── camelot_extractor.py       # CamelotTableExtractor + lazy import + CamelotNotInstalledError
├── pdfplumber_extractor.py    # PdfplumberTableExtractor + lazy import + PdfplumberNotInstalledError
└── factory.py                 # get_table_extractor(backend, params) 工厂函数
```

#### `base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class TableData:
    """单张表格单元. 3 个实现统一这个 shape, 让 runner 不关心后端."""
    page_no: int              # 1-based
    table_no: int             # 1-based (per page)
    rows: list[list[str]]     # 二维字符串表格


class TableExtractor(ABC):
    @abstractmethod
    def extract(
        self,
        pdf_path: str,
        *,
        _pymupdf_doc: "pymupdf.Document | None" = None,  # 给 pymupdf 后端复用已打开 doc
        **params: object,
    ) -> list[TableData]:
        """提取所有表格. PDF 无表格 → 返 []."""
        ...


class BackendNotInstalledError(RuntimeError):
    """后端 Python 包未安装. factory 调用时检测, 503 翻译用."""
    def __init__(self, backend: str, install_hint: str) -> None:
        super().__init__(f"{backend} 未安装: {install_hint}")
        self.backend = backend
        self.install_hint = install_hint
```

#### `factory.py`

```python
def get_table_extractor(backend: str, params: dict | None = None) -> TableExtractor:
    """工厂. 缺包 → 抛 BackendNotInstalledError (HTTP 503 翻译).
    
    Args:
        backend: "pymupdf" | "camelot" | "pdfplumber"
        params: backend-specific 参数 (flavor / edge_tol / vertical_strategy 等)
    
    Returns:
        TableExtractor 实例 (PymupdfTableExtractor / CamelotTableExtractor / PdfplumberTableExtractor)
    
    Raises:
        ValueError: backend 不在白名单
        BackendNotInstalledError: backend 选了 camelot/pdfplumber 但 Python 包没装
    """
    match backend:
        case "pymupdf":
            from .pymupdf_extractor import PymupdfTableExtractor
            return PymupdfTableExtractor(params or {})
        case "camelot":
            from .camelot_extractor import CamelotTableExtractor
            return CamelotTableExtractor(params or {})
        case "pdfplumber":
            from .pdfplumber_extractor import PdfplumberTableExtractor
            return PdfplumberTableExtractor(params or {})
        case _:
            raise ValueError(f"未知表格后端: {backend}")
```

3 个适配器各自一个文件:

| 文件 | 类 | 包依赖 | 关键逻辑 |
|---|---|---|---|
| `pymupdf_extractor.py` | `PymupdfTableExtractor` | `pymupdf` (已装) | 优先复用 `_pymupdf_doc`, 否则 `pymupdf.open(pdf_path)`. 遍历 `page.find_tables().tables[].extract()` |
| `camelot_extractor.py` | `CamelotTableExtractor` | `camelot-py>=2.0` (基础, 见 §安装决策表) | `camelot.read_pdf(path, flavor=..., edge_tol=..., row_tol=...)`. `.df.values.tolist()`. Lazy import, 包缺失 → 抛 `BackendNotInstalledError(backend="camelot", install_hint="uv add camelot-py")`. **额外**: 构造时检查 params 是否含 `flavor='ml'` + try `import camelot._...` 模块特定符号确认 `[ml]` extra 装了; 若 flavor='ml' 但 [ml] 缺 → 抛 `BackendNotInstalledError(backend="camelot[ml]", install_hint="uv add 'camelot-py[ml]'")` (不同 install_hint 让 admin 知道要装哪个 extra) |
| `pdfplumber_extractor.py` | `PdfplumberTableExtractor` | `pdfplumber>=0.11` (可选) | `pdfplumber.open(path)`, `page.extract_tables(table_settings={...})`. Lazy import, 包缺失 → 抛 `BackendNotInstalledError` |

**为什么 3 个适配器各自一个文件** (用户原话 2026-07-06): 一个后端一个文件, 加新后端时只动 `factory.py` + 加 1 文件, 不碰其他适配器代码, 符合 CLAUDE.md "每个函数职责单一" 原则.

**为什么 pymupdf 后端要复用 doc**: runner 同时用 pymupdf 做章节提取 + 关键词段落, 后端硬切换会让 camelot/pdfplumber 多开一次 PDF + 加内存.

**为什么 camelot/pdfplumber 走 try/except lazy import**: 模块级 catch ImportError, 包缺失时只在 admin 选这个后端时才报错. dev 主环境干净, 避免污染 pyproject.toml 主依赖.

---

## 数据模型

**核心理念 (2026-07-06 修订)**: 不在 upload 时持久化 config, runner 跑完才写 1 次执行快照 → 用户原话 "不需要持久化, 只需要有一个默认的配置, 然后每次执行按发送的配置执行". 这样:
- Upload 路径 0 校验复杂度 (前端的 form 字段直接 in-memory 传给后台任务)
- 默认配置在 yaml, 前端不发或后端遗漏走 yaml
- DB 仅记录 "本次跑用了什么" 用于详情页展示, 不参与主流程

### Alembic migration (2026-07-06)

`src/storage/migrations/versions/20260706_000000_pre_analysis_task_config.py`:

```python
def upgrade() -> None:
    op.add_column(
        "pre_analysis_tasks",
        sa.Column(
            "task_config_json",
            sa.Text,
            nullable=False,
            server_default="{}",   # 默认空 dict, 兼容 existing rows
        ),
    )

def downgrade() -> None:
    op.drop_column("pre_analysis_tasks", "task_config_json")
```

`down_revision = "20260703_000000"` (上一条 pre_analysis migration).

**字段形状** (Text NOT NULL, runner 跑完写 1 次):
```json
{}
{"table_backend": "pymupdf", "table_params": {}}
{"table_backend": "camelot", "table_params": {"flavor": "stream", "edge_tol": 80}}
{"table_backend": "pdfplumber", "table_params": {"vertical_strategy": "lines"}}
```

注意:
- 列名 `task_config_json` (不是 `table_extraction_config_json`): 保留通用性, 未来其他模块也能复用这个 JSON 列 (e.g. OCR 选项 / 分块策略)
- `nullable=False` + `server_default="{}"` → existing rows 是 `{}` 而不是 NULL, 0 迁移风险
- 跑前 `{}` → 跑完由 runner 写实际生效的 config (含 yaml 默认值 backend + admin 选择 params)
- 用 `sa.Text` + JSON 字符串 (跟 `output_files_json` / `summary_json` 一致); 改 JSONB 是独立 spec

### ORM 更新

`src/ingest/pre_analysis_models.py`:

```python
task_config_json: Mapped[str] = mapped_column(
    Text,
    nullable=False,
    server_default="{}",
    default="{}",
)
```

### Store 更新

`src/ingest/pre_analysis_store.py`:

- `_to_dict()` 增加 `task_config_json` 字段透传 (`json.loads` 反序列化)
- `save_task()` 不动 (新列有 server_default, 不传走默认值)
- `mark_completed()` 跑完写 task_config_json: 在原 `output_files + summary` 写入后追加 `task_config_json={实际生效的 config}`
- `load_task()` 透传即可, runner 不读 (runner 通过 in-memory 拿 config)

---



`configs/pre_analysis/table_extraction.yaml`:

```yaml
# 表格后端默认配置 (2026-07-06)
# Admin 上传时不显式选 → 走 pymupdf + 默认参数.
# 改此文件需重启 service, _register_extractors 在 import 阶段读一次.

default_backend: pymupdf

backends:
  pymupdf:
    enabled: true              # 已安装, 无需额外配置
    module_check: "pymupdf"
    install_hint: ""           # 已装, 不需要

  camelot:
    enabled: false             # dev 默认禁用, 需要时改 true
    module_check: "camelot"
    # 安装规则 (1 条记住): uv add camelot-py (不加 extra) 已够 lattice/stream/network/hybrid 4 个 flavor;
    #                     仅 admin 显式选 flavor='ml' 时才补 uv add 'camelot-py[ml]' (拉 PyTorch)
    install_hint: "uv add camelot-py"
    ml_install_hint: "uv add 'camelot-py[ml]'   # 仅 flavor='ml' 需要 (PyTorch 拉 +500MB)"

  pdfplumber:
    enabled: false             # dev 默认禁用, 需要时改 true
    module_check: "pdfplumber"
    install_hint: "uv add pdfplumber"

# 各后端默认参数 (admin 上传时未指定 → 这里取)
default_params:
  pymupdf: {}

  camelot:
    flavor: "lattice"          # lattice | stream | network | hybrid | ml (ml 需 [ml] extra + PyTorch)
    edge_tol: 50               # 边容差 (像素)
    row_tol: 2                 # 行容差

  pdfplumber:
    vertical_strategy: "lines"  # lines | lines_strict | text | explicit
    horizontal_strategy: "lines"
    snap_tolerance: 3          # 像素
    join_tolerance: 3          # 像素
```

### 安装决策表 (用户认知辅助, 1 页纸看明白)

| Admin 上传选择 | 后端 | 安装命令 (未装时) | 备注 |
|---|---|---|---|
| 默认 / 不展开高级选项 / 后端 = `pymupdf` | pymupdf | `(无需装, 已在项目)` | 0 额外依赖 |
| 后端 = `camelot`, flavor = `lattice` / `stream` / `network` / `hybrid` / 未指定 | camelot | `uv add camelot-py` | 默认装就够 (Camelot 2.0 pdfium bundled, 0 系统依赖) |
| 后端 = `camelot`, flavor = `ml` | camelot [ml] | `uv add 'camelot-py[ml]'` | 额外拉 PyTorch (~500MB); 处理弱表格线 / 扫描件 |
| 后端 = `pdfplumber` | pdfplumber | `uv add pdfplumber` | 纯 Python, MIT 许可证 |
| 后端 = `camelot + flavor=ml` + pdfplumber | 二者都装 | `uv add 'camelot-py[ml]' pdfplumber` | ml 涵盖 camelot-py 全部依赖, 写一个命令拉齐 |

**FAQ**: "是不是要装 2 个?" — 不, 只装 1 个就够. `camelot-py` 已经覆盖非 ml flavor, 只有 ml flavor 才补 `[ml]`. 不要提前装 `[ml]` 避免无谓的 500MB.

### Lazy 模块检测

```python
def _camelot_available() -> bool:
    try:
        import camelot  # noqa: F401
        return True
    except ImportError:
        return False
```

后端 `enabled` 跟实际 `module_check` AND: enabled=false → 即使装了也不让 admin 选; enabled=true + 模块缺失 → 返 install_hint 503.

(简化版: 只看 module 是否能 import, 不读 yaml 的 enabled — admin 想要装哪个就装哪个, 运行时 lazy 检测.)

---

## API 协议

### `POST /api/pre-analysis/upload` (现有端点增量)

**multipart/form-data**:

| 字段 | 类型 | 必填 | 默认 |
|---|---|---|---|
| `file` | File (.pdf) | ✅ | — |
| `table_backend` | str ("pymupdf" \| "camelot" \| "pdfplumber") | ❌ | "pymupdf" |
| `table_params` | str (JSON 字符串) | ❌ | "{}" |

**请求示例** (选 camelot + flavor=stream):

```
POST /api/pre-analysis/upload
Content-Type: multipart/form-data; boundary=...

--boundary
Content-Disposition: form-data; name="file"
Content-Type: application/pdf

<PDF binary>
--boundary
Content-Disposition: form-data; name="table_backend"

camelot
--boundary
Content-Disposition: form-data; name="table_params"

{"flavor": "stream", "edge_tol": 80}
--boundary--
```

**响应 (200 OK)** (跟现有 shape 一致):

```json
{
  "task_id": "pa-3f8c2e1a",
  "state": "pending",
  "pdf_filename": "D81.1.pdf"
}
```

**错误**:

| 状态码 | detail | 触发 |
|---|---|---|
| 400 | "未知表格后端: {backend}" | backend ∉ {pymupdf,camelot,pdfplumber} |
| 400 | "table_params JSON 非法: {err}" | table_params 解析失败 |
| 413 | "PDF > 100MB" | 现有逻辑 |
| **503** | "{backend} 未安装: {install_hint}" | 选了 camelot/pdfplumber 但缺包 |

503 是新增 — 让前端能区分"配置错误" vs "包缺失", 给用户装包指引.

### `_run_pre_analysis` 流水线

```
upload 端点接收 {table_backend, table_params}
  → 解析 form → table_config = {"table_backend": ..., "table_params": ...}
  → background.add_task(_run_pre_analysis, task_id, table_config)   # in-memory 传, 不存 DB

_run_pre_analysis(task_id, table_config):
  task = load_task(task_id)        # 拿 pdf_uri
  runner.run(task_id, pdf_uri, table_config=table_config)            # in-memory 传
    → load_config stage (无产物)
    → extract_chapters stage
        → 写 chapter_structure.json (ObjectStore)
        → update DB: append 1 项 {kind: chapter_structure, uri, filename, size_bytes}  # ★ 渐增可见
        → mark_stage_completed
    → extract_tables stage
        → 写 tables/page-1-table-1.csv (ObjectStore) → DB append 1 项
        → 写 tables/page-2-table-1.csv             → DB append 1 项
        → ...每张表都写完都 append DB...            # ★ admin 详情页能实时看到已写表
        → mark_stage_completed
    → extract_flagged stage
        → 写 flagged_paragraphs.csv (ObjectStore) → DB append 1 项
        → mark_stage_completed
    → write_outputs stage
        → 写 index.json (snapshot, 仅 completed 时有)  # ★ 仅此处写
        → mark_completed(summary, output_files, task_config_json)
        → output_files_json = 累计已落地的所有产物 (阶段化 append 累积)
        → task_config_json = table_config (执行快照)
        → summary_json = {total_chapters, total_tables, total_flagged, elapsed_ms, cross_page_candidates}
  → detail: detail result 表 task_config_json 列存本次实际生效的 config
```

参见 § 阶段化产物渐增写入 了解设计 rationale / 边界条件 / 风险取舍.

---

## 前端 UI

### 弹框"高级选项"折叠区

文件: `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx`

布局: 保持现有 3 段式 (FileDropzone / 文件信息 / 上传按钮) 不变, 在 FileDropzone 区域下方插入可折叠的 `Accordion` (shadcn):

```
┌──────────────────────────────────────────────────────────┐
│ 上传 PDF                                                  │
├──────────────────────────────────────────────────────────┤
│ ⬇ [拖文件到这]                                            │
│   或 [点击选择 .pdf 文件]                                  │
├──────────────────────────────────────────────────────────┤
│ ▶ 高级选项 (默认折叠)                                      │ ← 新增折叠区
├──────────────────────────────────────────────────────────┤
│                            [取消]  [开始上传]              │
└──────────────────────────────────────────────────────────┘
```

展开后:

```
┌──────────────────────────────────────────────────────────┐
│ ▼ 高级选项                                                │
├──────────────────────────────────────────────────────────┤
│ 表格后端    [ PyMuPDF ▾ ]                                  │
│                                                          │
│  ── pymupdf 显示: ──                                      │
│  ℹ 使用 PyMuPDF 内置 find_tables(), 无需额外配置           │
│                                                          │
│  ── camelot 显示: ──                                      │
│  Flavor        [ lattice ▾ ]                              │
│  Edge Tol      [ 50 ]                                     │
│  Row Tol       [ 2  ]                                     │
│                                                          │
│  ── pdfplumber 显示: ──                                   │
│  Vertical Strategy     [ lines     ▾ ]                   │
│  Horizontal Strategy   [ lines     ▾ ]                   │
│  Snap Tolerance        [ 3      ]                        │
│  Join Tolerance        [ 3      ]                        │
├──────────────────────────────────────────────────────────┤
│                            [取消]  [开始上传]              │
└──────────────────────────────────────────────────────────┘
```

### 状态管理

```typescript
type TableBackend = "pymupdf" | "camelot" | "pdfplumber";

const [showAdvanced, setShowAdvanced] = useState(false);
const [backend, setBackend] = useState<TableBackend>("pymupdf");
const [params, setParams] = useState<Record<string, string | number>>({});

useEffect(() => {
  // 切换 backend 时重置 params 到该 backend 的默认值
  switch (backend) {
    case "pymupdf":
      setParams({});
      break;
    case "camelot":
      setParams({ flavor: "lattice", edge_tol: 50, row_tol: 2 });
      break;
    case "pdfplumber":
      setParams({ vertical_strategy: "lines", horizontal_strategy: "lines", snap_tolerance: 3, join_tolerance: 3 });
      break;
  }
}, [backend]);
```

`handleUpload` 把 config 加进 `preAnalysisUpload` 调用:

```typescript
await preAnalysisUpload(pickedFile, { backend, params });
```

### 关键 UI 选择 (跟现有规则一致)

- **折叠区**: 用 shadcn `<Accordion>` 1 type="single" collapsible (默认 collapsed)  — 不抽新包装, shadcn Accordion 已够简单
- **Backend 选择**: 用项目 `<AppSelect>` ([components/common/input/app-select.tsx](../../packages/web/components/common/input/app-select.tsx)) — 不写 shadcn Select 6 行模板
- **Param 输入**: 用 shadcn `<Input>` (跟现有 dialog `<Input type="number">` 风格一致)
- **Flavor/Strategy 策略选项**: 也用 `<AppSelect>` — 跟 backend 选择复用同一组件
- **(2026-07-06 修订) Param 字段问号 `<AppTooltip>`**: 每个 Param label 旁配 `<AppTooltip content="...">` 包裹 `<HelpCircle>` 图标 (lucide-react), 鼠标悬浮显示该字段作用. 例: `edge_tol` label = `"Edge Tol 边缘容差 (像素)"` (中文 + 英文合一, **不**做 i18n, 直接硬编码字符串常量; tooltip content 同理), tooltip content = `"表格边缘检测的像素容差, 越大越宽松能识别弱线"`. 走项目 `<AppTooltip>` 封装 ([components/common/feedback/app-tooltip.tsx](../../packages/web/components/common/feedback/app-tooltip.tsx)), 不拼原生 shadcn Tooltip 4 子件 (TooltipProvider/Root/Trigger/Content, 根 layout 没装 Provider 易漏, 2026-06-18 health badge 教训 — 已被项目定为强制走 AppTooltip)

### 字段标签 + Tooltip 文案 (硬编码常量, 不进 i18n)

**(2026-07-06 修订) 用户原话**: "配置参数翻译成中文加上英文，不加国际化，方便用户看明白". 所以 label 和 tooltip 都硬编码中文+英文合一字符串, 不写 `t("...")` 不进 `messages/{zh,en}.json`. 后续如需 i18n 化再独立 spec 走 `useTranslations`.

| 字段 | Label (硬编码, JSX 直接写字面量) | Tooltip content (硬编码, JSX 直接写字面量) |
|---|---|---|
| backend 选择行 | `"Backend 后端"` | `"选择表格提取库. 默认 PyMuPDF (内置, 高速, AGPL); Camelot 处理弱表格线强; pdfplumber 纯 Python (MIT) 可视化调试"` |
| `flavor` | `"Flavor 解析器"` | `"lattice/stream/network/hybrid/ml 5 种. lattice 用表格线, stream 用空白间距, network/hybrid 综合, ml 是 Table Transformer (需 `camelot-py[ml]` extra)"` |
| `edge_tol` | `"Edge Tol 边缘容差 (像素)"` | `"表格线边缘像素容差. 越大越宽松能识别弱线, 但可能误检"` |
| `row_tol` | `"Row Tol 行容差 (像素)"` | `"同行文本垂直像素容差. 越大越能容忍跨行错位"` |
| `vertical_strategy` | `"Vertical Strategy 垂直策略"` | `"垂直线检测: lines 用显式线, lines_strict 严格, text 用文本对齐推断, explicit 显式坐标"` |
| `horizontal_strategy` | `"Horizontal Strategy 水平策略"` | `"水平线检测 (同 vertical_strategy 解释)"` |
| `snap_tolerance` | `"Snap Tolerance 吸附容差 (像素)"` | `"附近线条合并的像素容差"` |
| `join_tolerance` | `"Join Tolerance 合并容差 (像素)"` | `"端点接近的线条合并像素容差"` |

**实现**: 在 `pre-analysis-upload-dialog.tsx` 内定义一个 `PARAM_METADATA: Record<string, {label: string; tooltip: string}>` 常量, 渲染时遍历. 例:

```typescript
const PARAM_METADATA = {
  flavor: { label: "Flavor 解析器", tooltip: "lattice/stream/..." },
  edge_tol: { label: "Edge Tol 边缘容差 (像素)", tooltip: "..." },
  // ...
} as const;
```

每个后端的 params 字段数组也定义同模块常量 `CAMELOT_PARAMS = ["flavor", "edge_tol", "row_tol"] as const` / `PDFPLUMBER_PARAMS = [...]`.

**为什么不写 i18n**: 用户原话明确说"不加国际化, 方便用户看明白". 这是 admin 单一语言场景 (zh), zh.json 已经够多, 不值得为单页面 8 个字符串再加 en 翻译 + 同步责任. 后续真有需求再单独 spec.

- **不抽新 `<AppPdfConfigDialog>`**: 高选项仅 pre-analysis 1 处用, 不满足 ≥2 次封装门槛

### (2026-07-06 修订) 详情页产物列表 — 阶段化可见 + 手动刷新

文件: `packages/web/app/[locale]/admin/pre-analysis/[task_id]/_components/admin-pre-analysis-detail-client.tsx` (现有详情页 client 组件)

#### 当前状态

详情页表格列出 `task.output_files` (DB `output_files_json` 反序列化). 现状: **running 状态时表格全空** (write_outputs 阶段未跑), 等到 completed 才一次性出现所有产物.

#### 新行为 (2026-07-06 修订)

详情页表格改为**实时可见**已落地部分产物:

```
┌──────────────────────────────────────────────────────────────────┐
│ ← 返回    [pa-3f8c2e1a…]   阶段: extract_tables  [⟳ 刷新] [重试] │
├──────────────────────────────────────────────────────────────────┤
│ ▼ 当前阶段: extract_tables (60%)                                 │
│   3 / 12 页已提取                                              │
├──────────────────────────────────────────────────────────────────┤
│ ▼ 已落地产物 (5)                          [下载全部 ZIP disabled] │
│ ┌───┬──────────────────────┬──────────┬─────────────────────┐   │
│ │ ⬇ │ chapter_structure.json│  3.8 KB │ 阶段: extract_chapters  │   │
│ │ ⬇ │ tables/page-3-table-1│ 0.5 KB  │ 阶段: extract_tables     │   │
│ │ ⬇ │ tables/page-9-table-1│ 0.5 KB  │ 阶段: extract_tables     │   │
│ │ ⬇ │ tables/page-12-table │ 0.4 KB  │ 阶段: extract_tables     │   │
│ │ ⬇ │ flagged_paragraphs.csv│  2.1 KB │ 阶段: extract_flagged     │   │
│ └───┴──────────────────────┴──────────┴─────────────────────┘   │
│                                                                  │
│ ℹ️ 任务未完成, 已落地产物可下载 (每个 ⬇ 链接),                   │
│   ZIP 打包下载将在任务 completed 后可用                          │
└──────────────────────────────────────────────────────────────────┘
```

#### 关键 UI 元素

- **"⟳ 刷新"按钮** (跟现有 admin 列表的"刷新"按钮同风格): 点击 → `queryClient.invalidateQueries(["pre-analysis-task", id])` → GET `/api/pre-analysis/tasks/{id}` 重拉 DB → 表格新行出现. 不做 polling/WebSocket
- **每个产物独立 ⬇ 下载链接**: 走 `<a href download={uri}>` 项目封装 (admin 列表页"Download" 已用同样模式), 浏览器直接下 ObjectStore 文件 (走 `local://` / `s3://` URI 通过 `get_object_store().presign_get(...)` 签名)
- **"下载全部 ZIP"按钮**: 
  - task=completed → enabled, 走现有 `downloadPreAnalysisZip` endpoint
  - task=running → disabled, hover tooltip `"任务未完成, 请等待完成后下载, 或直接下载已落地部分产物"`
  - task=failed → disabled (复用 running 提示语)
- **任务未完成时头部提示**: "任务进行中 (stage X/Y), 落地产物实时可见, 可下载部分 / 总数" — 用户拍板 2026-07-06 不轮询, 0 后端推送

#### 不新增 API 端点

复用现有 `GET /api/pre-analysis/tasks/{id}` (已含 output_files 反序列化), 不加 `/artifacts/refresh` 端点 — 详情页 invalidate + 重 fetch 同一端点即可, 简单一致.

#### 不轮询明确 (用户原话 2026-07-06)

- ❌ 不加 WebSocket / SSE
- ❌ 不轮询 (setInterval refetch)
- ✅ 仅手动"刷新"按钮触发

#### 任务详情页测试

`packages/web/app/[locale]/admin/pre-analysis/[task_id]/page.test.tsx` 加 3 测试:

| 测试 | 断言 |
|---|---|
| `running 状态表格显示部分产物` | mock GET 端点返 `output_files=[3 项]`, `state=running`, 表格 3 行可见, "下载 ZIP" 按钮 disabled |
| `点刷新按钮 refetch` | mock fetch 2 次 (返不同 output_files), click ⟳, 表格行数从 3 → 5 |
| `completed 状态 ZIP 按钮 enabled` | mock GET 返 `state=completed`, "下载 ZIP" enabled, 详情页调用 `downloadPreAnalysisZip` |

---

## 错误处理

| 失败点 | 降级行为 |
|---|---|
| `table_backend=foo` (不合法) | API 400 `unknown_backend`, 弹框显示 backend 选择红框错误 |
| `table_params="{malformed"` | API 400 `table_params_invalid`, 弹框 params 红框错误 |
| `camelot` 后端选中 + 项目没装 camelot-py | API 503 `camelot_not_installed`, error 含 install_hint = `uv add camelot-py`; 如果 admin 上传时 flavor='ml' 但 `camelot-py[ml]` 未装 → 503 error 含 `uv add 'camelot-py[ml]'` (ml 单独检查) |
| `pdfplumber` 后端选中 + 项目没装 pdfplumber | API 503 `pdfplumber_not_installed`, error 含 install_hint |
| 后端装好但 PDF 损坏/异常导致 extract 抛错 | task `state=failed`, error=`extract_tables failed: {err}`, UI 显示可重试 |
| **(2026-07-06 修订) 中途失败** | stage N 失败时, stage 1..N-1 已写产物 **保留** (ObjectStore 不删, DB `output_files_json` 保留已 append 项), UI 明标 "部分产物 (做到 stage X 失败) X / Y", 已落地部分产物仍可下载 |
| **(2026-07-06 修订) DB/ObjectStore 极端不一致** | put_object_store 成功 + DB UPDATE 失败 (中间崩溃) → DB 缺项, ObjectStore 多孤儿文件. 本期不加事务包裹, 接受 0.01% 风险; admin 手工 reconciliation 或未来 spec 加 cron |
| 跨页表只取当前页 | 沿用原 spec §错误处理 (`summary.cross_page_candidates+=1`, 不报 fail) |
| 选了 `pymupdf` 不展开高级选项 | 走默认 backend=pymupdf + 空 params, 等同本期前行为 (0 回归) |
| 重新打开 dialog (上次选的是 camelot) | state 重置回 pymupdf + 默认 params (避免误用上次配置) |

---

## 测试隔离 (CLAUDE.md §强制 4 模式)

| 模块 | 模式 | Fixture | 备注 |
|---|---|---|---|
| `migrations/20260706_*.py` (新 task_config_json 列) | 3 (tmp_pg_schema) | 临时 schema | upgrade + 验列存在 + default `{}` + downgrade + 重复升级 |
| `pre_analysis_models.py` (新列) | 1 (mock) | `MagicMock()` | 字段反射存在 |
| `pre_analysis_store.py` `_to_dict` 透传 | 2 (db_session) | `db_session` | 验 `{}` default + 显式传入 roundtrip |
| `pre_analysis_store.py` `mark_completed` 写 task_config_json | 1 (mock) | `MagicMock()` | 验 mark_completed 接 task_config 参数, mock 后看到传值 |
| `table_extractors/base.py` TableData + ABC | 1 (mock) | 无 (纯接口契约) | 验 `TableData` 是 frozen dataclass, `TableExtractor.extract` 是 abstractmethod, 子类必须实现 |
| `table_extractors/pymupdf_extractor.py` | 1 (mock doc + 真 PDF d81_dummy) | 专用 fixture PDF | 2 测试: 复用已打开 doc (`_pymupdf_doc` kwarg 走传入 doc) + 自身开 doc (`_pymupdf_doc=None` 走 `pymupdf.open`). 验 `[(page_no, table_no, rows)]` shape |
| `table_extractors/camelot_extractor.py` | 1 (mock + 真 PDF) | 专用 fixture PDF | 2 测试: 1) 真 PDF 调 `camelot.read_pdf(flavor="lattice")` 返回 `TableData` 列表 (skipIf camelot 未装) 2) `monkeypatch.sys.modules` 把 `camelot` 模拟 ImportError → 构造时抛 `BackendNotInstalledError` |
| `table_extractors/pdfplumber_extractor.py` | 1 (mock + 真 PDF) | 专用 fixture PDF | 2 测试: 1) 真 PDF 调 `pdfplumber.open().pages[].extract_tables()` 返回 `TableData` 列表 (skipIf pdfplumber 未装) 2) 同上 ImportError 模拟 |
| `table_extractors/factory.py` | 1 (mock) | `monkeypatch` sys.modules | 4 测试: 3 backend 路由都对 (`get_table_extractor("pymupdf")` 返 `PymupdfTableExtractor` etc.) + 未知 backend (`"foo"`) 抛 `ValueError` |
| `pre_analysis_runner.py` (refactor: 接 config + 跑完写 task_config) | 1 (mock store + MagicMock task_store) + 2 (真 PDF d81_dummy) | 已有 fixture | 默认 backend=pymupdf 0 回归 + 指定 backend 路由对 + 跑完 mark_completed 收到 task_config |
| **`pre_analysis_runner.py` (2026-07-06 阶段化写入)** | 1 (mock store + MagicMock task_store 真 PDF d81_dummy) | 已有 fixture | **新增 4 测试**: 1) `extract_chapters` 跑完立即调 `object_store.put_bytes(chapter_structure_uri)` + DB append 1 项 (mock DB store 收到 update 调用含该 URI) 2) `extract_tables` 每张表都触发 put_bytes + DB append (用 mock 测 5 张表 → 5 次 put + 5 次 DB update) 3) `extract_flagged` 跑完 1 次 put + 1 次 DB update 4) **失败时已写产物保留**: stages 1+2 跑成功, stage 3 (`extract_tables`) mock 抛 Exception → mark_stage_failed + DB 中 output_files_json 仍是 [chapter_structure, tables/page-1.csv] (无 stage 3 产物, 也无 stage 4 产物) |
| `api.py` upload 端点 4 新 case | 1 (TestClient + mock runner) | `TestClient` + mock `_run_pre_analysis` | 400 (unknown backend / bad JSON) / 503 (缺包) / 200 (默认 + 自定义) 必测; 验 `_run_pre_analysis` 被 add_task 时收到 table_config |
| `api.py` GET 详情透传 task_config_json | 1 (TestClient) | mock load_task | 验响应里含 task_config_json 字段 |
| `pre-analysis-upload-dialog.tsx` | 1 (vitest) | fetch mock + render | 7 个测试: 旧 4 + 新 3 (advanced toggle / 后端切换 / 上传发 form 字段) |
| **`pre-analysis/[task_id]/page.test.tsx` (2026-07-06 详情页阶段化)** | 1 (vitest) | fetch mock + render | **新增 3 测试**: 1) running 状态表格显示部分产物, "下载 ZIP" 按钮 disabled 2) 点 "刷新" 按钮 refetch 后表格行数变化 (待 3 行 → 5 行) 3) completed 状态 ZIP 按钮 enabled |

---

## 不要做的事 (Top 5)

1. **不抽新前端组件 `<AppPdfConfigDialog>`** — 高级选项仅 pre-analysis 1 处用, 不满 ≥2 次门槛
2. **不做并跑多后端 A/B 对比** — 本期 per-task 单选, 不存用户级默认
3. **upload 时不写 task_config_json** — DB 这列由 runner 跑完统一写 1 次 (执行快照); upload 路径不参与 DB 写入, 0 校验复杂度 (用户原话 "不需要持久化, 只需要有一个默认的配置"). 任务详情页看到的 task_config_json = 实际生效的配置, 不是上传时存的草稿
4. **不动现有 `pre_analysis_tasks` 表的 JSON 列类型** — 本期新增列保持 `sa.Text` (跟 `output_files_json`/`summary_json` 一致), 改 JSONB 是独立 spec
5. **不依赖 docker 跑 Camelot** — 用户 2026-07-06 确认无 docker 路径; Camelot 2.0 默认装 pdfium bundled wheel 已够 (0 系统依赖), 仅 flavor='ml' 才需 [ml] extra + PyTorch, **不再需要装 ghostscript**
6. **(2026-07-06 修订) 不做 Zip 流式 / 中途下载** — task running 时 "下载 ZIP" 按钮 disabled, 仅 completed 可下载. 单产物文件 (chapter_structure.json / page-N-table-M.csv / flagged_paragraphs.csv) 详情页中途可下载, 但不打包成 zip
7. **(2026-07-06 修订) 不走 Redis 缓存产物列表** — 每 stage 跑完同步 update DB `output_files_json` (append 1 项), 详情页 query DB 取最新列表. 不引 Redis cache (项目历来 redis 都是 fail-open cache 不是单信息源). 0 cache invalidation 复杂度

---

## 实施拆分 (5 Milestone / 5 commits)

| # | Milestone | 文件 | commits |
|---|---|---|---|
| **M1** | Migration 加 `task_config_json` 列 + ORM + store 透传/mark_completed 写入 | `migrations/versions/20260706_000000_pre_analysis_task_config.py` [新] + `pre_analysis_models.py` [改] + `pre_analysis_store.py` [改] + tests | 1 |
| **M2** | `TableExtractor` strategy 文件夹 (base + 3 适配器 + factory) | `src/ingest/table_extractors/` [新, 含 `__init__/base/pymupdf_extractor/camelot_extractor/pdfplumber_extractor/factory.py`] + `tests/ingest/table_extractors/` [新, 含 `test_base.py` + `test_pymupdf_extractor.py` + `test_camelot_extractor.py` + `test_pdfplumber_extractor.py` + `test_factory.py`] + `pyproject.toml` 加 `camelot-py` + `pdfplumber` (可选依赖声明, dev 不强制装) | 1 |
| **M3** | Runner refactor 用 TableExtractor + 跑完回写 task_config_json + 默认 backend=pymupdf 0 回归 | `pre_analysis_runner.py` [改] + tests 更新 | 1 |
| **M4** | API upload 端点接受 `table_backend` + `table_params` form, in-memory 透传 runner, 503 缺包; GET 详情透传 task_config_json | `api.py` [改] + tests | 1 |
| **M5** | 前端弹框"高级选项"折叠区 (硬编码 zh+en 合一 label/tooltip, 走 AppTooltip) + 详情页展示 task_config_json | `pre-analysis-upload-dialog.tsx` [改, 含 PARAM_METADATA 常量] + `lib/api/pre-analysis.ts` [改] + `[task_id]/page.tsx` [改] + tests | 1 |

**5 commits 切分**:
1. `feat(service): add pre_analysis_tasks.task_config_json column for execution snapshot`
2. `feat(service): add TableExtractor strategy with pymupdf/camelot/pdfplumber`
3. `refactor(service): runner uses TableExtractor and writes task_config_json snapshot`
4. `feat(service): upload endpoint accepts table_backend + table_params, pass to runner`
5. `feat(web): add advanced options section to pre-analysis upload dialog + detail page incremental artifact list (no polling)`

每个 commit 单独跑 `uv run pytest` / `bun run test` + `ruff/pyright/oxlint/tsc` 全套验证 0 error 才进下一个.

**前置依赖**:
- M1 必先跑通 (DB schema 加列才能 store 持久化)
- M2-M5 可串联 (factory 必先存在才能被 runner 用)
- **(2026-07-06 修订) M3 额外要求**: 阶段化产物渐增写入是 M3 验收硬条件 (详情页开发依赖此), 见 § 阶段化产物渐增写入. M3 测试列表里"阶段化写入"4 个测试必全绿

---

## 验证 (Verification)

### 后端测试

```bash
cd packages/service

# M1
uv run pytest tests/migrations/test_pre_analysis_task_config.py -v
uv run pytest tests/ingest/test_pre_analysis_models.py -v

# M2 (新)
uv run pytest tests/ingest/table_extractors/ -v

# M3
uv run pytest tests/ingest/test_pre_analysis_runner.py -v

# M4
uv run pytest tests/ingest/test_pre_analysis_api.py -v
uv run pytest tests/test_api_contract.py -v   # CLAUDE.md §删 BFF 必跑 (新增 form 字段也要不破)
```

### 前端测试

```bash
cd packages/web
bun run test lib/api/pre-analysis.test.ts
bun run test app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx
bun run test app/[locale]/admin/pre-analysis/
```

### 代码质量 (项目铁律)

```bash
# Backend
cd packages/service
uv run ruff format && uv run ruff check --fix && uv run pyright

# Frontend
cd packages/web
bun run format && bun run lint:fix && bun run typecheck
```

### 手工 E2E (dev)

1. 启动后端 `uv run python main.py` + 前端 `bun run dev`
2. 登录 super_admin → `/zh/admin/pre-analysis`
3. 点 "上传 PDF" → 弹框 → 选 .pdf
4. 展开 "高级选项" → 看到 3 后端选择 (pymupdf 默认)
5. 选 `camelot` → 看到 flavor / edge_tol / row_tol 输入框 → 调整 flavor=stream
6. 上传 → toast 成功
7. 等任务 completed → 详情页 → 看 summary 跟产物表格是否跟选 camelot 后端一致
8. 重复选 `pdfplumber` → 验证 Strategy → vertical/horizontal 输入
9. 重复选 `pymupdf` → 行为跟改造前一致 (回归)
10. 选 `camelot` 但项目没装 → 后端返 503 → 弹框错误条红字显示 "未安装" + install hint

### 边界条件必测

- [ ] `table_backend=foo` → 400
- [ ] `table_params='{invalid'` → 400
- [ ] `camelot` 后端未装 → 503 + install_hint
- [ ] 跨页表候选检测沿用现有启发式 (本期不动)
- [ ] `_pymupdf_doc` 复用: pymupdf 后端不应重新打开 PDF
- [ ] DB 列默认值 `{"backend": "pymupdf", "params": {}}` 保证 existing rows 不破坏

---

## 关联文档

- 原 spec: [`2026-07-02-pdf-pre-analysis-design.md`](./2026-07-02-pdf-pre-analysis-design.md) — 本 spec 是它的修订 + 扩展, 不替代
- 模板: [`2026-07-02-motor-ontology-extract-design.md`](./2026-07-02-motor-ontology-extract-design.md) — KG 抽取解耦参考
- 计划: [`2026-07-03-pre-analysis-upload-dialog.md`](./../../plans/2026-07-03-pre-analysis-upload-dialog.md) — 本 spec 的实施 plan 在该 plan 文件加新 Task
- 项目根 [CLAUDE.md](../../../CLAUDE.md) — 代码质量铁律
- 后端 [packages/service/CLAUDE.md](../../../packages/service/CLAUDE.md) — 4 测试模式 + ObjectStore + DB schema 规范

---

## 待用户审阅

请审阅以下决策点:

1. **修正原 spec 错误**: 同意删除"Camelot 2018 年停更, 完全替代" + "pdfplumber 重叠, 不需要" 这两句话吗?
2. **(2026-07-06 修订) 执行快照而不是上传时持久化**: 同意 `task_config_json` 列由 runner 跑完统一写 1 次, upload 路径 in-memory 透传给后台任务, 默认 backend 在 yaml (用户原话 "不需要持久化, 只需要默认配置 + 按发送的执行")?
3. **(2026-07-06 修订) `pyproject.toml` 声明 `camelot-py` + `pdfplumber` (无 [base], 无 [ml] extra, 进 main 或 optional 由你拍)**: 默认 `uv add camelot-py` 即够 (Camelot 2.0 pdfium bundled 0 系统依赖, flavor='ml' 才需 [ml]); 是否走 `[project.optional-dependencies]` extras 取决于实际运行环境的合规要求 — 用户原话"只能用 uv 装不用 pip"
4. **3 后端 + 默认 pymupdf 0 回归**: 同意默认 `pymupdf` 不弹高级选项, 仅选其他时展开?
5. **(2026-07-06 修订) 拆 6 commits 加 M0 子包化**: M0 = `refactor(service): move pre_analysis_* to subpackage pre_analysis/`, 然后 M1-M5 不动; **M5 不动 messages/zh.json + en.json** (Param label/tooltip 硬编码 zh+en 合一字符串, 不走 i18n); 详情页 task_config_json 显示仍照常?
6. **(2026-07-06 新增) 阶段化产物渐增可下载**: 同意取消 `write_outputs` 聚合写, 每个 stage 跑完立即写自己产物 + DB append? 任务失败时已写部分保留? index.json 仅 completed 写? Zip 仅 completed 可下载? 详情页手动刷新 (无轮询/无 WebSocket)? 纯 DB 不用 Redis 缓存?
7. **(2026-07-06 新增) 业务产物不确定写次序引发的孤儿文件风险接受**: stage N put_object_store 成功 + DB UPDATE 失败 (中间崩溃) → DB 缺项, ObjectStore 多孤儿. 本期不加事务包裹, 接受 0.01% 风险. 同意?
6. **复用 shadcn Accordion + AppSelect**: 同意不抽新 `<AppPdfConfigDialog>` 仅在弹框内嵌折叠区?

---

**作者**: Claude (brainstorming skill)
**关联 spec**: 2026-07-02-pdf-pre-analysis-design.md
**关联 plan**: 2026-07-03-pre-analysis-upload-dialog.md
**日期**: 2026-07-06



