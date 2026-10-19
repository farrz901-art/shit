# Cookbook 教程

> 📅 最后更新：2026-06-25
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

## 📋 21 篇文件清单与进度

| # | 路径 | 类别 | 字数预估 | 状态 | 最后更新 |
|---|------|------|----------|------|----------|
| 1 | [ci/docker.md](ci/docker.md) | T-工具 | 4000-6000 | ✅ 已完成 | 2026-06-25 |
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
| 13 | [python/fastapi.md](python/fastapi.md) | L-语言 | 5000-8000 | ✅ 已完成 | 2026-06-25 |
| 14 | [python/python.md](python/python.md) | L-语言 | 10000+ | ❌ 待写 | — |
| 15 | [rag/deepagent.md](rag/deepagent.md) | A-AI 库 | 2500-4000 | ❌ 待写 | — |
| 16 | [rag/deepeval.md](rag/deepeval.md) | A-AI 库 | 2000-3000 | ❌ 待写 | — |
| 17 | [rag/langchain.md](rag/langchain.md) | A-AI 库 | 6000-10000 | ❌ 待写 | — |
| 18 | [rag/langfuse.md](rag/langfuse.md) | A-AI 库 | 3000-5000 | ❌ 待写 | — |
| 19 | [rag/langgraph.md](rag/langgraph.md) | A-AI 库 | 6000-10000 | ✅ 已完成 | 2026-06-25 |
| 20 | [rag/llama-index.md](rag/llama-index.md) | A-AI 库 | 5000-8000 | ❌ 待写 | — |
| 21 | [rag/mem0.md](rag/mem0.md) | A-AI 库 | 2500-4000 | ❌ 待写 | — |

> ✅ `docs/cookbook/rag/` 目录下原 `langchian.md` 已重命名为 `langchain.md`（保留 git 历史）

---

## ✅ 实施节奏

| 批次 | 内容 | 状态 |
|------|------|------|
| 本 plan | 总纲 + 3 模板 + 3 样例 + 重命名 | ✅ 已完成 |
| 第 1 批（下个 phase） | 7 个工具类（grafana, nginx, elk, minio, neo4j, postgres, redis） | ❌ 待启动 |
| 第 2 批（下个 phase） | 5 个语言类（python, nextjs, react, react-query, zustand） | ❌ 待启动 |
| 第 3 批（下个 phase） | 6 个 AI 库类（deepagent, deepeval, langchain, langfuse, llama-index, mem0） | ❌ 待启动 |

---

## 📖 相关文档

- 设计 spec：[docs/superpowers/specs/2026-06-19-cookbook-tutorial-design.md](../superpowers/specs/2026-06-19-cookbook-tutorial-design.md)
- 模板：[_template-T.md](_template-T.md) / [_template-L.md](_template-L.md) / [_template-A.md](_template-A.md)
- 样例：[ci/docker.md](ci/docker.md) / [python/fastapi.md](python/fastapi.md) / [rag/langgraph.md](rag/langgraph.md)
