---
name: project-rag-pdf-pipeline
description: RAG 项目的 PDF 处理流水线 — 分析器按复杂度分三类，分别用 kreuzberg/mineru/EasyOCR 处理
metadata: 
  node_type: memory
  type: project
  originSessionId: d5923208-4647-4dd0-9acb-40426948d1ee
---

**项目：** `C:\Users\abcuc\Desktop\rag` — RAG 系统的 PDF 结构化处理流水线

**核心架构（2026-06-01）：**
- 入口：`main.py::process_pdfs(input_dir, output_dir)`
- 分析器：`src/pdf_processor/analyzer.py::PDFAnalyzer` — 输出 `PDFInfo{is_simple, has_text, page_count, image_count, drawing_count, table_like_pages, reasons}`
- 转换器：见 [[project-mineru-docker-integration]]
  - `KreuzbergConverter` — 简单 PDF（有文字、非扫描件）
  - `MineruConverter` — 复杂 PDF（无文字/扫描件/矢量图形过多/图片过多）
  - `EasyOCRConverter` — 兜底
- 路径：`pdfs/`（输入）→ `pdfs/output/`（输出 markdown）

**关键技术决策：**
- 复杂度分类阈值（analyzer.py `_evaluate`）：`has_text=False` / `table_like_pages>0` / `drawing_count>100` / `image_count>10` 任意一个为真 → 复杂
- 走 TDD 流程（CLAUDE.md 要求），所有代码必须有单元测试
- 中文注释、保留原注释、不要删代码注释
