# 段落标注优化设计 (2026-07-07)

> 上下文: `packages/service/src/ingest/pre_analysis/runner.py` `_extract_flagged_paragraphs` 当前只能匹配中文硬编关键词, 英文 PDF 命中 0.
> 来源:
> - 3 份 DeepSeek 对话 (西门子 D81.1 关键词调研 + 5 类/7 类规则正则 + 5 步法实施)
> - 联网核验 (Explore agent 2026-07-07): 4 项需修正 (7 类→4 类+2 weight, blocks 优先, 多词 `\b` bug, 中文 footer + 去重)
> - 项目依赖分析 (v3, 2026-07-07): spacy 必选 + regex 库 + tiktoken token_count
> 范围: `_extract_flagged_paragraphs` + `_load_config` + `_detect_cross_page` + 新增 spacy enhancer; 不动 `extract_tables` / `extract_chapters`.

## 1. 现状盘点

### 1.1 当前实现 (`runner.py:364-389`)

```python
def _extract_flagged_paragraphs(self, doc, config):
    keywords = config.get("keywords", [])             # 全中文 in 子串匹配
    min_len = config.get("min_paragraph_length", 20)
    flagged = []
    for page_idx, page in enumerate(doc):
        text = page.get_text()
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]  # 按 \n 单切
        for para_text in paragraphs:
            if len(para_text) < min_len:
                continue
            matched = [kw for kw in keywords if kw in para_text]         # 布尔判断
            if matched:
                flagged.append({
                    "matched_keywords": ",".join(matched),
                    "page": page_idx + 1,
                    "section": "",
                    "text": para_text,
                })
    return flagged
```

### 1.2 当前 yaml (OLD state, 2026-07-02)

`configs/pre_analysis/rule_keywords.yaml` 落地真值. 仅 5 中文 + 4 footer 词, **未扩展**. §6 第 2 步才扩.

```yaml
keywords:                                   # 5 中文硬编 (本期保留, 不删)
  - 注意
  - 不能
  - 仅适用
  - 必须
  - 禁止

chapter_patterns:                           # 本期不动
  - "^\\s*第[一二三四五六七八九十百零]+章[\\s　]+"
  - "^\\s*\\d+\\.\\d+(\\.\\d+)?[\\s　]+"
  - "^\\s*#{1,6}\\s+"

min_paragraph_length: 20

cross_page_detection:
  min_column_match: 0.8 # 列数匹配度 ≥ 80%
  footer_keywords:
    - "续表"
    - "续"
    - "cont."
    - "(continued)"
```

### 1.2.1 期望 yaml (NEW state, 2026-07-07 v3, 字段全表见 §3.2)

期望落地的 yaml 内容. 在 §1.2 基础上加 `rule_patterns` / `safe_weight` / `rec_weight` / `paragraph_splitter` / `paragraph_splitter_fallback` / `dense_threshold` / `max_sentence_chars` / 扩 footer 词到 16 条 / 新增 `footer_dedup`. **旧字段一字不动** (5 中文 keywords, chapter_patterns, min_paragraph_length 全部保留).

具体真值以 §3.2 为准 (落地时直接复制该 § 的 yaml 块到 yaml 文件).

### 1.3 用户分享的 DeepSeek 调研结论

#### 1.3.1 西门子 D81.1 手册的关键词分布

- **Note 类** (14 段): 几乎都是 `Note:` + 段落, 规则密度中等
- **否定类** (12 段): `not possible`, `must not`, `not admissible`, `Not for:`, `is not permitted`
- **仅适用类** (10 段): `Only for:`, `Only for frame size 315 if ...`, `... can only be ordered for ...`
- **其他规则密集段** (10 段): 详细参数表 / 选项组合限制 / 防爆合规

#### 1.3.2 5 类规则正则 (第 1 份核心方案)

```python
patterns = {
    "否定":   r"\b(not|cannot|never|must not|should not|may not|forbidden|prohibited|excluded|not permissible|not possible|no|without)\b",
    "肯定":   r"\b(must|shall|should|will|is required to|have to|need to|ensure|make sure|only possible|necessary|obligation)\b",
    "条件":   r"\b(if|when|whereas|unless|provided that|as long as|except|apart from|depending on|subject to)\b",
    "允许":   r"\b(can|may|able to|capable of|suitable for|intended for|permissible|allowed|permit|approval)\b",
    "安全":   r"\b(danger|warning|caution|notice|safety|hazard|risk)\b",
}
```

#### 1.3.3 7 类 → 4 类 + 2 weight (联网核验 2026-07-07 决策)

第 2 份原建议 7 类, 联网核验 (LegalRuleML / CUAD / deontic 标准) 后决定**降级为 4 类 + 2 weight**:

| # | 类型 | key | 关键词示例 | 联网核验依据 |
|---|---|---|---|---|
| 1 | 否定/禁止 (Negation) | `neg` | not, cannot, must\s+not, forbidden, prohibited | deontic 标准 prohibition 类 |
| 2 | 强制/义务 (Obligation) | `obl` | must, shall, ensure, is\s+required\s+to | deontic 标准 obligation 类 |
| 3 | 条件/例外 (Condition) | `cond` | if, unless, provided\s+that, except | deontic 标准 modality 类 |
| 4 | 允许/能力 (Permission) | `perm` | can, may, able\s+to, permissible | deontic 标准 permission 类 |
| 5 | **安全加权** (safe weight) | `safe_weight` | danger, warning, caution, notice | obl 的子集, 用 1.5 weight 升权 (硬约束) |
| 6 | **推荐加权** (rec weight) | `rec_weight` | recommend, advisable, usually, typically | perm 的弱化变体, 用 0.5 weight 降权 (软建议) |

**降级理由** (Explore agent 联网核验结论):
- `safe` 是 obl 的工业安全子集, IEC 82079-1 是危险**等级**而非 deontic **类别**, 单独成类违反标准
- `rec` 是 perm 的 best-effort 弱化, 单独成类跟 LegalRuleML 不兼容
- `val` 是 obl 的 scope 限定, 学术界用 modality/scope 字段表达, 不进 deontic 类别
- 降级后标签稀疏性降低, 跟 CUAD/LegalBench 标准兼容, 业务方可按 weight 灵活调阈值

**多词正则修正** (`\b` bug 修复, 2026-07-07):
- `valid for` → `\bvalid\s+for\b` (避免误匹配 "invalid for")
- `is required to` → `\bis\s+required\s+to\b`
- `provided that` → `\bprovided\s+that\b`
- `as long as` → `\bas\s+long\s+as\b`
- 全角空格 `　` 在 preprocessor normalize 为 `\s+`

### 1.4 现有测试 (`tests/ingest/pre_analysis/test_runner.py`)

- mode 1 mock + 真 PDF fixture (`tests/fixtures/d81_dummy.pdf`)
- `mock_store` / `mock_task_store` / `patch_session_scope` 三 fixture
- 跑 1 个 PDF 端到端, 验产物数 + 5 stage 阶段化

### 1.5 项目依赖分析 (v3, 2026-07-07)

读取 `packages/service/pyproject.toml` 找出已装 NLP 库, 跟段落标注需求做映射:

| 库 | 状态 | 模型/数据 | 对本模块帮助 | spec v3 决策 |
|---|---|---|---|---|
| `spacy==3.8.13` | 已装 | **模型未下载** (项目用 `zh_core_web_sm`, 缺 `en_core_web_sm`/`de_core_web_sm`) | lemma 还原 (`mustn't` → `must not`) / `doc.sents` 准确切句 / POS 区分 / NER Zone/型号提取 | **必选**, 跟 `src/kg/router.py:73` 复用 lazy load + 503 fallback |
| `regex>=2026.5.9` | 已装 | — | 全角标点切分 `(?<=[\.!?。！？])\s+` / `\p{L}` Unicode letter class / fuzzy match `(?:must\b){e<=1}` / `\m` `\M` Unicode 起止 | **选** |
| `tiktoken>=0.13.0` | 已装 | cl100k_base / o200k_base encoding | `token_count` 字段 (跟 LLM 预算口径一致) | **选** |
| `torch>=2.12.0` | 已装 (~1GB) | — | — | ❌ 过重, 不用 |
| `pandas>=3.0.3` | 已装 | — | — | ❌ 跟段落提取无关, 不用 |
| `tqdm>=4.67.3` | 已装 | — | 进度条 (跑 PDF 时显示 N 页) | 可选, 不在 spec |
| `camelot-py` / `pdfplumber` | 已装 | — | 跟 `extract_tables` 冲突, 不在本模块 | ❌ |

**关键发现**:
- `spacy 3.8.13` 是项目直接依赖 (`pyproject.toml:18`), 注释明确说"知识图谱规则抽取器直接依赖", 跟本模块 1:1 同构 (规则 + 抽取)
- 项目里 `src/kg/router.py:73` 已有现成 lazy load + 503 fallback 模式, 本模块直接复用
- 业务侧需先 `uv run spacy download en_core_web_sm` (~40MB), 镜像 Dockerfile 加这一行

### 1.6 spacy 模型下载要求 (新增)

| 语种 | 模型 | 大小 | 用途 |
|---|---|---|---|
| 中文 | `zh_core_web_sm` | ~40MB | 项目已装 (KG 用), 段落标注中文 PDF 复用 |
| 英文 | `en_core_web_sm` | ~40MB | **需新下载**, 段落标注英文 PDF (西门子/GE/ABB 手册) |
| 德文 | `de_core_web_sm` | ~40MB | 可选, 西门子原产国手册 |

**下载命令**: `uv run spacy download en_core_web_sm` (在 `packages/service/` 目录)
**Dockerfile 加**: `RUN uv run spacy download en_core_web_sm` (跟 `zh_core_web_sm` 并列)
**首次启动**: +1s 模型加载, 走 lazy import, 跟 KG router 同模式

## 2. 设计目标

### 2.1 解决 5 个核心问题

| # | 问题 | 现状 | 目标 |
|---|---|---|---|
| 1 | 关键词语言单边 | 中文 5 词 in 子串 | 中文 5 词 (兼容旧) + 英文 4 类 + 2 weight (联网核验降级) |
| 2 | 关键词权重无差别 | 5 词等价 | 4 类独立计数 + safe/rec 权重修饰 + 总命中密度评分 |
| 3 | 段落切分太粗 | `text.split("\n")` 单行一段 | blocks 优先 → double_newline → sentence_fallback (联网核验调整) |
| 4 | 无规则密集度评估 | `if matched:` 布尔 | `weighted_density ≥ 阈值` 标 dense + 类别命中细节 |
| 5 | 跨页 footer 中文限 | 2 中文 + 2 英文 | 8 中文 + 8 英文 + 多列去重 (联网核验扩展) |

### 2.2 兼容性约束 (本 spec 关键原则)

- **必须兼容旧 yaml 5 词**: 旧 config 只有 `keywords: [注意, ...]` 时, 行为不能变 (5 词 in 子串), 仅多算命中数
- **必须兼容旧 CSV schema**: `flagged_paragraphs.csv` 列名不动 (`matched_keywords,page,section,text`), 仅 `matched_keywords` 格式扩 (可包含 `neg=2,cond=1`)
- **必须不动前端契约**: 详情页读 `flagged` 数组, 字段名 `matched_keywords` / `page` / `section` / `text` 不变
- **必须不动 min_paragraph_length 默认 20**: yaml 没改前, 旧 PDF 命中数不变
- **必须不破坏 LegalRuleML 兼容**: 4 类 deontic 标签 (neg/obl/cond/perm) 跟业界标准 1:1 对齐, 后续接入 LegalBench 评估零成本
- **必须不引入新依赖**: 不加 langdetect / spaCy / pdfplumber, 仍用 pymupdf + yaml + re + csv (项目祖传)

### 2.3 性能约束

- 正则模块加载期 `re.compile()` 一次 (不每段重复编译)
- 段落总数 = 总页数 × 平均段数 ≈ 1000 段/PDF, 5 正则 × 1000 = 5000 次匹配/PDF, < 100ms

## 3. 数据结构

### 3.1 新增 `FlaggedHit` dataclass (`runner.py` 内部)

```python
@dataclass(frozen=True)
class FlaggedHit:
    """(2026-07-07) 段落命中扩展. 旧 dict 形态保留, 新增字段平铺到 CSV."""
    page: int
    section: str
    text: str
    matched_keywords: list[str]          # 旧字段, 兼容
    rule_categories: dict[str, int]      # 新: {"neg": 2, "cond": 1, ...} (4 类)
    density: int                         # 新: sum(rule_categories.values())
    is_dense: bool                       # 新: density ≥ 阈值
    raw_density: int                     # v3: raw 加权
    weighted_density: float              # v3: 包含 safe/rec weight
    safe_hits: int                       # v3: 安全词命中数
    rec_hits: int                        # v3: 推荐词命中数
    lemmas: list[str] = field(default_factory=list)   # v3: spacy lemma 还原
    token_count: int = 0                 # v3: tiktoken 编码数 (跟 LLM 预算对齐)
    language: str = "unknown"            # v3: spacy lang detect ("en" / "zh" / "de")
```

**CSV 列序**: `matched_keywords,page,section,text,rule_categories,density,is_dense,raw_density,weighted_density,safe_hits,rec_hits,lemmas,token_count,language`
旧 CSV reader (`DictReader`) 只读前 4 列, 不破坏; 新 CSV writer 写 14 列.

### 3.2 yaml 配置扩展 (新加, 不删旧)

```yaml
# === 旧字段保留 (2026-07-02) ===
keywords:
  - 注意
  - 不能
  - 仅适用
  - 必须
  - 禁止

min_paragraph_length: 20

# === 新字段 (2026-07-07, opt-in) ===
# 4 类英文正则规则库 (联网核验后降级: safe/rec 不进类别 dict)
# 多词短语全部用 \bword\s+word\b 形式 (修 \b bug)
# 全角空格在 preprocessor normalize 为半角
rule_patterns:
  negation:    "(?i)\\b(not|cannot|never|must\\s+not|should\\s+not|may\\s+not|forbidden|prohibited|excluded|not\\s+permissible|not\\s+possible|no|without)\\b"
  obligation:  "(?i)\\b(must|shall|should|will|is\\s+required\\s+to|have\\s+to|need\\s+to|ensure|make\\s+sure|only\\s+possible|necessary|obligation)\\b"
  condition:   "(?i)\\b(if|when|whereas|unless|provided\\s+that|as\\s+long\\s+as|except|apart\\s+from|depending\\s+on|subject\\s+to)\\b"
  permission:  "(?i)\\b(can|may|able\\s+to|capable\\s+of|suitable\\s+for|intended\\s+for|permissible|allowed|permit|approval)\\b"

# 2 weight 修饰 (safe/rec 是 obl/perm 子集, 不进类别 dict)
safe_weight: 1.5   # danger/warning/caution/notice/safety/hazard/risk 命中后乘 1.5
rec_weight: 0.5    # recommend/advisable/usually/typically/suggested/preferred 命中后乘 0.5

# 段落切分升级 (新加, 默认 blocks 优先 — 联网核验 pymupdf 官方段落 API)
paragraph_splitter: "blocks"               # "blocks" (新, 默认) | "double_newline" | "newline" (旧) | "sentence_fallback"
paragraph_splitter_fallback: ["double_newline", "newline", "sentence_fallback"]

# 规则密集度阈值 (新加, 默认 3)
dense_threshold: 3

# 句子级 fallback 切分阈值 (新加, 默认 200)
max_sentence_chars: 200

# 跨页 footer 关键词扩展 (加中文 + "cont." 欧洲缩写 + 多列去重)
cross_page_detection:
  min_column_match: 0.8
  footer_keywords:
    # 中文
    - "续表"
    - "续上表"
    - "(续)"
    - "接下页"
    - "接上页"
    - "下转"
    - "转下页"
    # 英文
    - "cont."
    - "(continued)"
    - "continued"
    - "cont'd"
    - "continues"
    - "continued on"
    - "continued on next page"
    - "to be continued"
  # 多列去重 (避免每列底部 footer 重复触发, C5 seen_footers 方案)
  # 注: 字段仅留 footer_dedup 节点占位, 字段值本期**不读** (见 §4.6 修复说明)
  footer_dedup: {}

### 3.3 字典化 (跟项目 `dictionaries_seed.yaml` 规范对齐, 2026-07-08 跟进)

**关键决策**: 5 类英文规则关键词库**本期不**走字典 (`_build_enum` + lookup 表). 原因:

1. 5 类关键词是**模式库** (正则字符串), 不是 enum 值 (固定 code)
2. 字典是 `(code, label, is_active)` 三元组, 适合业务 enum (e.g. `task_status: pending/running`), 不适合正则字符串
3. 正则改动频次低, 改 yaml + 重启服务足够

**未来路径** (2026-07-08 spec 候选):

- 把 5 类各拆成 "关键词字典" (每条 `code=word, label=中文释义, pattern_type=neg/obl/...`)
- 启动期编译 pattern 池
- admin UI 改字典 → Redis pub/sub → 进程热加载 (已有 `dictionaries_enum` 机制可复用)
- **本期不做**, 仅在 spec 留 TODO

## 4. 实现步骤

### 4.1 Step 1: yaml 扩展

`configs/pre_analysis/rule_keywords.yaml` 加 `rule_patterns` / `paragraph_splitter` / `dense_threshold` / 跨页 footer 扩 8 词. **不改旧字段**.

### 4.2 Step 2: runner 内部 dataclass + 编译

```python
# runner.py 顶部加 (2026-07-07)
from dataclasses import dataclass, field

@dataclass(frozen=True)
class CompiledRulePatterns:
    """(2026-07-07) 启动期编译一次, 跑 PDF 时直接复用. 4 类 (联网核验后降级)."""
    negation: re.Pattern[str]
    obligation: re.Pattern[str]
    condition: re.Pattern[str]
    permission: re.Pattern[str]

    @classmethod
    def from_config(cls, cfg: dict) -> "CompiledRulePatterns":
        rp = cfg.get("rule_patterns", {})
        # 默认 X = 永不命中, yaml 缺 rule_patterns 时退化为旧 in 子串逻辑
        return cls(
            negation=re.compile(rp.get("negation", r"(?i)\bX\b")),
            obligation=re.compile(rp.get("obligation", r"(?i)\bX\b")),
            condition=re.compile(rp.get("condition", r"(?i)\bX\b")),
            permission=re.compile(rp.get("permission", r"(?i)\bX\b")),
        )
```

**设计要点**:
- 默认 pattern `(?i)\bX\b` 永不命中 → yaml 缺 `rule_patterns` 时, 4 类全 0 命中, 行为退化为旧 in 子串
- `re.Pattern` 不可变, 跨 runner 实例安全复用
- safe / rec 是 weight 修饰而非独立 Pattern, 在 `_extract_flagged_paragraphs` 里用 `re.findall` 直接命中后乘 weight

### 4.3 Step 3: 段落切分升级 (blocks 优先)

```python
def _split_paragraphs(
    self,
    page: pymupdf.Page,        # 联网核验: 传 Page 而不是 text, blocks mode 需要 bbox
    mode: str,
    max_sentence_chars: int = 200,
) -> list[str]:
    """(2026-07-07) 段落切分. 默认 blocks mode (pymupdf 官方段落 API).
    fallback 链: blocks → double_newline → newline → sentence_fallback.
    """
    if mode == "blocks":
        # 联网核验: pymupdf get_text("blocks") 返回 [(x0,y0,x1,y1,text,bn,bt), ...]
        blocks = page.get_text("blocks")     # type: ignore[attr-defined]
        return [b[4].strip() for b in blocks if b[4].strip()]
    if mode == "double_newline":
        text = page.get_text()                # type: ignore[attr-defined]
        paras = re.split(r"\n\s*\n", text)
        return [p.strip().replace("\n", " ") for p in paras if p.strip()]
    if mode == "newline":
        text = page.get_text()                # type: ignore[attr-defined]
        return [p.strip() for p in text.split("\n") if p.strip()]
    if mode == "sentence_fallback":
        text = page.get_text()                # type: ignore[attr-defined]
        sentences = re.split(r"(?<=[.?!])\s+", text)
        merged: list[str] = []
        buf = ""
        for s in sentences:
            if not s.strip():
                continue
            if len(buf) + len(s) <= max_sentence_chars:
                buf = (buf + " " + s).strip()
            else:
                if buf:
                    merged.append(buf)
                buf = s.strip()
        if buf:
            merged.append(buf)
        return merged
    raise ValueError(f"unknown splitter: {mode}")
```

**关键**:
- `blocks` mode 传 `page` 而不是 text, 因为 `get_text("blocks")` 需要 pymupdf Page 上下文
- `double_newline` 模式下, 段内换行合成空格 (`replace("\n", " ")`), 否则一句一行成空段
- `sentence_fallback` 按 `(?<=[.?!])\s+` 切句, 然后滑窗合回 ≤ `max_sentence_chars` 字符的段

### 4.4 Step 4: `_extract_flagged_paragraphs` 重写 (4 类 + 2 weight)

```python
def _extract_flagged_paragraphs(
    self, doc: pymupdf.Document, config: dict
) -> list[dict]:
    """(2026-07-07 v3) 多语言 + 4 类正则 + safe/rec 权重修饰 + 密度评分 + spacy 增强.

    Returns: 兼容旧 schema 4 列 + 新增 10 列 = 14 列.
    [{matched_keywords, page, section, text, rule_categories, density, is_dense,
      raw_density, weighted_density, safe_hits, rec_hits,
      lemmas, token_count, language}, ...]
    """
    keywords = config.get("keywords", [])
    min_len = config.get("min_paragraph_length", 20)
    splitter_mode = config.get("paragraph_splitter", "blocks")        # 默认 blocks (§3.2 / §8 风险表对齐)
    max_sentence_chars = config.get("max_sentence_chars", 200)
    dense_threshold = config.get("dense_threshold", 3)
    safe_weight = config.get("safe_weight", 1.5)
    rec_weight = config.get("rec_weight", 0.5)
    compiled = CompiledRulePatterns.from_config(config)
    enhancer = SpacyEnhancer(primary_lang="en")  # v3: lazy load, 缺模型抛 RuntimeError (§4.7)

    # safe / rec 是 weight 修饰, 在循环内 re.findall 命中后乘 weight
    safe_pattern = re.compile(
        r"(?i)\b(danger|warning|caution|notice|safety|hazard|risk)\b"
    )
    rec_pattern = re.compile(
        r"(?i)\b(recommend|advisable|usually|typically|suggested|preferred)\b"
    )

    flagged: list[dict] = []
    for page_idx, page in enumerate(doc):                            # type: ignore[arg-type]
        # blocks mode 跟其他 mode 都传 page, _split_paragraphs 内部统一处理 (C4)
        paragraphs = self._split_paragraphs(page, splitter_mode, max_sentence_chars)

        for para_text in paragraphs:
            if len(para_text) < min_len:
                continue
            # 旧: 中文 in 子串 (兼容)
            matched = [kw for kw in keywords if kw in para_text]
            # 4 类 deontic 正则
            rule_categories = {
                "neg": len(compiled.negation.findall(para_text)),
                "obl": len(compiled.obligation.findall(para_text)),
                "cond": len(compiled.condition.findall(para_text)),
                "perm": len(compiled.permission.findall(para_text)),
            }
            # safe / rec weight 修饰 (不进入类别 dict)
            safe_hits = len(safe_pattern.findall(para_text))
            rec_hits = len(rec_pattern.findall(para_text))

            # raw + weighted 双轨
            raw_density = sum(rule_categories.values())
            weighted_density = raw_density + safe_hits * (safe_weight - 1.0) + rec_hits * (rec_weight - 1.0)
            density = weighted_density
            is_dense = weighted_density >= dense_threshold

            # 命中条件: 旧 in 命中 OR 新密度 > 0
            if matched or density > 0:
                # === v3: spacy 增强 (在 cat_summary 计算之前, 让 lemma 回扫也进 matched_keywords 列) ===
                enhanced = enhancer.enhance(para_text)
                # lemma 回扫: mustn't → must not, 't token 还原后二次正则
                lemma_text = " ".join(enhanced["lemmas"])
                lemma_neg_extra = len(re.findall(r"\bnot\b", lemma_text))
                if lemma_neg_extra and not rule_categories["neg"]:
                    rule_categories["neg"] = lemma_neg_extra
                    density += lemma_neg_extra
                    weighted_density += lemma_neg_extra

                # cat_summary 必须在 lemma 回扫**之后**算, 否则 CSV matched_keywords 列漏掉 neg 命中
                cat_summary = ",".join(
                    f"{k}={v}" for k, v in rule_categories.items() if v > 0
                )
                weight_summary = []
                if safe_hits:
                    weight_summary.append(f"safe={safe_hits}*{safe_weight}")
                if rec_hits:
                    weight_summary.append(f"rec={rec_hits}*{rec_weight}")
                merged = matched + ([cat_summary] if cat_summary else []) + weight_summary

                flagged.append({
                    "matched_keywords": ",".join(merged),
                    "page": page_idx + 1,
                    "section": "",
                    "text": para_text,
                    "rule_categories": rule_categories,
                    "density": density,
                    "is_dense": is_dense,
                    "raw_density": raw_density,
                    "weighted_density": weighted_density,
                    "safe_hits": safe_hits,
                    "rec_hits": rec_hits,
                    "lemmas": json.dumps(enhanced["lemmas"], ensure_ascii=False),
                    "token_count": enhanced["token_count"],
                    "language": enhanced["language"],
                })
    return flagged
```

**关键设计决策**:

1. **4 类 deontic + 2 weight 修饰**: safe/rec 不进 `rule_categories` dict, 用 `safe_hits` / `rec_hits` 字段存原始命中数, `weighted_density` 自动叠加
2. **加权公式**: `weighted = raw + safe_hits × (safe_weight - 1.0) + rec_hits × (rec_weight - 1.0)`, 默认 safe_weight=1.5 → 每 safe 命中加 0.5, rec_weight=0.5 → 每 rec 命中减 0.5
3. **命中条件**: 旧 `matched` 命中 OR 新 `density > 0`, 任一即可, 保中文 PDF 行为不退化
4. **`matched_keywords` 字段**: 旧值 + 类摘要 + weight 摘要, 旧 CSV reader 不解析逗号后内容, 安全
5. **新字段在 dict 里**: 14 列全表 (`rule_categories` 4 key / `density` / `is_dense` / `raw_density` / `weighted_density` / `safe_hits` / `rec_hits` / `lemmas` / `token_count` / `language`)
6. **v3 spacy 增强 (本步整合)**: 命中段必跑 `enhancer.enhance()`, lemma 还原后对 `not` 单字二次回扫, 弥补缩写漏检 (mustn't → must not)

### 4.5 Step 5: CSV writer 扩 fieldnames

```python
# _write_flagged_paragraphs (runner.py:423) 改:
# 14 列 CSV (旧 4 列兼容 + 新 10 列), 顺序对齐 §3.1
fieldnames = [
    "matched_keywords", "page", "section", "text",          # 旧 4 列 (DictReader 兼容)
    "rule_categories", "density", "is_dense",               # v2 新增 3 列
    "raw_density", "weighted_density",                      # v2 新增 2 列
    "safe_hits", "rec_hits",                                # v2 新增 2 列
    "lemmas", "token_count", "language",                    # v3 新增 3 列 (spacy + tiktoken)
]
writer = csv.DictWriter(buf, fieldnames=fieldnames)
```

`rule_categories` / `lemmas` 序列化为 `json.dumps(..., ensure_ascii=False)` 防 dict/list 写入 CSV 出错.

### 4.6 Step 6: 跨页 footer 扩词 + 去重 (C5 修复)

`_detect_cross_page` (`runner.py:294-314`) 改: 多列去重**改用 `seen_footers` set** (C5 修复 — 旧版 `require_first_col and table_no != 1` 死代码, 因外层已判 `table_no == 1`):

```python
def _detect_cross_page(
    self,
    tables: list[tuple[int, int, list[list[str]]]],
    config: dict,
) -> int:
    """(2026-07-07 v3) 跨页表候选检测启发式 + 多列去重 (C5 seen_footers 方案)."""
    cross_config = config.get("cross_page_detection", {})
    col_match = cross_config.get("min_column_match", 0.8)
    footer_kws = cross_config.get("footer_keywords", []) or []

    prev_table = None
    cross_page = 0
    seen_footers: set[str] = set()    # C5: 同一 footer 文本只算一次跨页
    for page_no, table_no, rows in tables:
        if prev_table is not None and table_no == 1:
            prev_page, prev_cols = prev_table
            if prev_page == page_no - 1 and len(rows[0] if rows else []) >= prev_cols * col_match:
                last_row = (rows[-1][0] if rows and rows[-1] else "") or ""
                # 命中 footer 关键词, 且同 footer 文本未出现过
                if last_row in seen_footers:
                    continue    # C5: 多列表格每列底部 footer 重复 → 去重
                if any(kw in last_row for kw in footer_kws):
                    seen_footers.add(last_row)
                    cross_page += 1
                    logger.warning("跨页表候选 page={} -> page={}", prev_page, page_no)
        prev_table = (page_no, len(rows[0] if rows else []))
    return cross_page
```

**关键 (C5 修复)**:
- **方案**: `seen_footers: set[str]` 同 footer 文本去重. 多列表格每列底部都有 "cont." 时, 只有第一次出现计入跨页.
- **yaml 副作用**: `footer_dedup.require_first_column` / `require_cont_marker` 字段本期**不读** (死代码根因, 删). 后续若要严格"仅首列"语义, 需要重构成"按列解析"模式 + 单元坐标, 留后续 spec.
- **兼容性**: 检测行为对外接口 (`return int`) 不变, 中文 footer 4 词 → 16 词生效, 跨页计数更准.

### 4.7 Step 7: spacy enhancer (v3 必选)

`runner.py` 内部加 spacy enhancer, 跟 `src/kg/router.py:73` 复用 lazy load + 503 fallback 模式:

```python
# runner.py 顶部 (与 §4.8 import 口径一致, stdlib re 已被 regex 替换)
import regex as re           # v3: regex 库替换 stdlib re (全角标点 / Unicode 起止)
import spacy                 # v3: lemma 还原 (mustn't → must not)
import tiktoken              # v3: token_count (跟 LLM 预算对齐)


class SpacyEnhancer:
    """(v3) spacy 增强器. 单例, 进程内 lazy init.

    跟 src/kg/router.py:73 同模式: 缺模型抛 RuntimeError, 不静默降级.
    注: 调用点已在 §4.4 `_extract_flagged_paragraphs` 内合并, 本 § 仅定义类本身.
    """

    def __init__(self, primary_lang: str = "en"):
        self.primary_lang = primary_lang
        self.nlp = self._load(primary_lang)
        # tiktoken 用 cl100k_base (跟 OpenAI GPT-4 / text-embedding-3-small 对齐)
        self.enc = tiktoken.get_encoding("cl100k_base")

    def _load(self, lang: str):
        try:
            return spacy.load(f"{lang}_core_web_sm")
        except OSError as e:
            # 缺模型 → 跟 KG router 一样抛, runner 走 mark_failed
            raise RuntimeError(
                f"spaCy 模型 {lang}_core_web_sm 未加载: {e}. "
                f"请运行: cd packages/service && uv run spacy download {lang}_core_web_sm"
            ) from e

    def enhance(self, text: str) -> dict:
        """对单段文本跑 spacy + tiktoken, 返字段 (本期限定 3 项, 跟 §4.4 dict 对齐).

        返回: {lemmas, token_count, language}.
        历史字段 (sents/ents) 已删除 — 死计算, §3.1 dataclass / §4.4 dict / §4.5 fieldnames
        三方对齐 14 列, 不含 sents/ents. NER 留后续 KG 抽取复用, 本 spec 不暴露到 CSV.
        """
        doc = self.nlp(text)
        # lemma 还原 (mustn't → must not, can't → can not)
        lemmas = [t.lemma_ for t in doc if not t.is_punct and not t.is_space]
        # tiktoken token count (跟 LLM 预算口径一致)
        token_count = len(self.enc.encode(text))
        return {
            "lemmas": lemmas,
            "token_count": token_count,
            "language": self.primary_lang,
        }
```

> §4.7 唯一职责: 定义 `SpacyEnhancer` 类本身. 调用点已在 §4.4 `_extract_flagged_paragraphs` 末尾内联 (C2 修复). 早期草稿的 demo 代码块已删除, 避免实现者两处参考.

### 4.8 Step 8: 段落切分换 regex 库 (v3)

`§4.3 _split_paragraphs` 改用 regex 库 (已装, 支持全角标点 + Unicode 起止):

```python
def _split_paragraphs(
    self,
    page: pymupdf.Page,
    mode: str,
    max_sentence_chars: int = 200,
) -> list[str]:
    """(2026-07-07 v3) 段落切分. 默认 blocks mode.
    v3: 换 regex 库, 全角标点切分, Unicode 起止 \\m \\M.
    """
    if mode == "blocks":
        blocks = page.get_text("blocks")
        return [b[4].strip() for b in blocks if b[4].strip()]
    if mode == "double_newline":
        text = page.get_text()
        # v3: \\s+ 匹配全角空格 \\u3000 + 半角空格 + Tab
        paras = _regex.split(r"\n\s*\n", text)
        return [p.strip().replace("\n", " ") for p in paras if p.strip()]
    if mode == "newline":
        text = page.get_text()
        return [p.strip() for p in text.split("\n") if p.strip()]
    if mode == "sentence_fallback":
        text = page.get_text()
        # v3: 全角标点 `。！？` 加入切分集合 (中英混编 PDF)
        sentences = _regex.split(r"(?<=[\.!?。！？])\s+", text)
        merged: list[str] = []
        buf = ""
        for s in sentences:
            if not s.strip():
                continue
            if len(buf) + len(s) <= max_sentence_chars:
                buf = (buf + " " + s).strip()
            else:
                if buf:
                    merged.append(buf)
                buf = s.strip()
        if buf:
            merged.append(buf)
        return merged
    raise ValueError(f"unknown splitter: {mode}")
```

**§4.4 `_extract_flagged_paragraphs` 同步改**: 把 stdlib `import re` 改 `import regex as re`, 多词模式用 `_regex.compile(...)` 编译.

**多词正则 fuzzy** (可选 v3 增强): `r"(?e)(?:must\b){e<=1}"` 容忍 1 个编辑错误 (mustn → must), 西门子手册 OCR 错字场景.

## 5. 测试设计

### 5.1 测试矩阵 (mode 1 mock)

| # | 用例 | 输入 | 期望 |
|---|---|---|---|
| T1 | 中文旧行为不退化 | d81_dummy.pdf (中文手册) | `matched` 非空, `density` ≥ 旧值 |
| T2 | 英文 Note 段命中 | 西门子 D81.1 英文 PDF 段 "Note: If the voltage deviates..." | `safe ≥ 1` 且 `cond ≥ 1` |
| T3 | 否定句命中 | "A holding brake must not be used..." | `neg ≥ 1` |
| T4 | 仅适用句命中 | "Only for frame size 315 if..." | `cond ≥ 1` |
| T5 | 密度评分阈值 | 段含 5 个不同类词 | `is_dense = True` (假设 threshold=3) |
| T6 | 段落切分 blocks 优先 (联网核验) | pymupdf Page mock, `get_text("blocks")` 返 3 段 | paragraphs 数 = 3, 不依赖 \n |
| T7 | 跨页 footer 英文 + 去重 (联网核验) | footer "continued" + 多列表格 | 跨页候选 +1 (非每列重复) |
| T8 | yaml 缺 rule_patterns | 配置只含旧 keywords | 4 类全 0 命中, 走旧逻辑 |
| T9 | min_len 过滤 | 段长 < 20 字符 | 不入 flagged |
| T10 | CSV 14 列兼容 | 读旧 DictWriter (4 列) | 旧 reader 不报错 |
| T11 | 推荐类 weight (联网核验) | "We recommend that flexible couplings..." | `rec_hits ≥ 1`, `weighted_density = raw - 0.5` |
| T12 | 安全类 weight (联网核验) | "Note: Danger if voltage deviates..." | `safe_hits ≥ 1`, `weighted_density = raw + 0.5` |
| T13 | 句子级 fallback (第 3 份) | text 单段 800 字符, `paragraph_splitter=sentence_fallback, max_sentence_chars=200` | 切出 ≥ 4 段 |
| T14 | 多词 `\b` bug 修复 (联网核验) | "must not be used" (`must\s+not` 多词) | `neg ≥ 1`; "must be notable" (`must\s+\S+` 不是 not) | `neg = 0` (旧 bug 误命中) / 1 (修正后) |
| T15 | 全角空格 normalize (联网核验) | 中文混排 "注意　必须" 全角空格 | 命中 2 (旧 bug 漏命中) / 2 (修正后) |
| T16 | 多列 footer 去重 (联网核验) | 3 列表格, 每列底部都有 "continued" | 跨页计数 = 1 (旧 = 3) |
| T17 | spacy lemma 还原 (v3) | "A holding brake mustn't be used..." (缩写) | `lemmas` 含 `must not`, `neg ≥ 1` |
| T18 | spacy sentence 切分 (v3) | "First. Second! Third?" | `doc.sents` 长度 = 3 |
| T19 | spacy NER (v3) | "SIMOTICS XP motors in Zone 1" | `ents` 含 `Zone 1` (CARDINAL/GPE) |
| T20 | tiktoken token_count (v3) | 1 段 100 字符英文 | `token_count` 在 [20, 50] 区间 |
| T21 | spacy 模型缺失 (v3) | SpacyEnhancer `_load` 模拟 `OSError` | 抛 `RuntimeError`, 不静默降级 |
| T22 | regex 全角标点切分 (v3) | "中文。English. 中英混排！" | sentence_fallback 切出 ≥ 3 段 |

### 5.2 fixture 准备

`tests/fixtures/` 加 4 个纯文本 fixture:

- `flagged_zh_sample.txt` — 中文手册段 (5 段, 含 "注意/必须/禁止")
- `flagged_en_sample.txt` — 英文 D81.1 段 (10 段, 覆盖 4 类 + safe + rec + 缩写 mustn't)
- `flagged_mixed_sample.txt` — 中英混排 (3 段, 含全角空格 + 全角标点)
- `flagged_en_ner_sample.txt` — 英文含 NER 实体 (Zone 1 / SIMOTICS / Ex eb)

测试用 `MagicMock` 替 `pymupdf.Document`, `enumerate(doc)` mock 返 `(idx, page_with_get_text_and_get_blocks)`. **spacy enhancer** 单测用 `MagicMock` 替 `nlp`, 返 mock `doc` + `doc.sents` + `doc.ents`. 完全不连真 PDF / 真 spacy, 跑得快 (~10ms/case).

### 5.3 现有测试兼容性

`test_runner.py` 跑 `d81_dummy.pdf` 端到端, 必须:

1. `result.total_flagged ≥ 旧值` (中文 PDF 行为不退化)
2. `flagged_paragraphs.csv` 含 `matched_keywords` 列 (旧列)
3. `flagged_paragraphs.csv` 含 `density` / `safe_hits` / `rec_hits` / `token_count` / `lemmas` 列 (新列, 不破 DictReader 读前 4 列)

若旧测试红, 优先调整 runner 不退化工序, 不动 fixture.

## 6. 实施清单 (按依赖排序)

```
1. Dockerfile 加 spacy download     ← packages/service/Dockerfile (en_core_web_sm ~40MB)
2. yaml 扩展                         ← configs/pre_analysis/rule_keywords.yaml (按 §3.2, 4 类 + safe_weight + rec_weight + blocks mode + footer 16 词)
3. regex 库替换 stdlib re             ← runner.py 顶部 import regex as re
4. CompiledRulePatterns              ← runner.py 顶部 dataclass (4 Pattern 字段)
5. SpacyEnhancer                     ← runner.py 内部单例, 跟 src/kg/router.py:73 同 lazy load 模式
6. Tiktoken 内联到 SpacyEnhancer     ← runner.py 内部 lazy, 用 cl100k_base (无需独立 wrapper class)
7. _split_paragraphs 改传 page + regex 库  ← runner.py 内部 (4 mode, 全角标点切分)
8. 全角空格 normalize                  ← preprocessor 函数 (_normalize_whitespace)
9. _extract_flagged_paragraphs 重写    ← runner.py:364 (4 类 + 2 weight + SpacyEnhancer 整合 + token_count)
10. _write_flagged_paragraphs fieldnames 扩 14 列  ← runner.py:423 (+lemmas/token_count/language)
11. _detect_cross_page 多列去重 (seen_footers)  ← runner.py:294
12. 测试 fixture + 22 单测              ← tests/ingest/pre_analysis/test_runner.py

# 验证阶段
13. 端到端跑 d81_dummy.pdf    ← 验中文不退化
14. 跑全量 pytest             ← 验无新 fail
15. ruff format + check       ← 0 报错
16. pyright                  ← 0 error
```

## 7. 不做的事

- ❌ 字典化 5 类规则关键词库 (理由见 3.3, 留 2026-07-08 spec 候选)
- ❌ 段落切分换 LLM / NLP 模型 (本期正则足够, 加复杂度不值)
- ❌ 段落切分支持 PDF 表格内文字 (跟 `extract_tables` 职责冲突)
- ❌ 改前端 `flagged_paragraphs` UI (新字段暂不暴露, 留后续 UI 迭代)
- ❌ 改 `extract_chapters` 章节标题正则 (本期不动)
- ❌ 改 PDF stage 5 wrap 流程 (`load_config` / `extract_chapters` / `extract_tables` / `extract_flagged` / `write_outputs` 顺序不变)

## 8. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 旧中文 PDF 命中数变 | 中 | 中文产品回归 | T1 测试 + 阈值保 20 字符 + 旧 in 子串逻辑保留 |
| CSV 新列破前端 reader | 低 | 详情页 500 | 旧 DictReader 只读前 4 列, 加列不破坏; 后端测试 T10 |
| 正则 `\b` 中文失效 | 高 | 中文段命中数不变 (旧逻辑兜底) | 4 类正则只覆盖英文, 中文走旧 in 子串, 双轨并存 |
| 密度阈值默认 3 过严 | 中 | 英文 PDF 命中少 | yaml 可调, 旧逻辑 `matched or density > 0` 保底 |
| blocks mode 把表内文字切断 | 中 | 表格周边段被切错 | `paragraph_splitter` 默认 `blocks` (新, §3.2 对齐), 旧业务 yaml 显式 opt-in `newline` 回退 |

> 注: 之前 v3 草稿此行写错 — 旧实现默认 `newline` 不能动 (会回退 v0 行为), 而本期新行为默认 `blocks`. 风险表跟 §3.2 / §4.4 splitter_mode 默认值保持一致 (`blocks`).

## 9. 验收 (DoD)

- [ ] `Dockerfile` 加 `RUN uv run spacy download en_core_web_sm` (~40MB 镜像增量)
- [ ] `configs/pre_analysis/rule_keywords.yaml` 扩 `rule_patterns` (4 类 deontic) + `safe_weight` / `rec_weight` + `paragraph_splitter: blocks` (默认) + fallback 链 + `dense_threshold` + `max_sentence_chars` + footer 16 词 (中英) + `footer_dedup`, 旧字段保留
- [ ] `runner.py` 加 `CompiledRulePatterns` dataclass (4 Pattern 字段) + `SpacyEnhancer` 单例 (lazy load, 503 fallback, 内联 tiktoken cl100k_base) + `_split_paragraphs` (4 mode, blocks 优先, regex 库, 全角标点) + `_normalize_whitespace` (全角空格) + `_extract_flagged_paragraphs` 加权密度 + spacy lemma 回扫 + `_detect_cross_page` 多列去重
- [ ] `_write_flagged_paragraphs` CSV fieldnames 扩 14 列 (+lemmas/token_count/language)
- [ ] `tests/ingest/pre_analysis/test_runner.py` 加 T1-T22 + 4 fixture 文件 (含 NER fixture)
- [ ] 中文 fixture PDF (`d81_dummy.pdf`) 端到端 `total_flagged ≥ 旧值`
- [ ] 英文 fixture (D81.1 段) 命中 `density ≥ 3` 的段 ≥ 5 段
- [ ] blocks mode (T6) + 中文 footer + 去重 (T7) + 推荐 weight (T11) + 安全 weight (T12) 全绿
- [ ] 多词 \b bug (T14) + 全角空格 normalize (T15) + 多列去重 (T16) 全绿
- [ ] spacy lemma (T17) + spacy sents (T18) + NER (T19) + tiktoken (T20) + spacy 模型缺失 503 (T21) + regex 全角标点 (T22) 全绿
- [ ] `uv run pytest tests/ingest/pre_analysis/` 全绿 (无新 fail)
- [ ] `uv run ruff format` 0 报错
- [ ] `uv run ruff check --fix` 0 报错
- [ ] `uv run pyright` 0 error

## 10. 关联

- [2026-07-02-pdf-pre-analysis-design.md](2026-07-02-pdf-pre-analysis-design.md) — 原始 spec
- [2026-07-06-table-extractor-adapter-design.md](2026-07-06-table-extractor-adapter-design.md) — table_extractors factory
- [2026-07-03-pre-analysis-stages-retry-design.md](2026-07-03-pre-analysis-stages-retry-design.md) — 5 stage wrap
- [CLAUDE.md §字典使用规范](../../../../packages/service/CLAUDE.md) — 未来字典化路径
- [联网核验报告 2026-07-07](#) (Explore agent 输出, 4 项必须修正: 7→4 类 / blocks 优先 / \b bug / 中文 footer)

## 11. 修订历史

| 日期 | 修订内容 | 来源 |
|---|---|---|
| 2026-07-07 v1 | spec 初稿: 7 类 + double_newline + 12 词 footer | 3 份 DeepSeek 综合 |
| 2026-07-07 v2 | 7 类→4 类 + 2 weight, blocks 优先, 多词 `\s+`, 中文 footer + 去重 | 联网核验 + 用户决策 |
| 2026-07-07 v3 | spacy 必选 (lemma/sents/NER) + regex 库 (全角标点/Unicode) + tiktoken token_count, CSV 12→14 列 | 项目依赖分析 + 用户决策 |