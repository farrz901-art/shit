---
name: project-spacy-pkuseg-python314-incompatible
description: "spacy-pkuseg 1.0.1 在 PyPI 没有 cp314 wheel,Python 3.14 环境 uv run spacy download zh_core_web_sm 编译失败"
metadata: 
  node_type: memory
  type: project
  originSessionId: 432e511f-0290-4fae-b15c-cd498b7593bc
---

# spacy-pkuseg + Python 3.14 不兼容 (2026-07-03)

## 事实

- `spaCy 3.8.13` (项目 pyproject pin) + `zh_core_web_sm 3.8.0` 强依赖 `spacy-pkuseg<2.0.0,>=1.0.0`
- `spacy-pkuseg 1.0.1` 在 PyPI 上**只有源码包**, 无 cp314 wheel
- uv 从源码编译: `Building wheel for spacy-pkuseg (pyproject.toml)` 失败, exit code 1
- 实际跑 `uv run python -c "import spacy"` ✅ 通 (spaCy 3.8.13 装好), **但** `import spacy; nlp = spacy.load("zh_core_web_sm")` ❌ 拉模型时挂

## 验证环境

- Python 3.14.5
- uv 0.x (lock 3.8.13)
- Windows 11, MSVC 默认装
- `uv run spacy download zh_core_web_sm` → failed wheel build for spacy-pkuseg

## 影响范围

- `mem0ai[nlp]` 2.0.5 间接依赖 spacy 3.8.13 → mem0 启动期 warmup (`mem0_client.py:113 mem.search("__mem0_warmup__")`) 也可能挂 (如果它用 zh_core_web_sm 分词)
- **KG spacy_rule extractor** 端到端 smoke test 阻塞 (2026-07-03 spec §Task 4 没跳完, 留 handoff)
- 前端选 spacy_rule → router `_build_extractor` 走 503 fallback, **业务侧 0 可用** (跟修复前一致)

## Why

2026-07-03 spaCy 端到端 spec 实战遇到, 浪费 ~10 分钟调源码包编译. 不要重复踩坑.

## How to apply

- 写 spec / plan 时如果涉及 spaCy 中文模型, **先确认上游 pkuseg 兼容当前 Python 版本**, 或者改用 jieba 后端的 spaCy 版本
- 不要假设 `uv run spacy download zh_core_web_sm` 一定能成功, dev smoke test 留余地
- 等 spaCy-models 升级 (可能 3.8.14+) 或 spacy-pkuseg 发 cp314 wheel, 重新跑 end-to-end 验证