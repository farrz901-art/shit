# Cookbook 教程补全设计

> 📅 创建日期：2026-06-19
> 📁 项目代码引用：以 `c:/doc/Code/rag` 仓库当前代码为准
> 🎯 范围：把 `docs/cookbook/` 下 19 个 0 字节空文件补成中级工程师"读得懂、用得上"的中文教程

---

## 一、目标 & 三类文档范围

**目标**：把 `docs/cookbook/` 下 19 个 0 字节空文件补成"中级工程师读得懂、用得上"的中文教程。每篇覆盖：是什么 → 安装 → 核心概念 → 项目集成 → 项目代码示例 → 项目没用到的能力 → 最佳实践 → 常见坑。

**19 篇文件分类**：

| 类别 | 模板 | 文件 |
|------|------|------|
| 工具类（8） | T-工具模板 | ci/docker, ci/grafana, ci/nginx, db/elk, db/minio, db/neo4j, db/postgres, db/redis |
| 语言/框架类（6） | L-语言模板 | nextjs/nextjs, nextjs/react, nextjs/react-query, nextjs/zustand, python/fastapi, python/python |
| AI 库类（7） | A-AI库模板 | rag/deepagent, rag/deepeval, rag/langchain, rag/langfuse, rag/langgraph, rag/llama-index, rag/mem0 |

**信息源权重**：项目源码 50% + 官方文档 30% + 社区最佳实践 15% + LLM 样板 5%

**交付节奏**：本次产出 ①总纲 + ②三类模板 + ③3 篇样例（docker 工具类 + fastapi 语言类 + langgraph AI 库类）；后续按子目录分批出剩余 16 篇。

---

## 二、工具类模板（T-工具）

工具类 8 篇，模板（8 节，字数弹性，复杂工具自然到 4000-6000+，简单工具 2000-3000）：

1. **是什么 & 解决什么问题**（≥150字）：一段话讲清定位 + 与同类替代品对比
2. **安装 & 启动**（≥150字）：本地 docker 启动 / 操作系统安装 + 健康检查
3. **核心概念**（≥150字）：3-5 个关键术语
4. **⭐ 常用命令 & 用法速查**（≥200字）：分 3-4 个场景列命令（启停/查询/调试/排错），命令前加注释讲何时用
5. **项目集成点**（≥150字）：连接、配置、被引用的模块
6. **项目代码示例**（≥200字）：源码片段 + file_path:line_number
7. **项目没用到的能力**（≥150字）：官方但项目未用，标"待评估"
8. **运维 & 最佳实践 + 常见坑**（≥150字）：备份/监控/容量 + 3-5 条本项目已踩

> **说明**：docker.md 是特例（多写一节"docker compose 写作技巧"），仍归工具类。

---

## 三、语言/框架类模板（L-语言）

语言/框架类 6 篇，模板（9 节，字数无上限，可几万字）：

1. **是什么 & 适用场景**（≥150字）：定位 + 与同类对比
2. **安装 & 开发环境**（≥150字）：包管理、IDE/格式化、推荐 .editorconfig
3. **基础语法 & 类型系统**（≥150字）：核心语法、类型注解、常用结构
4. **核心概念**（≥150字）：5-8 个关键概念
5. **常用命令 & 工具链**（≥150字）：构建/测试/格式化/lint 命令
6. **项目集成点**（≥150字）：在 monorepo 中的位置、配置入口
7. **项目代码示例**（≥150字，重点）：直接引用项目源码 file_path:line_number
8. **项目没用到的能力 / 进阶方向**（≥150字）：项目未用但读者值得知道
9. **最佳实践 & 常见坑**（≥150字）：本项目风格指南 + 常见错误

> **说明**：字数完全弹性，按真实内容写，几万字也可以；下限 150 字仅防漏节。

---

## 四、AI 库类模板（A-AI库）

AI 库类 7 篇（deepagent、deepeval、langchain、langfuse、langgraph、llama-index、mem0），模板（9 节，字数弹性）：

1. **是什么 & 解决什么问题**（≥150字）：定位 + 同类对比
2. **安装 & 初始化**（≥150字）：包管理、配置 LLM provider、env key 列表
3. **核心概念 & 抽象**（≥150字）：5-8 个核心抽象
4. **常用 API & 命令速查**（≥150字）：建图/查询/调用样板代码片段
5. **项目集成点**（≥150字）：在 packages/service / packages/web 的引用位置、配置入口
6. **项目代码示例**（≥150字，重点）：从项目源码拉，带 file_path:line_number
7. **项目没用到的能力**（≥150字）：项目未用但读者值得学
8. **评测 & 调优技巧**（≥150字）：latency/token 监控、prompt 迭代、cost 控制
9. **最佳实践 & 常见坑**（≥150字）：版本兼容、async 陷阱、checkpoint 持久化

---

## 五、文档头部元信息 & 全局样式规范

**统一头部**：
```markdown
# {工具/库/语言名} 教程

> 📅 创建日期：2026-06-19
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 file_path:line_number
> 🏷️ 类别：T-工具 / L-语言/框架 / A-AI 库
> 🎯 读者：中高级 Python/TS 工程师，需要理解本项目为什么这样用、能怎么扩展
```

**目录**：每篇开头加可跳转目录（参考 `docs/docker-compose-analysis.md` 风格）。

**代码示例规范**：
- 所有代码块标注语言（```python、```ts、```yaml、```bash）
- 引用项目代码时上方标注：`<!-- 引用自 packages/service/app/main.py:42 -->` 或 `**引用：** packages/service/app/main.py:42-58`
- 示例代码必须可运行（去掉伪代码注释）
- 跨平台命令：Windows 用 `bash` shell 语法（用户环境是 Windows + bash）

**图片 / 图表**：可适度用 ASCII 图（参考已有 `docs/docker-compose-analysis.md` 的 ASCII 拓扑）。

**链接**：站内用相对路径 [filename.md](path/to/filename.md)，站外引用官方文档用 markdown 链接。

**章节命名规范**：每个模板章节有固定标题（一二级），便于跨文档对照。

**完成状态**：每篇文末加 ✅/🚧 进度标记（✅ 已完成 / 🚧 部分完成 / ❌ 待补充），便于读者快速判断可参考度。

---

## 六、实施节奏 & 交付物

**本次（本设计批准后）交付物**：
1. `docs/superpowers/specs/2026-06-19-cookbook-tutorial-design.md` ← 本设计文档
2. `docs/cookbook/README.md` ← 写作总纲（含三类模板全文 + 19 篇清单）
3. `docs/cookbook/_template-T.md` ← 工具类模板空白版
4. `docs/cookbook/_template-L.md` ← 语言/框架类模板空白版
5. `docs/cookbook/_template-A.md` ← AI 库类模板空白版
6. **样例 3 篇**（用户审过后推广）：
   - `docs/cookbook/ci/docker.md`（工具类样例）
   - `docs/cookbook/python/fastapi.md`（语言类样例）
   - `docs/cookbook/rag/langgraph.md`（AI 库类样例）
7. **重命名**：`git mv docs/cookbook/rag/langchian.md docs/cookbook/rag/langchain.md`（保留 git 历史）

**后续分批**（不在本次 spec 范围，写到下个 phase 计划）：
- 第 1 批：剩余 7 个工具类（grafana, nginx, elk, minio, neo4j, postgres, redis）
- 第 2 批：剩余 5 个语言类（python, nextjs, react, react-query, zustand）
- 第 3 批：剩余 6 个 AI 库类（deepagent, deepeval, langchain, langfuse, llama-index, mem0）

每批先看上一批审过风格再写。

**信息来源 & 工具**：
- 项目源码：`Grep` / `Read` / `Glob`
- 官方文档：`WebFetch` + `WebSearch`
- 社区最佳实践：博客/GitHub README star 数高者
- LLM 样板：仅作骨架或示例填充

---

## 七、质量门（独立章节，落到 implementation plan）

**质量门（每篇必过）**：
- 每篇至少 30% 篇幅引用项目源码（file_path:line_number 必须真实存在）
- 命令必须在 Windows + bash 环境可执行
- 章节齐全（每篇都按模板走完，不漏节）

**审核流程**：
- 每篇写完后，dispatch 一个独立 `gsd-code-reviewer` subagent 严格审核（不用自审）
- subagent 给出 PASS/FAIL，FAIL 则修，PASS 才进入下一批

**审核维度（subagent 视角）**：
1. 章节齐全性：对照模板，每节是否到位
2. 引用真实性：file_path:line_number 是否真实存在
3. 命令可执行性：bash + Windows 11 下能否跑
4. 内容准确性：与官方文档 / 本项目实际用法是否一致
5. 字数下限：语言/框架类每节 ≥150 字
6. 是否包含"项目没用到的能力"和"常见坑"两节
7. 头部元信息 & 目录是否齐全
8. 链接是否有效

---

## 八、风险 & 范围控制

**已识别风险**：
1. **范围爆炸**：19 篇 × 每篇数千字 → 总字数可达 10 万+。本设计只承诺"本次 = 总纲 + 3 篇样例"，剩余 16 篇进入下个 phase；不在本次 spec 范围
2. **项目代码量**：RAG 项目代码大，AI 库类文档需要读懂 LangGraph / LlamaIndex 等多个框架的源码引用，前期调研时间较长
3. **官方文档陈旧**：langchain/langgraph 在 2024-2025 大量破坏性变更，部分中文网络文章过时；优先引用官方英文文档，必要时以官方版本号锚定
4. **命令兼容性**：用户环境是 Windows + bash，但很多教程默认 Linux/Mac shell；需要逐条复核（特别是 docker compose v2 vs v1、uv vs poetry、bun vs npm）
5. ~~cookbook 拼写错误~~（已解决：用 `git mv docs/cookbook/rag/langchian.md docs/cookbook/rag/langchain.md` 重命名）
6. **依赖外部网络**：WebFetch / WebSearch 受网络影响，部分官方文档需 fallback

**范围外（本次不做）**：
- 19 篇全量写作（分批进入下个 phase）
- 教程配套的 example code 仓库
- 教程英文翻译
- 教程导出 PDF / mkdocs 站点
- 教程自动校验脚本（仅在 plan 里用 subagent 人工 review）
