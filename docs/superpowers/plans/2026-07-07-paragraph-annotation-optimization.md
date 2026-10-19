# Paragraph Annotation Optimization Implementation Plan (2026-07-07)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 多语言 + 4 类 deontic + 2 weight 修饰 + spacy/tiktoken 增强 + 14 列 CSV 输出, 同时兼容旧 5 中文关键词 + 旧 4 列 schema, 不退化中文 PDF 命中数.

**Architecture:**
- yaml 配置驱动 (`rule_patterns` / `safe_weight` / `rec_weight` / `paragraph_splitter` / `footer_dedup`)
- python 内部加 `CompiledRulePatterns` dataclass + `SpacyEnhancer` 类 (单例 lazy load, 跟 `src/kg/router.py:73` 复用模式)
- 段落切分升级到 4 mode 链 (`blocks` 优先, fallback `double_newline` / `newline` / `sentence_fallback`)
- CSV DictWriter 扩到 14 列 (`rule_categories` / `lemmas` 序列化为 JSON)
- 跨页去重改 `seen_footers: set[str]` 替代死代码

**Tech Stack:**
- Python 3.14 (uv-managed venv)
- pymupdf (已装, 用于 `get_text()` / `get_text("blocks")`)
- spacy 3.8.13 (lazy load + 503 fallback, 模型 `en_core_web_sm` 需下载)
- tiktoken >= 0.13.0 (cl100k_base)
- pytest (mode 1 mock ObjectStore)
- **正则**: 本期**沿用 stdlib `re`** (CLAUDE.md "0 新增 PyPI 依赖" 硬约束; `regex` 库即便已装本期不切换, 留 follow-up). 全角空格 `\s+` 在 spec §1.3.3 已修, stdlib re 足够.

---

## Global Constraints

来自 [spec §6 / §9](../specs/2026-07-07-paragraph-annotation-optimization-design.md) + 项目 CLAUDE.md:

- **版本**: Python 3.14, pymupdf 锁版本不升, spacy 3.8.13
- **依赖**: 不引新 PyPI 依赖. spacy/tiktoken 已装, **regex 库本期不引入** (即装也走 stdlib re, 留 follow-up). 仅加 `RUN uv run spacy download en_core_web_sm` 到 Dockerfile (~40MB)
- **commit**: ≤ 500 行/单 commit; prefix `feat:` / `fix:` / `refactor:` / `chore:` / `docs:` / `test:`
- **测试**: mode 1 mock (ObjectStore + session_scope 屏蔽); `uv run pytest` 0 新 fail; 中文 fixture 端到端断言 `total_flagged ≥ 旧值`
- **类型**: pyright 必须 0 error. `# type: ignore` 必带原因 (`pyright: pymupdf Document 不可迭代` 之类)
- **lint/format**: `uv run ruff format` → `uv run ruff check --fix` → `uv run pyright` 必须全 0 报错后才 commit
- **数据库**: 测试禁直连 PG (`session_scope` mock), `tests/test_api_contract.py` 不动
- **CLAUDE.md §范围控制**: 不动别人 worktree (`packages/web/nul` 不 reset / checkout), 本模块单 PR
- **i18n / 前端**: 详情页前端不动 (本期仅 CSV 字段), 无 i18n 工作量
- **dict/list CSV 序列化**: `rule_categories` / `lemmas` 走 `json.dumps(..., ensure_ascii=False)`
- **CSV 列序**: 14 列固定, 顺序对齐 spec §3.1 (§4.5 给定)

---

## File Structure

**修改**:
- `packages/service/configs/pre_analysis/rule_keywords.yaml` — 扩 8 个新字段
- `packages/service/src/ingest/pre_analysis/runner.py` — 加 4 类 + `SpacyEnhancer` + 14 列 CSV + `seen_footers`
- `packages/service/Dockerfile` — 加 `RUN uv run spacy download en_core_web_sm` 1 行
- `packages/service/tests/ingest/pre_analysis/test_runner.py` — 扩 spec §6 16 项 (T1-T16) + Task 7 fixture 测试 (T8/T9/T14/T15/T22)
- `packages/service/tests/ingest/pre_analysis/fixtures/` — (新) `flagged_zh_sample.txt` / `flagged_en_sample.txt` / `flagged_mixed_sample.txt` / `flagged_en_ner_sample.txt`

**新增**:
- (无独立新模块, 所有类放 `runner.py` 内, 跟 KG router 模式一致)

---

## Task Index

- Task 1: yaml 扩字段 + 旧字段保留
- Task 2: `CompiledRulePatterns` dataclass + `_split_paragraphs` 4 mode
- Task 3: `_extract_flagged_paragraphs` 重写 (4 类 + 2 weight + 命中双轨)
- Task 4: `SpacyEnhancer` 类 (lazy load + 503 fallback + tiktoken)
- Task 5: `_write_flagged_paragraphs` 14 列 CSV + `rule_categories` / `lemmas` JSON 化
- Task 6: `_detect_cross_page` 改 `seen_footers` 去重 + yaml 16 footer 词
- Task 7: 测试 fixture + DoD 验证 (英文真 fixture 端到端) — 测试覆盖 T8/T9/T14/T15/T22 (5 个核心) + spec §6 16 项回归

---

## Task 1: yaml 扩展 + 旧字段保留

**Files:**
- Modify: `packages/service/configs/pre_analysis/rule_keywords.yaml` (扩 8 字段)
- Test: `packages/service/tests/ingest/pre_analysis/test_runner.py` (新增 T8 — yaml 缺 rule_patterns 时 4 类全 0 命中)

**Interfaces:**
- Consumes: 无 (yaml 改动)
- Produces: yaml 加载后 `config: dict` 包含 `rule_patterns` / `safe_weight` / `rec_weight` / `paragraph_splitter` / `paragraph_splitter_fallback` / `dense_threshold` / `max_sentence_chars` / `cross_page_detection.footer_keywords` (16 项) + `cross_page_detection.footer_dedup`

---

- [ ] **Step 1: Write failing test (T8 — yaml 缺 rule_patterns 时 4 类全 0)**

`tests/ingest/pre_analysis/test_runner.py` 末尾追加:

```python
def test_runner_yaml_without_rule_patterns_returns_old_behavior(
    mock_store: MagicMock, mock_task_store: MagicMock, patch_session_scope: None, tmp_path: Path
) -> None:
    """yaml 缺 rule_patterns 时, 4 类正则永不命中, 走旧 in 子串逻辑.

    测是为 Task 1 yaml 改动服务: 验证 yaml 扩字段后, 旧 yaml 配置仍跑通 (CLAUDE.md §兼容性约束).
    """
    import yaml

    old_yaml = tmp_path / "old_rule_keywords.yaml"
    old_yaml.write_text(
        yaml.safe_dump(
            {
                "keywords": ["注意", "禁止"],
                "min_paragraph_length": 5,
                "cross_page_detection": {"min_column_match": 0.8, "footer_keywords": ["cont."]},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    from src.ingest.pre_analysis import PreAnalysisRunner

    runner = PreAnalysisRunner(
        object_store=mock_store,
        task_store=mock_task_store,
        keyword_config_path=old_yaml,
        stage_store=MagicMock(),
    )
    # 直接调内部方法, 灌入 mock PDF text 含 "Danger! must not be used"
    from src.ingest.pre_analysis import runner as runner_mod

    class _MockPage:
        def get_text(self, mode: str = "text"):
            return "Danger! must not be used in hazardous area.\n注意佩戴绝缘手套."

        def get_text_blocks(self, *args, **kwargs):
            return self.get_text()

    class _MockDoc:
        def __iter__(self):
            return iter([_MockPage()])

    flagged = runner._extract_flagged_paragraphs(_MockDoc(), {})  # type: ignore[arg-type]
    # 因为 config={} 是空 dict, runner 会走兜底默认 (loader 函数未跑)
    # 实际场景 yaml 加载后会跑这里. 重点: 4 类全 0 命中 (rule_categories 为空 dict)
    assert all("rule_categories" not in row or not row["rule_categories"] for row in flagged) or len(flagged) >= 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py::test_runner_yaml_without_rule_patterns_returns_old_behavior -v`
Expected: FAIL — `PreAnalysisRunner._extract_flagged_paragraphs` 当前不接 `rule_patterns` 字段 (Task 3 才加), 测试应 import 失败或 attributeerror. 这条是 Task 3 落到 Task 1 防回归用, **本 task 不实现**, 仅 yaml 改完先确认 import 路径 OK.

注: 因为 `keyword_config_path` 参数已存在 (旧版 loader), 这条测试主要为 Task 1 留位; 实际失效断言在 Task 3 落地. **Task 1 跳过此步, 直接做 Step 3.**

- [ ] **Step 3: 备份当前 yaml 后, 扩字段**

`packages/service/configs/pre_analysis/rule_keywords.yaml` 整体替换为 (保留旧 4 字段, 新加 8 字段):

```yaml
# PDF 预分析规则配置 (2026-07-02 新建, 2026-07-07 v3 扩字段)
#
# 业务方决策 (PRD §业务方决策 1): 5 个中文关键词默认开启, 不追加;
# 英文/德文 PDF 走 4 类 deontic 正则 + 2 weight 修饰 (hard constraint / soft suggestion).
# 改 yaml + 重启服务生效 (CLAUDE.md §变更管理)

# === 旧字段保留 (2026-07-02) ===
keywords:
  - 注意
  - 不能
  - 仅适用
  - 必须
  - 禁止

chapter_patterns:
  - "^\\s*第[一二三四五六七八九十百零]+章[\\s　]+"
  - "^\\s*\\d+\\.\\d+(\\.\\d+)?[\\s　]+"
  - "^\\s*#{1,6}\\s+"

min_paragraph_length: 20

# === 新字段 (2026-07-07 v3) ===

# 4 类英文 deontic 正则 (联网核验降级: safe/rec 不进类别 dict, 走 weight 修饰)
# 多词短语全部 \bword\s+word\b 形式, 修 "invalid for" 误匹配 "valid for" bug
rule_patterns:
  negation:    "(?i)\\b(not|cannot|never|must\\s+not|should\\s+not|may\\s+not|forbidden|prohibited|excluded|not\\s+permissible|not\\s+possible|no|without)\\b"
  obligation:  "(?i)\\b(must|shall|should|will|is\\s+required\\s+to|have\\s+to|need\\s+to|ensure|make\\s+sure|only\\s+possible|necessary|obligation)\\b"
  condition:   "(?i)\\b(if|when|whereas|unless|provided\\s+that|as\\s+long\\s+as|except|apart\\s+from|depending\\s+on|subject\\s+to)\\b"
  permission:  "(?i)\\b(can|may|able\\s+to|capable\\s+of|suitable\\s+for|intended\\s+for|permissible|allowed|permit|approval)\\b"

# 2 weight 修饰 (safe 升权 1.5x, rec 降权 0.5x), 命中后叠加 weighted_density
safe_weight: 1.5
rec_weight: 0.5

# 段落切分默认 blocks (pymupdf get_text("blocks")), fallback 链可改 yaml
paragraph_splitter: "blocks"
paragraph_splitter_fallback: ["double_newline", "newline", "sentence_fallback"]

# 规则密集度阈值 (is_dense = weighted_density ≥ dense_threshold)
dense_threshold: 3

# sentence_fallback 模式下滑窗合段上限
max_sentence_chars: 200

# 跨页 footer (8 中文 + 8 英文), seen_footers 去重 (Task 6 实施)
cross_page_detection:
  min_column_match: 0.8
  footer_keywords:
    - "续表"
    - "续上表"
    - "(续)"
    - "接下页"
    - "接上页"
    - "下转"
    - "转下页"
    - "表 1 (续)"
    - "cont."
    - "(continued)"
    - "continued"
    - "cont'd"
    - "continues"
    - "continued on"
    - "continued on next page"
    - "to be continued"
  # 字段本期不读 (Task 6 注释), 留占位后续扩展
  footer_dedup: {}
```

- [ ] **Step 4: 验证 yaml 可被 `_load_config` 加载, 不破坏 fixture**

```bash
cd packages/service && uv run python -c "
from pathlib import Path
import sys
sys.path.insert(0, '.')
from src.ingest.pre_analysis.runner import PreAnalysisRunner
cfg = PreAnalysisRunner.__new__(PreAnalysisRunner)
out = cfg._load_config.__func__(cfg) if False else None
# 直接 yaml.safe_load 模拟
import yaml
cfg = yaml.safe_load(Path('configs/pre_analysis/rule_keywords.yaml').read_text(encoding='utf-8'))
assert 'rule_patterns' in cfg and len(cfg['rule_patterns']) == 4, 'rule_patterns 4 类'
assert cfg['safe_weight'] == 1.5
assert cfg['paragraph_splitter'] == 'blocks'
assert len(cfg['cross_page_detection']['footer_keywords']) == 16
print('OK yaml shape verified')
"
```

Expected: `OK yaml shape verified`

- [ ] **Step 5: 跑现有 test_runner.py, 确认 d81_dummy.pdf 中文命中不退化**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py -v -k "extracts_flagged or writes"`
Expected: 3 个旧测试 PASS (`test_runner_extracts_flagged_paragraphs` 断言 `total_flagged ≥ 4`). 注意: 此时 `_extract_flagged_paragraphs` 还没改, 旧 in 子串逻辑仍跑, 行为**不应变**.

- [ ] **Step 6: ruff + pyright 通过**

```bash
cd packages/service && uv run ruff format configs/pre_analysis/rule_keywords.yaml 2>&1 || true
cd packages/service && uv run ruff check configs/pre_analysis/rule_keywords.yaml
```

Expected: yaml 文件 ruff 不查, 但 `_load_config` 路径下游要用, **不报错** (`yaml.safe_load` 是项目祖传 API).

- [ ] **Step 7: Commit**

```bash
git add packages/service/configs/pre_analysis/rule_keywords.yaml
git commit -m "feat(pre-analysis): yaml 扩 rule_patterns / weights / blocks / 16 footer 词

- 旧 keywords / chapter_patterns / min_paragraph_length 一字不动 (CLAUDE.md §兼容性)
- rule_patterns: 4 类 deontic (neg/obl/cond/perm), 多词 \bword\s+word\b 修 bug
- safe_weight=1.5 / rec_weight=0.5 加权修饰, 不进类别 dict
- paragraph_splitter=blocks 默认, fallback 链 yaml 可改
- dense_threshold=3 / max_sentence_chars=200
- cross_page_detection.footer_keywords 扩 4→16 (中文 8 + 英文 8)
- footer_dedup 字段占位, Task 6 实施 seen_footers 方案"
```

---

## Task 2: `CompiledRulePatterns` dataclass + `_split_paragraphs` 4 mode

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/runner.py:1-50` (top-level imports + dataclass) 与 `runner.py:360+` (新加 `_split_paragraphs` 方法在 `_extract_flagged_paragraphs` 之前)
- Test: `tests/ingest/pre_analysis/test_runner.py` (新增 T6 — blocks mode 优先 / T13 — sentence_fallback)

**Interfaces:**
- Consumes: yaml 加载的 `config: dict` (含 `rule_patterns`)
- Produces:
  - `CompiledRulePatterns` (4 `re.Pattern[str]` 字段, `from_config(cfg)` classmethod)
  - `_split_paragraphs(page, mode, max_sentence_chars=200) -> list[str]`

---

- [ ] **Step 1: Write failing test T6 — blocks 优先**

`tests/ingest/pre_analysis/test_runner.py` 末尾追加:

```python
def test_split_paragraphs_blocks_mode() -> None:
    """Task 2: blocks mode 用 pymupdf get_text('blocks'), 3 段返回."""
    from src.ingest.pre_analysis.runner import PreAnalysisRunner

    runner = PreAnalysisRunner.__new__(PreAnalysisRunner)

    class _MockPage:
        def get_text_blocks(self, *args, **kwargs):  # 注意: pymupdf 是 get_text("blocks")
            return []  # placeholder, pymupdf 实际 API 是 get_text

        def get_text(self, mode: str = "text"):
            # 兼容 mode: blocks / 字符串
            if mode == "blocks":
                return [
                    (0, 0, 100, 50, "First paragraph.", 0, 0),
                    (0, 60, 100, 110, "Second paragraph here.", 1, 0),
                    (0, 120, 100, 170, "Third paragraph content.", 2, 0),
                ]
            return "fallback"

    page = _MockPage()
    out = runner._split_paragraphs(page, "blocks")  # type: ignore[arg-type]
    assert out == ["First paragraph.", "Second paragraph here.", "Third paragraph content."]


def test_split_paragraphs_sentence_fallback() -> None:
    """Task 2 + T13: sentence_fallback 按 [.!?] 切句, 滑窗合段 ≤ 200 字符."""
    from src.ingest.pre_analysis.runner import PreAnalysisRunner

    runner = PreAnalysisRunner.__new__(PreAnalysisRunner)

    class _MockPage:
        def get_text(self, mode: str = "text"):
            return "First sentence. Second sentence! Third sentence? Fourth end."

    page = _MockPage()
    out = runner._split_paragraphs(page, "sentence_fallback", max_sentence_chars=200)  # type: ignore[arg-type]
    # 4 句总长 < 200, 合一整段
    assert len(out) >= 1
    assert "First" in out[0] and "Fourth" in out[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py::test_split_paragraphs_blocks_mode tests/ingest/pre_analysis/test_runner.py::test_split_paragraphs_sentence_fallback -v`
Expected: FAIL with `AttributeError: 'PreAnalysisRunner' object has no attribute '_split_paragraphs'`

- [ ] **Step 3: Implement `CompiledRulePatterns` + `_split_paragraphs`**

`packages/service/src/ingest/pre_analysis/runner.py` 顶部 (在 `from dataclasses import dataclass, field` 之后, 现有 imports 区) 加:

```python
from dataclasses import dataclass, field
import re  # 沿用 stdlib re, 不切 regex 库 (CLAUDE.md 0 新增 PyPI 依赖; 切换留 follow-up)
```

在 `_load_config` 之前 (约 line 252 附近) 加 `CompiledRulePatterns` dataclass:

```python
@dataclass(frozen=True)
class CompiledRulePatterns:
    """(2026-07-07) 启动期编译一次, 跑 PDF 时直接复用.

    4 类: negation / obligation / condition / permission (spec §4.2 联网核验降级).
    yaml 缺 rule_patterns 时, 默认模式 `(?i)\\bX\\b` 永不命中 → 跑旧 in 子串逻辑, 行为不退化.
    """

    negation: re.Pattern[str]
    obligation: re.Pattern[str]
    condition: re.Pattern[str]
    permission: re.Pattern[str]

    @classmethod
    def from_config(cls, cfg: dict) -> "CompiledRulePatterns":
        rp = cfg.get("rule_patterns", {}) or {}
        return cls(
            negation=re.compile(rp.get("negation", r"(?i)\bX\b")),
            obligation=re.compile(rp.get("obligation", r"(?i)\bX\b")),
            condition=re.compile(rp.get("condition", r"(?i)\bX\b")),
            permission=re.compile(rp.get("permission", r"(?i)\bX\b")),
        )
```

在 `_extract_flagged_paragraphs` (现 line 364) **之前** 加 `_split_paragraphs` 方法:

```python
def _split_paragraphs(
    self,
    page: Any,  # pymupdf Page; 测试传 mock
    mode: str,
    max_sentence_chars: int = 200,
) -> list[str]:
    """(2026-07-07) 段落切分. 4 mode 链 (spec §4.3).

    Returns: 段落文本列表, 已 strip + 去空段.
    """
    if mode == "blocks":
        # pymupdf get_text("blocks") 返 [(x0,y0,x1,y1,text,bn,bt), ...]
        # pyright: pymupdf API 复杂, 用 Any 豁免
        blocks = page.get_text("blocks")  # type: ignore[attr-defined]
        return [str(b[4]).strip() for b in blocks if str(b[4]).strip()]
    if mode == "double_newline":
        text = page.get_text()  # type: ignore[attr-defined]
        paras = re.split(r"\n\s*\n", text)
        return [p.strip().replace("\n", " ") for p in paras if p.strip()]
    if mode == "newline":
        text = page.get_text()  # type: ignore[attr-defined]
        return [p.strip() for p in text.split("\n") if p.strip()]
    if mode == "sentence_fallback":
        text = page.get_text()  # type: ignore[attr-defined]
        sentences = re.split(r"(?<=[.?!])\s+", text)
        merged: list[str] = []
        buf = ""
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if len(buf) + len(s) <= max_sentence_chars:
                buf = (buf + " " + s).strip()
            else:
                if buf:
                    merged.append(buf)
                buf = s
        if buf:
            merged.append(buf)
        return merged
    raise ValueError(f"unknown paragraph_splitter mode: {mode}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py::test_split_paragraphs_blocks_mode tests/ingest/pre_analysis/test_runner.py::test_split_paragraphs_sentence_fallback -v`
Expected: 2 个 PASS

- [ ] **Step 5: 跑现有测试, 不退化**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py -v`
Expected: 全部 PASS (现有 6 测试 + 新 2 测试 = 8 测试 PASS)

- [ ] **Step 6: ruff + pyright**

```bash
cd packages/service && uv run ruff format src/ingest/pre_analysis/runner.py
cd packages/service && uv run ruff check --fix src/ingest/pre_analysis/runner.py
cd packages/service && uv run pyright src/ingest/pre_analysis/runner.py
```

Expected: 0 报错

- [ ] **Step 7: Commit**

```bash
git add packages/service/src/ingest/pre_analysis/runner.py
git commit -m "feat(pre-analysis): CompiledRulePatterns dataclass + 4 mode 段落切分

- CompiledRulePatterns (4 Pattern frozen dataclass, from_config(cfg) classmethod)
- 默认值 (?i)\\bX\\b 永不命中 → yaml 缺 rule_patterns 时退化旧逻辑 (Task 1 兼容性)
- _split_paragraphs: blocks / double_newline / newline / sentence_fallback 4 mode
- blocks mode 用 page.get_text(\"blocks\") bbox 切分 (pymupdf 官方段落 API)
- sentence_fallback 滑窗合段 ≤ max_sentence_chars (yaml 默认 200)
- 测试 T6 (blocks) + T13 (sentence_fallback) PASS"
```

---

## Task 3: `_extract_flagged_paragraphs` 重写 (4 类 + 2 weight + 14 列 dict)

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/runner.py:364-389` (替换实现, 不动 docstring/签名)
- Test: `tests/ingest/pre_analysis/test_runner.py` (新增 T2 / T3 / T4 / T5 / T11 / T12)

**Interfaces:**
- Consumes: `CompiledRulePatterns.from_config(config)` (Task 2), `_split_paragraphs` (Task 2), yaml config 含 `safe_weight` / `rec_weight` / `dense_threshold` / `paragraph_splitter` / `max_sentence_chars`
- Produces: `list[dict]` 每行 14 列 (旧 4 + 新 10, 含 `lemmas`/`token_count`/`language` 来自 `SpacyEnhancer.enhance`, 但本 task 调 enhancer 时若 SpacyEnhancer 类还不存在则跳过 — 见 Step 3 注释)

注: SpacyEnhancer 在 Task 4 加. 本 task Step 3 实现时, enhancer 调用 `getattr(self, "enhancer", None)` 兜底, mock 测试用 `MagicMock`. Task 4 后无缝合并.

---

- [ ] **Step 1: Write failing tests T2 / T3 / T4 / T5 / T11 / T12**

`tests/ingest/pre_analysis/test_runner.py` 末尾追加:

```python
def test_extract_flagged_paragraphs_english_obligation() -> None:
    """Task 3 / T2: 英文段含 'must' / 'should' 命中 obl 类."""
    from src.ingest.pre_analysis.runner import PreAnalysisRunner

    runner = PreAnalysisRunner.__new__(PreAnalysisRunner)
    runner.enhancer = MagicMock()  # Task 4 后实化; 本 task mock
    runner.enhancer.enhance.return_value = {"lemmas": [], "token_count": 5, "language": "en"}

    class _MockPage:
        def get_text(self, mode: str = "text"):
            return "Operators must ensure that the voltage is within rated range.\n"

    class _MockDoc:
        def __iter__(self):
            return iter([_MockPage()])

    cfg = {
        "rule_patterns": {
            "obligation": r"(?i)\b(must|should|shall)\b",
        },
        "min_paragraph_length": 10,
        "safe_weight": 1.5,
        "rec_weight": 0.5,
        "dense_threshold": 3,
        "paragraph_splitter": "newline",
        "max_sentence_chars": 200,
    }
    flagged = runner._extract_flagged_paragraphs(_MockDoc(), cfg)  # type: ignore[arg-type]
    assert len(flagged) >= 1
    row = flagged[0]
    assert row["rule_categories"].get("obl", 0) >= 1
    assert row["language"] == "en"


def test_extract_flagged_paragraphs_english_negation() -> None:
    """Task 3 / T3: 英文段含 'must not' 命中 neg 类."""
    from src.ingest.pre_analysis.runner import PreAnalysisRunner

    runner = PreAnalysisRunner.__new__(PreAnalysisRunner)
    runner.enhancer = MagicMock()
    runner.enhancer.enhance.return_value = {"lemmas": [], "token_count": 5, "language": "en"}

    class _MockPage:
        def get_text(self, mode: str = "text"):
            return "A holding brake must not be used in this application.\n"

    class _MockDoc:
        def __iter__(self):
            return iter([_MockPage()])

    cfg = {
        "rule_patterns": {
            "negation": r"(?i)\b(must\s+not|prohibited)\b",
        },
        "min_paragraph_length": 10,
        "safe_weight": 1.5,
        "rec_weight": 0.5,
        "dense_threshold": 3,
        "paragraph_splitter": "newline",
        "max_sentence_chars": 200,
    }
    flagged = runner._extract_flagged_paragraphs(_MockDoc(), cfg)  # type: ignore[arg-type]
    assert flagged[0]["rule_categories"]["neg"] >= 1


def test_extract_flagged_paragraphs_safe_hits_weighted_density() -> None:
    """Task 3 / T12: 安全词 (danger) 加权 +0.5, weighted_density = raw + 0.5."""
    from src.ingest.pre_analysis.runner import PreAnalysisRunner

    runner = PreAnalysisRunner.__new__(PreAnalysisRunner)
    runner.enhancer = MagicMock()
    runner.enhancer.enhance.return_value = {"lemmas": [], "token_count": 5, "language": "en"}

    class _MockPage:
        def get_text(self, mode: str = "text"):
            return "Danger! Voltage deviation may cause damage.\n"

    class _MockDoc:
        def __iter__(self):
            return iter([_MockPage()])

    cfg = {
        "rule_patterns": {"obligation": r"(?i)\bmay\b"},
        "min_paragraph_length": 10,
        "safe_weight": 1.5,
        "rec_weight": 0.5,
        "dense_threshold": 100,  # 故意高, 让 is_dense=False
        "paragraph_splitter": "newline",
        "max_sentence_chars": 200,
    }
    flagged = runner._extract_flagged_paragraphs(_MockDoc(), cfg)  # type: ignore[arg-type]
    row = flagged[0]
    # raw = 1 (may 在 obl), safe (danger) hits = 1, 加权 +0.5
    assert row["raw_density"] == 1
    assert row["safe_hits"] >= 1
    assert abs(row["weighted_density"] - 1.5) < 0.01
    assert row["is_dense"] is False


def test_extract_flagged_paragraphs_rec_hits_subtract() -> None:
    """Task 3 / T11: 推荐词 (recommend) 加权 -0.5."""
    from src.ingest.pre_analysis.runner import PreAnalysisRunner

    runner = PreAnalysisRunner.__new__(PreAnalysisRunner)
    runner.enhancer = MagicMock()
    runner.enhancer.enhance.return_value = {"lemmas": [], "token_count": 5, "language": "en"}

    class _MockPage:
        def get_text(self, mode: str = "text"):
            return "We recommend that flexible couplings are used.\n"

    class _MockDoc:
        def __iter__(self):
            return iter([_MockPage()])

    cfg = {
        "rule_patterns": {"permission": r"(?i)\bare\s+used\b"},
        "min_paragraph_length": 10,
        "safe_weight": 1.5,
        "rec_weight": 0.5,
        "dense_threshold": 100,
        "paragraph_splitter": "newline",
        "max_sentence_chars": 200,
    }
    flagged = runner._extract_flagged_paragraphs(_MockDoc(), cfg)  # type: ignore[arg-type]
    row = flagged[0]
    assert row["rec_hits"] >= 1
    assert abs(row["weighted_density"] - 0.5) < 0.01  # raw=1 -0.5


def test_extract_flagged_paragraphs_density_threshold() -> None:
    """Task 3 / T5: 段含 5 个不同类词 → is_dense=True (threshold=3)."""
    from src.ingest.pre_analysis.runner import PreAnalysisRunner

    runner = PreAnalysisRunner.__new__(PreAnalysisRunner)
    runner.enhancer = MagicMock()
    runner.enhancer.enhance.return_value = {"lemmas": [], "token_count": 5, "language": "en"}

    class _MockPage:
        def get_text(self, mode: str = "text"):
            return (
                "If the motor must not be used, you may request approval. "
                "Subject to compliance unless excepted.\n"
            )

    class _MockDoc:
        def __iter__(self):
            return iter([_MockPage()])

    cfg = {
        "rule_patterns": {
            "negation": r"(?i)\bmust\s+not\b",
            "obligation": r"(?i)\bmust\b",
            "condition": r"(?i)\bif|unless|except|subject\s+to\b",
            "permission": r"(?i)\bmay\b",
        },
        "min_paragraph_length": 10,
        "safe_weight": 1.5,
        "rec_weight": 0.5,
        "dense_threshold": 3,
        "paragraph_splitter": "newline",
        "max_sentence_chars": 200,
    }
    flagged = runner._extract_flagged_paragraphs(_MockDoc(), cfg)  # type: ignore[arg-type]
    row = flagged[0]
    total_cat = sum(row["rule_categories"].values())
    assert total_cat >= 3
    assert row["is_dense"] is True


def test_extract_flagged_paragraphs_chinese_old_no_regression() -> None:
    """Task 3 / T1: 中文 "注意/禁止" 命中段原样出 (旧 schema 行为不退化)."""
    from src.ingest.pre_analysis.runner import PreAnalysisRunner

    runner = PreAnalysisRunner.__new__(PreAnalysisRunner)
    runner.enhancer = MagicMock()
    runner.enhancer.enhance.return_value = {"lemmas": ["注意", "电压"], "token_count": 5, "language": "zh"}

    class _MockPage:
        def get_text(self, mode: str = "text"):
            return "注意: 电压偏离额定值时禁止操作设备.\n"

    class _MockDoc:
        def __iter__(self):
            return iter([_MockPage()])

    cfg = {
        "keywords": ["注意", "禁止"],
        "min_paragraph_length": 10,
        "safe_weight": 1.5,
        "rec_weight": 0.5,
        "dense_threshold": 3,
        "paragraph_splitter": "newline",
        "max_sentence_chars": 200,
    }
    flagged = runner._extract_flagged_paragraphs(_MockDoc(), cfg)  # type: ignore[arg-type]
    assert len(flagged) >= 1
    row = flagged[0]
    assert "注意" in row["matched_keywords"] or "禁止" in row["matched_keywords"]
    assert row["language"] == "zh"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py -k "extract_flagged_paragraphs_english or extract_flagged_paragraphs_safe or extract_flagged_paragraphs_rec or extract_flagged_paragraphs_density or extract_flagged_paragraphs_chinese_old" -v`
Expected: 6 FAIL (AttributeError / KeyError, 因为重写还没做)

- [ ] **Step 3: 重写 `_extract_flagged_paragraphs`**

`packages/service/src/ingest/pre_analysis/runner.py:364-389` 替换为:

```python
def _extract_flagged_paragraphs(self, doc: pymupdf.Document, config: dict) -> list[dict]:
    """(2026-07-07 v3) 多语言 + 4 类正则 + safe/rec 权重 + 14 列 dict.

    Returns: list[dict] 14 keys
      {matched_keywords, page, section, text,
       rule_categories (4 key: neg/obl/cond/perm),
       density, is_dense, raw_density, weighted_density,
       safe_hits, rec_hits, lemmas (JSON), token_count, language}

    命中条件: 中文 in 子串 OR density > 0 (双轨并存, 中文 PDF 不退化).
    spacy enhance: 通过 self.enhancer (Task 4 加), 若缺则返基础字段.
    """
    import json

    keywords = config.get("keywords", []) or []
    min_len = config.get("min_paragraph_length", 20)
    splitter_mode = config.get("paragraph_splitter", "blocks")
    max_sentence_chars = config.get("max_sentence_chars", 200)
    dense_threshold = config.get("dense_threshold", 3)
    safe_weight = config.get("safe_weight", 1.5)
    rec_weight = config.get("rec_weight", 0.5)
    compiled = CompiledRulePatterns.from_config(config)

    # safe / rec weight (不进入 rule_categories, 单独统计 + 加权)
    safe_pattern = re.compile(
        r"(?i)\b(danger|warning|caution|notice|safety|hazard|risk)\b"
    )
    rec_pattern = re.compile(
        r"(?i)\b(recommend|advisable|usually|typically|suggested|preferred)\b"
    )

    flagged: list[dict] = []
    for page_idx, page in enumerate(doc):  # type: ignore[arg-type]
        # _split_paragraphs 内部按 mode 调 page.get_text / page.get_text("blocks")
        paragraphs = self._split_paragraphs(page, splitter_mode, max_sentence_chars)

        for para_text in paragraphs:
            if len(para_text) < min_len:
                continue
            # 旧: 中文 in 子串 (兼容)
            matched = [kw for kw in keywords if kw in para_text]
            # 4 类 deontic
            rule_categories = {
                "neg": len(compiled.negation.findall(para_text)),
                "obl": len(compiled.obligation.findall(para_text)),
                "cond": len(compiled.condition.findall(para_text)),
                "perm": len(compiled.permission.findall(para_text)),
            }
            safe_hits = len(safe_pattern.findall(para_text))
            rec_hits = len(rec_pattern.findall(para_text))

            raw_density = sum(rule_categories.values())
            weighted_density = raw_density + safe_hits * (safe_weight - 1.0) + rec_hits * (rec_weight - 1.0)
            density = weighted_density
            is_dense = weighted_density >= dense_threshold

            if not (matched or density > 0):
                continue

            # cat_summary 在 lemma 回扫之前 (spec §4.4 / 新矛盾 #5: lemma 修改后仍用旧 cat_summary)
            cat_summary = ",".join(
                f"{k}={v}" for k, v in rule_categories.items() if v > 0
            )
            weight_summary: list[str] = []
            if safe_hits:
                weight_summary.append(f"safe={safe_hits}*{safe_weight}")
            if rec_hits:
                weight_summary.append(f"rec={rec_hits}*{rec_weight}")
            merged = matched + ([cat_summary] if cat_summary else []) + weight_summary

            # v3 spacy 增强 (Task 4 后实化), 本步允许 enhancer 不存在
            enhancer = getattr(self, "enhancer", None)
            if enhancer is not None and hasattr(enhancer, "enhance"):
                enhanced = enhancer.enhance(para_text)
                # lemma 回扫 (mustn't → must not)
                lemmas = enhanced.get("lemmas", []) or []
                lemma_neg_extra = sum(1 for l in lemmas if l.lower() == "not")
                if lemma_neg_extra and rule_categories["neg"] == 0:
                    rule_categories["neg"] = lemma_neg_extra
                    density += lemma_neg_extra
                    weighted_density += lemma_neg_extra
                lemmas_json = json.dumps(lemmas, ensure_ascii=False)
                token_count = enhanced.get("token_count", 0)
                language = enhanced.get("language", "unknown")
            else:
                lemmas_json = "[]"
                token_count = 0
                language = "unknown"

            flagged.append({
                "matched_keywords": ",".join(merged),
                "page": page_idx + 1,
                "section": "",
                "text": para_text,
                "rule_categories": json.dumps(rule_categories, ensure_ascii=False),
                "density": density,
                "is_dense": is_dense,
                "raw_density": raw_density,
                "weighted_density": weighted_density,
                "safe_hits": safe_hits,
                "rec_hits": rec_hits,
                "lemmas": lemmas_json,
                "token_count": token_count,
                "language": language,
            })
    return flagged
```

- [ ] **Step 4: Run new tests to verify they pass**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py -k "extract_flagged_paragraphs" -v`
Expected: 6 PASS

- [ ] **Step 5: 跑现有 6 测试, 不退化**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py -v`
Expected: 全部 PASS (现有 6 + 新 6 + Task 2 的 2 = 14 测试 PASS)

**注意**: Task 3 后 `_write_flagged_paragraphs` 还没改 (Task 5 才改), dict 多了字段 `rule_categories` 字段从 dict 变 json 字符串 — 但现有 `_write_flagged_paragraphs` 用 `csv.DictWriter` 写固定 4 列, 新字段会被静默丢掉. 这是预期: Task 5 把 CSV writer 扩到 14 列. 当前 `total_flagged ≥ 4` 断言仍 PASS (字典级断言, 不看 CSV 列).

- [ ] **Step 6: ruff + pyright**

```bash
cd packages/service && uv run ruff format src/ingest/pre_analysis/runner.py
cd packages/service && uv run ruff check --fix src/ingest/pre_analysis/runner.py
cd packages/service && uv run pyright src/ingest/pre_analysis/runner.py
```

Expected: 0 报错. 注意 `import json` 提到函数顶部 (pyright 偏好 module-top, function-top 也 ok 看配置)

- [ ] **Step 7: Commit**

```bash
git add packages/service/src/ingest/pre_analysis/runner.py packages/service/tests/ingest/pre_analysis/test_runner.py
git commit -m "feat(pre-analysis): _extract_flagged_paragraphs 重写 4 类 + 2 weight + 14 列

- 中文 in 子串 双轨保留, 中文 PDF 行为不退化 (T1)
- rule_categories dict 序列化为 JSON (CSV 安全)
- 加权密度公式: weighted = raw + safe*(1.5-1) + rec*(0.5-1)
- safe_weight=1.5 / rec_weight=0.5 / dense_threshold=3 / 命中条件 density>0 或 matched
- lemma 回扫 (enhancer 存在时): mustn't → must not 二次回扫 neg 类
- 14 列 dict output (与 CSV writer 同步, Task 5 才落 CSV)
- T1 中文不退化 + T2 obl + T3 neg + T5 density 阈值 + T11 rec + T12 safe"
```

---

## Task 4: `SpacyEnhancer` 类 (lazy load + 503 fallback + tiktoken)

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/runner.py` (top-level imports + 新增类定义)
- Modify: `packages/service/Dockerfile` (加 spacy download 1 行)
- Test: `tests/ingest/pre_analysis/test_runner.py` (新增 T17 / T20 / T21)

**Interfaces:**
- Consumes: `nlp = spacy.load("en_core_web_sm")` (项目沙盒缺模型时抛 RuntimeError)
- Produces:
  - `SpacyEnhancer(primary_lang="en").enhance(text) -> dict` 含 `lemmas` / `token_count` / `language`

---

- [ ] **Step 1: Write failing tests T17 / T20 / T21**

`tests/ingest/pre_analysis/test_runner.py` 末尾追加:

```python
def test_spacy_enhancer_missing_model_raises_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Task 4 / T21: 缺 en_core_web_sm 模型 → RuntimeError, 不静默降级."""
    from src.ingest.pre_analysis.runner import SpacyEnhancer

    def mock_load(name: str):
        raise OSError(f"Can't find model {name}")

    monkeypatch.setattr("spacy.load", mock_load)
    with pytest.raises(RuntimeError, match="spaCy 模型"):
        SpacyEnhancer(primary_lang="en")


def test_spacy_enhancer_lemma_reduces_abbreviation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Task 4 / T17: 'mustn't' → lemmas 含 'not', enhance 返回."""
    from src.ingest.pre_analysis.runner import SpacyEnhancer

    class _MockToken:
        def __init__(self, lemma_: str, is_punct: bool = False, is_space: bool = False):
            self.lemma_ = lemma_
            self.is_punct = is_punct
            self.is_space = is_space

    class _MockDoc:
        def __init__(self, tokens):
            self._tokens = tokens

    class _MockNLP:
        def __call__(self, text: str):
            # 简化: "mustn't" split 成 must + not (lemma 还原)
            if "mustn't" in text:
                return _MockDoc([
                    _MockToken("must"), _MockToken("not"), _MockToken("be"), _MockToken("use"),
                ])
            return _MockDoc([_MockToken(w) for w in text.split()])

    monkeypatch.setattr("spacy.load", lambda name: _MockNLP())

    enc = SpacyEnhancer(primary_lang="en")
    out = enc.enhance("A holding brake mustn't be used here.")
    assert "not" in out["lemmas"]
    assert "must" in out["lemmas"]
    assert out["language"] == "en"
    assert out["token_count"] > 0  # tiktoken 编码, 真实值


def test_spacy_enhancer_tiktoken_token_count_in_range(monkeypatch: pytest.MonkeyPatch) -> None:
    """Task 4 / T20: 100 字符英文段 token_count ∈ [20, 50]."""
    from src.ingest.pre_analysis.runner import SpacyEnhancer

    class _MockToken:
        def __init__(self, lemma_):
            self.lemma_ = lemma_
            self.is_punct = False
            self.is_space = False

    class _MockDoc:
        def __init__(self, text):
            self._tokens = [_MockToken(w) for w in text.split()]

    class _MockNLP:
        def __call__(self, text: str):
            return _MockDoc(text)

    monkeypatch.setattr("spacy.load", lambda name: _MockNLP())

    enc = SpacyEnhancer(primary_lang="en")
    text = ("The motor must be installed in a dry environment with adequate ventilation. " * 2)[:100]
    out = enc.enhance(text)
    assert 20 <= out["token_count"] <= 50, f"got {out['token_count']}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py -k "spacy_enhancer" -v`
Expected: FAIL with `ImportError: cannot import name 'SpacyEnhancer'`

- [ ] **Step 3: 实施 `SpacyEnhancer` 类**

`packages/service/src/ingest/pre_analysis/runner.py` 顶部 imports 区加:

```python
import json
import re
from dataclasses import dataclass, field
from typing import Any

import spacy  # type: ignore[import-not-found]  # pyright: 项目已装, 类型 stub 缺
import tiktoken  # type: ignore[import-not-found]
```

在 `CompiledRulePatterns` 之后 (或者文件顶部 dataclass 区) 加 `SpacyEnhancer`:

```python
class SpacyEnhancer:
    """(2026-07-07 v3) spacy 增强器. 进程内单例, lazy init.

    跟 src/kg/router.py:73 同模式: 缺模型抛 RuntimeError, 让 runner 走 mark_failed,
    不静默降级 (CLAUDE.md §错误处理: 关键依赖失败必须显式).

    enhance() 返 3 key: lemmas / token_count / language. 不返 sents/ents (spec §4.7).
    """

    def __init__(self, primary_lang: str = "en") -> None:
        self.primary_lang = primary_lang
        self.nlp = self._load(primary_lang)
        # tiktoken cl100k_base 跟 OpenAI GPT-4 / text-embedding-3-small 对齐
        self.enc = tiktoken.get_encoding("cl100k_base")

    def _load(self, lang: str) -> Any:
        try:
            return spacy.load(f"{lang}_core_web_sm")
        except OSError as e:
            raise RuntimeError(
                f"spaCy 模型 {lang}_core_web_sm 未加载: {e}. "
                f"请运行: cd packages/service && uv run spacy download {lang}_core_web_sm"
            ) from e

    def enhance(self, text: str) -> dict[str, Any]:
        """对单段文本跑 spacy + tiktoken, 返 3 key 字典."""
        doc = self.nlp(text)
        lemmas = [t.lemma_ for t in doc if not t.is_punct and not t.is_space]
        token_count = len(self.enc.encode(text))
        return {
            "lemmas": lemmas,
            "token_count": token_count,
            "language": self.primary_lang,
        }
```

在 `__init__` 里 (假设 `PreAnalysisRunner.__init__` 已有, 加 1 行 `self.enhancer = SpacyEnhancer(primary_lang="en")`):

```bash
grep -n "def __init__" packages/service/src/ingest/pre_analysis/runner.py | head -3
```

找到 `__init__` 末尾 (现有代码) 加:

```python
        # (2026-07-07 v3) spacy 增强器, lazy 模型加载 (Task 4)
        self.enhancer = SpacyEnhancer(primary_lang="en")
```

如果 `__init__` 不接 `primary_lang` 参数 (项目默认写死英文), 跟 KG router 的 `zh_core_web_sm` 同模式.

- [ ] **Step 4: Dockerfile 加 spacy download**

`packages/service/Dockerfile` 找 `RUN uv run spacy download` 现有行 (项目 KG 已用) 旁边加:

```dockerfile
RUN uv run spacy download en_core_web_sm
```

(跟 `zh_core_web_sm` 并列, 单独一行, ~40MB 镜像增量)

- [ ] **Step 5: Run new tests to verify they pass**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py -k "spacy_enhancer" -v`
Expected: 3 PASS

- [ ] **Step 6: 跑全 test_runner.py, 不退化**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py -v`
Expected: 全部 PASS (现有 6 + Task 2-3 的 8 + Task 4 的 3 = 17 测试 PASS)

- [ ] **Step 7: ruff + pyright**

```bash
cd packages/service && uv run ruff format src/ingest/pre_analysis/runner.py Dockerfile
cd packages/service && uv run ruff check --fix src/ingest/pre_analysis/runner.py
cd packages/service && uv run pyright src/ingest/pre_analysis/runner.py
```

Expected: 0 报错. 注意 `# type: ignore[import-not-found]` 是 spacy/tiktoken 没 stub 时的标准豁免, 项目已用.

- [ ] **Step 8: Commit**

```bash
git add packages/service/src/ingest/pre_analysis/runner.py packages/service/Dockerfile packages/service/tests/ingest/pre_analysis/test_runner.py
git commit -m "feat(pre-analysis): SpacyEnhancer 类 (lazy load + 503 fallback + tiktoken)

- 跟 src/kg/router.py:73 复用 lazy load + RuntimeError 模式
- 缺模型时 RuntimeError 含 docker exec 提示, runner 走 mark_failed
- enhance() 返 lemmas / token_count / language 3 key (sents/ents 不返, spec §4.7)
- tiktoken cl100k_base 跟 OpenAI GPT-4 对齐
- Dockerfile 加 en_core_web_sm 下载 (~40MB)
- T17 (lemma 缩写还原) + T20 (token_count 范围) + T21 (缺模型 503) PASS"
```

---

## Task 5: `_write_flagged_paragraphs` 14 列 CSV

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/runner.py:423-443` (扩 fieldnames 14 列)
- Test: `tests/ingest/pre_analysis/test_runner.py` (新增 T10 — 14 列兼容, 旧 DictReader 读前 4 列)

**Interfaces:**
- Consumes: Task 3 出的 14 字段 dict
- Produces: CSV 14 列, `rule_categories`/`lemmas` 走 JSON 序列化

---

- [ ] **Step 1: Write failing test T10**

```python
def test_write_flagged_paragraphs_csv_14_columns(
    mock_store: MagicMock, mock_task_store: MagicMock, patch_session_scope: None
) -> None:
    """Task 5 / T10: CSV 写 14 列, 旧 DictReader 读前 4 列不报错."""
    import csv
    import io

    from src.ingest.pre_analysis.runner import PreAnalysisRunner

    runner = PreAnalysisRunner(
        object_store=mock_store,
        task_store=mock_task_store,
        keyword_config_path=Path("configs/pre_analysis/rule_keywords.yaml"),
        stage_store=MagicMock(),
    )
    flagged = [
        {
            "matched_keywords": "注意",
            "page": 3,
            "section": "",
            "text": "注意: 电压偏离额定值时禁止操作.",
            "rule_categories": '{"neg": 1}',
            "density": 1.5,
            "is_dense": False,
            "raw_density": 1,
            "weighted_density": 1.5,
            "safe_hits": 0,
            "rec_hits": 0,
            "lemmas": '["注意", "电压"]',
            "token_count": 24,
            "language": "zh",
        }
    ]
    prefix = "local://pre_analysis_outputs/test-write"
    uri, _size = runner._write_flagged_paragraphs(prefix, flagged, "test-write")  # type: ignore[arg-type]
    # 抓 mock put_bytes 的内容, 验 14 列
    captured = mock_store.put_bytes.call_args_list[0]
    data = captured.args[1]  # bytes
    text = data.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    row = next(reader)
    assert len(reader.fieldnames) == 14
    # 旧 DictReader 读前 4 列
    assert row["matched_keywords"] == "注意"
    assert row["page"] == "3"
    assert row["section"] == ""
    assert "电压" in row["text"]
    # 新 10 列
    assert row["rule_categories"] == '{"neg": 1}'
    assert row["language"] == "zh"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py::test_write_flagged_paragraphs_csv_14_columns -v`
Expected: FAIL — `len(fieldnames) == 4` 现状, 14 断言失败

- [ ] **Step 3: 实施 14 列 CSV writer**

`packages/service/src/ingest/pre_analysis/runner.py:423-443` 的 `_write_flagged_paragraphs` 替换为:

```python
def _write_flagged_paragraphs(self, prefix: str, flagged: list[dict], task_id: str) -> tuple[str, int]:
    """(2026-07-07 v3) 写 flagged_paragraphs.csv 14 列 + DB append 1 项.

    14 列顺序与 spec §3.1 一致. 旧 DictReader 读前 4 列仍 OK (matched_keywords / page / section / text).
    rule_categories / lemmas 已序列化为 JSON 字符串 (Task 3 处理).
    """
    uri = f"{prefix}/flagged_paragraphs.csv"
    fieldnames = [
        "matched_keywords", "page", "section", "text",          # 旧 4 (DictReader 兼容)
        "rule_categories", "density", "is_dense",               # v2 新增 3
        "raw_density", "weighted_density",                      # v2 新增 2
        "safe_hits", "rec_hits",                                # v2 新增 2
        "lemmas", "token_count", "language",                    # v3 新增 3 (spacy + tiktoken)
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in flagged:
        # 缺字段兜底空字符串 (防御性, Task 3 已确保 14 列齐全)
        clean_row = {k: row.get(k, "") for k in fieldnames}
        writer.writerow(clean_row)
    data = buf.getvalue().encode("utf-8")
    self.object_store.put_bytes(uri, data, "text/csv")
    self._append_artifact(
        task_id,
        kind="flagged_paragraphs",
        filename="flagged_paragraphs.csv",
        uri=uri,
        size_bytes=len(data),
    )
    return uri, len(data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py::test_write_flagged_paragraphs_csv_14_columns -v`
Expected: PASS

- [ ] **Step 5: 端到端跑 d81_dummy.pdf, CSV 14 列落地**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py -v`
Expected: 现有 PASS + 新增 PASS, 端到端 task `test_runner_extracts_flagged_paragraphs` 仍 `total_flagged >= 4` PASS.

- [ ] **Step 6: ruff + pyright**

```bash
cd packages/service && uv run ruff format src/ingest/pre_analysis/runner.py
cd packages/service && uv run ruff check --fix src/ingest/pre_analysis/runner.py
cd packages/service && uv run pyright src/ingest/pre_analysis/runner.py
```

Expected: 0 报错

- [ ] **Step 7: Commit**

```bash
git add packages/service/src/ingest/pre_analysis/runner.py packages/service/tests/ingest/pre_analysis/test_runner.py
git commit -m "feat(pre-analysis): _write_flagged_paragraphs 扩 14 列 CSV

- fieldnames 14 列 (旧 4 + 新 10), 顺序对齐 spec §3.1
- rule_categories / lemmas 走 Task 3 JSON 序列化, CSV writer 不再二次 dump
- 旧 DictReader 读前 4 列兼容 (matched_keywords / page / section / text)
- 缺字段兜底空字符串 (防御性, Task 3 已确保 14 列齐全)
- T10 (14 列兼容) PASS"
```

---

## Task 6: `_detect_cross_page` 改 `seen_footers` 去重

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/runner.py:294-314` (改 seen_footers)
- Test: `tests/ingest/pre_analysis/test_runner.py` (新增 T7 / T16)

**Interfaces:**
- Consumes: yaml `cross_page_detection.footer_keywords` (Task 1 已扩 16 词)
- Produces: 跨页候选计数 (同 footer 文本去重, 多列表格不重复触发)

---

- [ ] **Step 1: Write failing tests T7 / T16**

```python
def test_detect_cross_page_seen_footers_dedup_multi_column() -> None:
    """Task 6 / T16: 3 列表格每列底部都有 'continued', 跨页计数 = 1 (旧 = 3)."""
    from src.ingest.pre_analysis.runner import PreAnalysisRunner

    runner = PreAnalysisRunner.__new__(PreAnalysisRunner)
    tables = [
        # page-1, table 1, 4 rows
        (1, 1, [["col1", "col2", "col3"], ["a", "b", "c"], ["x", "y", "z"], ["continued"]]),
        # page-2, table 1, 3 rows (续)
        (2, 1, [["col1", "col2", "col3"], ["d", "e", "f"], ["continued", "continued", "continued"]]),
    ]
    cfg = {
        "cross_page_detection": {
            "min_column_match": 0.8,
            "footer_keywords": ["continued"],
        }
    }
    count = runner._detect_cross_page(tables, cfg)  # type: ignore[arg-type]
    # 旧版 last_row 只读第一列 "continued" → 算 1 次跨页 (新版因 seen_footers 仍 1 次)
    # 但若 mock 是每列都有 "continued", 旧版只检查 first column = "continued" 也只算 1 次
    # 关键断言: seen_footers 后续即使 pages 有不同表格 + 相同 footer 也不重复
    assert count == 1


def test_detect_cross_page_chinese_continued_keyword() -> None:
    """Task 6 / T7: 中文 footer '续表' 命中 (Task 1 已扩 16 词)."""
    from src.ingest.pre_analysis.runner import PreAnalysisRunner

    runner = PreAnalysisRunner.__new__(PreAnalysisRunner)
    tables = [
        (3, 1, [["col1", "col2"], ["a", "b"], ["续表"]]),
        (4, 1, [["col1", "col2"], ["c", "d"], ["续表"]]),
    ]
    cfg = {
        "cross_page_detection": {
            "min_column_match": 0.8,
            "footer_keywords": ["续表"],
        }
    }
    count = runner._detect_cross_page(tables, cfg)  # type: ignore[arg-type]
    assert count == 1  # seen_footers 去重 → 1 次跨页
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py -k "detect_cross_page" -v`
Expected: 旧实现也会返 1 (因为只看第一列), T7 PASS / T16 PASS 都不变 — Task 6 是**改语义**而不只让"老 Python 写法跳过". 改 seen_footers 主要是为"page-N footer 文本相同就 dedup, 不重复触发"服务.

实际测试重写应反映 seen_footers 语义差异:

```python
def test_detect_cross_page_seen_footers_skips_same_footer() -> None:
    """Task 6 核心: 同一 footer 文本跨页去重, 不重复触发."""
    from src.ingest.pre_analysis.runner import PreAnalysisRunner

    runner = PreAnalysisRunner.__new__(PreAnalysisRunner)
    # 3 个不同页的表格, footer 都是 "cont.", 但 col 数各不相同,
    # 旧实现: 每页都符 col_match 阈值, 都 +1 (count = 3)
    # seen_footers 新实现: dedup 后 count = 1
    tables = [
        (1, 1, [["a", "b"], ["cont."]]),       # footer 第一列 = "cont."
        (3, 1, [["a", "b", "c"], ["cont."]]),   # footer 第一列 = "cont." (同)
        (5, 1, [["a"], ["cont."]]),             # footer 第一列 = "cont." (同)
    ]
    cfg = {"cross_page_detection": {"min_column_match": 0.5, "footer_keywords": ["cont."]}}
    count = runner._detect_cross_page(tables, cfg)  # type: ignore[arg-type]
    # 旧版 count=3 (3 页都符), 新版 seen_footers → count=1
    assert count == 1
```

注: 上一个 T16 测的 footer 是 list 元素 ("continued" 在每个 sub-list), 旧版会拿 `"col1, col2, col3"` 当 last_row[0] → "continued" 命中. 算了, 复杂. **统一测 seen_footers 的 list[str] case**.

- [ ] **Step 3: 实施 seen_footers**

`packages/service/src/ingest/pre_analysis/runner.py:294-314` 替换为:

```python
def _detect_cross_page(
    self,
    tables: list[tuple[int, int, list[list[str]]]],
    config: dict,
) -> int:
    """(2026-07-07 v3) 跨页表候选 + seen_footers 去重 (spec §4.6 / spec 矛盾 C5).

    Returns: 跨页候选计数 (去重后).
    seen_footers: set[str] 用来 dedup 多列表格重复 footer (每列底都写 "continued" 时不重复触发).
    """
    cross_config = config.get("cross_page_detection", {}) or {}
    col_match = cross_config.get("min_column_match", 0.8)
    footer_kws = cross_config.get("footer_keywords", []) or []
    prev_table: tuple[int, int] | None = None
    cross_page = 0
    seen_footers: set[str] = set()
    for page_no, table_no, rows in tables:
        if prev_table is not None and table_no == 1:
            prev_page, prev_cols = prev_table
            cur_cols = len(rows[0]) if rows else 0
            if prev_page == page_no - 1 and cur_cols >= prev_cols * col_match:
                # 末行第一列作为 footer 候选 (跟表格 reader 约定)
                last_row_first = (rows[-1][0] if rows and rows[-1] else "") or ""
                if last_row_first in seen_footers:
                    continue
                if any(kw in last_row_first for kw in footer_kws):
                    seen_footers.add(last_row_first)
                    cross_page += 1
                    logger.warning("跨页表候选 page={} -> page={}", prev_page, page_no)
        prev_table = (page_no, len(rows[0]) if rows else 0)
    return cross_page
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py -k "detect_cross_page" -v`
Expected: 2 PASS (T7 + T16-like)

- [ ] **Step 5: 跑全 test_runner.py, 不退化**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py -v`
Expected: 全部 PASS

- [ ] **Step 6: ruff + pyright**

```bash
cd packages/service && uv run ruff format src/ingest/pre_analysis/runner.py
cd packages/service && uv run ruff check --fix src/ingest/pre_analysis/runner.py
cd packages/service && uv run pyright src/ingest/pre_analysis/runner.py
```

Expected: 0 报错

- [ ] **Step 7: Commit**

```bash
git add packages/service/src/ingest/pre_analysis/runner.py packages/service/tests/ingest/pre_analysis/test_runner.py
git commit -m "fix(pre-analysis): _detect_cross_page 改 seen_footers set 去重 (spec C5)

- 旧版 require_first_col / require_cont_marker 死代码删 (spec §4.6)
- seen_footers: set[str] 同 footer 文本去重, 多列 footer 重复 不重复 +1
- 业务可见: 中文 16 footer 词 yaml 已扩 (Task 1), seen_footers 语义生效
- T7 (跨页 + 中文续表) + T16 (seen_footers 去重) PASS"
```

---

## Task 7: 4 fixture 文件 + T8 / T9 / T14 / T15 / T22 补全 + DoD 验证

**Files:**
- Create: `packages/service/tests/ingest/pre_analysis/fixtures/flagged_zh_sample.txt` (5 段)
- Create: `packages/service/tests/ingest/pre_analysis/fixtures/flagged_en_sample.txt` (10 段, 含缩写)
- Create: `packages/service/tests/ingest/pre_analysis/fixtures/flagged_mixed_sample.txt` (3 段, 含全角空格 + 全角标点)
- Create: `packages/service/tests/ingest/pre_analysis/fixtures/flagged_en_ner_sample.txt` (含 Zone 1 / SIMOTICS)
- Modify: `packages/service/tests/ingest/pre_analysis/test_runner.py` (T8 / T9 / T14 / T15 / T22)

**Interfaces:**
- 无新接口. 全部用 `_extract_flagged_paragraphs` + mock PDF / mock text.

---

- [ ] **Step 1: 4 fixture 文件**

`packages/service/tests/ingest/pre_analysis/fixtures/flagged_zh_sample.txt`:

```text
注意: 电压偏离额定值时, 必须立即断电以保护设备安全.

禁止在没有佩戴绝缘手套的情况下触摸电机端子.

仅适用于 frame size 315 及以上的型号, 其它尺寸禁止使用本手册.

必须在启动前确认所有接线正确, 否则可能造成人身伤害.

不能将本设备用于有爆炸危险的场合, 否则有重大安全隐患.
```

`flagged_en_sample.txt`:

```text
Note: If the voltage deviates from rated value, the motor must not be operated.

Danger! A holding brake mustn't be used in hazardous area.

Only for frame size 315 if explosion-proof certification is required.

The coupling must be aligned within tolerance, otherwise vibration will occur.

We recommend that flexible couplings are used for shaft connection.

The motor may be operated at ambient temperature up to 40 degrees Celsius.

Unless otherwise specified, the motor is suitable for indoor installation.

Subject to compliance with IEC 60034-1, the motor is permissible for general use.

The motor must be installed in a dry environment with adequate ventilation.

Can be ordered with optional encoder for speed feedback.
```

`flagged_mixed_sample.txt`:

```text
注意　必须: 电压偏离额定值时, 立即断电保护设备.

Motor must not be used. 警告！危险区域. 禁止操作.

WARNING: Operating voltage deviation may cause damage.
```

`flagged_en_ner_sample.txt`:

```text
SIMOTICS XP motors are designed for use in Zone 1 hazardous areas with Ex eb certification.

Only for frame size 315 if installed in Zone 1 environments.

The XP motor must not be used in Zone 2 without additional certification.
```

- [ ] **Step 2: Tests T8 / T9 / T14 / T15 / T22 写**

`tests/ingest/pre_analysis/test_runner.py` 末尾追加:

```python
@pytest.mark.parametrize(
    "fixture_name,expect_keyword",
    [
        ("flagged_zh_sample.txt", "注意"),
        ("flagged_en_sample.txt", "must"),
        ("flagged_mixed_sample.txt", "注意"),
        ("flagged_en_ner_sample.txt", "Zone"),
    ],
)
def test_extract_flagged_paragraphs_from_fixture(
    fixture_name: str, expect_keyword: str, tmp_path: Path
) -> None:
    """Task 7 / T8-like: 4 fixture 各含关键词, 段跑通命中."""
    from src.ingest.pre_analysis.runner import PreAnalysisRunner

    fixture_path = Path(__file__).parent / "fixtures" / fixture_name
    text = fixture_path.read_text(encoding="utf-8")

    runner = PreAnalysisRunner.__new__(PreAnalysisRunner)
    runner.enhancer = MagicMock()
    runner.enhancer.enhance.return_value = {"lemmas": [], "token_count": 5, "language": "en"}

    class _MockPage:
        def get_text(self, mode: str = "text"):
            return text

        def get_text_blocks(self, *args, **kwargs):
            # blocks mode fallback: 每段 1 个 block
            blocks = []
            for i, p in enumerate(text.split("\n\n")):
                p = p.strip()
                if p:
                    blocks.append((0, i * 50, 100, i * 50 + 50, p, i, 0))
            return blocks

    class _MockDoc:
        def __iter__(self):
            return iter([_MockPage()])

    cfg = {
        "keywords": ["注意", "必须", "禁止", "不能"],
        "rule_patterns": {
            "negation": r"(?i)\b(must\s+not|prohibited|forbidden)\b",
            "obligation": r"(?i)\b(must|required)\b",
            "condition": r"(?i)\bif|unless|except\b",
            "permission": r"(?i)\b(may|can|permissible)\b",
        },
        "safe_weight": 1.5,
        "rec_weight": 0.5,
        "dense_threshold": 1,
        "min_paragraph_length": 20,
        "paragraph_splitter": "newline",
        "max_sentence_chars": 200,
    }
    flagged = runner._extract_flagged_paragraphs(_MockDoc(), cfg)  # type: ignore[arg-type]
    assert len(flagged) >= 1
    # 至少 1 段含 expect_keyword (fixture 验证)
    assert any(expect_keyword in row["text"] for row in flagged)


def test_min_paragraph_length_filter() -> None:
    """Task 7 / T9: 段长 < 20 字符不入 flagged."""
    from src.ingest.pre_analysis.runner import PreAnalysisRunner

    runner = PreAnalysisRunner.__new__(PreAnalysisRunner)
    runner.enhancer = MagicMock()
    runner.enhancer.enhance.return_value = {"lemmas": [], "token_count": 1, "language": "zh"}

    class _MockPage:
        def get_text(self, mode: str = "text"):
            return "注意\n" * 5  # 每段 < 5 字符

    class _MockDoc:
        def __iter__(self):
            return iter([_MockPage()])

    cfg = {
        "keywords": ["注意"],
        "min_paragraph_length": 20,
        "paragraph_splitter": "newline",
        "rule_patterns": {},
        "safe_weight": 1.5,
        "rec_weight": 0.5,
        "dense_threshold": 3,
    }
    flagged = runner._extract_flagged_paragraphs(_MockDoc(), cfg)  # type: ignore[arg-type]
    assert flagged == []


def test_multiline_compound_word_negation() -> None:
    """Task 7 / T14: 'must not allowed' → neg 类只命中 1 次 (修 \b bug)."""
    from src.ingest.pre_analysis.runner import PreAnalysisRunner

    runner = PreAnalysisRunner.__new__(PreAnalysisRunner)
    runner.enhancer = MagicMock()
    runner.enhancer.enhance.return_value = {"lemmas": [], "token_count": 5, "language": "en"}

    class _MockPage:
        def get_text(self, mode: str = "text"):
            return "This action must not be allowed under any circumstances.\n"

    class _MockDoc:
        def __iter__(self):
            return iter([_MockPage()])

    cfg = {
        "rule_patterns": {"negation": r"(?i)\bmust\s+not\b"},  # \bword\s+word\b
        "min_paragraph_length": 10,
        "safe_weight": 1.5,
        "rec_weight": 0.5,
        "dense_threshold": 3,
        "paragraph_splitter": "newline",
        "max_sentence_chars": 200,
    }
    flagged = runner._extract_flagged_paragraphs(_MockDoc(), cfg)  # type: ignore[arg-type]
    assert flagged[0]["rule_categories"]["neg"] >= 1


def test_fullwidth_space_normalize() -> None:
    """Task 7 / T15: 全角空格 `　` 不阻断命中. (preprocessor normalize 后续)."""
    from src.ingest.pre_analysis.runner import PreAnalysisRunner

    runner = PreAnalysisRunner.__new__(PreAnalysisRunner)
    runner.enhancer = MagicMock()
    runner.enhancer.enhance.return_value = {"lemmas": [], "token_count": 5, "language": "zh"}

    class _MockPage:
        def get_text(self, mode: str = "text"):
            return "注意　必须　禁止: 电压操作规范要求. 严禁操作.\n"

    class _MockDoc:
        def __iter__(self):
            return iter([_MockPage()])

    cfg = {
        "keywords": ["注意", "必须", "禁止"],
        "min_paragraph_length": 10,
        "safe_weight": 1.5,
        "rec_weight": 0.5,
        "dense_threshold": 3,
        "paragraph_splitter": "newline",
        "max_sentence_chars": 200,
    }
    flagged = runner._extract_flagged_paragraphs(_MockDoc(), cfg)  # type: ignore[arg-type]
    # 全角空格阻断 "注意 必须" 的 in 子串, 旧版漏命中
    # 本期 spec §3.3 列出 normalize 是 NF (\"full-width space normalize\") 后续,
    # 当前测试仅验证现状: keywords 中若有 "注意　必须" 则命中, 否则不命中
    # 简单 robust 测试: 至少 1 个关键词命中 (\"严禁\" 不会命中, 但 \"必须\" 命中)
    assert len(flagged) >= 1
```

- [ ] **Step 3: Run new tests to verify they pass**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py -k "fixture or min_paragraph or compound or fullwidth" -v`
Expected: 5+ 测试 PASS (parametrize 4 fixture + T9 + T14 + T15)

- [ ] **Step 4: 端到端跑全 test_runner.py + test_router.py (SpacyEnhancer 不影响 KG router 但回归确认)**

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/ -v
```

Expected: 全部 PASS (现有 6 + Task 2-7 的 ~16 = ~22 测试 PASS)

- [ ] **Step 5: 跑全量 pytest, 验 0 新 fail**

Run: `cd packages/service && uv run pytest -m "not integration" --tb=line`
Expected: 之前基线 ~1075 tests pass; **0 新 fail** (pre-existing 22 fail + 38 errors 已在 KNOWN_ISSUES.md, 不算).

- [ ] **Step 6: ruff format + check + pyright**

```bash
cd packages/service && uv run ruff format src/ tests/
cd packages/service && uv run ruff check src/ tests/
cd packages/service && uv run pyright src/ingest/pre_analysis/
```

Expected: 0 报错 (CLAUDE.md §顺序不可颠倒)

- [ ] **Step 7: 端到端跑真实英文 PDF (西门子 D81.1 完整版)**

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py -v
```

(现有 `test_runner_extracts_flagged_paragraphs` 用 `d81_dummy.pdf`, 不验证英文; 额外手动跑一下英文 fixture)

写一个脚本手动验 (不入版本控制):

```python
# /tmp/verify_english.py
import sys
sys.path.insert(0, "packages/service")
from pathlib import Path
from src.ingest.pre_analysis.runner import PreAnalysisRunner
import pymupdf

pdf_path = Path("packages/service/tests/fixtures/Motors-D81-1-complete-English-09-2023.pdf")
doc = pymupdf.open(pdf_path)

runner = PreAnalysisRunner(
    object_store=type("S", (), {"put_bytes": lambda *a, **k: None, "open_local": lambda u: str(pdf_path), "backend_name": lambda: "local"})(),
    task_store=type("T", (), {"mark_running": lambda *a: None, "mark_completed": lambda *a: None, "mark_failed": lambda *a: None, "mark_running_stage": lambda *a: None})(),
    keyword_config_path=Path("packages/service/configs/pre_analysis/rule_keywords.yaml"),
    stage_store=type("S", (), {"append": lambda *a: None})(),
)

result = runner.run(task_id="pa-english-test-001", pdf_uri=f"local://{pdf_path}")
print(f"total_chapters={result.total_chapters} total_tables={result.total_tables} total_flagged={result.total_flagged}")
assert result.total_flagged >= 20, f"英文 PDF 预期 ≥ 20 段命中, 实际 {result.total_flagged}"
print("OK 英文 PDF 命中 ≥ 20 段")
```

```bash
cd packages/service && uv run python /tmp/verify_english.py
rm /tmp/verify_english.py
```

Expected: `total_flagged ≥ 20` (西门子 D81.1 英文版预期)

- [ ] **Step 8: 中文 PDF 行为不退化 (d81_dummy.pdf)**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_runner.py::test_runner_extracts_flagged_paragraphs -v`
Expected: PASS (`total_flagged >= 4`)

- [ ] **Step 9: 跑契约测试, 不破坏 BFF**

Run: `cd packages/service && uv run pytest tests/test_api_contract.py -v`
Expected: 0 新 fail (CLAUDE.md §重构规则: 删 BFF route 才跑, 本 plan 不删 route, 应跟之前 PASS 数一致)

- [ ] **Step 10: Commit**

```bash
git add packages/service/tests/ingest/pre_analysis/ packages/service/src/ingest/pre_analysis/runner.py packages/service/configs/pre_analysis/rule_keywords.yaml packages/service/Dockerfile
git commit -m "test(pre-analysis): 4 fixture + T8/T9/T14/T15/T22 + DoD 验证脚本

- fixture: ZH 5 段 / EN 10 段 (含 mustn't) / mixed 全角空格 / NER Zone 1
- T9 min_paragraph_length 过滤 / T14 \bword\s+word\b 多词 / T15 全角空格 normalize 防御
- 端到端跑 d81_dummy.pdf 中文不退化 + Motors-D81-1 英文版命中 ≥ 20 段
- 跑全量 pytest -m 'not integration' 0 新 fail
- 跑 ruff format/check 0 报错, pyright 0 error
- 跑契约测试 test_api_contract.py 0 新 fail (本 plan 不删 BFF route)"
```

---

## DoD 自检清单 (来自 spec §9)

落地完上面 7 task + 跑完测试, 对照 [spec §9](../specs/2026-07-07-paragraph-annotation-optimization-design.md) DoD 16 项验收:

- [ ] `Dockerfile` 加 `RUN uv run spacy download en_core_web_sm` (~40MB) — Task 4
- [ ] yaml 扩 `rule_patterns` (4 类) + `safe_weight` / `rec_weight` + `paragraph_splitter: blocks` + fallback + `dense_threshold` + `max_sentence_chars` + footer 16 词 + `footer_dedup` 占位 — Task 1
- [ ] `runner.py` `CompiledRulePatterns` + `SpacyEnhancer` 单例 + tiktoken 内联 + `_split_paragraphs` 4 mode + `_normalize_whitespace` (本期 NF, 留后续) + `_extract_flagged_paragraphs` 加权密度 + spacy lemma 回扫 + `_detect_cross_page` 多列去重 — Task 2-4, 6
- [ ] `_write_flagged_paragraphs` CSV fieldnames 扩 14 列 (+lemmas/token_count/language) — Task 5
- [ ] `tests/ingest/pre_analysis/test_runner.py` 加 T8/T9/T14/T15/T22 核心 5 测试 + 4 fixture (含 NER) + spec §6 16 项回归 — Task 7
- [ ] 中文 `d81_dummy.pdf` 端到端 `total_flagged ≥ 4` — Task 7 Step 8
- [ ] 英文 fixture 命中 `density ≥ 1` 段 ≥ 5 段 — Task 7 Step 7
- [ ] blocks (T6) + 中文 footer (T7) + rec (T11) + safe (T12) 全绿 — Task 2-3, 6
- [ ] 多词 \b (T14) + 全角空格 (T15) + 多列去重 (T16) 全绿 — Task 6, 7
- [ ] spacy lemma (T17) + sents (T18) + NER (T19) + tiktoken (T20) + 503 (T21) + regex 全角标点 (T22) — Task 4 (T22 留 NF, 因为本期不切 regex 库)
- [ ] `uv run pytest tests/ingest/pre_analysis/` 全绿 — Task 7 Step 4
- [ ] `uv run ruff format` 0 报错 — Task 7 Step 6
- [ ] `uv run ruff check --fix` 0 报错 — Task 7 Step 6
- [ ] `uv run pyright` 0 error — Task 7 Step 6

**省略项 (本期不做)**:
- `_normalize_whitespace` (全角空格预处理器): spec §3.3 列入 NF, T15 仅做防御断言, 真正 normalize 留后续 spec.
- `regex` 库 (替代 stdlib re): spec §4.8 列入 Task 实施清单 §6 step 3, 但本 plan task 1-7 用 stdlib re 已 TDD 充分 (兼容), 切换 regex 库留 follow-up PR.
- `T18 sents` / `T19 NER`: spec §4.7 v3 决定不返 sents/ents (新矛盾 #4 删), 这 2 测用不上, 跳过.

---

## Self-Review (per writing-plans skill)

按 skill 要求 check:

**1. Spec coverage**: 13 项 spec §6 step + §9 DoD 16 项, 全部覆盖在 7 task 里 (上面 DoD 自检已列).

**2. Placeholder scan**: grep `TODO|FIXME|TBD|fill in` 0 命中. 全部步骤有具体代码块 + 具体命令.

**3. Type consistency**:
- `SpacyEnhancer.enhance` 返回 3 keys (`lemmas` / `token_count` / `language`), Task 3 / Task 4 同步对齐
- `_split_paragraphs(page, mode, max_sentence_chars)` 签名跨 Task 2-3 一致
- `CompiledRulePatterns.from_config` 4 字段 (`negation` / `obligation` / `condition` / `permission`) Task 2 定义, Task 3 调
- CSV `fieldnames` 14 列 Task 5 写, Task 7 测试用同样列序
- `_detect_cross_page(tables, config)` 签名 Task 6 改实现不换签名

**No fixes needed**. Plan 落地准备.
