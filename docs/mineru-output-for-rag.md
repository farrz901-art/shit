# mineru 转换产物在 RAG 中的使用

> 适用对象：本项目 RAG 流水线第一阶段（PDF → markdown）的下游消费者
> 数据来源：实测 [mineru Docker 镜像](src/rag_ingest/converters/__init__.py) 处理本仓库 `pdfs/` 下 PDF 的产出

## 概述

当一个 PDF 被 `MineruConverter` 处理后，会在 `output_dir` 下生成一个**嵌套目录**，包含 **8 个文件 + 1 个 `images/` 子目录**。本项目用 `mineru -p /app/input -o /app/output` 调用（[converters/__init__.py:104](src/rag_ingest/converters/__init__.py#L104)），未传 `--method` 参数，因此 mineru 默认按 `auto` 方法处理（即逐页自动判断文字/图片，对图片页走 OCR）。

```
output_dir/
└── <pdf_stem>/                    # 输入 PDF 的文件名（去后缀）
    └── auto/                      # mineru 的 method 名（auto/ocr/txt/...）
        ├── <pdf_stem>.md                 ← 渲染好的 markdown
        ├── <pdf_stem>_content_list.json  ← 结构化内容列表（v1）
        ├── <pdf_stem>_content_list_v2.json
        ├── <pdf_stem>_layout.pdf
        ├── <pdf_stem>_middle.json
        ├── <pdf_stem>_model.json
        ├── <pdf_stem>_origin.pdf
        ├── <pdf_stem>_span.pdf
        └── images/
            └── *.jpg               ← 从 PDF 抽出的图片
```

## 产物逐项说明

| 文件 | 是什么 | 进 RAG 吗 | 体积占比 | 说明 |
|---|---|---|---|---|
| **`<stem>.md`** | 渲染好的 markdown 文本 | ⭐⭐⭐ 必选 | 小 | 文本流直接喂给 splitter + embedding |
| **`<stem>_content_list.json`** | 结构化内容列表（v1） | ⭐⭐⭐ 强烈推荐 | 中 | 27 条左右结构化记录，每条带 `type=text/image/table/title` + `text` + `bbox` + `page_idx` |
| **`<stem>_content_list_v2.json`** | 同上 v2 版 | ⭐⭐ | 中 | mineru 升级后启用，部分 PDF 当前只有 1 条（数据未正常产出） |
| **`<stem>_layout.pdf`** | 带版面分析框的 PDF | ❌ | 大 | 开发/调试肉眼检查"版面分析对不对"用，**绝不能进 RAG** |
| **`<stem>_middle.json`** | 中间结果（检测到的区块、公式等） | ⚠️ 高级用 | 大 | 自定义切片策略时可能用，普通 RAG 用不上 |
| **`<stem>_model.json`** | 模型原始输出 | ❌ | 大 | mineru 内部诊断用，噪音多 |
| **`<stem>_origin.pdf`** | 原 PDF 复制 | ❌ | 等于原 PDF | 纯浪费空间，可删 |
| **`<stem>_span.pdf`** | 带文本 span 标注的 PDF | ❌ | 大 | 调试用 |
| **`images/*.jpg`** | 从 PDF 抽出的图片 | ⭐⭐ | 中 | RAG 多模态场景下用（图文一起 embed），纯文本 RAG 可忽略 |

## 三个 RAG 接入档位

按 RAG 实际需求从简到繁三档，按需选择：

### 第 1 档：纯文本 RAG（最简）

**只用 `<stem>.md`**。

```python
# MineruConverter 当前实现
md_path = os.path.join(output_dir, f"{pdf_name}.md")
content = open(md_path, encoding='utf-8').read()
# 直接喂给 splitter
```

- ✅ 简单、够用
- ❌ 切片时按行切，表格/图片/标题的结构信息全部丢失

### 第 2 档：结构化 RAG（推荐）

**用 `<stem>.md` + `<stem>_content_list.json`**。

content_list.json 的典型结构（实测 [本仓库产物](../../pdfs/output/book_zh_HGT51022016_extracted_page_12/auto/)）：

```json
[
  {
    "type": "text",
    "text": "5.4.3 操作",
    "text_level": 2,
    "bbox": [98, 101, 208, 117],
    "page_idx": 0
  },
  {
    "type": "text",
    "text": "在GB/T2918规定的标准状态下，测定试样的质量及表面积...",
    "bbox": [98, ...],
    "page_idx": 0
  }
]
```

- ✅ 切片时按 `block` 切（保留"公式/图片/表格/段落"的结构）
- ✅ 表格不会被切断
- ✅ 知道每个块的页码和坐标，检索时可回溯到 PDF 原位置
- ⚠️ 需要下游 splitter 改写为按 content_list 切分（不能直接用 LangChain 的 RecursiveCharacterTextSplitter）

### 第 3 档：多模态 RAG

第 2 档基础上 + `images/*.jpg`。

- 图片过 CLIP / ViT 编码，与文本 embedding 同空间
- 适合"图文混排"场景（产品图册、教材、论文）

## 当前代码状态

`MineruConverter.convert_batch`（[src/rag_ingest/converters/__init__.py:87-122](src/rag_ingest/converters/__init__.py#L87-L122)）**只读取 `.md`**，把 `content_list.json`、`images/` 都丢在磁盘上没回收：

```python
results = {}
for pdf_path in pdf_paths:
    pdf_name = Path(pdf_path).stem
    md_path = os.path.join(output_dir, f"{pdf_name}.md")
    if os.path.exists(md_path):
        with open(md_path, 'r', encoding='utf-8') as f:
            results[pdf_path] = f.read()  # 只读 .md
```

## 后续可改进方向

按优先级：

| 方向 | 价值 | 难度 |
|---|---|---|
| **A. 维持现状**：只读 .md，下游 RAG 自己用 .md | 0（不做事） | 0 |
| **B. 加读 content_list.json**：返回 `{file: {md, content_list}}` | ⭐⭐⭐ | 中（需改 convert_batch 签名 + 改 main.py 调用方） |
| **C. 回收中间产物**：跑完 mineru 后删 layout/middle/model/origin/span | ⭐⭐ | 小（一段 `os.remove` + 删 `images/` 外的诊断文件） |
| **D. 显式指定 `--method`**：避免 `auto` 嵌套 | ⭐ | 极小（mineru CLI 加 `--method ocr` 即可，但 `auto` 嵌套层改不了） |

## 决策建议

**先做 C（回收中间产物）**：磁盘节省 60%+，代码改动最小，几乎无风险。

**再做 B（加读 content_list.json）**：把第 2 档数据暴露给下游，让 RAG 切片质量上一个台阶。

**D（指定 method）慎做**：mineru 的 `auto` 嵌套目录是它写死的，指定 method 只改目录名（如 `auto` → `ocr`），治标不治本。除非有明确证据 `auto` 选错页类型，否则保留默认。
