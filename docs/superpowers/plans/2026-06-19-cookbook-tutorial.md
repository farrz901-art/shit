# Cookbook 教程补全 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `docs/cookbook/` 下 19 个 0 字节空文件补成"中级工程师读得懂、用得上"的中文教程。本 plan 落地"总纲 + 3 类模板 + 3 篇样例 + 文件重命名"；剩余 16 篇进入下个 phase。

**Architecture:** 3 类文档（工具 / 语言框架 / AI 库）对应 3 个差异化模板；每篇用 subagent 严格审核（不用自审）；写作过程中一边 `Grep/Read` 项目源码、一边 `WebFetch/WebSearch` 官方文档 + 社区最佳实践。

**Tech Stack:** Markdown / Git / Grep+Read+Glob / WebFetch+WebSearch / `gsd-code-reviewer` subagent

**Spec:** `docs/superpowers/specs/2026-06-19-cookbook-tutorial-design.md`

---

## File Structure

本 plan 涉及的文件：

- **创建**：
  - `docs/cookbook/README.md` — 写作总纲（含三类模板全文 + 19 篇清单 + 进度表）
  - `docs/cookbook/_template-T.md` — 工具类模板空白版
  - `docs/cookbook/_template-L.md` — 语言/框架类模板空白版
  - `docs/cookbook/_template-A.md` — AI 库类模板空白版
  - `docs/cookbook/ci/docker.md` — 工具类样例
  - `docs/cookbook/python/fastapi.md` — 语言/框架类样例
  - `docs/cookbook/rag/langgraph.md` — AI 库类样例
- **修改/重命名**：
  - `docs/cookbook/rag/langchian.md` → `docs/cookbook/rag/langchain.md`（用 `git mv`）

每个文件的职责单一：模板只放骨架；样例展示完整写作风格；总纲管进度 & 索引。

---

## 任务依赖关系

```
Task 1 (git mv) ─┐
                 ├─→ Task 2 (README 总纲) ─→ Task 3 (T 模板) ─┐
                                                            ├─→ Task 4 (L 模板) ─→ Task 5 (A 模板) ─→ Task 6/7/8 (3 篇样例) ─→ Task 9 (subagent 审稿) ─→ Task 10 (commit)
```

---

### Task 1: 重命名 `langchian.md` → `langchain.md`

**Files:**
- Rename: `docs/cookbook/rag/langchian.md` → `docs/cookbook/rag/langchain.md`

- [ ] **Step 1: 用 `git mv` 重命名（保留 git 历史）**

```bash
cd c:/doc/Code/rag
git mv docs/cookbook/rag/langchian.md docs/cookbook/rag/langchain.md
```

- [ ] **Step 2: 验证重命名成功**

```bash
cd c:/doc/Code/rag
ls docs/cookbook/rag/ | grep -E "lang(chai|ch)n"
```

Expected: 输出 `langchain.md`，无 `langchian.md`

- [ ] **Step 3: 提交**

```bash
cd c:/doc/Code/rag
git commit -m "refactor(cookbook): rename langchian.md → langchain.md (typo fix)"
```

---

### Task 2: 写 `docs/cookbook/README.md` 写作总纲

**Files:**
- Create: `docs/cookbook/README.md`

- [ ] **Step 1: 先盘点要写进 README 的素材**

需要列出的内容（用作 README 大纲）：
- 19 篇文件清单（含 3 类分类、字数预估、写作状态、最后更新日期）
- 3 类模板章节结构（精简版，详见独立 _template-*.md）
- 文档头部元信息规范
- 链接到 3 个 _template-*.md
- 链接到已完成样例
- 进度跟踪表（✅/🚧/❌）

- [ ] **Step 2: 写 `docs/cookbook/README.md`**

```markdown
# Cookbook 教程

> 📅 创建日期：2026-06-19
> 📁 项目代码引用：本目录教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🎯 读者：中高级 Python/TS 工程师，需要理解本项目为什么这样用、能怎么扩展

---

## 📚 写作总纲

本目录是 RAG 项目的工具 / 库 / 语言入门到精通教程，按三类分别有专属模板。

### 三类文档与模板

| 类别 | 模板 | 字数控制 | 章节数 | 适用范围 |
|------|------|----------|--------|----------|
| **T-工具** | [_template-T.md](_template-T.md) | 弹性（复杂 4000+，简单 2000-3000） | 8 节 | 运维/中间件（Docker、Redis、Postgres 等） |
| **L-语言/框架** | [_template-L.md](_template-L.md) | 无上限（可几万字） | 9 节 | 编程语言或重生态框架（Python、FastAPI、Next.js、React 等） |
| **A-AI 库** | [_template-A.md](_template-A.md) | 弹性（复杂 6000-10000+，简单 1500-3000） | 9 节 | AI 专精 SDK（LangGraph、LlamaIndex、Mem0 等） |

### 统一规范（所有文档适用）

1. **头部元信息**（每篇开头）：
   ```markdown
   # {工具/库/语言名} 教程

   > 📅 创建日期：YYYY-MM-DD
   > 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准
   > 🏷️ 类别：T-工具 / L-语言/框架 / A-AI 库
   > 🎯 读者：中高级 Python/TS 工程师
   ```

2. **代码引用**：所有引用项目源码处标注 `file_path:line_number`（如 `packages/service/main.py:42`）
3. **可执行命令**：必须 Windows + bash 环境可跑；优先 docker / uv / bun 等本项目栈命令
4. **进度标记**：每篇文末标 ✅ 已完成 / 🚧 部分完成 / ❌ 待补充

### 信息源权重

- 项目源码 **50%**（最重要，必须有 `file_path:line_number` 真实引用）
- 官方文档 **30%**（锚定官方版本号，避免过期内容）
- 社区最佳实践 **15%**（博客 / 高 star GitHub README）
- LLM 样板 **5%**（仅作骨架与示例填充）

---

## 📋 19 篇文件清单与进度

| # | 路径 | 类别 | 字数预估 | 状态 | 最后更新 |
|---|------|------|----------|------|----------|
| 1 | [ci/docker.md](ci/docker.md) | T-工具 | 4000-6000 | 🚧 样例 | 2026-06-19 |
| 2 | [ci/grafana.md](ci/grafana.md) | T-工具 | 2000-3000 | ❌ 待写 | — |
| 3 | [ci/nginx.md](ci/nginx.md) | T-工具 | 2500-3500 | ❌ 待写 | — |
| 4 | [db/elk.md](db/elk.md) | T-工具 | 3000-4500 | ❌ 待写 | — |
| 5 | [db/minio.md](db/minio.md) | T-工具 | 2000-3000 | ❌ 待写 | — |
| 6 | [db/neo4j.md](db/neo4j.md) | T-工具 | 3000-4500 | ❌ 待写 | — |
| 7 | [db/postgres.md](db/postgres.md) | T-工具 | 4000-6000 | ❌ 待写 | — |
| 8 | [db/redis.md](db/redis.md) | T-工具 | 4000-6000 | ❌ 待写 | — |
| 9 | [nextjs/nextjs.md](nextjs/nextjs.md) | L-语言 | 5000-8000 | ❌ 待写 | — |
| 10 | [nextjs/react.md](nextjs/react.md) | L-语言 | 4000-6000 | ❌ 待写 | — |
| 11 | [nextjs/react-query.md](nextjs/react-query.md) | L-语言 | 2000-3500 | ❌ 待写 | — |
| 12 | [nextjs/zustand.md](nextjs/zustand.md) | L-语言 | 2000-3000 | ❌ 待写 | — |
| 13 | [python/fastapi.md](python/fastapi.md) | L-语言 | 5000-8000 | 🚧 样例 | 2026-06-19 |
| 14 | [python/python.md](python/python.md) | L-语言 | 10000+ | ❌ 待写 | — |
| 15 | [rag/deepagent.md](rag/deepagent.md) | A-AI 库 | 2500-4000 | ❌ 待写 | — |
| 16 | [rag/deepeval.md](rag/deepeval.md) | A-AI 库 | 2000-3000 | ❌ 待写 | — |
| 17 | [rag/langchain.md](rag/langchain.md) | A-AI 库 | 6000-10000 | ❌ 待写 | — |
| 18 | [rag/langfuse.md](rag/langfuse.md) | A-AI 库 | 3000-5000 | ❌ 待写 | — |
| 19 | [rag/langgraph.md](rag/langgraph.md) | A-AI 库 | 6000-10000 | 🚧 样例 | 2026-06-19 |
| 20 | [rag/llama-index.md](rag/llama-index.md) | A-AI 库 | 5000-8000 | ❌ 待写 | — |
| 21 | [rag/mem0.md](rag/mem0.md) | A-AI 库 | 2500-4000 | ❌ 待写 | — |

> ⚠️ 注意：`docs/cookbook/rag/` 目录下原 `langchian.md` 已重命名为 `langchain.md`（commit 中）

---

## 🚧 实施节奏

| 批次 | 内容 | 状态 |
|------|------|------|
| 本 plan | 总纲 + 3 模板 + 3 样例 + 重命名 | 🚧 进行中 |
| 第 1 批（下个 phase） | 7 个工具类（grafana, nginx, elk, minio, neo4j, postgres, redis） | ❌ 待启动 |
| 第 2 批（下个 phase） | 5 个语言类（python, nextjs, react, react-query, zustand） | ❌ 待启动 |
| 第 3 批（下个 phase） | 6 个 AI 库类（deepagent, deepeval, langchain, langfuse, llama-index, mem0） | ❌ 待启动 |

---

## 📖 相关文档

- 设计 spec：[docs/superpowers/specs/2026-06-19-cookbook-tutorial-design.md](../superpowers/specs/2026-06-19-cookbook-tutorial-design.md)
- 模板：[_template-T.md](_template-T.md) / [_template-L.md](_template-L.md) / [_template-A.md](_template-A.md)
- 样例：[ci/docker.md](ci/docker.md) / [python/fastapi.md](python/fastapi.md) / [rag/langgraph.md](rag/langgraph.md)
```

- [ ] **Step 3: 验证 README 渲染正确（用 wc 统计行数）**

```bash
cd c:/doc/Code/rag
wc -l docs/cookbook/README.md
```

Expected: 100-150 行之间

- [ ] **Step 4: 提交**

```bash
cd c:/doc/Code/rag
git add docs/cookbook/README.md
git commit -m "docs(cookbook): 写作总纲 README + 19 篇清单 + 模板索引"
```

---

### Task 3: 写 `docs/cookbook/_template-T.md` 工具类模板

**Files:**
- Create: `docs/cookbook/_template-T.md`

- [ ] **Step 1: 写工具类模板（8 节骨架，章节标题固定）**

```markdown
# {工具名} 教程

> 📅 创建日期：YYYY-MM-DD
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：T-工具
> 🎯 读者：中高级 Python/TS 工程师

---

## 目录

- [一、是什么 & 解决什么问题](#一是什么--解决什么问题)
- [二、安装 & 启动](#二安装--启动)
- [三、核心概念](#三核心概念)
- [四、常用命令 & 用法速查](#四常用命令--用法速查)
- [五、项目集成点](#五项目集成点)
- [六、项目代码示例](#六项目代码示例)
- [七、项目没用到的能力](#七项目没用到的能力)
- [八、运维 & 最佳实践 + 常见坑](#八运维--最佳实践--常见坑)

---

## 一、是什么 & 解决什么问题

<!-- 150-300 字：定位 + 与同类替代品（Redis vs Memcached / Postgres vs MySQL / Grafana vs Prometheus）对比 -->

## 二、安装 & 启动

<!-- 150-250 字：本地 docker 启动 / 操作系统安装 + 健康检查 -->
<!-- 引用项目 docker-compose.yml 片段 -->

## 三、核心概念

<!-- 150-300 字：3-5 个关键术语 -->

## 四、常用命令 & 用法速查

<!-- 200-400 字：分 3-4 个场景列命令（启停/查询/调试/排错），命令前加注释讲何时用 -->

### 4.1 启停

```bash
# 启动
# 停止
# 重启
```

### 4.2 查询

```bash
# ...
```

### 4.3 调试

```bash
# ...
```

### 4.4 排错

```bash
# ...
```

## 五、项目集成点

<!-- 150-300 字：连接字符串配置、在哪几个模块被用到、连接池/认证 -->

## 六、项目代码示例

<!-- 200-400 字：直接引用项目源码片段，标注 file_path:line_number -->

**引用：** `path/to/file.ext:42-58`

```python
# 实际代码
```

## 七、项目没用到的能力

<!-- 150-350 字：从官方文档拉，但项目未用的特性。标"待评估" -->

## 八、运维 & 最佳实践 + 常见坑

<!-- 150-250 字：备份/监控/容量规划/SLO + 3-5 条本项目已踩或常见误用 -->

---

## 📚 参考

<!-- 官方文档、社区最佳实践链接 -->

---

**状态：** 🚧 模板（待套用）
```

- [ ] **Step 2: 验证模板完整性**

```bash
cd c:/doc/Code/rag
grep -c "^## " docs/cookbook/_template-T.md
```

Expected: 8（一、二、…、八）

- [ ] **Step 3: 提交**

```bash
cd c:/doc/Code/rag
git add docs/cookbook/_template-T.md
git commit -m "docs(cookbook): 工具类模板 _template-T.md (8 节骨架)"
```

---

### Task 4: 写 `docs/cookbook/_template-L.md` 语言/框架类模板

**Files:**
- Create: `docs/cookbook/_template-L.md`

- [ ] **Step 1: 写语言/框架类模板（9 节骨架）**

```markdown
# {语言/框架名} 教程

> 📅 创建日期：YYYY-MM-DD
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：L-语言/框架
> 🎯 读者：中高级 Python/TS 工程师

---

## 目录

- [一、是什么 & 适用场景](#一是什么--适用场景)
- [二、安装 & 开发环境](#二安装--开发环境)
- [三、基础语法 & 类型系统](#三基础语法--类型系统)
- [四、核心概念](#四核心概念)
- [五、常用命令 & 工具链](#五常用命令--工具链)
- [六、项目集成点](#六项目集成点)
- [七、项目代码示例](#七项目代码示例)
- [八、项目没用到的能力 / 进阶方向](#八项目没用到的能力--进阶方向)
- [九、最佳实践 & 常见坑](#九最佳实践--常见坑)

---

## 一、是什么 & 适用场景

<!-- 300 字：定位 + 与同类对比（Flask vs FastAPI / Vue vs React / Express vs Fastify） -->

## 二、安装 & 开发环境

<!-- 300 字：包管理、IDE/格式化、.editorconfig -->

## 三、基础语法 & 类型系统

<!-- 500+ 字：核心语法、类型注解、常用结构 -->
<!-- Python 涉及：dataclass/pydantic/async/await -->
<!-- Next.js 涉及：App Router/RSC/中间件 -->
<!-- React 涉及：JSX/Hooks/Server Components -->

## 四、核心概念

<!-- 400 字：5-8 个关键概念 -->
<!-- Python：GIL/异步/装饰器/上下文管理器/生成器 -->
<!-- Next.js：路由/渲染策略/数据获取 -->
<!-- React：渲染模型/Hooks 规则/Reconciliation -->

## 五、常用命令 & 工具链

<!-- 300 字：构建/测试/格式化/lint 命令 -->
<!-- Python：uv/pip/pytest/ruff/mypy -->
<!-- Next.js：bun install/next dev/next build/tsc -->

## 六、项目集成点

<!-- 250 字：在 monorepo 中的位置、配置 tsconfig/pyproject、env 管理 -->

## 七、项目代码示例

<!-- 500+ 字，重点：直接引用项目源码 file_path:line_number，覆盖典型场景 -->

**引用：** `path/to/file.ext:42-58`

```python
# 实际代码
```

## 八、项目没用到的能力 / 进阶方向

<!-- 300 字：项目未用但读者值得知道 -->
<!-- Python：3.12 新 type 语法、match-case、tomllib -->
<!-- Next.js：Server Actions、PPR -->
<!-- React：use、useFormState -->

## 九、最佳实践 & 常见坑

<!-- 300 字：本项目风格指南 + 常见错误 -->

---

## 📚 参考

<!-- 官方文档、PEP/TC39 规范、社区最佳实践链接 -->

---

**状态：** 🚧 模板（待套用）
```

- [ ] **Step 2: 验证模板完整性**

```bash
cd c:/doc/Code/rag
grep -c "^## " docs/cookbook/_template-L.md
```

Expected: 9

- [ ] **Step 3: 提交**

```bash
cd c:/doc/Code/rag
git add docs/cookbook/_template-L.md
git commit -m "docs(cookbook): 语言/框架类模板 _template-L.md (9 节骨架)"
```

---

### Task 5: 写 `docs/cookbook/_template-A.md` AI 库类模板

**Files:**
- Create: `docs/cookbook/_template-A.md`

- [ ] **Step 1: 写 AI 库类模板（9 节骨架）**

```markdown
# {库名} 教程

> 📅 创建日期：YYYY-MM-DD
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：A-AI 库
> 🎯 读者：中高级 Python 工程师

---

## 目录

- [一、是什么 & 解决什么问题](#一是什么--解决什么问题)
- [二、安装 & 初始化](#二安装--初始化)
- [三、核心概念 & 抽象](#三核心概念--抽象)
- [四、常用 API & 命令速查](#四常用-api--命令速查)
- [五、项目集成点](#五项目集成点)
- [六、项目代码示例](#六项目代码示例)
- [七、项目没用到的能力](#七项目没用到的能力)
- [八、评测 & 调优技巧](#八评测--调优技巧)
- [九、最佳实践 & 常见坑](#九最佳实践--常见坑)

---

## 一、是什么 & 解决什么问题

<!-- 300 字：定位 + 同类对比 -->
<!-- LangChain vs LlamaIndex vs LangGraph -->
<!-- Mem0 vs Zep -->
<!-- Langfuse vs Phoenix -->

## 二、安装 & 初始化

<!-- 300 字：pip install / pnpm add、配置 LLM provider、env key 列表 -->

## 三、核心概念 & 抽象

<!-- 400 字：5-8 个核心抽象 -->
<!-- LangGraph: StateGraph/Node/Edge/Checkpoint -->
<!-- LlamaIndex: Index/Retriever/QueryEngine -->
<!-- Mem0: Memory/MemoryClient -->
<!-- Langfuse: Trace/Span/Generation -->

## 四、常用 API & 命令速查

<!-- 350 字：建图/查询/调用样板代码片段，可直接 copy-paste -->

## 五、项目集成点

<!-- 250 字：在 packages/service / packages/web 的引用位置、配置入口 -->

## 六、项目代码示例

<!-- 500+ 字，重点：从项目源码拉，带 file_path:line_number -->

**引用：** `path/to/file.ext:42-58`

```python
# 实际代码
```

## 七、项目没用到的能力

<!-- 300 字：项目未用但读者值得学 -->
<!-- LangGraph：subgraph/human-in-the-loop -->
<!-- Langfuse：evaluation/dataset -->
<!-- LlamaIndex：agent -->
<!-- Mem0：graph memory -->

## 八、评测 & 调优技巧

<!-- 300 字：latency/token 监控、prompt 迭代、cost 控制、与 deepeval 的指标配合 -->

## 九、最佳实践 & 常见坑

<!-- 300 字：版本兼容（langchain 0.1→0.3 breaking）、async 陷阱、checkpoint 持久化、token 上限 -->

---

## 📚 参考

<!-- 官方文档、API reference -->

---

**状态：** 🚧 模板（待套用）
```

- [ ] **Step 2: 验证模板完整性**

```bash
cd c:/doc/Code/rag
grep -c "^## " docs/cookbook/_template-A.md
```

Expected: 9

- [ ] **Step 3: 提交**

```bash
cd c:/doc/Code/rag
git add docs/cookbook/_template-A.md
git commit -m "docs(cookbook): AI 库类模板 _template-A.md (9 节骨架)"
```

---

### Task 6: 写 `docs/cookbook/ci/docker.md` 工具类样例

**Files:**
- Create: `docs/cookbook/ci/docker.md`

- [ ] **Step 1: 调研项目 docker 现状（必须做）**

```bash
cd c:/doc/Code/rag
ls docker/
cat docker/docker-compose.yml | head -30
ls docker/scripts/ 2>/dev/null
```

收集：项目用了哪些镜像、哪些服务、哪些 healthcheck、哪些 volume、哪些 network。

- [ ] **Step 2: WebFetch Docker 官方文档拉高级特性**

```text
URL: https://docs.docker.com/compose/compose-file/
URL: https://docs.docker.com/build/building/multi-stage/
```

收集：项目没用到的特性（multi-stage build、BuildKit secrets、healthcheck 高级选项、depends_on 条件、profiles）。

- [ ] **Step 3: 写 `docs/cookbook/ci/docker.md`**

按 `_template-T.md` 的 8 节结构写作。**强制要求**：
- 头部元信息（4 行：日期、引用、类别、读者）
- 目录（8 个跳转链接）
- "四、常用命令速查" 必须含 4 个场景：启停、查询、调试、排错
- "六、项目代码示例" 至少 3 段代码，每段带 `file_path:line_number`，真实从项目源码拉
- "七、项目没用到的能力" 标"待评估"
- 文末标 `**状态：** 🚧 样例` + `**最后更新：** 2026-06-19`

项目代码引用样例（必须真实可查）：
- `docker/docker-compose.yml:14-20`（postgres service）
- `docker/docker-compose.yml:42-58`（neo4j healthcheck）
- `docker/docker-compose.yml:108-115`（depends_on 条件）

> 命令必须 Windows + bash 可执行。docker compose v2 语法（`docker compose up` 不用连字符）。

- [ ] **Step 4: 验证文件长度与章节**

```bash
cd c:/doc/Code/rag
wc -l docs/cookbook/ci/docker.md
grep -c "^## " docs/cookbook/ci/docker.md
```

Expected: 章节数 = 8（含目录节，共 9 个 `## `）

- [ ] **Step 5: 验证 file_path:line_number 引用真实**

```bash
cd c:/doc/Code/rag
grep -oE "docker/docker-compose\.yml:[0-9-]+" docs/cookbook/ci/docker.md | while read ref; do
  line=$(echo $ref | cut -d: -f2 | cut -d- -f1)
  echo "=== $ref ==="
  sed -n "${line}p" docker/docker-compose.yml
done
```

Expected: 每条引用对应的行内容是真实代码行

- [ ] **Step 6: 提交**

```bash
cd c:/doc/Code/rag
git add docs/cookbook/ci/docker.md
git commit -m "docs(cookbook): ci/docker.md 工具类样例教程"
```

---

### Task 7: 写 `docs/cookbook/python/fastapi.md` 语言/框架类样例

**Files:**
- Create: `docs/cookbook/python/fastapi.md`

- [ ] **Step 1: 调研项目 FastAPI 现状**

```bash
cd c:/doc/Code/rag
grep -rn "from fastapi" packages/service/ | head -20
grep -rn "@app\." packages/service/ | head -20
ls packages/service/app/ 2>/dev/null
```

收集：项目用了哪些 FastAPI 特性（依赖注入、中间件、BackgroundTasks、APIRouter、Pydantic、异常处理）。

- [ ] **Step 2: WebFetch FastAPI 官方文档**

```text
URL: https://fastapi.tiangolo.com/tutorial/
URL: https://fastapi.tiangolo.com/advanced/
```

收集：项目未用特性（WebSocket、GraphQL、Sub-application、Async Tests、Templates）。

- [ ] **Step 3: 写 `docs/cookbook/python/fastapi.md`**

按 `_template-L.md` 的 9 节结构写作。**强制要求**：
- 头部元信息
- 目录
- "三、基础语法"覆盖：类型注解 + Pydantic + async/await + 依赖注入
- "四、核心概念"覆盖：路由、依赖注入、中间件、BackgroundTasks、Pydantic 模型、异常处理
- "七、项目代码示例"至少 5 段，每段带真实 file_path:line_number

字数预估 5000-8000（不强制），按真实需要写。

- [ ] **Step 4: 验证文件**

```bash
cd c:/doc/Code/rag
wc -l docs/cookbook/python/fastapi.md
grep -c "^## " docs/cookbook/python/fastapi.md
```

Expected: 章节数 = 9

- [ ] **Step 5: 验证引用真实**

```bash
cd c:/doc/Code/rag
# 抽取所有 file_path:line_number 引用并验证至少 5 条存在
grep -oE "packages/service/[a-zA-Z_/.-]+:[0-9-]+" docs/cookbook/python/fastapi.md | head -10 | while read ref; do
  file=$(echo $ref | cut -d: -f1)
  line=$(echo $ref | cut -d: -f2 | cut -d- -f1)
  if [ -f "$file" ]; then
    echo "✅ $ref exists"
  else
    echo "❌ $ref MISSING"
  fi
done
```

Expected: 至少 5 条 ✅

- [ ] **Step 6: 提交**

```bash
cd c:/doc/Code/rag
git add docs/cookbook/python/fastapi.md
git commit -m "docs(cookbook): python/fastapi.md 语言/框架类样例教程"
```

---

### Task 8: 写 `docs/cookbook/rag/langgraph.md` AI 库类样例

**Files:**
- Create: `docs/cookbook/rag/langgraph.md`

- [ ] **Step 1: 调研项目 LangGraph 现状**

```bash
cd c:/doc/Code/rag
grep -rn "from langgraph" packages/service/ 2>/dev/null
grep -rn "StateGraph\|create_react_agent" packages/service/ 2>/dev/null
ls packages/service/ 2>/dev/null
```

收集：项目用了哪些 LangGraph 特性（StateGraph、MessageGraph、checkpoint、subgraph）。

- [ ] **Step 2: WebFetch LangGraph 官方文档**

```text
URL: https://langchain-ai.github.io/langgraph/
URL: https://langchain-ai.github.io/langgraph/concepts/
URL: https://langchain-ai.github.io/langgraph/how-tos/
```

收集：项目未用特性（subgraph、human-in-the-loop、time travel、persistence、streaming、langgraph studio）。

- [ ] **Step 3: 写 `docs/cookbook/rag/langgraph.md`**

按 `_template-A.md` 的 9 节结构写作。**强制要求**：
- 头部元信息
- 目录
- "三、核心概念"覆盖：StateGraph/Node/Edge/Checkpoint/Thread（5-8 个抽象）
- "四、常用 API"含可直接 copy-paste 的样板代码
- "六、项目代码示例"至少 3 段，每段带真实 file_path:line_number
- "九、最佳实践"必须包含版本兼容提示（langchain 0.1→0.3 大量 breaking）
- "八、评测 & 调优"必须含 token/latency 监控、prompt 调优

字数预估 6000-10000（不强制）。

- [ ] **Step 4: 验证文件**

```bash
cd c:/doc/Code/rag
wc -l docs/cookbook/rag/langgraph.md
grep -c "^## " docs/cookbook/rag/langgraph.md
```

Expected: 章节数 = 9

- [ ] **Step 5: 验证引用真实**

```bash
cd c:/doc/Code/rag
grep -oE "packages/service/[a-zA-Z_/.-]+:[0-9-]+" docs/cookbook/rag/langgraph.md | head -10 | while read ref; do
  file=$(echo $ref | cut -d: -f1)
  line=$(echo $ref | cut -d: -f2 | cut -d- -f1)
  if [ -f "$file" ]; then
    echo "✅ $ref exists"
  else
    echo "❌ $ref MISSING"
  fi
done
```

Expected: 至少 3 条 ✅

- [ ] **Step 6: 提交**

```bash
cd c:/doc/Code/rag
git add docs/cookbook/rag/langgraph.md
git commit -m "docs(cookbook): rag/langgraph.md AI 库类样例教程"
```

---

### Task 9: 质量门 — 派 `gsd-code-reviewer` subagent 严格审核 3 篇样例

**Files:** 审核 3 篇：`docs/cookbook/ci/docker.md` / `docs/cookbook/python/fastapi.md` / `docs/cookbook/rag/langgraph.md`

- [ ] **Step 1: 派 subagent 审核（每篇一次）**

调用工具：

```text
Agent(subagent_type: gsd-code-reviewer, prompt: <逐篇调用>)
```

**subagent prompt 模板**（替换 `{FILE}` 为实际文件路径）：

```text
请严格审核 cookbook 教程：{FILE}

**审核目标**：确保教程质量符合 docs/superpowers/specs/2026-06-19-cookbook-tutorial-design.md
**审核维度**（每项给 PASS/FAIL + 证据）：

1. **章节齐全性**：对照本文件所属模板（工具类 8 节 / 语言类 9 节 / AI 库类 9 节），每节是否到位且 ≥150 字
2. **引用真实性**：所有 `file_path:line_number` 引用必须真实存在于仓库中。用 Grep/Read 工具验证每一条
3. **命令可执行性**：所有 bash 命令块在 Windows + bash 环境能跑（重点：docker compose v2、uv、bun、git 语法）
4. **内容准确性**：
   - 与官方文档（WebFetch 验证）一致
   - 与本项目实际用法（Grep 项目源码验证）一致
5. **是否包含"项目没用到的能力"和"常见坑"两节**：必须存在
6. **头部元信息 & 目录**：4 行头部 + 可跳转目录齐全
7. **链接有效性**：站内相对路径链接指向的文件存在；站外链接到官方文档
8. **文档完成度**：有文末状态标记（✅/🚧/❌）

**输出格式**：
- 总评分：PASS / FAIL
- 每个维度：PASS/FAIL + 1-2 句证据
- FAIL 项必须给出具体修复建议（修改哪一行、怎么改）

不要自审。独立判断。如果觉得不确定，倾向 FAIL。
```

> 每篇调用一次，三次共 3 次 subagent。**不要并发**，等前一篇 PASS 再审下一篇（防止 subagent 上下文被污染）。

- [ ] **Step 2: 修复 subagent 标出的 FAIL 项**

对每篇 subagent 报告中的 FAIL 项：
- 用 Edit 工具修改文件
- 改完后再 run 一遍该篇对应的 step 4-5 验证（wc -l + grep 章节数）

- [ ] **Step 3: subagent 重新审核（仅修过的篇）**

对每篇修改过的文件，再 dispatch 一次 subagent 确认 PASS。

- [ ] **Step 4: 全部 3 篇 PASS 后，提交（如有未提交修改）**

```bash
cd c:/doc/Code/rag
git status
# 如果有未提交：
git add docs/cookbook/
git commit -m "docs(cookbook): 3 篇样例经 subagent 审核后修复"
```

---

### Task 10: 更新 README 进度表（标记 3 样例状态从 🚧 → ✅）

**Files:**
- Modify: `docs/cookbook/README.md`

- [ ] **Step 1: 更新 README 中 3 样例状态**

将 `docs/cookbook/README.md` 中：
- `ci/docker.md` 行：`🚧 样例` → `✅ 已完成`
- `python/fastapi.md` 行：`🚧 样例` → `✅ 已完成`
- `rag/langgraph.md` 行：`🚧 样例` → `✅ 已完成`

以及"实施节奏"表：本 plan 状态从 `🚧 进行中` → `✅ 已完成`

- [ ] **Step 2: 提交**

```bash
cd c:/doc/Code/rag
git add docs/cookbook/README.md
git commit -m "docs(cookbook): 标记 3 样例完成 + 本 plan 收尾"
```

---

## 自审（spec 覆盖）

| Spec 章节 | 实施 task |
|-----------|----------|
| 一、目标 & 三类文档范围 | Task 2 (README 概述) |
| 二、工具类模板 | Task 3 |
| 三、语言/框架类模板 | Task 4 |
| 四、AI 库类模板 | Task 5 |
| 五、文档头部元信息 & 全局样式规范 | Task 2/3/4/5/6/7/8 (所有创建文件都遵循) |
| 六、实施节奏 & 交付物 | Task 1-10 |
| 七、质量门 | Task 9 (subagent 审核) |
| 八、风险（langchian typo） | Task 1 (git mv) |
| 八、风险（范围外）| 在 README "实施节奏" 表中标注 "下个 phase" |

无占位符、无 TBD。所有 file_path:line_number 引用都对得上现有项目结构（Task 6/7/8 在 step 5 都要求验证）。

## 执行选择

**Plan complete and saved to `docs/superpowers/plans/2026-06-19-cookbook-tutorial.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
