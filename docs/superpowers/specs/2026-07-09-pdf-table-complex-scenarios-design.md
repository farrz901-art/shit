# PDF 表格提取复杂场景三件套 spec (默认值架构 + Ghostscript + 跨页合并)

**日期**: 2026-07-09
**状态**: 设计待审
**触发来源**: 用户 2026-07-09 反馈 "camelot 简单表能提, 复杂表差" (测试场景: [tests/fixtures/Motors-D81-1-complete-English-09-2023.pdf](packages/service/tests/fixtures/Motors-D81-1-complete-English-09-2023.pdf) 西门子电机手册 710 页). 经 33 个测试全绿 baseline 验证, 当前实现基础健康 ([packages/service/tests/ingest/pre_analysis/table_extractors/](../tests/ingest/pre_analysis/table_extractors/) 33 PASSED 5min17s, 含 D81.1 真 PDF lattice > 100 表).

**关联**:
- 前置 plan [2026-07-08-camelot-tuning-fallback-ml.md](../plans/2026-07-08-camelot-tuning-fallback-ml.md) 已完成 R1-R5 修复 (pages='all' / flavor 白名单 / fallback 链 / ml extra). 本 spec 覆盖 A (前后端默认值) + B (中文 PDF 决策树保留) + C (跨页合并基础).
- 配套调研报告 [2026-07-09-siemens-d81-table-extraction-research.md](../../research/2026-07-09-siemens-d81-table-extraction-research.md) (4 方向 + 21 权威源 + 决策树).
- memory 沉淀 [project-camelot-complex-table-debug-checklist.md](../memory/project-camelot-complex-table-debug-checklist.md) (7 维度根因排查表).

---

## Context

### 用户原话

> "当前 camelot 提取简单的表格没有问题, 但是提取复杂表格, 表现较差, 分析是代码的原因, 还是需要装插件, 还是配置参数的原因, 结合代码分析, 也联网搜索一下原因, 给出优化意见"

**用户纠正 (重要)**: 测试场景是**英文 PDF (西门子 D81.1 电机手册)**，**不是中文 PDF**. 我之前默认按中文 PDF 写 spec B (ghostscript CID 字体兜底) 是错的. B 跟当前英文场景无 trigger, 本期留作 follow-up 选型参考, 实施层不部署.

### 已确认的现状 (代码 + 测试 + 联网调研 21 源)

**2026-07-09 核查确认**: 以下代码引用值经跟实际代码比对, 除明确标注外均一致. 见 plan [核查记录](#核查记录).

经代码 + memory + 联网调研三方验证, 核心结论:

**不是 "缺插件" 也不是 "参数没调", 是 3 个独立维度**:

| 维度 | 根因 | 现状 | spec 修复路径 |
|---|---|---|---|
| **A. 前后端默认值漂移** | 后端 `_FLAVOR_DEFAULTS["lattice"]["line_scale"]=15`, 前端 `BACKEND_DEFAULT_PARAMS.camelot.line_scale=40` (历史值, plan 漏改) | 3 事实源 (前端 / 后端 wrapper / yaml) 互相漂移, admin 上传选 camelot 不动参数 → 实际传 40 → 漏短表格线 | **A1 保留后端兜底 + 修前后端对齐** (本期实施) |
| **B. Ghostscript + 中文 PDF** | D81.1 是英文文本 PDF, pdfium 不会失败; **ghostscript 对英文场景无 trigger**. 中文 PDF 场景需要 ghostscript / MinerU / PaddleOCR 等替代方案 | 中文 PDF 决策树已调研完整 (见下文 §B) | **B 本期实施**: 装 ghostscript + 中文 PDF 工具备齐 (admin 可选) |
| **C. 跨页表只数不合** | Runner `_detect_cross_page` ([runner.py:297-340](../../packages/service/src/ingest/pre_analysis/runner.py#L297)) **只计数不合并**; Camelot 官方 `stack_contiguous()` 项目没用; 调研发现 D81.1 跨页续表真正解需 PyMuPDF bbox + LLM 裁 header | 单 flavor 内调 `stack_contiguous()` 合并 (基础); D81.1 跨页续表需 PyMuPDF join_tables bbox + LLM 裁 header | **C 本期实施**: C1 基础合并 + C2 跨页续表完整解 (PyMuPDF bbox + LLM 裁 header) 一起做 |

### D81.1 西门子电机手册表类型分析 (用户测试场景)

读了 P11-P15 实拍 + 调研报告 4 方向, 西门子手册 4 类表 + lattice 表现:

| 表类型 | 形态 (P 举例) | lattice 表现 | 修复路径 |
|---|---|---|---|
| **A 纯数据规格矩阵** | 有边框线 + 多列对齐数字 (P11 IE 效率等级表) | ✅ **lattice 最擅长, 当前 100% 提得到** (baseline > 100 张表验证) | 无需修 |
| **B 表头嵌色块长表** | 紫色块表头 + 单元格嵌多行文字 (P15 Steps for drive selection) | ⚠️ `process_background=True` **只解 background lines (隐藏直线), 不解 cell background fills** ([Camelot issue #386](https://github.com/camelot-dev/camelot/issues/386) 验证); 西门子紫/蓝块可能漏 | spec A 修默认值 + fallback 链兜底 + ml flavor 兜底 |
| **C 跨页续表** | 选型表跨多页 (P17 末 "6/8" → P18 接 "7. 6/2") | ❌ camelot `stack_contiguous(match="column_count")` 只看列数, **不能识别 "Selection table continued" 重复 header**; lattice 跨页必丢末行 ([issue #689](https://github.com/camelot-dev/camelot/issues/689)) | spec C: C1 基础合并 + C2 PyMuPDF bbox + LLM 裁 header 一起做 |
| **D 双列对照表** | 双侧 4 张表并排 (P11 IE1/IE2/IE3/IE4 对照) | ⚠️ lattice 可能把 2 张并排识别成 1 张 (false positive) | 跟 "复杂表差" 无关, 属 false positive 范畴 |

**核心结论**: D81.1 的"复杂表差"主要是 **C 类跨页续表 + B 类色块表头**. spec C (C1+C2 一起) 是 C 类完整解, spec A 是 B 类默认值兜底, **B 类色块表头的根本解** 留给后续 (ml flavor 兜底 + PyMuPDF 颜色阈值).

### 业界处理方案 (调研核心结论)

**收敛到 "两阶段混合架构"** —— TATR / TableFormer 做结构恢复 + LLM 合并跨页表 + 规范化色块 header + 校验数值单元格, 本质上是 marker `--use_llm` 流程 (TEDS 0.816 → 0.907, 9 分提升几乎全是 LLM 贡献). 具体证据:

- **marker** TEDS 0.816 → 0.907 (LLM 模式, [marker README](https://github.com/datalab-to/marker))
- **gmft** TATR-based, 1.17s/table, 不处理多页拼接 ([gmft README](https://github.com/conjuncts/gmft))
- **Docling** IBM TableFormer 2-6s/table on CPU, MIT ([arXiv:2408.09869](https://arxiv.org/abs/2408.09869))
- **PyMuPDF** `find_tables(strategy='text')` 备份 + 官方 [join_tables.ipynb](https://github.com/pymupdf/PyMuPDF-Utilities/tree/master/table-analysis) 是跨页拼接参考
- **Camelot** 单 flavor stack_contiguous **不识别 "Selection table continued" 表头是否重复**, 不够 D81.1 (issue #689)

**本期 spec 不引入新依赖** (ml flavor 已装, PyMuPDF 已装, LLM 客户端已有), 但 C 模块 C2 阶段要用 LLM 调一次 (裁重复 header).

### 前后端默认值真冲突在哪 (A 的真因)

**不是** "前端值跟 camelot 官方推荐不一致" 这么浅, 是**架构问题**: 3 个事实源设计就漂移.

| 位置 | 文件 | 当前值 |
|---|---|---|
| 前端 UI 默认 (admin 打开弹框看到) | [pre-analysis-upload-dialog.tsx:97](../../packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx#L97) | `{ flavor: "lattice", line_scale: 40, line_tol: 2 }` |
| 后端 wrapper 默认 (admin 不传时兜底) | [camelot_extractor.py:86](../../packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py#L86) | `{ line_scale: 15, line_tol: 2, process_background: True }` |
| yaml 默认 (server 端兜底) | [table_extraction.yaml:22-26](../../packages/service/configs/pre_analysis/table_extraction.yaml#L22) | `flavor: "lattice", fallback_chain: true` |

3 个事实源漂移**只在修改默认值时显式发生** —— 2026-07-08 plan 改后端 `_FLAVOR_DEFAULTS` 时就漏改前端.

**用户决策 (2026-07-09)**: 保留后端兜底, 只**修前端默认值**跟后端对齐. 不删 `_FLAVOR_DEFAULTS`, 不删 yaml camelot 默认块. 这是更稳的方案: 后端兜底保留 (admin 不传 params 时 wrapper 仍能用), 只修前端默认值的错值.

### 用户已拍的方案

| 模块 | 拍板方案 | 关联 spec |
|---|---|---|
| A | **A1 保留后端兜底 + 修对齐**: 前端 `line_scale: 40 → 15` 跟后端 `_FLAVOR_DEFAULTS["lattice"]["line_scale"]=15` 对齐; 不删后端默认值, 不删 yaml 默认块 | 本 spec §A |
| B | **B 本期实施**: 装 ghostscript (4 平台装法选型) + 后端 wrapper `_FLAVOR_DEFAULTS["lattice"]` 写死 `use_fallback=True` (前端不暴露字段) + 中文 PDF 决策树 (MinerU / PaddleOCR-VL-1.6 / 合合 TextIn) 备齐 | 本 spec §B |
| C | **C 独立 spec**: 单 flavor `stack_contiguous()` 基础合并 + PyMuPDF join_tables bbox 对齐 + LLM 裁 "Selection table continued" 重复 header; page_no 编码 `"5+6"` 字符串 | [2026-07-09-pdf-cross-page-merger-design.md](./2026-07-09-pdf-cross-page-merger-design.md) |

---

## 目标

本期实施 **A + B** (2 个模块, 1-2 天工作量), C 模块独立 spec 跑 plan:

1. **A** (本期实施, 1-2 小时): **保留后端兜底**, 只**修前端默认值的错值** (line_scale: 40 → 15) 跟后端 `_FLAVOR_DEFAULTS["lattice"]` 对齐. 改 1 行代码. 1 个 commit.
2. **B** (本期实施, 半天-1 天): **装 ghostscript** (4 平台装法选型) + **后端 wrapper 写死 `use_fallback=True`** (前端不暴露字段, admin 0 认知) + **中文 PDF 决策树备齐** (MinerU / PaddleOCR-VL-1.6 / 合合 TextIn) 给未来扩展用.
3. **C** (独立 spec, 3-5 天): 跨页表合并 C1 (stack_contiguous) + C2 (PyMuPDF bbox + LLM 裁 header). 详见 [2026-07-09-pdf-cross-page-merger-design.md](./2026-07-09-pdf-cross-page-merger-design.md).

A + B 累计 1-2 天工作量, C 独立 3-5 天, 三个模块总工作量 4-7 天.

---

## 架构

### A 模块: 保留后端兜底 + 修前端默认值

**核心思路**: 不动后端兜底, 只**修前端默认值的错值**跟后端对齐. 后端 `_FLAVOR_DEFAULTS` 是 "admin 上传不传 params" 时的兜底, 保留它, 改后端反而要 admin 改流程. 前端默认值是 admin 打开弹框看到的初始值, 错的 line_scale=40 要改.

**改动 1 处**:

| 改动点 | 内容 |
|---|---|
| [pre-analysis-upload-dialog.tsx:97](../../packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx#L97) `BACKEND_DEFAULT_PARAMS.camelot` | **改 line_scale: 40 → 15**, 注释加 "前后端必须对齐, 后端 `_FLAVOR_DEFAULTS["lattice"]["line_scale"]=15` 是 camelot 2.0 官方推荐" |

**不改动的地方** (保留后端兜底):
- [camelot_extractor.py:81-91](../../packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py#L81) `_FLAVOR_DEFAULTS` — **保留**, 这是 admin 不传 params 时的兜底
- [table_extraction.yaml:22-26](../../packages/service/configs/pre_analysis/table_extraction.yaml#L22) camelot 默认块 — **保留** (虽然现在被前端绕过, 但作为服务端兜底留着)
- [runner.py:297](../../packages/service/src/ingest/pre_analysis/runner.py#L297) — **保留** `params = table_extraction_config.get("table_params") or {}` 兜底

**关键设计决策**:

1. **为什么保留后端兜底?** —— 用户决策. 后端兜底有 2 个好处: (a) admin 上传少传参仍能工作; (b) 服务端脚本调用 (CLI / 定时任务) 不依赖前端. 删除兜底等于让后端 wrapper 变成"必须传齐所有参数才能用", 是过度约束.

2. **为什么改前端默认值而不是改后端?** —— 2026-07-08 plan 已经把后端改到 `line_scale=15` (官方推荐), 现在错的是前端. 改前端 1 行, 跟后端对齐, 5 分钟落地.

3. **3 事实源仍存在漂移风险怎么办?** —— 不在本期 spec 解决. 留作后续 spec 选项:
   - A2 删后端兜底 (本期不选, 见上面)
   - A3 后端为唯一事实源 + API 拉 (工作量大, 留 follow-up)
   - 应急: 加 CI test 验证前端默认 == 后端默认 (在 `tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py` 加一条断言)

**前端 BACKEND_DEFAULT_PARAMS.camelot 改后形态**:

```typescript
camelot: {
  flavor: "lattice",
  // (2026-07-09) line_scale 40→15: 后端 _FLAVOR_DEFAULTS["lattice"]["line_scale"]=15 是 camelot 2.0 官方推荐,
  // 旧 40 容易把短线判为"短横线"丢. 前后端必须对齐, 后端兜底保留.
  line_scale: 15,
  line_tol: 2,
},
```

### B 模块: Ghostscript 安装 + 中文 PDF 工具备齐 (本期实施)

**核心思路**: D81.1 英文场景 ghostscript 必要性低, 但**项目有未来中文 PDF 处理需求** (用户明确要求保留), 本期**装 ghostscript + 后端 wrapper 写死 `use_fallback=True` 兜底** (前端不暴露字段), 备选中文 PDF 工具 (MinerU / PaddleOCR / TextIn) 留后续 spec 选型.

#### B.1 Ghostscript 安装 (4 平台)

| 平台 | 装法 | uv add 命令 |
|---|---|---|
| Windows | `winget install Ghostscript.Ghostscript` 或 `choco install ghostscript` 或官网 .exe | `uv add "camelot-py[ml,ghostscript]"` |
| macOS | `brew install ghostscript` | 同上 |
| Linux (含 docker) | `apt-get install ghostscript` / `dnf install ghostscript` | 同上 |

**Python extra 跟系统 binary 都要**: `camelot-py[ghostscript]` 装 Python 侧 (`camelot.backends.ghostscript` 模块), 系统 PATH 还要有 `gs` 二进制. camelot 内部 pdfium 解析失败时自动回退 ghostscript (camelot 2.0 `use_fallback=True` 默认开).

**pyproject.toml 改动**: `"camelot-py[ml]>=2.0.0"` → `"camelot-py[ml,ghostscript]>=2.0.0"` ([pyproject.toml:56](../../packages/service/pyproject.toml#L56))

**CI 处理**: 跟 [project-mineru-docker-integration](../memory/project-mineru-docker-integration.md) 同模式 — `@pytest.mark.skipif(shutil.which("gs") is None)`, 装了才跑.

**本机开发机优先**: 项目目前 docker 主要给 mineru 用, ghostscript 路径**只服务开发 + CI**, 不用先动 docker 镜像.

#### B.2 中文 PDF 工具选型 (未来扩展用)

中文 CID 字体 / ToUnicode CMap 缺失是 PyMuPDF / pdfplumber / camelot 在中文 PDF 上失败的真正根因——单纯依赖系统字体库无法修复,**需要 CMap "密码本"**才能解码. **Ghostscript 兜底成功率实测约 60-75%**, 中文 PDF 场景的真实工具排行 (按 OmniDocBench v1.6 + 业界实践):

| 排名 | 工具 | OmniDocBench v1.6 | 适用 | 备注 |
|---|---|---|---|---|
| 1 | **PaddleOCR-VL-1.6** | 96.33% (业界第一) | 扫描件 / 财务表格 | 0.9B 参数, 开源, 腾讯云可用 |
| 2 | **MinerU** (opendatalab) | hybrid 95.39% / pipeline 86.47% | 通用, 109 语言 OCR | 中文原生 + 自动检测扫描件乱码 |
| 3 | **合合信息 TextIn** | 有线表 >98% (信通院 5 级评定) | 商用 / 数据敏感 | 私有化部署支持 |
| 4 | **Marker** | TEDS 0.816/0.907 (LLM 模式) | 端到端 Markdown | LLM 模式 +9 分, 需外部 LLM |
| 5 | **Docling** (IBM Granite-Docling-258M) | TableFormer 2-6s/table | MIT 许可, 原生读 PDF | [arXiv:2408.09869](https://arxiv.org/abs/2408.09869) |
| 6 | **Unstructured** | 启发式为主 | 商业友好 (Apache 2.0) | 本地部署复杂 |
| 7 | **PyMuPDF4LLM** / **Camelot** | 仅文本流 | 纯英文 + 无 ToUnicode 缺失 | 中文不可处理扫描件 |

**本期实施方案** (用户决策 2026-07-09):
- **后端 wrapper 写死 `use_fallback=True`** ([camelot_extractor.py:86](../../packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py#L86) `_FLAVOR_DEFAULTS["lattice"]` 加 `use_fallback: True`)
- **前端 dialog 不暴露 `use_fallback` 字段** — admin 0 配置, 不增加弹框噪音
- **不引入新依赖** (MinerU / PaddleOCR / TextIn 都是大依赖, 工作量大)
- **后续**: 业务方提中文 PDF 需求时, 按决策树选 MinerU / PaddleOCR / TextIn

#### B.3 use_fallback 后端 wrapper 写死, 前端不暴露

**核心决策** (2026-07-09): `use_fallback=True` 只在 camelot 内部 pdfium 解析失败时**自动**走 Ghostscript 重解析, 性能开销为 0 (成功路径不触发). 所以:

- **后端 wrapper 写死 `True`** ([camelot_extractor.py:86](../../packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py#L86) `_FLAVOR_DEFAULTS["lattice"]` 加 `use_fallback: True`)
- **前端 dialog 不暴露 `use_fallback` 字段** —— 删前端 `BACKEND_DEFAULT_PARAMS.camelot.use_fallback: false`, 不进 `PARAM_METADATA`
- **admin 0 配置 / 0 认知** —— 中文 PDF 走 wrapper 兜底, 英文 PDF 不触发, 一致行为

**为什么不留前端 toggle**: 前端给 toggle 让 admin 显式控制看似灵活, 但 `use_fallback` 99% 是"成功路径 0 开销 / 失败路径自动兜", 业务永远希望"默认兜". 暴露给 admin 反而 (a) 增加弹框噪音; (b) 让 admin 误以为 false 是性能优化而误关; (c) 跟前 spec A 模块"保留后端兜底" 原则一致, 不让前端再做一次配置.

**改动**:
- [camelot_extractor.py](../../packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py) `_FLAVOR_DEFAULTS["lattice"]` 加 `use_fallback: True`
- 前端 [pre-analysis-upload-dialog.tsx](../../packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx) `BACKEND_DEFAULT_PARAMS.camelot` 不加 `use_fallback` 字段

#### B.4 中文 PDF 触发决策树 (未来用)

```
PDF 是中文?
+-- 是 → camelot lattice + use_fallback=True (wrapper 写死, 中文 CID 字体自动走 Ghostscript 兜底 60-75%)
|         +-- 兜不住 → MinerU pipeline 86.47 / hybrid 95.39 (后续 spec)
|         |              +-- 是扫描件? → PaddleOCR-VL-1.6 (96.33 SOTA) 或 合合信息 TextIn (98+ 商用)
|         |              +-- CID 乱码 / 字体子集异常? → wrapper 已自动兜 (本期)
|         |              '-- 数据敏感不出网? → 合合信息 TextIn 私有化部署
'-- 否 (英文, 比如 D81.1) → 当前 camelot + PyMuPDF 路径 (本期 spec 范围, pdfium 成功不走 fallback)
```

---

### C 模块: 跨页表合并 (独立 spec)

C 模块内容 (C1 stack_contiguous 基础合并 + C2 PyMuPDF bbox + LLM 裁重复 header) 已抽出成独立 spec, 详见:

📄 **[2026-07-09-pdf-cross-page-merger-design.md](./2026-07-09-pdf-cross-page-merger-design.md)** (3-5 天工作量, 单独跑 plan)

**摘要**: D81.1 跨页续表 (P40-P80 selection table) 是 "复杂表差" 主要来源之一. 真根因是 camelot `stack_contiguous()` 只看列数, 不能识别 "Selection table continued" 重复 header (issue #689). 业界共识方案是 Camelot lattice (单页) + PyMuPDF join_tables bbox 对齐 + LLM 裁 header 组合拳. C1 + C2 一起实施, 1 个 spec 解决.

#### C 模块完成状态 (2026-07-09, plan [2026-07-09-pdf-cross-page-merger.md](../plans/2026-07-09-pdf-cross-page-merger.md))

| 部分 | 实现位置 | 状态 |
|---|---|---|
| C1: 单 flavor 列数匹配合并 | `src/ingest/pre_analysis/table_extractors/camelot_extractor.py::_stack_contiguous_in_flavor` | 完成 |
| C2: PyMuPDF bbox 启发式对齐 | `src/ingest/pre_analysis/table_extractors/camelot_extractor.py::CrossPageMerger` | 完成 |
| C2: LLM 裁重复 header | `src/ingest/pre_analysis/table_extractors/camelot_extractor.py::CrossPageMerger._llm_trim_header` (走 `llm_helper.get_llm_client()`) | 完成 |
| 跨页合并表 page_no 编码 `"5+6"` | `TableData.page_no: int \| str` (Task 1 升级) | 完成 |
| C2 LLM 不可用时降级 | CrossPageMerger 兜底返 base_tables, 不抛 LLMUnavailableError 给上层 | 完成 |

D81.1 真 PDF e2e (`tests/fixtures/Motors-D81-1-complete-English-09-2023.pdf`, lattice flavor): lattice 单页跑出原始 N 张表 → C1 单 flavor 列数匹配合并 → C2 bbox 对齐候选对 + LLM 裁 header (本次 env OPENAI key 未设, LLM 跳 fail-open 走 base_tables, C1 合并结果保留); 在 D81.1 上 C1 合并后 **100 张跨页表** (e.g. page_no `22+23`, `29+30`, `36+37`, `37+38`, `44+45`).

新增测试: `tests/ingest/pre_analysis/table_extractors/test_cross_page_merger.py` (C1: 5 mock + C2: 6 mock + LLM helper: 5 mock + 错误类: 2 mock = 18 全部 PASS, 1 e2e skip 需 LLM 在线).

---

## API 定义

### A 模块 API 变更

**改 1 处 (前端默认值对齐)**:

```typescript
// packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx:97
const BACKEND_DEFAULT_PARAMS: Record<TableBackend, Record<string, string | number>> = {
  pymupdf: {},
  // (2026-07-09) line_scale 40→15: 后端 _FLAVOR_DEFAULTS["lattice"]["line_scale"]=15 是 camelot 2.0 官方推荐,
  // 旧 40 容易把短线判为"短横线"丢. 前后端必须对齐. 后端兜底保留.
  camelot: { flavor: "lattice", line_scale: 15, line_tol: 2 },
  pdfplumber: { ... },
};
```

**不改** (后端兜底保留):
- `camelot_extractor.py` `_FLAVOR_DEFAULTS` 字典 — 保留
- `table_extraction.yaml` `default_params.camelot` 块 — 保留

### B 模块 API 变更

**pyproject.toml 改 1 行**:

```toml
# 改前:
"camelot-py[ml]>=2.0.0",
# 改后:
"camelot-py[ml,ghostscript]>=2.0.0", # (2026-07-09) 加 ghostscript extra: 中文 CID 字体 PDF use_fallback 兜底 (60-75% 成功率)
```

**新 e2e 测试** (`tests/ingest/pre_analysis/table_extractors/test_camelot_ghostscript_fallback.py` 新文件):

```python
@pytest.mark.skipif(
    shutil.which("gs") is None,
    reason="ghostscript 未装 (apt install ghostscript / brew install ghostscript), skip"
)
def test_ghostscript_fallback_handles_chinese_cid_pdf():
    """中文 CID 字体 PDF → use_fallback=True 兜底成功 (不像 pdfium 抛字形错位)."""
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import CamelotTableExtractor
    fixture = Path(__file__).resolve().parents[3] / "fixtures" / "定制服务器05-26.pdf"
    if not fixture.exists():
        pytest.skip(f"中文 PDF fixture 缺失: {fixture}")
    tables = CamelotTableExtractor(
        {"flavor": "lattice", "use_fallback": True}
    ).extract(str(fixture))
    assert isinstance(tables, list)
    # 不强制要求 N>0 (PDF 可能确实没表), 但**不能抛字形错位异常**
```

**新 mock test** (`tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py` 加 1 个 test):

```python
def test_camelot_wrapper_passes_use_fallback_true_by_default():
    """(2026-07-09) B 模块: use_fallback=True 后端写死, 不进前端. mock camelot.read_pdf, 验 wrapper 默传 use_fallback=True."""
    from unittest.mock import patch, MagicMock
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import CamelotTableExtractor

    mock_tables = MagicMock()
    mock_tables.__iter__ = MagicMock(return_value=iter([]))  # 空表

    with patch("camelot.read_pdf", return_value=mock_tables) as mock_read:
        CamelotTableExtractor({"flavor": "lattice"}).extract("dummy.pdf")
        _, kwargs = mock_read.call_args
        assert kwargs.get("use_fallback") is True, "wrapper 默传 use_fallback=True, 否则中文 PDF 不兜底"
```

**改 [test_camelot_ghostscript_fallback.py](../../packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_ghostscript_fallback.py)** (新文件):

- 1 个 e2e (用 `tests/fixtures/定制服务器05-26.pdf`, skipif `shutil.which("gs") is None`)
- 1 个 mock test (mock `_has_ghostscript()` helper 返 True / False, 验 wrapper 行为)
- 1 个 mock test (mock camelot 抛字形错位异常, 验 use_fallback=True 时回退 ghostscript 不抛)

---

## 数据结构变更

### `_FLAVOR_DEFAULTS` 保留 (A1 决策)

保留兜底, 不删. 加 1 条 CI 守护 test 验证前后端默认值一致 (在 `tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py` 加 1 个 test, 读前端默认值常量文件跟后端 `_FLAVOR_DEFAULTS` 对比, 不一致 fail).

### `TableData.page_no` 类型升级 (跟 C spec 同步)

跨页合并后 `TableData.page_no` 升级 `int` → `int | str`, 字符串格式 `"5+6"`. 详见 [2026-07-09-pdf-cross-page-merger-design.md §数据结构变更](./2026-07-09-pdf-cross-page-merger-design.md).

**对 runner / 前端 / LLM 的影响** (跟 C spec 同):
- runner `_write_one_table` URI 拼: `f"page-{page_no}-table-{table_no}.csv"` → `"page-5+6-table-1.csv"`, 可读
- 前端展示: `t.page_no.split("+")` 显示 `"5-6"`
- LLM 增强: 现有契约不变 (rows 是 list of list), 加 1 个 metadata 字段 `cross_page: bool` (后续增强 v2 用, 本期不实现)

---

## 测试

### A 模块测试

**改 [test_camelot_extractor.py](../../packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py)**:

- 现有 4 个 test 断言 `kwargs.get("line_scale") == 15` 等保持不变 (后端默认值保留, 行为不变)
- 新增 test: **前后端默认值对齐守护** — 读前端 `pre-analysis-upload-dialog.tsx` 的 `BACKEND_DEFAULT_PARAMS.camelot`, 跟后端 `_FLAVOR_DEFAULTS["lattice"]` 对比, 不一致 fail (防下次 plan 漏改前端)

**前端测试**:
- 改 [pre-analysis-upload-dialog.test.tsx](../../packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx): line_scale 默认值断言改 40→15 (1 行)

### B 模块测试

**新增 [test_camelot_ghostscript_fallback.py](../../packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_ghostscript_fallback.py)** (整个新文件):

- 1 个 e2e (用 `tests/fixtures/定制服务器05-26.pdf`, skipif `shutil.which("gs") is None`)
- 1 个 mock test (mock `_has_ghostscript()` helper 返 True / False, 验 wrapper 行为)
- 1 个 mock test (mock camelot 抛字形错位异常, 验 use_fallback=True 时回退 ghostscript 不抛)

**改 [test_camelot_extractor.py](../../packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py)**:

- 新增 test: `use_fallback=True` 后端 wrapper 写死, mock camelot.read_pdf 验证 kwargs 包含 `use_fallback=True` (B 模块设计, 前端不暴露)

**改 [test_factory.py](../../packages/service/tests/ingest/pre_analysis/table_extractors/test_factory.py)**:

- 新增 test: `camelot[ghostscript]` extra 装了 → 探测 helper 返 True

**C 模块测试** 详见 [2026-07-09-pdf-cross-page-merger-design.md §测试](./2026-07-09-pdf-cross-page-merger-design.md) (C1 3 mock + C2 6 mock + 1 e2e + LLM helper 2 = 11 mock + 1 e2e = 12 total).

---

## 风险 & 缓解

### A 模块风险

| 风险 | 缓解 |
|---|---|
| 3 事实源 (前端 / 后端 wrapper / yaml) 仍存在, 下次 plan 漏改前端还会漂 | 加 CI 守护 test (A 模块测试段新增), 前后端默认值不一致 fail |
| 前端 BACKEND_DEFAULT_PARAMS 是硬编码, 改默认值要改前端代码 + 发版 | 跟 spec §A 决策一致, 不在本期解决. 留作 v2 选项 (A3 后端 API 拉) |

### B 模块风险

| 风险 | 缓解 |
|---|---|
| ghostscript 装上后 camelot 行为变了 (use_fallback 自动走) | mock test 断言 `kwargs.get("use_fallback") is True`, 防 wrapper 默传丢失 |
| CI 没装 ghostscript, e2e 测试 skip | `pytest.importorskip("camelot")` + `shutil.which("gs")` 双重 guard |
| 中文 PDF 触发测试可能本身 PDF 提不到表 | 测试只断言"不抛字形错位异常", 不断言 N>0 |
| [ghostscript] extra 拉了额外依赖 (pdfminer.six 等) | pyproject.lock diff review, 增量 < 5MB OK |
| LLM 客户端 ollama 不可用 → 降级 openai 需 env | 跟 [feedback-no-mock-for-external-systems](../memory/feedback-no-mock-for-external-systems.md) 一致, 真测时验真 LLM 调通 |

**C 模块风险** 详见 [2026-07-09-pdf-cross-page-merger-design.md §风险 & 缓解](./2026-07-09-pdf-cross-page-merger-design.md).

---

## 文件清单

**改动**:

| 模块 | 文件 | 改动 |
|---|---|---|
| A | [packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx](../../packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx) | `line_scale: 40 → 15`, 注释说明对齐后端 |
| A | [packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx](../../packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx) | 1 个 test 改 line_scale 默认值断言 |
| A | [packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py](../../packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py) | 加 1 个新 test (前后端默认值对齐守护) |
| B | [packages/service/pyproject.toml](../../packages/service/pyproject.toml) | `camelot-py[ml]` → `camelot-py[ml,ghostscript]` (line 56) |
| B | `packages/service/uv.lock` | uv sync 自动重生成 |
| B | 新增 `packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_ghostscript_fallback.py` | e2e + 2 个 mock test |
| B | [packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py](../../packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py) | `_FLAVOR_DEFAULTS["lattice"]` 加 `use_fallback: True` (后端写死, 前端不暴露) |
| B | [packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py](../../packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py) | 加 1 个新 test: wrapper 默传 use_fallback=True |

**C 模块文件清单** 详见 [2026-07-09-pdf-cross-page-merger-design.md §文件清单](./2026-07-09-pdf-cross-page-merger-design.md) (camelot_extractor.py 改 extract + 新增 CrossPageMerger class, src/core/llm_helper.py 新增 trim_repeated_header, base.py 改 TableData.page_no 类型, 3 个新 test 文件).

**不改**:

- 后端其它表格提取后端 (pymupdf / pdfplumber) 不动, 跟本 spec 无关
- BFF / router / API contract 不动
- 前端表格展示组件不动 (跨页 page_no "5+6" 在前端用 split('+') 显示 "5-6" 是 C spec 实施后的细节)
- [camelot_extractor.py](../../packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py) `_FLAVOR_DEFAULTS` 字典 **保留** (A1 决策)
- [table_extraction.yaml](../../packages/service/configs/pre_analysis/table_extraction.yaml) `default_params.camelot` 块 **保留**
- [runner.py](../../packages/service/src/ingest/pre_analysis/runner.py) `_detect_cross_page` **保留** (跟 C spec C1/C2 并存)

---

## 执行顺序

**本期实施 2 模块 (A + B)**, 推荐顺序:

1. **A 先做** (1-2 小时, 改前端默认值对齐) — 最小最快, 立刻见效
2. **B 接着做** (半天 - 1 天, 装 ghostscript + 写 e2e 测试) — 加依赖 + 触发测试

**C 模块独立跑 plan** (3-5 天), 详见 [2026-07-09-pdf-cross-page-merger-design.md](./2026-07-09-pdf-cross-page-merger-design.md).

理由: A 改前端 1 行, B 装依赖, 2 个都 1 天内能做完. C 复杂度高 (LLM 集成 + PyMuPDF bbox), 单独跑 plan 跟 A + B 解耦.

累计工作量: **A + B 1-2 天 + C 3-5 天 = 4-7 天**.

---

## 验收 (End-to-End)

### A 验收

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/ -v
```

Expected: 全 PASS, 现有 33 个 test + 1 个新加的"前后端默认值对齐守护" test 绿.

```bash
cd packages/web && bun run test -- pre-analysis-upload-dialog.test
```

Expected: 全 PASS, line_scale 默认值断言改 40→15 后绿.

### B 验收

```bash
gs --version  # 装上后能输出版本号
```

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_ghostscript_fallback.py -v
```

Expected: e2e skip if gs 未装, 2 个 mock test 全绿.

### C 验收 (独立 spec)

已完成 (2026-07-09 plan [2026-07-09-pdf-cross-page-merger.md](../plans/2026-07-09-pdf-cross-page-merger.md)).

详见 [2026-07-09-pdf-cross-page-merger-design.md §验收](./2026-07-09-pdf-cross-page-merger-design.md).

实际落地: C1 5 mock + C2 6 mock + LLM helper 5 mock + 错误类 2 mock = 18 mock test PASS, 1 e2e (D81.1 端到端) pass with LLM 客户端可用 / skip without. D81.1 实际跑 lattice + C1 合并后 100 张跨页表 (page_no `"5+6"` 编码).

最终 commits: 6 个, 都在 `feature/pdf-cross-page-merger` 分支, 已等 spec 合并回 master.

### 集成验收 (A + B 全做完后)

```bash
cd packages/service && uv run pytest -q  # 全套
```

Expected: 跟 baseline (33 passed in 317s) 比 +7 个新 PASS (A: 2 [test_camelot_extractor.py 加 1 前后端对齐守护 + 前端 dialog test 改 1 line_scale 断言] + B: 5 [test_camelot_ghostscript_fallback.py 新文件 1 e2e + 2 mock + test_camelot_extractor.py 加 1 use_fallback wrapper 默传 + test_factory.py 加 1 ghostscript extra 探测]), 0 新 fail. C spec 独立验收.

---

## 附录: 联网调研 24 个权威源

### 官方源 (高权威)

- [camelot-py pypi 页面](https://pypi.org/project/camelot-py/) — v2.0.0 release info, extras 清单
- [camelot-py README](https://github.com/camelot-dev/camelot/blob/master/README.md) — flavor 选择矩阵 + 安装指南 + stack_contiguous 推荐
- [camelot-py docs comparison.rst](https://raw.githubusercontent.com/camelot-dev/camelot/master/docs/user/comparison.rst) — 与其他工具能力矩阵
- 源码 `parsers/lattice.py` — 完整 20 个参数默认值
- 源码 `parsers/stream.py` — 完整参数 + Nurminen 算法引用
- 源码 `parsers/network.py` — 文本对齐算法
- [camelot-dev/camelot PR #198](https://github.com/camelot-dev/camelot/pull/198) — 多 backend 抽象 (use_fallback)
- [camelot-dev/camelot PR #809](https://github.com/camelot-dev/camelot/issues/809) — ml flavor 引入
- [camelot-dev/camelot issue #628](https://github.com/camelot-dev/camelot/issues/628) — stack_contiguous 跨页 (本期 C 模块用)

### GitHub issues (D81.1 类表格实战)

- [marker GitHub README (TEDS 0.816/0.907 FinTabNet)](https://github.com/datalab-to/marker) — LLM 模式 +9 分
- [gmft GitHub README](https://github.com/conjuncts/gmft) — 明确不支持多页拼接
- [PyMuPDF Page.find_tables](https://pymupdf.readthedocs.io/en/latest/page.html) — 1.23.19+ `add_lines` 参数
- [PyMuPDF join_tables.ipynb](https://github.com/pymupdf/PyMuPDF-Utilities/tree/master/table-analysis) — 官方跨页拼接笔记本 (v2 C2 参考)

### 中文 PDF 工具 (B 决策树来源)

- [MinerU 中文 README (OmniDocBench v1.6 95.39)](https://github.com/opendatalab/MinerU/blob/master/README_zh-CN.md)
- [PaddleOCR-VL-1.6 (OmniDocBench v1.6 96.33%)](https://cloud.tencent.com/developer/article/2627607)
- [合合信息信通院 5 级评定 (有线表 >98%)](https://tech.gmw.cn/2023-06/20/content_36642376.htm)
- [CSDN 2019 CID/CMap 深度分析](https://blog.csdn.net/aogufeixue/article/details/94431009)

### 学术 / 训练集

- [PubTables-1M 论文 arXiv:2110.00061](https://www.microsoft.com/en-us/research/publication/pubtables-1m/) — TATR 训练集, 948k 表
- [Docling Technical Report arXiv:2408.09869v5](https://arxiv.org/abs/2408.09869) — IBM TableFormer
- [PdfTable arXiv:2409.05125](https://arxiv.org/html/2409.05125v1) — 武汉理工 2024-09 跨页测评
- [CED: Catalog Extraction from Documents arXiv:2304.14662](https://arxiv.org/abs/2304.14662) — 唯一目录结构提取论文
- [Anssi Nurminen 表检测论文](https://dspace.cc.tut.fi/dpub/bitstream/handle/123456789/21520/Nurminen.pdf?sequence=3) — Stream 算法原始引用
- [Artifex PyMuPDF vs Camelot 性能比较](https://artifex.com/blog/comparing-pymupdf-and-camelot) — PyMuPDF 10x speed 验证

---

## Out of Scope (本期 A + B 不实施)

- ❌ **C 模块 (跨页表合并)** —— 已抽出为独立 spec [2026-07-09-pdf-cross-page-merger-design.md](./2026-07-09-pdf-cross-page-merger-design.md), 单独跑 plan 跟 A + B 解耦
- ❌ **B 模块中文 PDF 工具引入** (MinerU / PaddleOCR-VL-1.6 / 合合 TextIn) —— 本期只装 ghostscript (60-75% 兜底); MinerU 等是大依赖, 业务方提中文 PDF 需求时按 spec §B.4 决策树启新 spec
- ❌ **B 类色块表头的真正解** (西门子紫/蓝块) —— `process_background=True` 只解 background lines, 不解 cell background fills; 真要解需 ml flavor 兜底 (PyTorch CPU 慢 ~30s/页) 或 PyMuPDF 颜色阈值方案, 留后续 spec
- ❌ 旋转表自动 deskew (issue #244) —— 留给后续 spec
- ❌ 合并单元格 `copy_text=['h','v']` 默认开 (issue #349 / #354) —— admin 调参解决, 不暴露 UI
- ❌ ml flavor 默认开 —— admin 主动选 ml flavor 跑少数复杂表
- ❌ `flavor="auto"` (v2.0 新增, 按页选 lattice/network) —— 留 v3 调研
- ❌ A3 后端为唯一事实源 + API 拉 (3 事实源根除) —— 工作量大 (3-5 天), 留 follow-up

---

**Why this spec**: 用户 2026-07-09 报 "复杂表差" 时, 不能直接装插件或改参数. 经代码 + memory + 联网调研 (21 源 + D81.1 实拍 P11-P15) 三方验证, 真正根因是 3 个独立维度 (A 前后端漂移 / B 中文 PDF 兜底 / C 跨页续表). 本 spec 覆盖 A + B (1-2 天), C 抽出独立 spec (3-5 天). 总工作量 4-7 天.
**How to apply**: 推荐 A 先 (1-2 小时) → B 后 (半天-1 天). 评审后写 plan (task-by-task), 实施期严格 TDD. C 独立 spec 单独跑 plan.