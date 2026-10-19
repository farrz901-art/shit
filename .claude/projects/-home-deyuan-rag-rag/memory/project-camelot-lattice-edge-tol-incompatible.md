---
name: project-camelot-lattice-edge-tol-incompatible
description: "Camelot lattice flavor 不接受 edge_tol (stream 才用), 后端透传必 raise ValueError"
metadata: 
  node_type: memory
  type: project
  originSessionId: ca7f1596-a25b-43ef-a912-2fcb64a64812
---

Camelot 表格提取后端 (packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py) 在 __init__ 全量读 params (flavor / edge_tol / row_tol), extract() 全量透传给 camelot.read_pdf。

**关键不兼容**: flavor='lattice' (走 OpenCV 隐线检测) 只接受 row_tol, **不接受 edge_tol** (edge_tol 是 flavor='stream' 的参数, 走文本对齐线). 库直接 raise `ValueError: edge_tol, row_tol cannot be used with flavor='lattice'`.

**前端的坑 (2026-07-06)**: pre-analysis-upload-dialog.tsx BACKEND_DEFAULT_PARAMS.camelot 默认给 `{ flavor: "lattice", edge_tol: 50, row_tol: 2 }` + BACKEND_PARAMS_KEYS.camelot 三个 key 全列, 用户在"高级选项"里选 Camelot (默认是 lattice) → 必报. yaml 默认值 configs/pre_analysis/table_extraction.yaml:23-25 同样错.

**复现路径**: 选 Camelot backend (默认) → 不动参数直接上传 → state=failed + error="edge_tol, row_tol cannot be used with flavor='lattice'" (0% extract_tables stage).

**修法 (留给用户决定)**:
1. 前端预检: 选 flavor='lattice' 时去掉 edge_tol UI, 不让用户误传.
2. 后端 camelot_extractor: 按 flavor 分支过滤 params (lattice → 只 row_tol, stream → 只 edge_tol/row_tol), 防御性.
3. yaml default_params.camelot: flavor=stream + edge_tol + row_tol (或 flavor=lattice + row_tol).
