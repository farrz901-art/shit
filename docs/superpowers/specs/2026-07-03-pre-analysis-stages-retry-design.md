# PreAnalysis Stages / Retry / Orphan 设计 (2026-07-03)

> **Status**: draft → implementation pending
> **Owner**: frontend + backend
> **Scope**: 阶段状态机 + stages 表 + 重试 + orphan 清理 + 列表新列 + 不跳详情

## 背景

`packages/web/app/[locale]/admin/pre-analysis/` 当前显示 4 状态 (pending/running/completed/failed),用户痛点:
1. **长任务 36MB PDF 跑几分钟看不出卡在哪个环节** — 表格只显示 "处理中"
2. **orphan running** — 后端 session 重启后任务卡 running 永远 (之前 debug 已确认, 没清理)
3. **失败原因看不到** — failed 只显示 Badge, 不展开 stderr
4. **失败不可逆** — 失败后不能重试, 必须重新上传
5. **成功强制跳详情页** — 上传完弹框直接跳过去, 列表视野丢失

## 方案

### 方案对比 (已敲定 A)

| 方案 | 评估 |
|---|---|
| A. 5 detail stage + 4 overall stage + mark_stage_xxx (推荐) | ✅ 阶段粒度清晰 + 跟 runner try-block 兼容 |
| B. stage 装饰器 | ❌ 引入新 Python 特性, 跟现状不一致 |
| C. SSE 流式 | ❌ 复杂度高, 跟轮询列表冲突 |

### 用户决策 (2026-07-03 brainstorming)

1. **5 detail stage** + **4 overall stage** (2 列)
2. **重试 = 整个 task reset** (不重试单 stage)
3. **数据模型**: 新表 `pre_analysis_task_stages` (DB, JSONB)
4. **UI**: 行点弹框 (AppDialog) + 列表新列 + hover Tooltip + failed 重试按钮
5. **上传成功**: 只关弹框, **不跳详情页**

## 状态机

### 4 个 overall stage (UI 列表列展示)

| enum | 中文 | detail stage 聚合 | 显示时机 |
|---|---|---|---|
| `parse_pdf` | 解析 PDF | load_config + (pymupdf open) | task 进入 running, 第一件事 |
| `extract` | 提取 | extract_chapters + extract_tables + extract_flagged_paragraphs | parse_pdf 完成立即 |
| `write_outputs` | 写产物 | _write_chapter_structure + _write_flagged_paragraphs + _write_tables + _write_index | extract 完成立即 |
| `done` | 完成 | mark_completed (写 summary 进 DB) | 所有 write 完 |

### 5 个 detail stage (UI 弹框展示, 后端逐 stage tracking)

| enum | 中文 | runner 函数 | 依赖 |
|---|---|---|---|
| `load_config` | 加载配置 | `_load_config` | — |
| `extract_chapters` | 章节提取 | `_extract_chapters` | load_config |
| `extract_tables` | 表格提取 | `_extract_tables` | extract_chapters (并行可, 但串行简单) |
| `extract_flagged` | 段落标记 | `_extract_flagged_paragraphs` | extract_tables |
| `write_outputs` | 写产物 | _write_chapter_structure + _write_flagged_paragraphs + _write_tables + _write_index (聚合 1 stage) | extract_flagged |

> **说明**: `write_outputs` 是聚合 stage, 含 4 个写文件步骤。弹框展示 5 行但 write_outputs 内部多步骤用 progress 0→100 表达。

## 架构

### 后端

**1. 新模型 `PreAnalysisStage`** (`pre_analysis_stage_models.py`):
```python
class PreAnalysisStage(Base):
    __tablename__ = "pre_analysis_task_stages"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("pre_analysis_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)  # 5 个 detail stage enum
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # started/completed/failed/skipped
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)  # 0-100
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**2. 新增 alembic migration** `2026-07-03_000000_pre_analysis_task_stages.py`:
- CREATE TABLE + 1 个 index

**3. PreAnalysisTask model 加 `current_stage`**:
```python
current_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)  # overall_stage enum
```

**4. Stage store** (`pre_analysis_stage_store.py`):
- `mark_stage_started(task_id, stage)` → INSERT row (id=next), 更新 task.current_stage
- `mark_stage_completed(task_id, stage, progress=100, message=None)` → UPDATE row status='completed', finished_at=NOW(), progress=100, message=message
- `mark_stage_failed(task_id, stage, error)` → UPDATE row status='failed', finished_at=NOW(), progress=0, message=error[:1000]
- `list_stages(task_id)` → SELECT ordered by started_at ASC
- `delete_all_stages(task_id)` → DELETE 用于 retry

**5. PreAnalysisRunner 改 5 处 wrap**:
```python
def _extract_chapters(self, doc, task_id):
    self.stage_store.mark_stage_started(task_id, "extract_chapters")
    try:
        result = self._extract_chapters_inner(doc)
        self.stage_store.mark_stage_completed(task_id, "extract_chapters", progress=100, message=f"{len(result)} 章")
        return result
    except Exception as e:
        self.stage_store.mark_stage_failed(task_id, "extract_chapters", str(e))
        raise
```

runner 同步更新 task.current_stage 通过 task_store。

**6. 重试 API** (`POST /api/pre-analysis/tasks/{id}/retry`):
- 鉴权: require_super_admin
- 流程:
  - PG FOR UPDATE 锁 task
  - state != failed → 409 (幂等拒绝)
  - UPDATE task: state=pending, error=NULL, finished_at=NULL, output_files_json='[]', summary_json='{}', current_stage=NULL, started_at=NOW()
  - DELETE FROM pre_analysis_task_stages WHERE task_id=:id
  - 返回 200 + state=pending
  - background.add_task(_run_pre_analysis, id)

**7. 列表/详情 API 扩展**:
- `GET /tasks` 加 `current_stage` 字段
- `GET /tasks/{id}` 加 `current_stage`
- 新 `GET /tasks/{id}/stages` → `[{stage, status, progress, started_at, finished_at, message}, ...]`

**8. Orphan cleanup** (`core/lifespan.py _setup_dictionaries` 之后):
- 启动时: `UPDATE pre_analysis_tasks SET state='failed', error='服务重启导致中断' WHERE state IN ('pending', 'running') AND started_at < NOW() - INTERVAL '5 minutes'`
- **5 分钟阈值** (vs runner 通常 < 1 min, 大 PDF 36MB 可能 5-10 min, 留 buffer)

### 前端

**1. API client** (`lib/api/pre-analysis.ts`):
- `listPreAnalysisStages(taskId)` → 新增
- `retryPreAnalysisTask(taskId)` → 新增
- `PreAnalysisTaskItem` type 加 `current_stage: PreAnalysisOverallStage | null`

**2. 类型** (`lib/api/pre-analysis.ts`):
```typescript
export type PreAnalysisOverallStage = "parse_pdf" | "extract" | "write_outputs" | "done";
export type PreAnalysisDetailStage = "load_config" | "extract_chapters" | "extract_tables" | "extract_flagged" | "write_outputs";
export type PreAnalysisStageStatus = "started" | "completed" | "failed" | "skipped";

export interface PreAnalysisStageItem {
  stage: PreAnalysisDetailStage;
  status: PreAnalysisStageStatus;
  progress: number;  // 0-100
  started_at: string;
  finished_at: string | null;
  message: string | null;
}
```

**3. 列表新列** (`admin-pre-analysis-client.tsx`):
```
| 文件名 | 上传时间 | 状态 Badge | 总体阶段 | 操作 |
| D81.pdf | 10:32 | 运行中 | 解析 PDF | [查看详情] [重试*] |
```
- "总体阶段" 列: current_stage 映射 badge + progress (可选), default "—"
- "操作" 列: 原"查看详情" + 新 retry 按钮 (仅 state=failed 渲染)
- **hover Tooltip**: failed 时显示 error[:200]
- **onRowClick**: 触发 AppDialog (stages dialog)
- **不轮询**: 列表 useQuery **不**设 refetchInterval, 改手动刷新按钮 (右上角, lucide RefreshCw icon) → user 点才 refresh
- **手动触发**: 上传成功 / 重试成功后自动 invalidate query (TanStack Query refetch 一次, 不轮询)

**4. 新组件 `pre-analysis-stages-dialog.tsx`**:
- Props: `open` + `onOpenChange` + `taskId`
- 内部 useQuery listPreAnalysisStages
- title: task 名 + state
- body: DataTable columns = [阶段 (中文 label), 状态 (badge), 进度 (百分比), 消息 (failure 详情/状态描述), 开始时间, 结束时间]
- footer: [关闭]

**5. 上传成功后**: 不跳详情, 只关弹框 + list 自动 refetch (TanStack Query invalidated)

**6. Retry 按钮**:
- 列表行操作列, 仅 state='failed' 渲染
- onClick → retryPreAnalysisTask(taskId) → invalidate query → toast.success("已重试")

### i18n 新文案 (~12 keys × 2 lang)

| key (zh identity) | en |
|---|---|
| `总体阶段` | Overall stage |
| `操作` | Actions |
| `重试` | Retry |
| `重试中…` | Retrying... |
| `已重试` | Retry scheduled |
| `解析 PDF` | Parsing PDF |
| `提取` | Extracting |
| `写产物` | Writing outputs |
| `加载配置` | Load config |
| `章节提取` | Extract chapters |
| `表格提取` | Extract tables |
| `段落标记` | Flag paragraphs |
| `服务重启导致中断` | Service restart interrupted |
| `刷新` | Refresh |
| `刷新成功` | Refreshed |

### 风险

| 风险 | 缓解 |
|---|---|
| Stage 表 migration 在已有 DB 上失败 | alembic upgrade head + 老表不动, 缺则新建 |
| 重试并发触发出 2 个 runner | PG FOR UPDATE 锁, 第二个请求等锁后 state != failed 拒绝 |
| 大 PDF 36MB 超 5 分钟 orphan 误判 | 5 分钟阈值, 实测 36MB 跑 25 分钟 (之前 debug 数据); 后续 spec 加 timeout |
| Stage 写 DB 自身失败 | stage_store 内部 try/except + loguru WARNING, 不阻断 runner |
| UI 频繁 refetch 性能 | ✅ 不轮询解决; 仅手动 refresh (点按钮) 或用户主动操作 (上传/重试) 后 invalidate |

## 改动文件清单

### 后端 (7 个)

| 文件 | 类型 | 改动量 |
|---|---|---|
| `src/ingest/pre_analysis_stage_models.py` | 新增 | ~40 行 |
| `src/ingest/pre_analysis_stage_store.py` | 新增 | ~80 行 |
| `src/storage/migrations/versions/2026-07-03_pre_analysis_task_stages.py` | 新增 | ~30 行 |
| `src/ingest/pre_analysis_models.py` | 改 | +1 列 current_stage |
| `src/ingest/pre_analysis_runner.py` | 改 | 5 处 wrap + runner ctor 接 stage_store |
| `src/ingest/api.py` | 改 | 2 新端点 (stages, retry) + _to_dict 加 current_stage + orphan cleanup |
| `src/core/lifespan.py` | 改 | 启动钩子跑 orphan cleanup |
| `tests/ingest/test_pre_analysis_stage_store.py` | 新增 | ~80 行 (3-4 test) |
| `tests/ingest/test_pre_analysis_retry_api.py` | 新增 | ~100 行 (2-3 test) |
| `tests/ingest/test_pre_analysis_runner_stages.py` | 新增 | ~80 行 (1-2 test) |

### 前端 (5 个)

| 文件 | 类型 | 改动量 |
|---|---|---|
| `lib/api/pre-analysis.ts` | 改 | +2 API + 3 type |
| `app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.tsx` | 改 | 新列 + retry btn + 刷新按钮 + onRowClick |
| `app/[locale]/admin/pre-analysis/_components/pre-analysis-stages-dialog.tsx` | 新增 | ~120 行 |
| `app/[locale]/admin/pre-analysis/_components/pre-analysis-stages-dialog.test.tsx` | 新增 | ~80 行 (3 test) |
| `app/[locale]/admin/pre-analysis/_components/admin-pre-analysis-client.test.tsx` | 改 | 现有 test + 1 新 (retry 按钮渲染) |
| `app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx` | 改 | 删 onSuccess router.push, 改成只关弹框 + invalidate |
| `messages/{zh,en}.json` | 改 2 文件 | 各 13 个 key |

## 验收

- [ ] 上传 PDF 成功 → 弹框关闭, **不跳**详情页, 列表自动 invalidate 1 次 (TanStack Query refetch 一次, 不是轮询)
- [ ] 列新加 "总体阶段" 列, running 时显示 "解析 PDF" badge, 进度 %
- [ ] 右上角 "刷新" 按钮 (lucide RefreshCw + 文字) → 点 → 列表 fetch 一次, 不轮询
- [ ] 行点击 → 弹框显示 5 行 stages 表 (load_config / extract_chapters / extract_tables / extract_flagged / write_outputs), 各 status + progress + 失败 message
- [ ] 失败 hover badge → Tooltip 显示 error[:200]
- [ ] failed 行操作列显示 "重试" 按钮 → 点 → list 自动 invalidated (重试成功后 toast + refresh 一次)
- [ ] 后端重启后, 之前 running 状态自动转 failed + error="服务重启导致中断"
- [ ] `useQuery` 不含 `refetchInterval`, 单纯 manual fetchOnMount + invalidate
- [ ] i18n zh/en.json 13 个 key 全部同步
- [ ] `bun run typecheck` + `bun run lint` 0 error
- [ ] `bun run test` + `uv run pytest` 0 新 fail
- [ ] 后端 alembic upgrade head 一次性 OK (含新表 + current_stage 列)
- [ ] 手动 smoke: 36MB PDF 跑 5+ 分钟, 列表每 3s 刷新显示当前 stage 变化

## 实施步骤 (writing-plans 阶段展开)

1. 后端: 写 stage model + stage_store + runner 改 5 处 wrap + 测试
2. 后端: alembic migration + DB 加 current_stage 列
3. 后端: API 改 (2 新端点 + current_stage 字段) + orphan lifespan
4. 后端: pytest 全跑 (含 lint + pyright)
5. 前端: API client 扩 + type 扩
6. 前端: stages-dialog 组件 + 测试
7. 前端: 列表新列 + retry + 刷新按钮 + onRowClick
8. 前端: i18n zh/en 同步
9. 前端: 弹框 onSuccess 改 (只关不跳)
10. 全套验证
