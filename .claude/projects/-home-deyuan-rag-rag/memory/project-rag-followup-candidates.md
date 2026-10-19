---
name: project-rag-followup-candidates
description: 用户在 to-do.md 写的 3 个未来工作（CAD 多路融合 / 压缩包处理 / 架构重组），下一轮 spec 阶段的候选
metadata: 
  node_type: memory
  type: project
  originSessionId: eec4f205-4669-4734-b77f-77c2e0b18e11
---

**项目：** `C:\Users\abcuc\Desktop\rag` — RAG 系统第一阶段（已支持 PDF + CAD + md passthrough + 20+ 主流格式）

**用户 to-do.md 写的未来工作**（2026-06-02 记 3 个 + 2026-06-09 增 1 个多 domain schema）：

### 1. CAD 多路融合（更高质量 CAD→markdown）

用户**早期**草稿建议：
- **第一路**：ezdxf 提取文字/属性/图层 → 基础 markdown（已实现，见 `src/pdf_processor/cad_converter.py`）
- **第二路**：ODA 渲染 CAD → 高清 PNG → VLM（Qwen-VL 等）→ 补充 markdown（视觉/标题栏/技术要求）
- **合并**：两路 markdown 拼接写知识库

**注意**：用户后来在 [[docs/cad-converter.md]] 决策里**明确选了**"用 ezdxf + SVG 矢量（零 matplotlib 依赖）"路线。to-do.md 的 VLM 路线**已经被覆盖决策取代**。下一轮做这件事前**先 brainstorming 重新对齐方向**（要不要回 VLM 路线？还是 ezdxf + SVG 已经够？）。

### 2. 压缩包处理（zip/rar 自动解压再处理）

input_dir 里可能有 `.zip` / `.rar` / `.7z` 等压缩包。**先解压到临时目录，再走 4 桶路由流水线**。

涉及：
- 选个解压库（标准库 `zipfile` + `py7zr` + `unrar` 等）
- 临时目录清理策略
- 压缩包内的递归 / 防 zip bomb
- 路由顺序：压缩包必须在普通文件**之前**处理（解压产物可能跟原 zip 同名要避免冲突）

### 3. 包重命名 + 架构重组

用户提出：
- `main.py` 应该移到 `src/pdf_processor/` 内部（不是入口文件）
- 整个 `src/pdf_processor/` 名字改成更适合 RAG 系统的名字（候选：`rag_ingest` / `ingest` / `pipeline` / `docflow`）
- 整理代码结构

**为什么需要**：项目从"PDF 处理"演进到"多格式文档处理"后，包名 `pdf_processor` 已经名不副实；`main.py` 不应该是入口（更上层 RAG 系统会调用这些函数）。

涉及：包重命名会**影响所有 import**，需要一次性 sed + 测试 + 文档同步。

---

**关联**：
- 跟当前完成的多格式路由架构（8 task）正交 —— 不需要重做
- 跟 [[project-rag-pdf-pipeline]] / [[project-mineru-docker-integration]] 是同一项目的不同切片

**How to apply**：下次用户开始新一轮 spec 阶段，**主动**把这 4 项列为 brainstorming 候选。如果用户没提，自己问"to-do.md 里那几项要不要先做？"

### 4. 多 domain schema 拓展 (2026-06-09 增)

用户目前只有电机本体, 未来可能加别的领域, 需要支持多 schema 并存:
- `configs/knowledge-schema.yaml` (现有 RAG 通用 Product/Series/Document/QAPair) 保留
- 新增 `configs/motor-schema.yaml` (电机本体 6 类中文 label: 产品系列/技术参数/参数值/部件/工况条件/认证标准)
- 后端: 新增 `/api/kg/schemas` 列出 + `/api/kg/schema?domain=motor` 切换
- 前端: 知识库页加 domain 选择器, URL 区分 `/knowledge/motor/triples` 等
- 替代当前 BFF 用 `Product/Series` 硬编码的兜底 (neo4j.Product ?? 0)
- **根因**: 当前 BFF /api/knowledge/stats 因 schema 跟数据 label 名不匹配, 返全 0 (虽然 [[feedback-bff-must-propagate-502-not-silently-zero]] 已不静默吞 500, 但 200 时仍兜底 0)
- **参考数据**: 2026-06-09 探针 `{"产品系列":1,"技术参数":26,"参数值":26,"工况条件":1,"部件":2,"认证标准":1}` + 5 关系 `具有参数/参数值/参数对应/适用工况/符合标准`
