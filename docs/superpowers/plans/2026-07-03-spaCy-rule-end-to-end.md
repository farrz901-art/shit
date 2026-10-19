# spaCy Rule 接入端到端实施 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 SpacyRuleExtractor 从"骨架 + 配置 + mock 测试"状态接入端到端,让前端选 spacy_rule 真能抽出 entity。

**Architecture:** 懒加载 + 失败 503。`_build_extractor("spacy_rule")` 在 router 调用时才 `spacy.load("zh_core_web_sm")`,加载失败抛 HTTPException 503 给前端明确提示。避免启动期 slow load,符合按需加载原则。

**Tech Stack:** spaCy 3.8.13 (跟 mem0ai[nlp] pin 对齐) + Python 3.14 + uv

---

## 背景

### 当前状态 (2026-07-03)

- [packages/service/src/kg/extractors/spacy_rule/extractor.py](packages/service/src/kg/extractors/spacy_rule/extractor.py) 骨架完整,接受注入 `nlp`
- [packages/service/configs/extractors/spacy_rule.yaml](packages/service/configs/extractors/spacy_rule.yaml) 配 `spacy_model: zh_core_web_sm`
- [packages/service/src/kg/router.py:665-666](packages/service/src/kg/router.py#L665-L666) 工厂函数 `_build_extractor` 传 `nlp=None`
- [packages/service/tests/kg/extractors/spacy_rule/test_extractor.py](packages/service/tests/kg/extractors/spacy_rule/test_extractor.py) 3 个 mock test,全绿

### 问题

前端 `POST /api/kg/extract/start {extractor: "spacy_rule"}` → 后端永远走 `error="spaCy nlp 未初始化"` → 业务侧 0 可用。

### 目标

- 前端选 spacy_rule → 真能抽 entity → 业务侧能用
- spaCy 模型没下 → 503 明确提示安装命令,不静默降级

### 范围控制 (CLAUDE.md §范围控制)

3 个文件改动,预计 ~50 行净增,**不碰 Dockerfile** (生产部署是另一回事,留给后续 spec)。

---

## Task 1: pyproject.toml 加 spacy==3.8.13 (跟 mem0ai pin 对齐)

**Files:**
- Modify: [packages/service/pyproject.toml:23](packages/service/pyproject.toml) (在 `mem0ai[nlp]` 那行后面)

- [ ] **Step 1: 修改 pyproject.toml**

在 `packages/service/pyproject.toml` 的 dependencies 列表里,找到第 23 行 `"mem0ai[nlp]>=2.0.5"`,在它**后面**加一行:

```toml
  "mem0ai[nlp]>=2.0.5", # 对话记忆层 (src/memory/mem0_client.py) — PyPI 包名 mem0ai, import 仍用 mem0
  "spacy==3.8.13", # 知识图谱规则抽取器直接依赖 (src/kg/extractors/spacy_rule/extractor.py),跟 mem0ai[nlp] pin 对齐
```

**为什么要 pin `==3.8.13`**:
- uv.lock 第 3160-3168 行已经锁了 `spacy-3.8.13` 作为 `mem0ai[nlp]` 的依赖
- 用 `==` 而非 `>=` 跟 mem0ai 的 pin 对齐,避免未来 spaCy 升级时两边版本漂移
- pyright 能直接推断 spacy.load 返回类型,IDE 提示完整

- [ ] **Step 2: 跑 uv sync 装 spaCy**

```bash
cd packages/service && uv sync
```

Expected: spaCy 3.8.13 装到 `.venv`(uv resolver 会选跟 lock 一致的 3.8.13)。

- [ ] **Step 3: 验证 spacy 可 import**

```bash
cd packages/service && uv run python -c "import spacy; print('spacy:', spacy.__version__)"
```

Expected: `spacy: 3.8.13`

- [ ] **Step 4: Commit**

```bash
git add packages/service/pyproject.toml packages/service/uv.lock
git commit -m "feat(deps): add spacy==3.8.13 (KG rule extractor, aligned with mem0ai pin)"
```

---

## Task 2: 改 _build_extractor() 懒加载 spaCy,失败返 503

**Files:**
- Modify: [packages/service/src/kg/router.py:663-669](packages/service/src/kg/router.py#L663-L669) (`_build_extractor` 函数)

- [ ] **Step 1: 改写 _build_extractor 函数**

把现有的 `_build_extractor` 函数 ([router.py:663-669](packages/service/src/kg/router.py#L663-L669)):

```python
def _build_extractor(extractor_id: str):
    """工厂函数: extractor_id → BaseExtractor 实例"""
    if extractor_id == "spacy_rule":
        return SpacyRuleExtractor(nlp=None)
    if extractor_id == "llm_pydantic":
        return LlmPydanticExtractor(llm=None)
    raise ValueError(f"未知 extractor_id: {extractor_id}")
```

改成:

```python
def _build_extractor(extractor_id: str):
    """工厂函数: extractor_id → BaseExtractor 实例

    spacy_rule 懒加载 spaCy 模型 (避免启动期 slow load),加载失败抛 HTTPException 503
    提示用户安装命令,符合"业务侧 0 静默降级"原则.
    """
    if extractor_id == "spacy_rule":
        import spacy

        try:
            nlp = spacy.load("zh_core_web_sm")
        except OSError as e:
            # spacy 模型未下载 → 503 明确提示, 不静默降级返 None
            raise HTTPException(
                status_code=503,
                detail=(
                    f"spaCy 模型 zh_core_web_sm 未加载: {e}. "
                    "请运行: cd packages/service && uv run spacy download zh_core_web_sm"
                ),
            ) from e
        return SpacyRuleExtractor(nlp=nlp)
    if extractor_id == "llm_pydantic":
        return LlmPydanticExtractor(llm=None)
    raise ValueError(f"未知 extractor_id: {extractor_id}")
```

**关键决策说明**:
- 用 `import spacy` 函数内 lazy import 而非顶部,因为 `_build_extractor` 是路由工厂函数,按需调用;`packages/service/src/` 当前 0 处直接 import spaCy, 全部走 `mem0ai[nlp]` 间接路径, 函数内 lazy import 跟项目现有惯例一致
- `OSError` 是 spacy.load model 不存在时抛的异常 (跟 spaCy 3.x 文档一致)
- HTTPException 503 而不是 500:503 = 服务可用但依赖缺失,500 = 服务本身出错,语义更准
- prompt 写"cd packages/service &&"明确 cwd,避免用户困惑

- [ ] **Step 2: 验证 pyright 类型**

```bash
cd packages/service && uv run pyright src/kg/router.py
```

Expected: 0 errors (HTTPException / spacy.load 类型已知,无需 `# type: ignore`)。

- [ ] **Step 3: 跑 ruff format + check**

```bash
cd packages/service && uv run ruff format src/kg/router.py && uv run ruff check src/kg/router.py
```

Expected: format 无 diff,check 无 error。

- [ ] **Step 4: Commit**

```bash
git add packages/service/src/kg/router.py
git commit -m "feat(kg): lazy-load spacy model in _build_extractor, 503 on missing model"
```

---

## Task 3: 修 test_router_extract.py 旧断言 + 加新 503 测试

**Files:**
- Modify: [packages/service/tests/kg/test_router_extract.py:36-47](packages/service/tests/kg/test_router_extract.py#L36-L47) (旧测试 `test_build_extractor_spacy_returns_spacy_rule` 改写)
- Modify: 同文件追加新测试 `test_build_extractor_spacy_missing_model_raises_503`

- [ ] **Step 1: 改写旧测试,断言 nlp 不再 None**

[packages/service/tests/kg/test_router_extract.py:36-47](packages/service/tests/kg/test_router_extract.py#L36-L47) 现在的代码:

```python
def test_build_extractor_spacy_returns_spacy_rule():
    """[M7] _build_extractor('spacy_rule') → SpacyRuleExtractor (nlp=None)"""
    from typing import Any, cast

    from src.kg.extractors.spacy_rule.extractor import SpacyRuleExtractor
    from src.kg.router import _build_extractor

    ext = _build_extractor("spacy_rule")
    assert isinstance(ext, SpacyRuleExtractor)
    assert ext.extractor_id == "spacy_rule"
    # nlp 是 None (v1 default), cast(Any) 让 pyright 不报 unknown attr
    assert cast(Any, ext).nlp is None  # type: ignore[attr-defined]
```

改成 (用 mock 避免真加载 spaCy 模型,符合 CLAUDE.md §测试必须 mock):

```python
def test_build_extractor_spacy_returns_spacy_rule(monkeypatch: pytest.MonkeyPatch):
    """[2026-07-03] _build_extractor('spacy_rule') → SpacyRuleExtractor (nlp=<mock>)"""
    from unittest.mock import MagicMock

    from src.kg.extractors.spacy_rule.extractor import SpacyRuleExtractor
    from src.kg.router import _build_extractor

    # mock spacy.load, 避免真依赖 spaCy 模型 + 保证测试稳定
    mock_nlp = MagicMock()
    monkeypatch.setattr("spacy.load", lambda model_name: mock_nlp)

    ext = _build_extractor("spacy_rule")
    assert isinstance(ext, SpacyRuleExtractor)
    assert ext.extractor_id == "spacy_rule"
    assert ext.nlp is mock_nlp
```

**改写要点**:
- 加 `monkeypatch` fixture 注入 mock
- `monkeypatch.setattr("spacy.load", lambda model_name: mock_nlp)` 在 `_build_extractor` 函数内 `import spacy` 之后,**实际是 setattr spacy 模块的 load 属性**
- 断言从 `nlp is None` 改成 `nlp is mock_nlp`

- [ ] **Step 2: 加新测试,验 503 行为**

在 `test_build_extractor_spacy_returns_spacy_rule` 后面追加:

```python
def test_build_extractor_spacy_missing_model_raises_503(monkeypatch: pytest.MonkeyPatch):
    """[2026-07-03] spacy.load 抛 OSError → HTTPException 503 + 安装命令提示"""
    from fastapi import HTTPException

    from src.kg.router import _build_extractor

    # mock spacy.load 抛 OSError, 模拟模型未下载
    def _fake_load(_model_name: str):
        raise OSError("Can't find model 'zh_core_web_sm'")

    monkeypatch.setattr("spacy.load", _fake_load)

    with pytest.raises(HTTPException) as exc_info:
        _build_extractor("spacy_rule")
    assert exc_info.value.status_code == 503
    assert "zh_core_web_sm" in exc_info.value.detail
    assert "spacy download" in exc_info.value.detail
```

**测试要点**:
- OSError 跟 spacy.load 真实抛的异常类一致 ([spaCy 文档](https://spacy.io/api/cli#download))
- 断言 detail 里含 `zh_core_web_sm` 和 `spacy download` 两个关键词,确保提示用户安装模型

- [ ] **Step 3: 跑新测试,验证通过**

```bash
cd packages/service && uv run pytest tests/kg/test_router_extract.py -v
```

Expected: 全部 PASS,包括新增的 2 个 test (改写 + 新增)。

- [ ] **Step 4: 跑全量测试,确保没破坏现有**

```bash
cd packages/service && uv run pytest -q
```

Expected: 通过数 +2,失败数 0 增。Pre-existing 22 fail / 38 errors 不算 ([KNOWN_ISSUES.md](packages/service/KNOWN_ISSUES.md))。

- [ ] **Step 5: Commit**

```bash
git add packages/service/tests/kg/test_router_extract.py
git commit -m "test(kg): update spacy_rule extractor test for lazy-load + 503 fallback"
```

---

## Task 4: 端到端 dev 验证 (manual smoke test)

**Files:** 无 (手动验证)

- [ ] **Step 1: dev 环境装 spaCy 中文模型**

```bash
cd packages/service && uv run spacy download zh_core_web_sm
```

Expected: 下载 ~50MB 模型文件,输出 `✔ Download and installation successful`。

- [ ] **Step 2: 启动 dev server**

```bash
cd packages/service && uv run python main.py
```

Expected: uvicorn 启动在 8000 端口,**不报 spaCy 错误**(懒加载,不启动期 load)。

- [ ] **Step 3: 触发 spacy_rule 抽取**

构造一个测试请求 (需要先登录拿 token,token 从 `/api/auth/login` 拿,这里用 curl 示意):

```bash
# 1. 登录拿 token (密码按实际 dev admin)
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"dev_password"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

# 2. 上传测试 markdown 文件
URI=$(curl -s -X POST http://localhost:8000/api/kg/extract/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@docs/superpowers/specs/2026-07-01-markdown-extract-kg-design.md;type=text/markdown" \
  -F "dataset=motor" \
  | python -c "import json,sys; print(json.load(sys.stdin)['uri'])")

# 3. 启动 spacy_rule 抽取
curl -s -X POST http://localhost:8000/api/kg/extract/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"uri\":\"$URI\",\"dataset\":\"motor\",\"extractor\":\"spacy_rule\",\"splitter\":\"heading\"}"
```

Expected: 返 `{"task_id":"...","state":"queued"}`,**不报 5xx**。

- [ ] **Step 4: 验证抽取结果非空** (假设 cwd 在仓库根目录, 即 `c:/Users/abcuc/Desktop/rag/`)

等 3-5 秒后 (注意把 `<task_id>` 替换成 Step 3 拿到的实际 task_id):

```bash
curl -s http://localhost:8000/api/kg/extract/tasks/<task_id>/preview \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool | head -30
```

Expected: `entities` list **不为空**(应该至少识别出 markdown 里的英文 token / 数字型号),**不返 `error`**。

**如果失败**:
- 503 + "model not found" → 模型没下,回 Step 1
- 500 + stack trace → 看后端日志,可能是 spacy 模型加载路径问题,需要排查

- [ ] **Step 5: 记录 dev 验证结果到 handoff**

新建 `docs/superpowers/handoffs/2026-07-03-spaCy-rule-end-to-end.md`,记录:

```markdown
# spaCy Rule 端到端接入 (2026-07-03)

## 改动 3 文件
- pyproject.toml: 加 spacy==3.8.13
- src/kg/router.py: _build_extractor 懒加载 + 503
- tests/kg/test_router_extract.py: 改 1 测试 + 加 1 测试

## dev 验证
- uv run spacy download zh_core_web_sm: ✔
- POST /api/kg/extract/start extractor=spacy_rule: ✔ task_id=...
- GET /api/kg/extract/tasks/{id}/preview: entities=[{...}], 不空

## 已知 follow-up
- [ ] Dockerfile 生产镜像集成 spacy 模型 (单独 spec, 本期不动)
- [ ] ontology spec (2026-07-02 motor-ontology) M4 提到 spacy 同义词合并, 后续接入
```

(这是一个 verification 记录,**不需要 commit**, 本地文件即可)

---

## 完成定义

✅ Task 1-3 全部 commit
✅ pyright 0 error, ruff 0 error, pytest 全绿 (pre-existing fail 不算)
✅ Task 4 端到端 manual smoke test 跑通,entities 非空

## 不在范围

❌ Dockerfile 加 spacy 模型下载 (生产部署是另一回事)
❌ ontology 同义词合并 (2026-07-02 motor-ontology spec M4)
❌ mem0ai[nlp] 跟 spaCy 依赖冲突排查 (已知 spaCy 已作为 mem0ai 间接依赖)
❌ 重写 SpacyRuleExtractor 用 spaCy Matcher API (当前 doc.ents 已经够用,优化留后续)

---

## Self-Review (作者自查)

### Spec 覆盖率

原 spec ([2026-07-01-markdown-extract-kg-design.md](docs/superpowers/specs/2026-07-01-markdown-extract-kg-design.md)) 提到的 spacy_rule 接入要求:
- "extractor_id 白名单 spacy_rule / llm_pydantic" → 已有 (不改)
- "spaCy Matcher + EntityRuler" → 已有 (不改)
- "`X 是 Y 的` 模式" → 已有 (不改)
- 端到端可调用 → **Task 2 + Task 4 覆盖**

### Placeholder 扫描

- 无 "TBD" / "TODO" / "implement later"
- 无 "add appropriate error handling"
- 所有代码步骤含完整代码块
- 所有命令含具体 expected output

### 类型一致性

- `SpacyRuleExtractor.__init__(nlp=None)` 签名 Task 2 / Task 3 引用一致 (不破坏现有 3 个 mock test)
- `monkeypatch.setattr("spacy.load", ...)` Task 2 / Task 3 一致
- `HTTPException(status_code=503, ...)` Task 2 / Task 3 一致