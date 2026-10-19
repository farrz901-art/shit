# 评估页重设计 + 异步后端

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Date:** 2026-06-09
**Status:** Approved (待实施)
**Scope:** 评估页前端 3 页面 + 后端异步运行器 + admin token 调试机制
**前置依赖**: storage spec (4 个 model) + 客户端 token spec (BFF 中间件, 本 spec 实施时若未完成则 stub)

## Goal

把"一次性静态报告"改成"可上传 CSV → 异步跑评估 → 历史可查"的工作流, 前端 3 页面统一编辑风格, 后端落 DB 而非 JSON 落盘。

## User Story

1. 开发者打开 `/evaluate`, 看到历史评估列表 (空态)
2. 点 "+ 新建评估" → `/evaluate/new`, 下载模板 → 填 30 题 → 上传
3. 跳到 `/evaluate/{id}` 详情页, 状态从 `pending → running → completed`, 看到 4 指标卡 + 逐条结果
4. 返回列表, 看到这次记录排在最上
5. 跑一半想停 → 点"取消", 状态变 `cancelled`

## Architecture

```
Browser (3 页面)
  ↓ fetch + multipart
Next.js BFF
  /api/evaluate/runs         (GET 列表, POST 上传)
  /api/evaluate/runs/{id}    (GET 详情, 轮询)
  /api/evaluate/runs/{id}/cancel  (POST 取消)
  /api/evaluate/template      (GET 下载 CSV 模板)
  ↓
FastAPI
  /api/evaluate/runs/* (src/rag/eval/router.py)
  resolve_user() 鉴权 → CurrentUser
  ↓
BackgroundTasks 调:
  DifyClient.achat(question) 拿 answer + contexts
  RAGASEvaluator.evaluate_single() 算 4 指标
  ↓
SQLite (data/app.db)
  evaluations + evaluation_samples
```

## 3 个前端页面

### `/evaluate` (历史列表, 默认页)

```
┌────────────────────────────────────────────────┐
│ eyebrow: 质量评估                                │
│ display:  评估历史                                │
│ desc:     上传 CSV, 让大模型作答, 自动评分       │
│                                                  │
│ [ + 新建评估 ]    [ ↓ 下载模板 ]                 │
│                                                  │
│ ┌────────────────────────────────────────────┐ │
│ │ #  │ 名称        │ 状态   │ 题数 │ 时间  │ →│ │
│ │ 01 │ 6月验收集   │ ✓ 完成 │ 30   │ 06-09│ →│ │
│ │ 02 │ 1LE0 冒烟   │ ⟳ 跑中 │ 5/12 │ 06-09│ →│ │
│ │ 03 │ 错例复查   │ ✗ 失败 │ 0/8  │ 06-08│ →│ │
│ └────────────────────────────────────────────┘ │
└────────────────────────────────────────────────┘
```

**交互**:
- 行可点 → `/evaluate/{id}`
- "+ 新建评估" → `/evaluate/new`
- "下载模板" → `GET /api/evaluate/template` 触发浏览器下载

**状态徽章** (`StatusBadge.tsx`):
- `pending` 灰 / `running` 青蓝带脉动 / `completed` moss / `failed` clay / `cancelled` ink

**空态**: 大号 "还没有评估" + "+ 新建评估" 主按钮

**轮询**: 当前**不**轮询 (列表只展示终态); 跑中状态由详情页轮询, 列表点进去看

### `/evaluate/new` (新建评估)

```
┌────────────────────────────────────────────────┐
│ ← 返回        eyebrow: 新建评估                  │
│ display:  上传问答 CSV                            │
│                                                  │
│ ┌────────────────────────────────────────┐     │
│ │   拖拽 CSV 到这里 / 点击选择             │     │
│ │   仅支持 .csv, 最多 5MB, 1-200 行        │     │
│ │   [ ↓ 没模板? 下载 ]                    │     │
│ └────────────────────────────────────────┘     │
│                                                  │
│ 文件名: eval_6月.csv  (12 行)                    │
│                                                  │
│ 预览前 3 行:                                     │
│ ┌──────────────┬────────────────────────┐      │
│ │ question     │ ground_truth            │      │
│ ├──────────────┼────────────────────────┤      │
│ │ 1LE0001-1AA4 │ 西门子 1LE0 低压...    │      │
│ │ ...                                       │    │
│ └──────────────┴────────────────────────┘      │
│                                                  │
│ 并发数: [ — 5 + ]                                │
│                                                  │
│ [ 取消 ]                       [ 开始评估 → ]   │
└────────────────────────────────────────────────┘
```

**CSV 字段** (跟现有 `tests/fixtures/rag_eval/qa_dataset.yaml` 对齐):
- `question` (必填, string)
- `ground_truth` (可选, string, 评估 `context_recall` 用)

**模板文件 `eval_template.csv`** (后端 `/api/evaluate/template` 生成, 也可放 `web/public/templates/eval_template.csv` 静态):

```csv
question,ground_truth
"1LE0001-1AA4 是什么系列?","西门子 1LE0 低压高效电机"
"3RT2026 是接触器还是断路器?","西门子 3RT 接触器系列"
"请解释 1FK7 伺服电机的编码器类型","1FK7 编码器类型取决于订货号后缀..."
```

**校验** (前端 papaparse + 后端 pydantic 双重):
- 文件 ≤ 5MB
- 1 ≤ 行数 ≤ 200
- 必须有 `question` 列
- 每行 `question` 非空
- 编码 UTF-8

**交互**:
- 拖拽/选择 → papaparse 解析 (已有依赖)
- 失败显示红框 + 具体错 (列名/行数/编码/行内容预览)
- "开始评估" → `POST /api/evaluate/runs` (multipart/form-data: file + concurrency)
- 跳 `/evaluate/{id}` 详情页

### `/evaluate/[id]` (单次详情)

直接搬现有 `web/app/evaluate/page.tsx` 内容, 改造:
- 顶部加 "← 返回列表" + 状态徽章 + "取消" 按钮 (running 时显示)
- 数据源从 `useSWR("/api/evaluate/reports")` 改为 `useSWR("/api/evaluate/runs/" + id)`
- 轮询: 状态为 `running` 时 2 秒一次 SWR `refreshInterval: 2000`, 切到终态后停

**保留** (现有): 4 指标卡 / MetricBar 柱状图 / SampleTable 逐条表格

## 后端 API

| 方法 | 路径 | 用途 | 鉴权 |
|---|---|---|---|
| GET | `/api/evaluate/runs` | 历史列表 (admin 看全部, 普通用户看自己) | CurrentUser |
| POST | `/api/evaluate/runs` | 上传 CSV, 启动后台任务, 返回 `{id, status: "pending"}` | CurrentUser |
| GET | `/api/evaluate/runs/{id}` | 详情 + samples (admin 可看任何, 普通用户仅自己的) | CurrentUser |
| POST | `/api/evaluate/runs/{id}/cancel` | 取消 running (普通用户仅自己的) | CurrentUser |
| GET | `/api/evaluate/template` | 下载 CSV 模板 (无需鉴权, 模板里没数据) | 无 |

**POST `/api/evaluate/runs` 流程**:
1. `multipart/form-data`: `file` (csv, ≤ 5MB) + `concurrency` (int, 1-10)
2. 校验 CSV schema (`src/rag/eval/csv_parser.py`)
3. 落 `data/eval_datasets/{uuid}.csv` (后续重跑可恢复)
4. 解析为 `list[dict]`, 创建 `Evaluation` 记录 (`status=pending`, 关联 `user_id`)
5. `BackgroundTasks` 启动 async runner:
   - `status → running`
   - 调 `DifyClient.achat(question)` 拿 answer + contexts
   - `asyncio.to_thread(RAGASEvaluator.evaluate_single, ...)` 算 4 指标 (ragas 是 sync)
   - 每完成一条 → 插 `EvaluationSample` 行
   - 全部完成 → `status=completed`, 写 `avg_metrics` / `duration_seconds` / `finished_at`
   - 异常 → `status=failed`, 写 `error_message`
6. 返回 `{id}` 让前端轮询

**取消机制** (单进程内存表):
- 模块级 `dict[int, asyncio.Event] = {}`, key=evaluation_id
- `POST /runs/{id}/cancel` → `events[id].set()`
- 后台 task 每条前 `check events.get(id)`, 若 set → 跳出, status=cancelled
- 单进程 OK, 多 worker 时要换 Redis 之类 (YAGNI)

**重启恢复**:
- 启动时扫 `status=running` 的记录 → 标 `failed` (写 error_message="服务重启中断")
- 避免"僵尸 running"

**踩过的坑** (从 `scripts/batch_rag_eval.py` 复盘):
- RAGAS 是 sync, 必须 `asyncio.to_thread` 释放事件循环
- 整体限并发 (Dify + RAGAS 一起限), 之前漏过导致 6 个 achat 全开
- per_sample 按 `index` 排序 (gather 完成顺序 ≠ 入队顺序)

## 调试机制: Admin Token

**目的**: 区分超级管理员, 开发时好调试 (看所有用户数据), 不做账号系统, 部署时 env 留空 = 零攻击面.

**新增 env** (放 `.env.local` / `.env`, **不入库**):
```bash
# 调试用, 留空 = 关闭. 多个 admin 共享这个值
RAG_ADMIN_TOKEN=admin-debug-9f2e8c4b
```

**生成**:
```bash
python -c "import secrets; print(secrets.token_hex(16))"
```

**`CurrentUser` Pydantic 模型** (新文件 `src/rag/middleware/auth.py`, 也用于客户端 token spec):

```python
class CurrentUser(BaseModel):
    id: int                # admin 时固定 0 (自增 PK 从 1 开始, 不冲突)
    public_token: str      # admin 时是 env 配的值
    is_admin: bool = False
```

**`resolve_user()` 中间件**:
```python
def resolve_user(request: Request) -> CurrentUser:
    # 1. admin 优先
    admin_token = os.getenv("RAG_ADMIN_TOKEN", "")
    if admin_token and request.headers.get("x-admin-token") == admin_token:
        return CurrentUser(id=0, public_token=admin_token, is_admin=True)
    
    # 2. 普通客户端 token
    user_token = request.headers.get("x-user-token", "")
    if not user_token:
        raise HTTPException(401, "missing x-user-token")
    
    with session_scope() as s:
        user = s.query(User).filter_by(public_token=user_token).first()
    if not user:
        raise HTTPException(401, "invalid user token")
    return CurrentUser(id=user.id, public_token=user_token, is_admin=False)
```

**业务 router 用法** (举评估列表):
```python
@router.get("/api/evaluate/runs")
def list_runs(current: CurrentUser = Depends(resolve_user), db: Session = Depends(get_session)):
    q = db.query(Evaluation)
    if not current.is_admin:
        q = q.filter(Evaluation.user_id == current.id)
    return q.order_by(Evaluation.created_at.desc()).all()
```

**前端调试用法**:
1. 后端 `.env.local` 配 `RAG_ADMIN_TOKEN=...`
2. 浏览器 devtools → Network → 拦截 fetch
3. header `x-user-token` 换成 `x-admin-token: <你配的值>`
4. 看到所有用户的 evaluations

**安全细节**:
- `RAG_ADMIN_TOKEN` 留空 → admin 分支跳过, 等于不存在
- 建议 `secrets.token_hex(16)` 生成
- 前端 `evalApi.getAdminToken()` 跟 `getUserToken()` 分两个函数, 默认 getUserToken
- 文档 / README 写明"**仅开发调试**, 生产部署务必留空"

**为什么 admin 走 Pydantic 不入库**:
- users 表不增 `is_admin` 字段, 避免"admin 不入库却字段存在"的语义污染
- 虚拟 user + DB user 走同一 `CurrentUser` 接口, 业务代码无感
- 见 [storage spec 的 "Admin 虚拟 User" 节](2026-06-09-storage-layer-design.md#admin-虚拟-user-跨-spec-约定-不入-users-表)

## File Structure

```
src/rag/eval/
├── __init__.py
├── models.py                  # 已在 storage spec 定
├── router.py                  # 新建: FastAPI 路由
├── runner.py                  # 新建: 异步运行器 (搬 scripts/batch_rag_eval.py 逻辑)
├── template.py                # 新建: 生成 CSV 模板
└── csv_parser.py              # 新建: 校验/解析 CSV

src/rag/middleware/
├── __init__.py
└── auth.py                    # 新建: CurrentUser + resolve_user (跟客户端 token spec 共用)

web/app/evaluate/
├── page.tsx                   # 改: 列表页
├── new/
│   └── page.tsx               # 新建: 上传页
├── [id]/
│   └── page.tsx               # 新建: 详情页 (从原 page.tsx 搬)
└── page.test.tsx              # 改: 列表页测试

web/components/evaluate/
├── StatusBadge.tsx            # 新建: 状态徽章
├── EvalListRow.tsx            # 新建: 列表行
├── NewEvalForm.tsx            # 新建: 上传表单 (大件, 拆出来)
├── MetricBar.tsx              # 保留
└── SampleTable.tsx            # 保留

web/lib/evaluate/
├── types.ts                   # 改: 加 EvaluationRun / EvaluationStatus 枚举
└── template.ts                # 新建: 客户端模板示例 (跟后端同步)

web/app/api/evaluate/
├── runs/
│   ├── route.ts               # 新建: GET 列表 / POST 上传
│   └── [id]/
│       ├── route.ts           # 新建: GET 详情
│       └── cancel/
│           └── route.ts       # 新建: POST 取消
└── template/
    └── route.ts               # 新建: GET 模板下载

tests/rag/eval/
├── test_router.py             # 新建
├── test_runner.py             # 新建
├── test_csv_parser.py         # 新建
└── test_template.py           # 新建

tests/rag/middleware/
└── test_auth.py               # 新建: CurrentUser + resolve_user

web/e2e/
└── 04-evaluate.spec.ts        # 新建: 3 页面 E2E
```

## 测试策略

### 后端单测

- `test_csv_parser.py`: 文件大小 / 行数 / 列名 / 编码 / 空行 / ground_truth 可选
- `test_runner.py`: mock Dify + RAGAS, 跑 2 题验证落库 / avg_metrics / 状态机
- `test_router.py`: 鉴权 (普通用户 401 / 看自己 200 / 看别人 404 / admin 看全部 200)
- `test_template.py`: 模板内容非空 + 含表头

### 前端单测

- 列表页: mount + 空态 + 5 行数据展示
- 上传页: 拖拽模拟 + papaparse 解析 + 校验错展示
- 详情页: 轮询 (mock SWR refreshInterval) + 取消按钮可见性

### E2E

- `04-evaluate.spec.ts`: 走通"模板下载 → 改写 → 上传 → 跳详情 → 看到结果"全链路
- 真实 Dify 跑 1-2 题小数据集, 验证端到端

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| Dify 超时拖垮整批 | 单题 60s timeout, 失败记 `error` 不影响其他 |
| 后台任务重启后丢失 | 启动时扫 `status=running` 标 `failed` (重启恢复) |
| CSV 大文件解析慢 | 限制 ≤ 5MB + ≤ 200 行 |
| 用户并发跑多批 | 不限制 (前端不显示), 后续 spec 再加并发限制 |
| `RAG_ADMIN_TOKEN` 误提交到生产 | `.env` 加 `.gitignore` 注释, README 写明"生产留空" |
| 客户端 token spec 未实施 | 本 spec 实施时 `resolve_user` stub 版只校验 header 存在, 后续 spec 替换 |

## 跟现有代码兼容

**复用** (直接 import):
- `RAGASEvaluator` (src/rag/telemetry/ragas_evaluator.py)
- `DifyClient` (src/rag/integrations/dify_client.py)
- `RAGAMetrics` / `EvaluationReport` (src/rag/common/evaluation.py)
- `MetricBar` / `SampleTable` 组件 (web/components/evaluate/)

**保留**:
- `scripts/batch_rag_eval.py` (CI / 离线用, 业务改走 `src/rag/eval/runner.py` 异步版)

**前端类型**:
- `web/lib/evaluate/types.ts` 加 `EvaluationRun` / `EvaluationStatus` 枚举
- 现有 `EvalReport` 保留当 `GET /runs/{id}` 响应的子结构

## 实施顺序

1. ✅ storage spec (地基) — 4 model
2. ⏳ 客户端 token spec (auth 配套)
3. ⏳ **本 spec** (评估页重设计) — router 鉴权依赖 #2, 实施时若 #2 未完成 stub
4. ⏳ 聊天 spec (复用同一套 CurrentUser + 中间件)

**当前 spec 只覆盖第 3 步**: 评估页重设计 + 异步后端 + admin token 调试。

## Success Criteria

1. `/evaluate` 列表页能展示所有用户的历史评估 (admin) 或自己的 (普通用户)
2. `/evaluate/new` 上传 CSV → 跳详情, 状态 `pending → running → completed`
3. `/evaluate/{id}` 详情页轮询 2 秒一次, 看到 4 指标 + 逐条
4. 跑中点"取消" → 状态 `cancelled`, 不再生成新 sample
5. 下载模板文件能用 Excel/Numbers 打开, 列名匹配后端 parser
6. 配 `RAG_ADMIN_TOKEN` → 前端用 `x-admin-token` header 能看到所有用户数据
7. 现有 E2E (5 页面冒烟) 仍全绿
8. 单元测试覆盖率: `src/rag/eval/*` ≥ 80%
