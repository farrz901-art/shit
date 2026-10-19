---
name: feedback-audit-env-changes-introduce
description: "新增 env var / embedder / provider 集成时必须告诉用户全部影响面, 不留隐藏默认"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: cdd2021a-1a31-4669-81ff-496a2134f22b
---

新引入跟外部系统绑定的配置 (embedder / LLM / vector store / 第三方 SDK) 时,
必须主动列清楚:

1. **provider 默认值是什么** (用户不看代码不会知道)
2. **网络/账号前提** (e.g. HF provider 要能访问 HF Hub, 离线/封网就卡)
3. **能不能用 env 切走** (缺了 = bug, 不能让用户改代码)
4. **handoff 文档必须列影响面**, 不能只写 "pre-existing infra 问题" 一笔带过

**Why**: 2026-06-16 用户质问 mem0 handoff 里 "Pre-E2E SKIP: embedder HuggingFace
网络阻塞" —— 实际上是我在 mem0_client.py 写死了 HF provider 引入的, 根本不是
pre-existing. 用户用 HF 网络封了的环境, 整个 app 起不来. 必须改成 env 可配 +
暴露给用户.

**How to apply**:
- 写 "pre-existing" 措辞前先确认是不是真 pre-existing, 是不是本次引入
- 涉及外部 SDK 配置 (mem0 / langfuse / openai / ollama) 必须提供 env 切换点
- 在 handoff / docs 列 "已知的隐含依赖" 一段, 写明 provider 默认值 + 网络要求
- 用户问"你加了 X 吗"时, 第一反应是查代码, 不是凭印象答
