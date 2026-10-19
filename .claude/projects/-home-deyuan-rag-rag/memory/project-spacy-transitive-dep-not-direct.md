---
name: project-spacy-transitive-dep-not-direct
description: "spaCy 在 RAG 项目里只走 mem0ai[nlp] 间接依赖,pyproject.toml 不直接声明是正确设计"
metadata: 
  node_type: memory
  type: project
  originSessionId: 432e511f-0290-4fae-b15c-cd498b7593bc
---

# spaCy 间接依赖设计 (2026-07-03)

## 事实

- 项目 spaCy 用在 2 处:
  1. 自研 `SpacyRuleExtractor` ([packages/service/src/kg/extractors/spacy_rule/extractor.py](packages/service/src/kg/extractors/spacy_rule/extractor.py)): 构造函数 `__init__(nlp=None)` **不直接 import spaCy**,只调用注入的 nlp 对象
  2. mem0 链路 ([packages/service/src/memory/mem0_client.py](packages/service/src/memory/mem0_client.py:100-148)): 只在注释/日志里写 "spacy en_core_web_sm 缺",不直接 import
- pyproject.toml 不直接声明 `spacy`,只声明 `mem0ai[nlp]>=2.0.5` ([packages/service/pyproject.toml:23](packages/service/pyproject.toml#L23))
- uv.lock 第 1461 行已经把 spacy 作为 `mem0ai[nlp]` 的依赖拉进来,spacy 3.8.13 (mem0ai 2.0.5 固定 pin)

## 为什么不直接声明 spacy 是对的

- 直接声明 spacy 会跟 mem0ai[nlp] 拉的 spaCy 重复,uv 不会冲突但语义冗余
- 自研 SpacyRuleExtractor 当前是骨架,router [_build_extractor()](packages/service/src/kg/router.py#L665-L666) 传 `nlp=None`,走 `error="spaCy nlp 未初始化"` 分支;真要跑需要改 router 注入 spaCy.load("zh_core_web_sm") + 装模型
- 测试侧传 mock nlp,不依赖 spaCy 包本身,符合 CLAUDE.md "测试必须 mock,不连真依赖"

## 什么时候需要把 spacy 写进 pyproject.toml

业务侧真要让 SpacyRuleExtractor 跑起来时 (改 router 注入 spaCy.load 模型),需要:
1. pyproject.toml 加 `"spacy>=3.8.13"`
2. Dockerfile / setup 加 `spacy download zh_core_web_sm` (跟 [configs/extractors/spacy_rule.yaml](packages/service/configs/extractors/spacy_rule.yaml) 的 `spacy_model: zh_core_web_sm` 对应)

## Why

2026-07-03 用户问 "代码里用了 spacy 为什么不写进 pyproject.toml",避免后续 reviewer 误以为是 bug 而误加。

## nlp=None 不是 TODO,是 v1 留口子

[4cdb3cbd (2026-07-02)](packages/service/src/kg/extractors/spacy_rule/extractor.py) 原始 commit docstring 写 `v1 测试侧传 mock, 业务侧注入真 nlp`——**有意识的架构决策**,不是没开发完。

v3 (markdown-extract-kg-v3, 7 PR 收尾于 2026-07-02 2f9ef8f2) 完整交付骨架 + yaml + 测试 + 接入路由,但**故意不在 router 注入 spaCy**——spaCy zh_core_web_sm 模型镜像 +300MB 是产品决策,需要拍板"是否值得为高吞吐兜底付出镜像成本"。

## v2 接通 spaCy 真用要做 3 件事

1. pyproject.toml 加 `"spacy>=3.8.13"`
2. Dockerfile / setup 加 `spacy download zh_core_web_sm`
3. router [_build_extractor()](packages/service/src/kg/router.py#L665-L666) 改 `nlp=None` → `nlp = spacy.load("zh_core_web_sm")`

## How to apply

- 看到 spaCy 相关代码改动时,先确认是不是只动 mock 路径;如果只动 mock/extractor 骨架,pyproject.toml 不动
- 真要把 SpacyRuleExtractor 接到生产 router 时,先跟用户对齐是否值得加 ~300MB spaCy 模型镜像,再决定直接声明 spacy