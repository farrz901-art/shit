# ingest 单文件支持 + README 拆分

**日期**: 2026-06-08
**状态**: 待批准

## Context

### 背景 1：ingest 子命令不支持单文件

当前 `uv run python main.py ingest` 的 `p_ingest` 子解析器没定义任何参数 ([main.py:36-37](main.py#L36-L37))，`cmd_ingest()` 也不接 kwargs，固定走 `process_files()` 无参模式（即从 `config.toml [paths].input_dir` 扫整个目录）。

用户场景：拿到 1 个 PDF 想试一下转换效果，现在必须：
1. 把 PDF 拷贝到 config 里的 `input_dir` 目录
2. 跑 `ingest`
3. 处理完再删

体验差。期望直接 `uv run python main.py ingest ./abc.pdf` 就处理这一个文件。

### 背景 2：README 越来越杂

`README.md` 现在 180 行，混了 5 类内容：
1. **项目结构**（架构信息）
2. **快速启动**（部署信息）
3. **产品订货号解析服务**（产品解析器的完整使用说明，~80 行）
4. **测试命令**
5. **开发者规范**

用户希望 README 只留**项目部署**和**项目用法**，其他（架构、规范、详细 API 等）拆出去到 `docs/`。

## 关键设计

### 1. CLI 改动（main.py）

```python
def cmd_ingest(path: str | None = None) -> None:
    """跑 PDF 离线流水线（支持单文件 / 单目录 / 默认）"""
    from src.rag.ingest.pipeline import process_path
    process_path(path)


# 在 main() 里:
p_ingest = sub.add_parser("ingest", help="跑 PDF 离线流水线")
p_ingest.add_argument(
    "path", nargs="?", default=None,
    help="可选：单个文件路径 或 目录路径；不传走 config.toml 默认 input_dir",
)
p_ingest.set_defaults(_handler=cmd_ingest)
```

### 2. 新增 `process_path` 顶层入口（pipeline.py）

```python
def process_path(path: str | None = None) -> dict | None:
    """三路分发：单文件 / 单目录 / 默认 config

    Args:
        path: 单文件路径 / 目录路径 / None 走 config
    """
    from .config import get_paths

    if path is None:
        # None → 走 config 默认目录
        return process_files()

    p = Path(path)
    if not p.exists():
        print(f"路径不存在: {path}")
        return None

    if p.is_file():
        # 单文件 → 按扩展名分桶 → 调对应的 list[str] 入口
        return _process_single_file(str(p))

    # 是目录（含 zip 路径）→ 走完整目录流水线
    return process_files(input_dir=str(p))


def _process_single_file(file_path: str) -> dict:
    """单文件模式：按扩展名路由到 document/cad/passthrough"""
    from .converters import CONVERTERS

    p = Path(file_path)
    ext = p.suffix.lower()
    paths = get_paths()
    output_path = paths.output_dir

    if ext in MarkdownPassthroughHandler.extensions:
        return process_passthrough([file_path], str(output_path))
    if any(ext in c.extensions for c in [EzdxfConverter]):
        return process_cad_files([file_path], str(output_path))
    if any(ext in c.extensions for c in CONVERTERS.values()):
        return process_documents([file_path], str(output_path))

    # 未知扩展名
    print(f"[WARN] 不支持的文件格式: {ext}（跳过: {p.name}）")
    return {"document": [], "cad": [], "passthrough": []}
```

**关键决策**：
- **新增 `process_path` 入口，不动 `process_files`**：避免让 `process_files` 内部加 self-adaptive 分支（"传入是文件就跳过 zip、传入是目录就跑全流水线"）—— 这种自适配会污染入口语义，也违反 [[feedback-no-shim-no-minimal-changes]]。
- **zip 文件当目录透传**：`process_files` 内部已经把 zip 当目录扫（archive_handler 接管），单文件路径不需要重复实现解压逻辑。
- **复用现有 `process_documents / process_cad_files / process_passthrough`**：这三个函数 2026-06-08 shim 清理后签名严格为 `file_paths: list[str]`，完美支持"传单文件 list"。

### 3. 行为表

| 调用 | 行为 |
|---|---|
| `uv run python main.py ingest` | 走 `config.toml [paths].input_dir` 全扫 |
| `uv run python main.py ingest ./abc.pdf` | 单文件 PDF → `process_documents(["abc.pdf"])` |
| `uv run python main.py ingest ./a.dxf` | 单文件 DXF → `process_cad_files(["a.dxf"])` |
| `uv run python main.py ingest ./README.md` | 单文件 MD → `process_passthrough(["README.md"])` |
| `uv run python main.py ingest ./abc.xyz` | 未知扩展 → 打印 WARN 跳过 |
| `uv run python main.py ingest ./pdfs/` | 目录 → `process_files(input_dir="./pdfs/")` |
| `uv run python main.py ingest ./bundle.zip` | 目录透传 → `process_files` 内 zip 解压走全流水线 |
| `uv run python main.py ingest ./nope` | 不存在 → 打印报错返回 None |

### 4. README 拆分

**README.md（精简后约 50 行）**：
- 项目简介（1 段）
- 快速启动（uv sync / `python main.py` / `ingest` 用法表）
- 各文档链接（部署 / 架构 / 产品解析器 / 流水线 / 开发者规范）

**docs/deployment.md**（新）：
- 环境要求（uv、Python ≥ 3.11、ODA 可选、GPU 可选 for mineru）
- 启动命令（`uv run python main.py` 各模式）
- 端口/主机/重载参数

**docs/architecture.md**（新）：
- 旧 README 第 1 节"项目结构"（目录树）
- 模块职责（product_decoders / rag.ingest / FastAPI / pipeline）
- 配置文件位置（config.toml、.env、YAML configs）

**docs/product-decoder.md**（新）：
- 旧 README 第 3 节全部内容
  - 添加新系列
  - 配置目录（configs/product_decoders/）
  - 统一输出 Schema
  - API 接口（/decode /series /health）
  - Dify 工作流接入
  - 解码示例

**docs/ingestion.md**（新）：
- RAG 流水线用法（无参 / 目录 / 单文件 / `--output` 覆盖）
- 三类转换器（kreuzberg / mineru / ezdxf）选择规则
- archive_handler 配置（max_depth / max_total_size / max_file_count）
- ODA 配置（环境变量 + [cad] 段）

**docs/dev-conventions.md**（新）：
- 旧 README 第 4 节（测试命令）
- 旧 README 第 5 节（中文注释、中文日志、TDD、uv、文档位置）
- shim 禁令（[[feedback-no-shim-no-minimal-changes]] 摘要）

**现有文档不动**（已是独立文件）：
- `docs/cad-converter.md`
- `docs/cad-ezdxf-best-practices.md`
- `docs/mineru-output-for-rag.md`

## 关键设计决策

### 决策 1：`process_path` 独立 vs `process_files` 自适配

**选独立**：
- `process_files` 保持"目录场景的完整流水线"单一职责（含 zip 解压、tempfile 隔离、递归 rglob）
- 单文件路径不需要 zip 也不需要 tempfile，让 `_process_single_file` 干瘦活
- 跟 [[feedback-no-shim-no-minimal-changes]] 一致：不堆 self-adaptive 分支

### 决策 2：单文件 zip 怎么处理

**选透传 `process_files`**：
- `process_files` 内部 `archive_handler.is_supported()` 已经识别 zip
- 单文件模式（_process_single_file）不处理 zip，直接让目录模式接管
- 行为最简：单文件 = 不带 zip 的纯文件流；目录 = 完整流程

### 决策 3：未知扩展名怎么处理

**选打印 WARN 跳过，不抛异常**：
- 跟 `process_files` 内部对 unknown 桶的行为对齐（"未找到可处理的文件" / "不识别的格式"）
- CLI 友好：用户传错扩展名时不会让 ingest 整个崩

### 决策 4：README 拆 5 个 docs

按主题拆，README 仅作总入口（项目简介 + 快速启动 + 链接）。

**不拆**：
- 产品解析器的 API 详细 schema、YAML 写法、添加新系列步骤 → 单独成 `product-decoder.md`
- RAG 流水线用法 / 转换器选择 / 配置 → 单独成 `ingestion.md`
- 架构 / 模块职责 / 项目结构 → 单独成 `architecture.md`
- 部署 / 环境要求 / 启动命令 → 单独成 `deployment.md`
- 测试命令 / 中文规范 / TDD / shim 禁令 → 合并成 `dev-conventions.md`

## 测试

### 单元测试（新增 `tests/rag/ingest/test_pipeline_path.py`）

| 测试 | 覆盖 |
|---|---|
| `test_process_path_none_delegates_to_process_files` | None → 调 `process_files()` 无参 |
| `test_process_path_directory_delegates_to_process_files` | 目录 → 调 `process_files(input_dir=...)` |
| `test_process_path_single_pdf_routes_to_process_documents` | PDF → 调 `process_documents([file])` |
| `test_process_path_single_dxf_routes_to_process_cad_files` | DXF → 调 `process_cad_files([file])` |
| `test_process_path_single_md_routes_to_process_passthrough` | MD → 调 `process_passthrough([file])` |
| `test_process_path_unknown_extension_prints_warning` | `.xyz` → 打印 WARN 不抛 |
| `test_process_path_missing_path_prints_error_returns_none` | 不存在 → 打印 + 返回 None |
| `test_process_path_zip_delegates_to_process_files` | `.zip` → 调 `process_files(input_dir=...)` |

**所有测试用 mock 验证下游函数被调，不真跑 PDF 转换**（TDD 友好、快）。

### CLI 解析测试（新增 `tests/test_main.py` 或 `tests/rag/test_main_cli.py`）

| 测试 | 覆盖 |
|---|---|
| `test_ingest_parser_accepts_optional_path` | `argparse` 接受 `ingest ./abc.pdf` |
| `test_ingest_parser_accepts_no_args` | `argparse` 接受 `ingest`（nargs="?"） |
| `test_ingest_parser_passes_path_to_handler` | 验证 `cmd_ingest(path=...)` 被调，path 是字符串 |

### 反射测试禁令

**不准加** `test_process_path_NOT_importable` 之类（[[feedback-no-shim-no-minimal-changes]] 第二条）。

### 文档存在性测试（新增 `tests/test_docs_structure.py`）

| 测试 | 覆盖 |
|---|---|
| `test_docs_subdirs_exist` | 5 个 docs 文件都存在 |
| `test_readme_links_resolve` | README 里的所有相对链接都指向真实文件 |
| `test_readme_does_not_contain_extracted_sections` | README 不再含产品解析器详细 schema、YAML 示例、API 详情（避免回滚） |

## 实施步骤概要

1. 写 `process_path` + `_process_single_file` 到 `src/rag/ingest/pipeline.py`（TDD：先红测试）
2. 改 `main.py`：argparse 加 `path` 位置参数 + `cmd_ingest` 接 kwargs
3. 写 8 个单测到 `tests/rag/ingest/test_pipeline_path.py`
4. 写 3 个 CLI 解析测试到 `tests/test_main_cli.py`
5. 创建 5 个新 docs 文件
6. 改写 `README.md` 成精简版
7. 写 `tests/test_docs_structure.py` 守住结构
8. 跑全量测试确认无回归
9. 提交一个 commit

## 风险

| 风险 | 缓解 |
|---|---|
| `process_path` 跟 `process_files` 输出 schema 不一致 | 三个底层函数（document/cad/passthrough）签名统一，单文件模式直接复用 |
| README 拆分后内部链接 404 | 全部用相对路径 + `test_readme_links_resolve` 自动检查 |
| zip 文件走"目录"路径可能有意外行为 | `_process_single_file` 不识别 zip 直接返回"未知"也行，但选透传更一致 |
| argparse `nargs="?"` 接受空字符串 | 加 `default=None` + 检查 None 才走默认 |
