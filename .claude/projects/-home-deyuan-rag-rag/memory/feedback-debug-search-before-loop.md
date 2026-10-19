---
name: feedback-debug-search-before-loop
description: "遇到报错必须先搜索/查官方文档, 不能重复试错; 连续失败 2 次相同方案必须停下来换思路"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 822e2447-09c4-4b8a-9808-d37453aff4b8
---

遇到技术问题时的强制行为准则:

## 禁止: 重复试错循环

**连续 2 次相同方案失败 → 必须停下来**, 做以下之一:
1. 搜索官方文档 / PyPI / GitHub issues
2. 搜索 StackOverflow / 博客
3. 向用户澄清问题再动手

**绝对不能**: 第 3 次尝试同一个方案的不同变体.

## 案例: LlamaIndex 评估替换 RAGAS (2026-06-10, 浪费 2 小时)

| 次数 | 我做了什么 | 结果 | 应该做什么 |
|---|---|---|---|
| 1 | 用 `llama_index.llms.openai.OpenAI` | `Unknown model 'MiniMax-M3'` | → 搜 "llama_index deepseek" |
| 2 | 改模型名 `gpt-4o-mini` | `Connection error` (MiniMax) | → 搜 "llama_index custom LLM" |
| 3 | 写 HttpxLLM 绕过 | `missing metadata` | → 搜 "llama_index CustomLLM 接口要求" |
| 4 | 加 metadata 属性 | `missing chat method` | → 搜 "llama-index-llms-deepseek" |
| 5 | 继续补方法 | ... | **用户指出有 llama-index-llms-deepseek 包** |

**正确路径**: 第 1 次失败后直接搜 → `uv add llama-index-llms-deepseek` → 改 1 行 → 完事.

## 强制规则

1. **报错信息包含 `Unknown model` / `Connection error` / `missing xxx`** → 先搜 "llama_index [问题关键词]" / "[库名] [问题关键词]"
2. **PyPI 有官方集成包** → 直接用, 不要自己造轮子 (如 `llama-index-llms-deepseek`)
3. **查官方文档**: https://docs.llamaindex.ai → 找对应模块的 LLM 集成列表
4. **每个方案最多试 1 次**, 失败立刻搜而不是再试变体
5. **写代码前先查接口要求**: 如果要实现自定义类, 先查父类的 abstract methods, 不要边写边补

## How to apply

每次遇到:
- ImportError / ModuleNotFoundError → 搜 PyPI 有没有现成包
- "Unknown model" / "missing xxx" → 搜官方文档的 LLM 集成列表
- 连续 2 次失败 → 强制暂停, 搜索, 再继续
