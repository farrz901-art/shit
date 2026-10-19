# spaCy Rule 端到端接入 handoff (2026-07-03)

## 任务来源

`docs/superpowers/plans/2026-07-03-spaCy-rule-end-to-end.md`

## 已完成 (3 commits)

| Commit | 内容 |
|---|---|
| 84dfa4aa | feat(deps): add spacy==3.8.13 (KG rule extractor, aligned with mem0ai pin) |
| 6d22c44b | feat(kg): lazy-load spacy model in _build_extractor, 503 on missing model |
| 578e1e37 | test(kg): update spacy_rule extractor test for lazy-load + 503 fallback |

## 代码改动覆盖

| 文件 | 改动 | 行数 |
|---|---|---|
| `packages/service/pyproject.toml:24` | 加 `"spacy==3.8.13"` (跟 mem0ai[nlp] pin 对齐) | +1 |
| `packages/service/src/kg/router.py:663-685` | `_build_extractor` 改写, spacy_rule 懒加载 spaCy.load, 失败 503 | +19 -2 |
| `packages/service/tests/kg/test_router_extract.py:36-66` | 旧测试改写 (mock nlp) + 新增 503 fallback 测试 | +27 -5 |

## 验证状态

✅ **代码逻辑验证** (12/12 tests pass):
- `test_build_extractor_spacy_returns_spacy_rule` — monkeypatch `spacy.load` → 返回 `SpacyRuleExtractor(nlp=mock_nlp)`, 符合预期
- `test_build_extractor_spacy_missing_model_raises_503` — `spacy.load` 抛 OSError → HTTPException(503), detail 含 "zh_core_web_sm" + "spacy download", 符合预期

✅ **spaCy 包安装** (uv run python -c "import spacy"):
- 输出 `spacy: 3.8.13`

❌ **dev end-to-end smoke test 阻塞** (环境问题, 非代码):
- `uv run spacy download zh_core_web_sm` 失败
- 根因: `zh_core_web_sm-3.8.0` 强依赖 `spacy-pkuseg<2.0.0,>=1.0.0` (zh_core_web_sm 的分词器后端)
- spacy-pkuseg 1.0.1 在 PyPI 上**没有 cp314 wheel**, uv 从源码编译失败 (C 扩展不兼容 Python 3.14)
- **不是代码 bug**, 是上游包 + Python 3.14 兼容性问题

## 接手者 follow-up

### 选项 A: 升级 spaCy 到 3.8.14+ 等有 jieba 后端的版本

spaCy 中文分词器后端从 pkuseg 迁到 jieba 是社区路线, 需要等 spacy-models 发新版 (zh_core_web_sm >= 3.8.14 时可能切到 jieba, 调研后确认).

### 选项 B: 临时换 en_core_web_sm 跑 dev smoke

48MB 英文模型, 不依赖 pkuseg. 修改 `configs/extractors/spacy_rule.yaml` 的 `spacy_model: en_core_web_sm`, router 改 `spacy.load("en_core_web_sm")`. 业务侧能跑通, 但**只抽英文文档**.

### 选项 C: 等 spaCy 3.9+ 或 4.0 解决 pkuseg 问题

上游 [spacy-models #issue 跟踪](https://github.com/explosion/spacy-models/issues), 关注 zh_core_web_sm 下一个版本.

### 已知不变量

**Task 2 的 lazy load + 503 fallback 在所有 3 个选项下都成立** — 即使 dev 不能跑 curl smoke test, 503 fallback 路径已被 unit test 覆盖, 生产环境(假设有 pkuseg wheel 或换模型)也能正确 fallback.

## 留尾 / 待办

- [ ] Dockerfile 集成 spacy 模型 (生产部署, 不在本 spec 范围)
- [ ] ontology 同义词合并 (2026-07-02 motor-ontology spec M4)
- [ ] spacy-pkuseg + Python 3.14 兼容性 follow-up