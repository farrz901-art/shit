# RAG 流水线

## 用法

```bash
# 走 config.toml [paths].input_dir 默认目录（最常用）
uv run python main.py ingest

# 显式指定目录
uv run python main.py ingest ./pdfs/

# 单文件模式（按扩展名自动路由）
uv run python main.py ingest ./abc.pdf
uv run python main.py ingest ./drawing.dxf
uv run python main.py ingest ./readme.md

# zip 压缩包（自动解压到临时目录后处理）
uv run python main.py ingest ./bundle.zip
```

### 行为表

| 输入 | 行为 |
|---|---|
| 不传参 | 走 `config.toml [paths].input_dir` 全扫 |
| 单文件 PDF | 调 `process_documents(["abc.pdf"])` |
| 单文件 DXF/DWG | 调 `process_cad_files(["abc.dxf"])` |
| 单文件 MD | 调 `process_passthrough(["abc.md"])` |
| 单文件未知扩展 | 打印 WARN 跳过 |
| 目录 | 调 `process_files(input_dir=...)` 完整流水线 |
| zip | 透传给 `process_files`，内含 zip 解压 |
| 不存在路径 | 打印报错返回 None |

## 转换器选择

| 格式 | 转换器 | 触发条件 |
|---|---|---|
| PDF（简单：纯文本 + 少图） | `KreuzbergConverter` | 自动路由 |
| PDF（复杂：扫描件/多图/表格） | `MineruConverter`（需 Docker） | 自动路由 |
| DXF | `EzdxfConverter` | `.dxf` |
| DWG | `EzdxfConverter` + ODA 转 DXF | `.dwg`，需装 ODA |
| MD | `MarkdownPassthroughHandler` | `.md` 直通复制 |

简单/复杂由 `PDFAnalyzer` 判定（页数、文本量、图片数）。

## mineru 配置

复杂 PDF 走 mineru Docker 容器，需要：

1. Docker daemon 运行
2. （可选）NVIDIA GPU + nvidia-container-toolkit（GPU 加速）
3. 配置镜像：`mineru` 相关环境变量

详见 [mineru-output-for-rag.md](mineru-output-for-rag.md)。

## ODA 配置

DWG → DXF 转换需要 ODA File Converter。两种配置方式（按优先级）：

### 1. 环境变量（推荐）

```bash
# Windows
set ODA_WIN_PATH=C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe
# Linux
export ODA_UNIX_PATH=/usr/bin/ODAFileConverter
```

### 2. `config.toml` `[cad]` 段

```toml
[cad]
oda_win_path = "C:\\Program Files\\ODA\\ODAFileConverter\\ODAFileConverter.exe"
oda_unix_path = "/usr/bin/ODAFileConverter"
```

[cad] 段缺失或键缺失都走默认空串（合法，DXF 不需要 ODA）。

## archive_handler 配置

`config.toml [archive]` 段控制压缩包解压行为：

```toml
[archive]
max_depth = 1               # zip 嵌套解压层数
max_total_size = 1073741824 # 总大小上限 (默认 1 GiB)
max_file_count = 10000      # 总文件数上限
```

[archive] 段缺失会 raise KeyError（项目必备）。

## 输出

所有产物输出到 `config.toml [paths].output_dir`（默认 `./output/`）。
