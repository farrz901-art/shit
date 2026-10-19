# PDF 结构化预分析 spec (v1)

**日期**: 2026-07-02
**状态**: 设计待审
**触发来源**: 用户给 DeepSeek 分享链接 `https://chat.deepseek.com/share/wbmg0i1neb616saobg`, 内部头脑风暴验证后立项.

---

## Context

DeepSeek 对话给的是西门子 D81.1 / D84.1 手册"结构化预分析"5 步方法论 (人工解构目录 → 自动化提取 → 关键词标记 → 产物落地). 调研确认:

1. **本项目已覆盖大半**: ingest 流水线 (kreuzberg/mineru) 已跑 PDF→markdown, pymupdf 已用于 PDF 复杂度分析 ([analyzers/pdf.py:5](packages/service/src/ingest/analyzers/pdf.py)).
2. **DeepSeek 提的 PyMuPDF4LLM / Camelot 都不需要新装**:
   - pymupdf 已 import, `page.find_tables()` 是 2020 年后 PyMuPDF 的内置功能 (替代 Camelot).
   - PyMuPDF4LLM 是 markdown 输出, kreuzberg 已经在做.
3. **未覆盖**: 把 markdown 再加工成"目录结构 JSON + 表格 CSV + 规则段落 CSV"这种 admin 能下载验收的产物集, 跟 DeepSeek 方法论产出 1:1 对齐.

新功能定位是 **独立模块 `pre_analysis`**, 跟现有 `ingest` / `kg` 平级, **不耦合** KG 抽取 (区别于 2026-07-02 motor-ontology-extract spec). 给 admin 一个工具, 把手册 PDF 在送进 kg extract 之前先做一遍预分析, 让预抽取的人工核对成本降下来.

## 目标

实现一个 "**PDF 上传 → 后台异步 → 产物清单 → admin 下载**" 的预分析流水线, 跟 DeepSeek 5 步方法论产出 1:1 对齐:

- **chapter_structure.json** — PDF 章节结构 (章/节标题 + 层级 + 页码) + kreuzberg/mineru markdown 渲染节录
- **tables/page-3-table-1.csv** 等 — PDF 中每个表格单独导出 CSV
- **flagged_paragraphs.csv** — 关键词 ["注意", "不能", "仅适用", "必须", "禁止"] 命中的段落列表

前端: 1 个 super_admin 表格页 `/admin/pre-analysis` (上传 PDF + 进度 + 下载 zip), 跟现有 `/api/ingest/...` 风格对齐.

**非目标 (本期不做, 给未来 spec 留空间)**:

- ❌ 跟 KG 抽取流水线联动 (上传 PDF 后自动送 kg extract) — 单独 spec, 走 `kg_extraction` ↔ `pre_analysis` 解耦, admin 手动 2 步走
- ❌ 跨页表格自动合并 — pymupdf `find_tables()` 限制, 后续 spec
- ❌ OCR / 扫描件识别 — kreuzberg/mineru 已 layer 覆盖, 本模块假设 PDF 至少 pymupdf `get_text()` 返非空
- ❌ 同义归并 / 单位归一 — 这是 `motor-ontology-extract` spec (2026-07-02) 范围
- ❌ MLFB 状态机 / TIA Selection Tool 反向验证 — 同 2026-07-02 spec 非目标
- ❌ 实时 (sub-second) 返回 — 复用 ingest 异步 BackgroundTasks 模式
- ❌ 多用户 — 仅 super_admin 可访问 (项目 admin 是 1 类用户群)

## 产物示例 (D81_2021.pdf, 50 页西门子电机手册)

> **目的**: 让审 spec 的人 1 眼看明白落地形态. 数据来源: 模拟 D81.1 真手册真实结构, 字段对齐 spec §抽象接口.

### 4.1 `chapter_structure.json`

```json
{
  "pdf_filename": "D81_2021.pdf",
  "total_pages": 50,
  "total_chapters": 6,
  "total_sections": 23,
  "extracted_at": "2026-07-02T14:32:11+08:00",
  "toc_source": "pdf_outline",
  "chapters": [
    {
      "level": 1,
      "title": "通用技术指导",
      "page_start": 1,
      "page_end": 8,
      "section_index": "1",
      "preview_markdown": "## 1 通用技术指导\n\n本章介绍国际能效定义、电机选型指导...\n\n### 1.1 国际能效等级\n\nIE3 / IE4 / IE5 等级划分依据 IEC 60034-30-1..."
    },
    {
      "level": 1,
      "title": "SIMOTICS GP/SD 系列标准电机 (1LE1/1PC1 强冷型)",
      "page_start": 9,
      "page_end": 22,
      "section_index": "2",
      "preview_markdown": "## 2 SIMOTICS GP/SD 系列标准电机\n\n### 2.1 1LE1 系列 三相异步电机\n\n功率范围 0.55 - 200 kW, 机座号 80 - 315 mm..."
    },
    {
      "level": 1,
      "title": "SIMOTICS GP/SD VSD10 变频器驱动电机",
      "page_start": 23,
      "page_end": 30,
      "section_index": "3",
      "preview_markdown": "## 3 SIMOTICS GP/SD VSD10\n\n配合 SINAMICS V90/V20 变频器, 强制风冷..."
    },
    {
      "level": 1,
      "title": "SIMOTICS XP 1MB1 防爆电机",
      "page_start": 31,
      "page_end": 38,
      "section_index": "4",
      "preview_markdown": "## 4 SIMOTICS XP 1MB1 防爆系列\n\nEx d IIB T4 Gb / Ex d IIC T4 Gb..."
    },
    {
      "level": 1,
      "title": "SIMOTICS DP 1PC1 排烟电机",
      "page_start": 39,
      "page_end": 44,
      "section_index": "5",
      "preview_markdown": "## 5 SIMOTICS DP 1PC1 排烟电机\n\nF300 / F400 耐火等级..."
    },
    {
      "level": 1,
      "title": "附录: NEMA 电机 / 服务支持 / 工具",
      "page_start": 45,
      "page_end": 50,
      "section_index": "6",
      "preview_markdown": "## 6 附录\n\nNEMA MG1 标准映射表, 选件代码..."
    }
  ]
}
```

### 4.2 `tables/page-9-table-1.csv` (第 9 页 1LE1 选型表)

```csv
机座号,极数,额定功率 kW,额定电压 V,额定电流 A,效率 %,转速 rpm,机座长度
80M,2,0.75,400,1.7,82.5,2880,M
80M,4,0.55,400,1.5,78.0,1430,M
90S,2,1.5,400,3.2,84.0,2880,S
90S,4,1.1,400,2.6,79.5,1430,S
90L,2,2.2,400,4.6,85.5,2885,L
90L,4,1.5,400,3.4,81.0,1430,L
100L,2,3.0,400,6.1,86.5,2895,L
100L,4,2.2,400,4.8,83.0,1440,L
```

### 4.3 `tables/page-31-table-1.csv` (第 31 页 防爆电机选型表)

```csv
型号,防爆等级,功率 kW,机座号,适用环境
1MB1 80M,Ex d IIB T4 Gb,0.55-0.75,80,Zone 1 工厂
1MB1 90S,Ex d IIB T4 Gb,1.1-1.5,90,Zone 1 工厂
1MB1 100L,Ex d IIC T4 Gb,2.2-3.0,100,Zone 1 化工
```

### 4.4 `flagged_paragraphs.csv`

```csv
matched_keywords,page,section,text
注意,3,1.2,注意：海拔超过 1000 米时, 输出功率需按每 1000 米降容 8% 计算. 超过 4000 米需特殊订购
不能,5,1.3,不能将 1LE1 与 1LA4 系列的接线盒混用, 两者安装孔位不兼容
必须,5,1.3,所有 1LE1 系列电机必须配置接地端子, 接地电阻 ≤ 4 Ω
仅适用,12,2.1.3,本降容曲线仅适用于 IE3 高效等级电机, IE2 电机需参考附录 B
禁止,15,2.2.1,禁止在海拔 > 5000 米环境使用 1LE0102 型号, 高海拔绝缘击穿风险
不能,18,2.3.4,1LE0102 与 1LE0103 不能同时接入同一变频器, 两者启动特性冲突
必须,21,2.4,变频驱动时必须配置输出滤波器, 否则轴承电流将导致过早损坏
禁止,28,3.2,VSD10 严禁超过额定转速 110% 运行, 永磁体退磁风险
仅适用,32,4.1,1MB1 防爆系列仅适用于 Zone 1 区域, Zone 0 需特殊设计
注意,35,4.3,注意：防爆电机维修后必须重新进行泄漏测试, 否则失去防爆认证
必须,40,5.1,排烟电机必须每 6 个月进行一次 F300/F400 耐火测试
```

### 4.5 `index.json` (产物清单索引, DB 持久化用)

```json
{
  "task_id": "pa-3f8c2e1a-4b5d-4e7f-9a1c-2d3e4f5a6b7c",
  "pdf_filename": "D81_2021.pdf",
  "extracted_at": "2026-07-02T14:32:11+08:00",
  "elapsed_ms": 28421,
  "summary": {
    "total_chapters": 6,
    "total_sections": 23,
    "total_tables": 12,
    "total_flagged_paragraphs": 11,
    "total_output_files": 15
  },
  "files": [
    {
      "kind": "chapter_structure",
      "filename": "chapter_structure.json",
      "size_bytes": 3842,
      "uri": "s3://rag-ingest/pre_analysis_outputs/pa-3f8c2e1a.../chapter_structure.json"
    },
    {
      "kind": "flagged_paragraphs",
      "filename": "flagged_paragraphs.csv",
      "size_bytes": 2156,
      "uri": "s3://rag-ingest/pre_analysis_outputs/pa-3f8c2e1a.../flagged_paragraphs.csv"
    },
    {
      "kind": "table",
      "filename": "tables/page-9-table-1.csv",
      "size_bytes": 512,
      "uri": "s3://rag-ingest/pre_analysis_outputs/pa-3f8c2e1a.../tables/page-9-table-1.csv"
    },
    {
      "kind": "table",
      "filename": "tables/page-31-table-1.csv",
      "size_bytes": 384,
      "uri": "s3://rag-ingest/pre_analysis_outputs/pa-3f8c2e1a.../tables/page-31-table-1.csv"
    }
  ]
}
```

### 4.6 zip 包结构 (admin 下载后解压)

```
D81_2021_pre_analysis_pa-3f8c2e1a.zip
├── chapter_structure.json              (3.8 KB)
├── flagged_paragraphs.csv              (2.1 KB)
├── index.json                          (1.2 KB)
└── tables/
    ├── page-9-table-1.csv              (0.5 KB) - 1LE1 选型
    ├── page-12-table-1.csv             (0.4 KB) - 机座号尺寸
    ├── page-15-table-1.csv             (0.7 KB) - 轴承规格
    ├── page-21-table-1.csv             (0.3 KB) - 滤波器选型
    ├── page-23-table-1.csv             (0.5 KB) - VSD10 选型
    ├── page-31-table-1.csv             (0.4 KB) - 防爆选型
    ├── page-39-table-1.csv             (0.4 KB) - 排烟选型
    ├── page-45-table-1.csv             (0.6 KB) - NEMA 映射
    ├── page-46-table-1.csv             (0.3 KB) - 选件代码
    ├── page-47-table-1.csv             (0.4 KB) - 工具清单
    ├── page-48-table-1.csv             (0.3 KB) - 服务热线
    └── page-49-table-1.csv             (0.4 KB) - 文档版本
```

### 4.7 跟 DeepSeek 原方法论 1:1 对照

| DeepSeek 原方法论产物 | 本项目落地 | 字段覆盖 |
|---|---|---|
| `chapter_structure.json` (章标题 + 层级 + 页码) | ✅ 含 `chapters[].{level, title, page_start/end, section_index}` + `preview_markdown` (kreuzberg 渲染) | 100% + bonus preview |
| `tables/page-N-table-M.csv` (每个表格单独 CSV) | ✅ `tables/` 子目录, 命名规范 `page-N-table-M.csv` | 100% |
| `flagged_paragraphs.csv` (关键词命中段落) | ✅ 含 `matched_keywords + page + section + text` | 100% + 加 page/section 定位 |
| 验证迭代 (人工抽查 + 调 Camelot 参数) | ✅ 详情页 UI + 下载 zip + 任务失败 stderr | 100% |

## 调研结论

### 已有依赖 (不新装)

| 库 | 已在 | 本期用途 |
|---|---|---|
| `pymupdf` (>=1.24) | 是 (analyzers/pdf.py:5) | `get_toc()` 拿目录, `page.find_tables()` 拿表格 |
| `loguru` | 是 | logger 走 loguru, 不用 stdlib logging |
| `pydantic` v2 | 是 (CLAUDE.md 强制) | Request / Response schema |
| `kreuzberg>=4.9.7` | 是 (kreuzberg.py:7) | 章节 markdown 文本片段渲染 (复用 convert_batch) |

**不装** PyMuPDF4LLM / Camelot / pdfplumber. 理由:
- PyMuPDF4LLM ≈ markdown 输出, kreuzberg 已经在做这个; 重复引入会 2 套 markdown 引擎
- Camelot 2018 年停更, pymupdf 2020 后内置 `find_tables()` 完全替代
- pdfplumber 跟 pymupdf 重叠, 仅 pymupdf 即可

### ObjectStore ABC 复用

[src/storage/object_store.py:113](packages/service/src/storage/object_store.py) 已 14 抽象方法封装完整. 本期 0 新增方法, 直接复用 `put_bytes/get_bytes/presign_put/list_prefix`. URI 布局:

```
s3://rag-ingest/pre_analysis_inputs/{task_id}/input/foo.pdf
s3://rag-ingest/pre_analysis_outputs/{task_id}/chapter_structure.json
s3://rag-ingest/pre_analysis_outputs/{task_id}/tables/page-3-table-1.csv
s3://rag-ingest/pre_analysis_outputs/{task_id}/flagged_paragraphs.csv
s3://rag-ingest/pre_analysis_outputs/{task_id}/index.json           (清单索引)
```

### 数据存储: 新建独立 pre_analysis_tasks 表 (2026-07-02 用户决策)

**决策 (2026-07-02 用户拍板)**: **新建独立 `pre_analysis_tasks` 表**, **不**复用 `ingest_tasks` 表 + task_kind 列. 理由: admin 列表清晰, 跟 ingest 解耦, 不混产.

**新表 schema** (1 个 alembic migration):

```python
# packages/service/src/storage/migrations/versions/20260702_000000_pre_analysis_tasks.py

def upgrade() -> None:
    op.create_table(
        "pre_analysis_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_hash", sa.String(64), nullable=False, index=True),  # 跟 ingest_tasks 一致 (2026-06-15)
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("pdf_filename", sa.String(255), nullable=False),
        sa.Column("pdf_uri", sa.String(500), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "output_files_json",
            sa.Text,
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "summary_json",
            sa.Text,
            nullable=False,
            server_default="{}",
        ),
    )
    op.create_index(
        "ix_pre_analysis_tasks_user_started",
        "pre_analysis_tasks",
        ["user_hash", "started_at"],
    )

def downgrade() -> None:
    op.drop_index("ix_pre_analysis_tasks_user_started", "pre_analysis_tasks")
    op.drop_table("pre_analysis_tasks")
```

**字段说明**:

| 字段 | 类型 | 用途 |
|---|---|---|
| `id` | String(36) UUID | 业务 ID |
| `user_hash` | String(64) | super_admin user_hash (从 token 派生, 跟 ingest_tasks 模式一致) |
| `state` | String(20) | pending / running / completed / failed |
| `pdf_filename` | String(255) | 原 PDF 文件名 (admin UI 显示) |
| `pdf_uri` | String(500) | ObjectStore URI `s3://rag-ingest/pre_analysis_inputs/{id}/input/{file}` |
| `started_at` | DateTime | 任务创建时间 |
| `finished_at` | DateTime | 任务结束时间 (NULL = 还在跑) |
| `error` | Text | stderr tail (失败时填) |
| `output_files_json` | Text | `[{"kind": "chapter_structure", "uri": "...", "filename": "...", "size_bytes": 3842}, ...]` |
| `summary_json` | Text | `{"total_chapters": 6, "total_tables": 12, "total_flagged_paragraphs": 11, "elapsed_ms": 28421, "cross_page_candidates": 1}` |

**summary_json.cross_page_candidates** (2026-07-02 调研后加): 启发式统计 "页 N 表格 N 跟页 N+1 表格 1 列数一致 + footer 关键词" 的跨页候选数. UI 详情页提示 admin "本任务含 N 个跨页候选表, 详见 page-X / page-Y".

**ORM 类** (新文件 `packages/service/src/ingest/pre_analysis_models.py`):

```python
class PreAnalysisTask(Base):
    __tablename__ = "pre_analysis_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # 跟 ingest_tasks 一致
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    pdf_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    pdf_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_files_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    __table_args__ = (Index("ix_pre_analysis_tasks_user_started", "user_hash", "started_at"),)
```

### 后台异步模式复用

[src/ingest/api.py:392](packages/service/src/ingest/api.py) `background.add_task(_run_ingest, task.id, ...)` 是模板. 本期：

- 新建 `PreAnalysisRunner` 类 ([src/kg/extract_runner.py:49](packages/service/src/kg/extract_runner.py) `run_extraction` 同模式, 抄)
- API 端点 `POST /api/pre-analysis/upload` 接 PDF → 创建 ingest_task + work_dir → `add_task(_run_pre_analysis, ...)`
- `_run_pre_analysis` 调 `pymupdf` 提取 + 写产物 + 更新 task state

### 鉴权复用

仅 super_admin 可调. 复用现有 `request.state.user` + `auth.is_super_admin` 守卫 (CLAUDE.md §鉴权). 不引新鉴权层.

---

## 架构设计

### 后端目录布局 (增量)

```
packages/service/
├── configs/
│   └── pre_analysis/                          # [新] 预分析配置
│       └── rule_keywords.yaml                 # [新] 关键词白名单 + 同义扩展 (默认 5 个, 可扩)
├── src/
│   ├── ingest/
│   │   ├── pre_analysis_models.py                 # [新] PreAnalysisTask ORM 类
│   │   ├── api.py                                 # [改] 加 4 个 /pre-analysis/* 端点, 抄 ingest template
│   │   └── pre_analysis_runner.py                 # [新] PreAnalysisRunner 后台 pipeline
│   ├── storage/
│   │   └── migrations/
│       └── versions/
│           └── 20260702_000000_pre_analysis_tasks.py   # [新] 新建 pre_analysis_tasks 表
└── tests/
    ├── ingest/
    │   ├── test_pre_analysis_runner.py         # [新] 14 测试: 3 提取器 + 1 runner + 2 集成 + 1 zip
    │   ├── test_pre_analysis_api.py            # [新] 4 测试: 4 端点
    │   └── fixtures/
    │       └── pre_analysis/
    │           ├── d81_dummy.pdf                # [新] pymupdf 程序生成 (5 页, 1 表, 3 关键词段) 走模式 2/4
    │           └── flagged_paragraphs_expected.csv   # [新] 真值对照
```

### 前端目录布局 (增量)

> **关键决策 (2026-07-02 复用核查)**: 前端本期 **0 新组件**, 全部走项目已有封装 ([packages/web/CLAUDE.md §封装组件](../../packages/web/CLAUDE.md)). 仅 2 个新 page + 1 个新 API wrapper.

```
packages/web/
├── app/[locale]/admin/pre-analysis/
│   ├── page.tsx                                 # [新] 主表格页 (复用 DataTable + GuardPage, 抄 admin/users/page.tsx 模板)
│   └── [task_id]/
│       └── page.tsx                             # [新] 详情页 (复用 DataTable 列产物清单, 上传用内嵌 FileDropzone 不抽 dialog)
└── lib/api/
    └── pre-analysis.ts                          # [新] 4 端点 fetch wrapper + 3 type + vitest (抄 lib/api/users.ts 模板)
```

**复用清单 (本期前端的全部 UI 元素)**:

| UI 需求 | 复用现成组件 | 引用位置 |
|---|---|---|
| 主表格 (任务列表) | `<DataTable<PreAnalysisTaskItem>>` | `@/components/common/table/data-table` (CLAUDE.md §表格组件强制) |
| 详情页产物清单 | `<DataTable<PreAnalysisOutputFile>>` | 同上 |
| 上传 PDF | `<FileDropzone>` | `@/components/common/input/file-dropzone` (CLAUDE.md §新封装 6) |
| 上传表单 / 校验 | `<Form>` + `<FormField>` | `@/components/common/form` (CLAUDE.md §已有封装 7) |
| 状态徽章 (pending/running/completed/failed) | `<Badge>` + state→variant 映射函数 | `@/components/ui/badge.tsx` (shadcn 已装) |
| 错误提示 | `<ErrorBanner>` | `@/components/common/feedback/error-banner` (CLAUDE.md §新封装 6) |
| 下载按钮 | `<Button asChild><a href download href={api_url}>` | `@/components/ui/button.tsx` + 原生 `<a download>`, **不**抽 `<DownloadZipButton>` (业务出现 1 次, 不满足 ≥2 次封装门槛) |
| 详情页返回 | `<BackLink>` | 项目现成 (admin 页都用) |
| 鉴权 + 重定向 | `<GuardPage pageKey="admin">` | `@/components/auth/guard-page` (CLAUDE.md §GuardPage) |
| 列表 + 详情页标题区 | `<PageHero>` | 项目现成 |
| i18n 跳转 | `useRouter` from `@/i18n/navigation` | CLAUDE.md §路由跳转强制 |
| 数据获取 | TanStack Query `useQuery` (5.x) | CLAUDE.md §优先用已安装库 |

**不新建组件的依据** ([packages/web/CLAUDE.md §封装新组件流程](../../packages/web/CLAUDE.md)):

> "凡是'组合 ≥3 个 shadcn/Radix 原语'或'业务出现 ≥2 次'都要考虑封装成 `<AppXxx>`". 本期 PDF 上传仅 admin/pre-analysis 1 处用, **不满足业务 ≥2 次门槛**, 因此不上传 dialog 不抽 `<AppPdfUploadDialog>`, 在 page.tsx 内嵌 `<FileDropzone>` + `<Form>` 即可.

**测试文件位置** (跟 CLAUDE.md §TDD 一致):
- `app/[locale]/admin/pre-analysis/page.test.tsx` — page 测 DataTable 渲染 + 状态 badge
- `app/[locale]/admin/pre-analysis/[task_id]/page.test.tsx` — 详情页测产物清单 + 下载按钮渲染
- `lib/api/pre-analysis.test.ts` — 4 端点 + 错误码 (mode 1 mock fetch)

### 数据流

```
admin 上传 PDF
    │
    ▼ POST /api/pre-analysis/upload
    │
    │ 1. super_admin guard
    │ 2. ObjectStore.put_bytes(s3://.../pre_analysis_inputs/{uuid}/input/{file})
    │ 3. INSERT pre_analysis_tasks (id=uuid, state='pending', pdf_uri, user_hash, ...)
    │ 4. background.add_task(_run_pre_analysis, uuid)
    │
    ▼ BackgroundTasks
    │
    │ _run_pre_analysis(uuid):
    │   1. ObjectStore.open_local(work_dir + 'input/foo.pdf')
    │   2. pymupdf.open(path) → get_toc() → chapter_structure.json
    │   3. for page in doc: page.find_tables().tables[i].to_pandas().to_csv() → tables/page-N-table-M.csv
    │   4. text: chunks = 按段切 (markdown 或纯文本), regex 关键词匹配 → flagged_paragraphs.csv
    │   5. ObjectStore.put_bytes(.../chapter_structure.json, json.dumps(...))
    │   6. ObjectStore.put_bytes(.../tables/*.csv, csv content)
    │   7. ObjectStore.put_bytes(.../flagged_paragraphs.csv, csv content)
    │   8. ObjectStore.put_bytes(.../index.json, {产物清单})
    │   9. UPDATE pre_analysis_tasks SET state='completed', output_files_json=[...], summary_json={...}, finished_at=NOW()
    │
    ▼ GET /api/pre-analysis/tasks/{id}
        返回 task 元数据 + 产物清单
        ▼ admin 点击 "Download ZIP"
        GET /api/pre-analysis/tasks/{id}/download → streaming zip
```

### 关键算法: 关键词标记段落

```python
# src/ingest/pre_analysis_runner.py
KEYWORDS_DEFAULT = ["注意", "不能", "仅适用", "必须", "禁止"]

def flag_paragraphs(text: str, keywords: list[str]) -> list[FlaggedParagraph]:
    """按段落切, 任一关键词命中 → 标 [RULE]"""
    result = []
    # 段落 = double-newline 分隔, 含标题层级 (Markdown '#' 开头也算段)
    paragraphs = re.split(r"\n\s*\n", text)
    cursor = 0
    for para in paragraphs:
        para_text = para.strip()
        if not para_text:
            cursor += len(para) + 2  # skip 2 \n
            continue
        matched = [kw for kw in keywords if kw in para_text]
        if matched:
            result.append(FlaggedParagraph(
                matched_keywords=matched,
                text=para_text,
                char_offset=cursor,
                char_length=len(para_text),
            ))
        cursor += len(para) + 2
    return result
```

**为什么不做 LLM 抽取实体**: DeepSeek 第 4 步仅 "关键词标记", 实体抽取是 kg extract 范围, 解耦.

### 关键算法: 表格 CSV

```python
# 用 pymupdf 内置 find_tables (替代 Camelot)
import pymupdf
doc = pymupdf.open(pdf_path)
for page_idx, page in enumerate(doc):
    tables = page.find_tables()  # TabularParser
    for table_idx, table in enumerate(tables):
        # table.extract() 是 list[list[str]]
        df = pd.DataFrame(table.extract()[1:], columns=table.extract()[0])
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        put_bytes(f"s3://.../tables/page-{page_idx+1}-table-{table_idx+1}.csv", csv_bytes)
```

**`pandas` 依赖**: 当前项目 `pyproject.toml` 需 check. 如果没装, fallback 用 `csv` stdlib (`table.extract()` 是 list[list[str]], 直接 `csv.writer`).

### 4 个 API 端点

| Method | Path | 用途 | request_id? |
|---|---|---|---|
| POST | `/api/pre-analysis/upload` | 上传 PDF, 创建 task, 后台跑 | ✅ @audited `pre_analysis.upload` |
| GET | `/api/pre-analysis/tasks` | 列表 (分页 limit/offset) | — |
| GET | `/api/pre-analysis/tasks/{id}` | 详情 (state, 产物清单, error) | — |
| GET | `/api/pre-analysis/tasks/{id}/download` | 下载 zip 包 (含 4 类产物) | ✅ @audited `pre_analysis.download` |

**鉴权**: 4 端点全 super_admin, 走 `Depends(auth.require_super_admin)` (复用现有守卫). anon 走 `value_error` (跟 ingest 一致).

**@audited 触发点**:
- 上传: 写操作 (含 input PDF 文件 + 创建 pre_analysis_tasks 行) — 审计
- 下载: 数据导出 (含 PDF 衍生结构化数据) — 审计

### 数据库 schema 变更

详见 [§调研结论 — 数据存储: 新建独立 pre_analysis_tasks 表](#数据存储-新建独立-pre_analysis_tasks-表-2026-07-02-用户决策). 本节不重复.

### 配置文件

```yaml
# configs/pre_analysis/rule_keywords.yaml
# 规则段落关键词白名单 (DeepSeek 方法论第 4 步 "flag_rule_paragraphs")
keywords:
  - 注意
  - 不能
  - 仅适用
  - 必须
  - 禁止

# 章节标题正则 (识别 ## / # / numbered chapters)
chapter_patterns:
  - "^\\s*第[一二三四五六七八九十百零]+章[\\s\\u3000]+"
  - "^\\s*\\d+\\.\\d+(\\.\\d+)?[\\s\\u3000]+"
  - "^\\s*#{1,6}\\s+"

# 段落最小长度 (避免误标单字符)
min_paragraph_length: 20
```

---

## 抽象接口

### PreAnalysisRunner

```python
# src/ingest/pre_analysis_runner.py
from dataclasses import dataclass, field
from pathlib import Path

@dataclass(frozen=True)
class PreAnalysisResult:
    """单 PDF 跑完产物清单 (写 DB 的 output_files_json 用)"""
    chapter_structure_uri: str            # s3://.../chapter_structure.json
    flagged_paragraphs_uri: str           # s3://.../flagged_paragraphs.csv
    table_uris: list[str]                 # ["s3://.../tables/page-3-table-1.csv", ...]
    index_uri: str                        # s3://.../index.json
    total_chapters: int
    total_tables: int
    total_flagged: int
    elapsed_ms: int


@dataclass(frozen=True)
class PreAnalysisRunner:
    """跟 extract_runner.py 同模式, 异步后台 pipeline"""
    object_store: ObjectStore
    task_store: PreAnalysisTaskStore      # pre_analysis_models.py:PreAnalysisTask 配套 store
    keyword_config_path: Path            # configs/pre_analysis/rule_keywords.yaml

    def run(self, task_id: str, pdf_uri: str) -> PreAnalysisResult:
        """主入口, 接收 ObjectStore URI 形式 PDF, 返回产物清单
        
        任何抛错 → IngestTask state=failed + error=stderr
        跑完 → IngestTask state=completed + output_files_json=[...]
        """
        ...
```

### API schema

```python
# src/ingest/api.py 增量
class PreAnalysisUploadResponse(BaseModel):
    task_id: str
    state: Literal["pending"]
    input_uri: str                        # s3://.../pre_analysis_inputs/{uuid}/input/foo.pdf


class PreAnalysisTaskItem(BaseModel):
    id: str
    state: Literal["pending", "running", "completed", "failed"]
    started_at: datetime
    finished_at: datetime | None
    input_file: str                       # 文件名
    output_files: list[PreAnalysisOutputFile]
    error: str | None
    summary: PreAnalysisSummary            # 含 cross_page_candidates (2026-07-02 加)


class PreAnalysisOutputFile(BaseModel):
    kind: Literal["chapter_structure", "flagged_paragraphs", "table", "index"]
    uri: str
    filename: str                         # chapter_structure.json
    size_bytes: int
```

### Frontend API wrapper

```typescript
// packages/web/lib/api/pre-analysis.ts
export async function preAnalysisUpload(file: File): Promise<PreAnalysisUploadResponse> { ... }
export async function listPreAnalysisTasks(params?: { limit?: number; offset?: number }): Promise<PreAnalysisTaskItem[]> { ... }
export async function getPreAnalysisTask(id: string): Promise<PreAnalysisTaskItem> { ... }
export async function downloadPreAnalysisZip(id: string): Promise<Blob> { ... }

export interface PreAnalysisTaskItem {
  id: string;
  state: "pending" | "running" | "completed" | "failed";
  taskKind: "pre_analysis";
  startedAt: string;
  finishedAt: string | null;
  inputFile: string;
  outputFiles: PreAnalysisOutputFile[];
  error: string | null;
}
```

---

## 实施拆分 (5 Milestone / 约 3 工作日 / 14 commits)

> **范围控制**: 5 PR / 各 ≤ 450 行单 PR 红线. 跟 CLAUDE.md §单 PR 500 行红线 留缓冲.

| # | Milestone | 文件 | 行数估算 | 验证 | commits |
|---|---|---|---|---|---|
| **M1** | PG 迁移 + 新建 `pre_analysis_tasks` 表 + ORM 类 | `migrations/versions/20260702_000000_pre_analysis_tasks.py` [新] + `ingest/pre_analysis_models.py` [新] + tests | 120 | `uv run pytest tests/migrations/test_pre_analysis_tasks.py -v` (mode 1 mock + mode 2 集成回滚) | 2 |
| **M2** | `PreAnalysisRunner` 后台流水线 (含 3 提取器 + DB 状态更新) | `pre_analysis_runner.py` [新] + `configs/pre_analysis/rule_keywords.yaml` [新] + tests | 350 | `uv run pytest tests/ingest/test_pre_analysis_runner.py -v` (mock store + 真 PDF fixture) | 4 |
| **M3** | 4 个 API 端点 + zip 流下载 | `ingest/api.py` [改] (pre_analysis 4 端点) + tests | 300 | `uv run pytest tests/ingest/test_pre_analysis_api.py -v` (TestClient + mock runner) | 4 |
| **M4** | 前端 API wrapper + 4 type | `lib/api/pre-analysis.ts` [新] + vitest | 150 | `bun run test packages/web/lib/api/pre-analysis.test.ts` | 2 |
| **M5** | 前端 admin 页面 (列表 + 详情 + 内嵌 FileDropzone) — **0 新组件, 全部复用项目封装** (2026-07-02 修订) | `app/[locale]/admin/pre-analysis/page.tsx` [新] + `[task_id]/page.tsx` [新] + `lib/api/pre-analysis.ts` [新] + 2 个 page test + 1 个 api test + i18n | 250 (含 i18n 80 行) | `bun run test packages/web/app/admin/pre-analysis/` + `bun run typecheck` + 浏览器手测 | 2 |

**PR 拆分**:
- **PR1 = M1** (2 commits, 80 行) — PG 迁移, 零业务
- **PR2 = M2** (4 commits, 350 行) — 后台 runner
- **PR3 = M3** (4 commits, 300 行) — 4 API 端点
- **PR4 = M4 + M5** (4 commits, 600 行) — 前端 (**超 500 行红线**, 拆 2 个 PR: M4 一个, M5 一个)

**修正**: PR4 拆 PR4a (M4, 150 行) + PR4b (M5, 450 行), 实际 6 个 PR.

**前置依赖**:
- 必须先 M1 跑成功 (新建 `pre_analysis_tasks` 表 + alembic upgrade head + downgrade 演练 1 次)
- 前端 M5 独立 spec 落地也可 (本期 M5 不阻塞 M1-M4 后端)

**风险点**:
- M2 PDF 跑崩溃可能污染 ObjectStore — `run` 包 try/finally, 失败时清理已写文件 + state='failed' + error=stderr tail 1000 chars
- M3 `download` 大 zip 内存爆 — 用 `StreamingResponse` + `zipfile.ZipFile` 流模式, 不 load 全文件进内存

---

## 错误处理

| 失败点 | 降级行为 |
|---|---|
| PDF 上传空文件 / 非 .pdf | 422 `bad_request`, 不入库 |
| PDF 打开失败 / 损坏 | task state='failed', error='pymupdf.open raised: ...', UI 显示可重试 |
| `get_toc()` 返空 (PDF 无 outline) | chapter_structure.json = `{chapters: [], note: "no_toc"}`, 不报错 |
| `find_tables()` 全页无表 | tables/*.csv 不产, index.json 标 `total_tables=0` |
| 关键词匹配命中数 = 0 | flagged_paragraphs.csv 只有 header 行, 不报错 |
| ObjectStore 写失败 (如桶满) | task state='failed', error=stderr, 不删已写文件 (admin 手动清理) |
| 并发 2 个 admin 上传同名 PDF | 走 ObjectStore UUID 隔离, 不冲突 |
| `download` 产物文件缺失 | 404 `result_missing`, UI 显示重试 |
| `find_tables()` 跨页表只取当前页 (e.g. D81.1 page-45 NEMA 映射表延伸到 page-46) | logged WARNING + summary.cross_page_candidates+=1, 不报 fail. 详情页 UI 加 "本任务含 N 个跨页候选表" 提示, admin 手动 Excel 合并 |

---

## 测试隔离 (CLAUDE.md §强制 4 模式)

| 模块 | 模式 | Fixture | 备注 |
|---|---|---|---|
| `migrations/.../20260702_*.py` | 1 + (4 dev 演练) | tmp yaml 不适用; dev DB 实跑 + downgrade | 强制回滚 1 次 |
| `pre_analysis_runner.py` | 1 (mock store) + 2 (真 PDF fixture) | d81_dummy.pdf 程序生成 (5 页, 1 表, 3 关键词段) | 真值对照表 |
| `ingest/api.py` 4 端点 | 1 | TestClient + mock PreAnalysisRunner + mock ObjectStore | 鉴权 422/403 必测 |
| `lib/api/pre-analysis.ts` | 1 | vitest + fetch mock | 4 端点 + 错误码 |
| `app/admin/pre-analysis/page.tsx` | 1 | vitest + @testing-library/react | 列表渲染 + 状态 badge |

**模式 1 单测覆盖所有边界** (PDF 损坏 / 无 TOC / 无表 / 0 关键词命中), 模式 2 集成测只跑 1 个 happy path + 真 PDF.

---

## 验证 (Verification)

### 单元测试

```bash
# 后端
uv run pytest tests/migrations/test_pre_analysis_tasks.py -v          # M1
uv run pytest tests/ingest/test_pre_analysis_runner.py -v            # M2 (mock + 真 PDF)
uv run pytest tests/ingest/test_pre_analysis_api.py -v               # M3 (TestClient + mock)
uv run pytest tests/test_api_contract.py -v                          # 不退化 (CLAUDE.md §删 BFF 必跑)

# 前端
bun run test packages/web/lib/api/pre-analysis.test.ts              # M4
bun run test packages/web/app/admin/pre-analysis/                    # M5

# 代码质量铁律
uv run ruff format && uv run ruff check --fix && uv run pyright
bun run format && bun run lint:fix && bun run typecheck
```

### 手工 E2E (dev 环境)

1. 启动后端 `uv run python main.py` + 前端 `bun run dev`
2. 拿 super_admin token 登录
3. 访问 `http://localhost:3000/zh/admin/pre-analysis`
4. 上传真 D81.1 PDF (或 d81_dummy.pdf fixture)
5. 等 30s, 列表显示 `completed`
6. 点详情页, 看到产物清单:
   - chapter_structure.json (1 个, ~5KB)
   - tables/page-N-table-M.csv (0-N 个)
   - flagged_paragraphs.csv (1 个)
7. 点 "Download ZIP", 解压验证 4 类产物齐全
8. 用 kreuzberg/mineru 解析同 PDF, 对比 chapter_structure.json 的 chapters 数量 (允许 ±1)
9. Curl 验鉴权: anon token POST /api/pre-analysis/upload → 403

### 业务验收

| 验收项 | 期望 |
|---|---|
| 上传 50 页 D81.1 PDF | 60s 内完成, 产物 ~200KB |
| `chapter_structure.json` | 解码后含 `total_chapters >= 3` (假设真手册 6 章) |
| `tables/page-N-table-M.csv` | 表格页含 ≥10 行, 列数正确 |
| `flagged_paragraphs.csv` | 真手册含 ["注意", "不能"] 关键词段落, 全部命中 |
| ZIP 包解压 | 4 类文件齐全, 文件名跟 DB output_files_json 一致 |
| anon token 尝试 upload | 403, audit log 有记录 |

---

## 不要做的事 (Top 7)

1. **不引 PyMuPDF4LLM / Camelot / pdfplumber** — pymupdf 已够, 重复引入会 2 套 markdown 引擎 / 跨页表 Camelot 优势不复存在
2. **不引 fuzzy / sentence-transformers / pint** — 项目无依赖, 引入需评估 pyright strict
3. **新建独立 `pre_analysis_tasks` 表, 不复用 ingest_tasks** (2026-07-02 决策) — admin 列表清晰, 跟 ingest 解耦. 1 个 alembic migration + 1 个 ORM 类. 复用 ingest 表会混产, admin 体验差
4. **不联动 KG 抽取** — admin 手动 2 步走, 解耦后续 spec
5. **不实现跨页表格合并** — pymupdf `find_tables()` 限制, 后续 spec
6. **不做实时 (sub-second) 返回** — 复用 BackgroundTasks 异步, 复用 `_run_ingest` 模板
7. **不新建前端组件** (2026-07-02 修订) — 表格 / 表单 / 上传 / 状态徽章 / 错误提示 / 鉴权 / 页面包装 全部走项目现有 `<DataTable>` / `<Form>` / `<FileDropzone>` / `<Badge>` / `<ErrorBanner>` / `<GuardPage>` / `<PageHero>` / `<BackLink>`. PDF 上传只 admin/pre-analysis 1 处用, 不抽 `<AppPdfUploadDialog>` (CLAUDE.md §封装新组件流程 不满足 ≥2 次门槛). 抽包装必须先用户同意 (CLAUDE.md §强制)

---

## 未来工作 (独立 spec, 2026-07-02 后另起)

| # | 工作 | 工作量 | 立项依据 |
|---|---|---|---|
| 1 | **跨页表格合并** — pymupdf `find_tables()` 逐页提取后, 启发式合并同名表的相邻页 | 1.5 天 | D81.1 真手册含跨页表, admin 反馈后立项 |
| 2 | **pre-analysis ↔ kg extract 联动** — pre-analysis 产物直接喂 kg extract 任务, 自动沿用 chapter 切分 | 1 天 | 解耦 admin 手动 2 步 |
| 3 | **OCR 层** — 真扫描件 PDF (pymupdf `get_text()` 返空) 走 Tesseract / paddleOCR | 3 天 | 扫描件手册需求 |
| 4 | **章节摘要 LLM** — 每章自动摘要为 1 句话, 写进 chapter_structure.json | 0.5 天 | admin 阅读加速 |
| 5 | **多 PDF 批量** — 1 个 admin 上传 50 个 PDF, 1 个 task_kind='pre_analysis_batch' 任务 (注: 未来 spec 应改为新表 `pre_analysis_batch_tasks` 或 `pre_analysis_tasks.parent_id` 自引用) | 1 天 | 手册系列批量 |

---

## 关联文档

- 项目根 [CLAUDE.md](../../CLAUDE.md) — 代码质量铁律, 工具链锁定
- 后端 [packages/service/CLAUDE.md](../../packages/service/CLAUDE.md) — 4 测试模式 + @audited + ObjectStore ABC
- 前端 [packages/web/CLAUDE.md](../../packages/web/CLAUDE.md) — i18n + 组件封装 + 路由跳转
- 触发: DeepSeek 对话 `https://chat.deepseek.com/share/wbmg0i1neb616saobg` (D81.1 / D84.1 手册结构化预分析 5 步)
- 关联: [`2026-07-02-motor-ontology-extract-design.md`](./2026-07-02-motor-ontology-extract-design.md) — KG 抽取 + 本体校验, 上下游解耦
- 模板: [`2026-07-01-markdown-extract-kg-design.md`](./2026-07-01-markdown-extract-kg-design.md) — IngestTask + BackgroundTasks 异步模式

---

## 待用户审阅

本 spec 是头脑风暴后定稿, 请审阅以下决策点:

1. **不装 PyMuPDF4LLM / Camelot**: 同意只复用 pymupdf 跟 kreuzberg/mineru? 还是希望装专库?
2. ~~**复用 ingest_tasks + 1 列 task_kind**: 同意不建新表?~~ → **2026-07-02 修订: 新建独立 `pre_analysis_tasks` 表 (用户决策)**, 跟 ingest_tasks 解耦. spec §调研结论 已改
3. **不联动 KG 抽取**: 同意解耦 admin 手动 2 步 (本期不做联动)?
4. **产物文件命名沿用 DeepSeek 原名**: 同意 `chapter_structure.json` + `tables/*.csv` + `flagged_paragraphs.csv`?
5. **PR 拆分 6 个**: M1/M2/M3/M4 各 1 个 PR, M5 单独 1 个 PR, 总 6 PR (M4 + M5 拆开走前端规约 §单 PR 500 行红线)?
