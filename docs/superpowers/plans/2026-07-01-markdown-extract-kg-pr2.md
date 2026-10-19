# Markdown Extract KG — PR2: Splitters + Extractors + 配置 + 迁移 (M3 + M4 + M5, v3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 把"无状态可独立测"的零件 (3 splitter + BaseExtractor + 2 extractor + 配置 + alembic 迁移含 dataset 字段) 一次性合。

**Scope (8 commits, ~9h):**
- Task 6 (M3): BaseSplitter Protocol + TextChunk + HeadingSplitter
- Task 7 (M3): TokenSplitter (tiktoken cl100k_base 滑窗)
- Task 8 (M3): SemanticSplitter (句切 + embedder cosine, 降级 heading)
- Task 9 (M4): BaseExtractor Protocol + 数据类
- Task 10 (M4): SpacyRuleExtractor
- Task 11 (M4): LlmPydanticExtractor
- Task 12 (M5): configs/extractors/ 2 yaml + config_loader
- Task 13 (M5): alembic 迁移 kg_extract_items (含 dataset 字段 + CHECK 约束, AST 验证禁真 PG)

**v3 调整**:
- **Extractor 白名单只 2 个**: spacy_rule / llm_pydantic (HanLP/mREBEL 已删)
- **kg_extract_items 表加 `dataset` 列**: 记录写哪个 dataset label
- **CHECK 约束校验 dataset 格式**: `^[A-Za-z_][A-Za-z0-9_]*$` 防注入
- **测试全 mock**: 模式 1 (含迁移 AST 验证, 禁真 PG)

## 项目规约 (PR2 必须遵守)

1. **测试 100% mock, 0 真实 PG/Neo4j/模型**: extractor 全部 mock, splitter 是纯函数
2. **业务 enum 走 lookup**: `extractor_id` / `splitter_id` 走 `src/lookups/`, 不许新增 `StrEnum`
3. **JSONB 列必用 `from sqlalchemy.dialects.postgresql import JSONB`**: 禁止 `sa.JSON()`
4. **alembic migration 可回滚**: upgrade + downgrade 都写, `downgrade -1 + upgrade head` 干净
5. **loguru 日志**: `logger.info("kg_extract done task={}", task_id)`
6. **PR 收尾必须跑**: `uv run pytest -q && uv run ruff format && uv run ruff check --fix && uv run pyright`

---

## Task 6: BaseSplitter Protocol + TextChunk + HeadingSplitter

**Files:**
- Create: `packages/service/src/kg/splitters/__init__.py` (空)
- Create: `packages/service/src/kg/splitters/base.py`
- Create: `packages/service/src/kg/splitters/heading.py`
- Test: `packages/service/tests/kg/splitters/__init__.py` (空)
- Test: `packages/service/tests/kg/splitters/test_heading.py` (4 个 test)

```python
# packages/service/src/kg/splitters/base.py
"""BaseSplitter Protocol + TextChunk dataclass"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class TextChunk:
    chunk_id: str   # sha256(source_uri + idx + text)[:12]
    text: str
    meta: dict = field(default_factory=dict)


@runtime_checkable
class BaseSplitter(Protocol):
    splitter_id: str
    def split(self, text: str, source_uri: str) -> list[TextChunk]: ...


def _make_chunk_id(text: str, source_uri: str, idx: int) -> str:
    h = hashlib.sha256(f"{source_uri}#{idx}".encode("utf-8"))
    h.update(text.encode("utf-8"))
    return h.hexdigest()[:12]


# packages/service/src/kg/splitters/heading.py
"""Heading 切: Markdown # / ## / ### 切, 保留 heading_path 层级"""
from __future__ import annotations

import re
from .base import TextChunk, _make_chunk_id

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


class HeadingSplitter:
    splitter_id = "heading"

    def split(self, text: str, source_uri: str) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        matches = list(_HEADING_RE.finditer(text))
        if not matches:
            return [TextChunk(
                chunk_id=_make_chunk_id(text, source_uri, 0),
                text=text,
                meta={"heading_path": [], "start_line": 0},
            )]

        for idx, m in enumerate(matches):
            start = m.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            section_text = text[start:end].rstrip()
            heading_path = self._build_heading_path(matches, idx)
            chunks.append(TextChunk(
                chunk_id=_make_chunk_id(section_text, source_uri, idx),
                text=section_text,
                meta={"heading_path": heading_path,
                      "start_line": text[:start].count("\n")},
            ))
        return chunks

    @staticmethod
    def _build_heading_path(matches, idx):
        path = []
        current_heading = matches[idx]
        current_level = current_heading.group(1).count("#")
        path.insert(0, current_heading.group(2).strip())
        for i in range(idx - 1, -1, -1):
            level = matches[i].group(1).count("#")
            if level < current_level:
                path.insert(0, matches[i].group(2).strip())
                current_level = level
                if current_level <= 1:
                    break
        return path
```

**4 个 test**:
- `test_heading_splitter_splits_at_h2`
- `test_heading_splitter_no_heading_returns_single_chunk`
- `test_heading_splitter_preserves_h3_under_h2`
- `test_heading_splitter_chunk_id_stable_same_input`

```bash
cd packages/service && uv run pytest tests/kg/splitters/test_heading.py -v
git add packages/service/src/kg/splitters/ packages/service/tests/kg/splitters/
git commit -m "feat(kg): BaseSplitter Protocol + HeadingSplitter (Markdown heading 切, 保留 path)"
```

---

## Task 7: TokenSplitter (tiktoken cl100k_base 滑窗)

**Files:**
- Create: `packages/service/src/kg/splitters/token.py`
- Test: `packages/service/tests/kg/splitters/test_token.py` (4 个 test)

```python
# packages/service/src/kg/splitters/token.py
"""Token 滑窗: tiktoken cl100k_base, 切窗口 + overlap"""
from __future__ import annotations
import tiktoken
from .base import TextChunk, _make_chunk_id

_ENCODER = tiktoken.get_encoding("cl100k_base")


class TokenSplitter:
    splitter_id = "token"

    def __init__(self, chunk_size: int = 512, overlap: int = 32):
        if overlap >= chunk_size:
            raise ValueError(f"overlap ({overlap}) 必须 < chunk_size ({chunk_size})")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str, source_uri: str) -> list[TextChunk]:
        tokens = _ENCODER.encode(text)
        if not tokens:
            return []

        chunks: list[TextChunk] = []
        stride = self.chunk_size - self.overlap
        idx = 0
        chunk_idx = 0
        while idx < len(tokens):
            window = tokens[idx:idx + self.chunk_size]
            chunk_text = _ENCODER.decode(window)
            chunks.append(TextChunk(
                chunk_id=_make_chunk_id(chunk_text, source_uri, chunk_idx),
                text=chunk_text,
                meta={"start_token": idx, "token_count": len(window)},
            ))
            idx += stride
            chunk_idx += 1
        return chunks
```

```bash
git add packages/service/src/kg/splitters/token.py packages/service/tests/kg/splitters/test_token.py
git commit -m "feat(kg): TokenSplitter (tiktoken cl100k_base 滑窗, overlap 默认 32)"
```

---

## Task 8: SemanticSplitter (句切 + embedder cosine 距离, 降级 heading)

**Files:**
- Create: `packages/service/src/kg/splitters/semantic.py`
- Test: `packages/service/tests/kg/splitters/test_semantic.py` (4 个 test)

```python
# packages/service/src/kg/splitters/semantic.py
"""Semantic 切: 句切 + embedder cosine 距离"""
from __future__ import annotations

import math
import re
from loguru import logger
from .base import TextChunk, _make_chunk_id
from .heading import HeadingSplitter

_SENT_RE = re.compile(r"[^。！？.!?]+[。！？.!?]+")


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticSplitter:
    splitter_id = "semantic"

    def __init__(
        self,
        embedder,
        cosine_threshold: float = 0.5,
        min_chunk_size: int = 200,
        max_chunk_size: int = 2000,
    ):
        self.embedder = embedder
        self.cosine_threshold = cosine_threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

    def split(self, text: str, source_uri: str) -> list[TextChunk]:
        try:
            sentences = [s.strip() for s in _SENT_RE.findall(text) if s.strip()]
            if not sentences:
                return HeadingSplitter().split(text, source_uri)
            embeddings = self.embedder.embed_batch(sentences)
            return self._merge_by_cosine(sentences, embeddings, source_uri)
        except Exception as e:
            logger.warning("SemanticSplitter 降级到 HeadingSplitter ({}): {}", source_uri, e)
            return HeadingSplitter().split(text, source_uri)

    def _merge_by_cosine(self, sentences, embeddings, source_uri):
        chunks: list[TextChunk] = []
        current_group: list[str] = []
        current_text = ""
        for idx, (sent, emb) in enumerate(zip(sentences, embeddings)):
            if not current_group:
                current_group.append(sent)
                current_text = sent
                continue
            prev_emb = embeddings[idx - 1]
            dist = 1.0 - _cosine(prev_emb, emb)
            if dist < self.cosine_threshold and len(current_text) < self.max_chunk_size:
                current_group.append(sent)
                current_text += sent
            else:
                if len(current_text) >= self.min_chunk_size or not chunks:
                    chunks.append(TextChunk(
                        chunk_id=_make_chunk_id(current_text, source_uri, len(chunks)),
                        text=current_text,
                        meta={"start_idx": idx - len(current_group),
                              "sentence_count": len(current_group)},
                    ))
                current_group = [sent]
                current_text = sent
        if current_text:
            chunks.append(TextChunk(
                chunk_id=_make_chunk_id(current_text, source_uri, len(chunks)),
                text=current_text,
                meta={"start_idx": len(sentences) - len(current_group),
                      "sentence_count": len(current_group)},
            ))
        return chunks
```

```bash
git add packages/service/src/kg/splitters/semantic.py packages/service/tests/kg/splitters/test_semantic.py
git commit -m "feat(kg): SemanticSplitter (句切 + cosine 距离, 降级 heading)"
```

---

## Task 9: BaseExtractor Protocol + 数据类

**Files:**
- Create: `packages/service/src/kg/extractors/__init__.py` (空)
- Create: `packages/service/src/kg/extractors/base.py`
- Test: `packages/service/tests/kg/extractors/test_base.py` (6 个 test)

```python
# packages/service/src/kg/extractors/base.py
"""BaseExtractor Protocol + 数据类 (2026-07-01 v3, v1 HanLP/mREBEL 已删)

RuleType 一等公民: 把隐性规则 (兼容/依赖/互斥/降容) 升到显式标签
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

RuleType = Literal["compatibility", "dependency", "exclusion", "derating", "factual"]


@dataclass
class ExtractedEntity:
    text: str
    label: str
    chunk_id: str
    char_span: tuple[int, int]
    confidence: float = 1.0


@dataclass
class ExtractedRelation:
    head: str
    rel_type: str
    tail: str
    chunk_id: str
    confidence: float = 1.0
    rule_type: RuleType = "factual"


@dataclass
class ExtractionResult:
    entities: list[ExtractedEntity] = field(default_factory=list)
    relations: list[ExtractedRelation] = field(default_factory=list)
    extractor_id: str = ""
    elapsed_ms: int = 0
    error: str | None = None


@runtime_checkable
class BaseExtractor(Protocol):
    extractor_id: str
    def extract(self, chunks: list) -> ExtractionResult: ...
```

```bash
git add packages/service/src/kg/extractors/ packages/service/tests/kg/extractors/
git commit -m "feat(kg): BaseExtractor Protocol + ExtractedEntity/Relation/Result + RuleType Literal"
```

---

## Task 10: SpacyRuleExtractor (spaCy Matcher + EntityRuler + "X 是 Y 的" 规则)

**Files:**
- Create: `packages/service/src/kg/extractors/spacy_rule/__init__.py` (空)
- Create: `packages/service/src/kg/extractors/spacy_rule/extractor.py`
- Test: 3 个 test (mock nlp)

```python
# packages/service/src/kg/extractors/spacy_rule/extractor.py
"""spaCy 规则抽取器 (2026-07-01 spec, v3 保留)"""
from __future__ import annotations

import re
from ..base import ExtractedEntity, ExtractedRelation, ExtractionResult

_IS_TYPE_RE = re.compile(r"(.+?)\s+是\s+(.+?)的")


class SpacyRuleExtractor:
    extractor_id = "spacy_rule"

    def __init__(self, nlp=None):
        self.nlp = nlp

    def extract(self, chunks: list) -> ExtractionResult:
        if self.nlp is None:
            return ExtractionResult(extractor_id=self.extractor_id, error="spaCy nlp 未初始化")
        entities: list[ExtractedEntity] = []
        relations: list[ExtractedRelation] = []
        for chunk in chunks:
            doc = self.nlp(chunk.text)
            for ent in doc.ents:
                entities.append(ExtractedEntity(
                    text=ent.text, label=ent.label_,
                    chunk_id=chunk.chunk_id,
                    char_span=(ent.start_char, ent.end_char),
                ))
        for chunk in chunks:
            for m in _IS_TYPE_RE.finditer(chunk.text):
                head, tail = m.group(1).strip(), m.group(2).strip()
                relations.append(ExtractedRelation(
                    head=head, rel_type="IS_TYPE_OF", tail=tail,
                    chunk_id=chunk.chunk_id, rule_type="factual",
                ))
        return ExtractionResult(
            entities=entities, relations=relations,
            extractor_id=self.extractor_id, elapsed_ms=0,
        )
```

```bash
git add packages/service/src/kg/extractors/spacy_rule/ packages/service/tests/kg/extractors/spacy_rule/
git commit -m "feat(kg): SpacyRuleExtractor (Matcher + EntityRuler + 'X 是 Y 的' 模式)"
```

---

## Task 11: LlmPydanticExtractor (主力, OpenAI 兼容 + JSON Schema 强约束 + tenacity retry)

**Files:**
- Create: `packages/service/src/kg/extractors/llm_pydantic/__init__.py` (空)
- Create: `packages/service/src/kg/extractors/llm_pydantic/extractor.py`
- Create: `packages/service/configs/extractors/llm_pydantic.prompt.txt`
- Test: 4 个 test (mock LLM)

```python
# packages/service/src/kg/extractors/llm_pydantic/extractor.py
"""LLM + Pydantic 强约束抽取器 (主力, 2026-07-01 spec, v3)"""
from __future__ import annotations

import json
from ..base import ExtractedEntity, ExtractedRelation, ExtractionResult


class LlmPydanticExtractor:
    extractor_id = "llm_pydantic"

    def __init__(self, llm=None, prompt_template: str = "", max_retries: int = 3):
        self.llm = llm
        self.prompt_template = prompt_template or _DEFAULT_PROMPT
        self.max_retries = max_retries

    def extract(self, chunks: list) -> ExtractionResult:
        if self.llm is None:
            return ExtractionResult(extractor_id=self.extractor_id, error="LLM 未初始化")
        entities: list[ExtractedEntity] = []
        relations: list[ExtractedRelation] = []
        for chunk in chunks:
            response_text = self._call_llm_with_retry(chunk.text)
            try:
                data = json.loads(response_text)
            except json.JSONDecodeError:
                continue
            for e in data.get("entities", []):
                span = e.get("span", [0, 0])
                entities.append(ExtractedEntity(
                    text=e["text"], label=e["label"], chunk_id=chunk.chunk_id,
                    char_span=(span[0], span[1]) if len(span) == 2 else (0, 0),
                    confidence=e.get("confidence", 1.0),
                ))
            for r in data.get("relations", []):
                relations.append(ExtractedRelation(
                    head=r["head"], rel_type=r["rel_type"], tail=r["tail"],
                    chunk_id=chunk.chunk_id, confidence=r.get("confidence", 1.0),
                    rule_type=r.get("rule_type", "factual"),
                ))
        return ExtractionResult(entities=entities, relations=relations,
                                extractor_id=self.extractor_id, elapsed_ms=0)

    def _call_llm_with_retry(self, chunk_text: str) -> str:
        from tenacity import retry, stop_after_attempt, wait_exponential
        @retry(stop=stop_after_attempt(self.max_retries), wait=wait_exponential(min=1, max=10))
        def _call():
            return self.llm.chat(messages=[
                {"role": "system", "content": self.prompt_template},
                {"role": "user", "content": chunk_text},
            ])
        return _call()


_DEFAULT_PROMPT = """从以下中文 Markdown 文本抽取实体和关系. 严格返 JSON 格式, 不要任何额外解释:

{
  "entities": [{"text": "...", "label": "Product|Series|Spec|Standard", "span": [start, end], "confidence": 0.0-1.0}],
  "relations": [{"head": "...", "rel_type": "HAS_SPEC|BELONGS_TO|MATCHES|IS_TYPE_OF", "tail": "...",
                  "rule_type": "compatibility|dependency|exclusion|derating|factual", "confidence": 0.0-1.0}]
}

rule_type 必填, 5 选 1:
- compatibility: 兼容关系
- dependency: 依赖关系
- exclusion: 互斥关系
- derating: 降容关系
- factual: 事实陈述 (默认)

只输出 JSON, 不输出解释文字."""
```

```bash
git add packages/service/src/kg/extractors/llm_pydantic/ packages/service/configs/extractors/llm_pydantic.prompt.txt packages/service/tests/kg/extractors/llm_pydantic/
git commit -m "feat(kg): LlmPydanticExtractor (OpenAI 兼容 + JSON Schema 强约束 prompt + tenacity retry)"
```

---

## Task 12: configs/extractors/ 2 个 yaml + config_loader

**Files:**
- Create: `packages/service/configs/extractors/spacy_rule.yaml`
- Create: `packages/service/configs/extractors/llm_pydantic.yaml`
- Create: `packages/service/src/kg/config_loader.py`
- Test: `packages/service/tests/kg/test_config_loader.py`

```yaml
# configs/extractors/spacy_rule.yaml
extractor_id: spacy_rule
enabled: true
spacy_model: zh_core_web_sm
patterns:
  - label: Product
    pattern: "\\d[A-Z]{2}\\d{4}-[A-Z0-9]+"

# configs/extractors/llm_pydantic.yaml
extractor_id: llm_pydantic
enabled: true
llm_provider: ""    # env: RAG_LLM_PROVIDER
model: ""           # env: RAG_LLM_MODEL
temperature: 0.0

# 注: hanlp.yaml 和 rebel.yaml 已删除 (2026-07-01 调研: HanLP 无 RE API, mREBEL 3 年无更新)
```

```python
# packages/service/src/kg/config_loader.py
import os
from pathlib import Path
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_DIR = Path(os.getenv("RAG_EXTRACTOR_CONFIG_DIR", str(_REPO_ROOT / "configs" / "extractors")))


def load_extractor_config(extractor_id: str) -> dict:
    path = _CONFIG_DIR / f"{extractor_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"extractor config 不存在: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_extractor_ids() -> list[str]:
    if not _CONFIG_DIR.exists():
        return []
    return sorted(p.stem for p in _CONFIG_DIR.glob("*.yaml") if p.stem)
```

```bash
git add packages/service/configs/extractors/ packages/service/src/kg/config_loader.py packages/service/tests/kg/test_config_loader.py
git commit -m "feat(kg): 2 个 extractor yaml + config_loader (hanlp/rebel 已删除)"
```

---

## Task 13: alembic 迁移 kg_extract_items (含 dataset 字段 + CHECK 约束, AST 验证禁真 PG)

**Files:**
- Create: `packages/service/src/storage/migrations/versions/20260701_kg_extract_items.py`
- Test: `packages/service/tests/migrations/test_kg_extract_items.py` (**AST 验证 + SQL 文本校验, 禁真 PG**)

**v3 关键调整**:
- 加 `dataset` 字段 (NOT NULL, CHECK 格式 `^[A-Za-z_][A-Za-z0-9_]*$`)
- 索引用 `(task_id, dataset)` 不是 `(task_id, user_hash)`
- **测试走 AST + SQL 文本 grep, 不连 PG** (CLAUDE.md §测试隔离 强制)

```python
# packages/service/src/storage/migrations/versions/20260701_kg_extract_items.py
"""kg_extract_items: 临时存储抽取结果 (2026-07-01 v3)

v3 字段: 加 dataset (Neo4j dataset label, env 白名单 KG_ALLOWED_DATASETS)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260701_kg_extract_items"
down_revision = "<上一条 migration>"  # 实际查现有 revisions
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kg_extract_items",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("task_id", sa.Text, nullable=False),
        sa.Column("dataset", sa.Text, nullable=False),  # v3: 写哪个 dataset
        sa.Column("extractor", sa.Text, nullable=False),
        sa.Column("splitter", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("selected", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("chunk_id", sa.Text),
        sa.Column("corrected_payload", JSONB),
        sa.Column("confirmed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("kind IN ('entity', 'relation')", name="ck_kg_extract_items_kind"),
        sa.CheckConstraint(
            "dataset ~ '^[A-Za-z_][A-Za-z0-9_]*$'",
            name="ck_kg_extract_items_dataset_format",
        ),
    )
    op.create_index("ix_kg_extract_items_task_dataset", "kg_extract_items", ["task_id", "dataset"])
    op.create_index(
        "ix_kg_extract_items_dataset_created",
        "kg_extract_items",
        ["dataset", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_kg_extract_items_dataset_confirmed",
        "kg_extract_items",
        ["dataset", "confirmed_at"],
        postgresql_where=sa.text("confirmed_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_kg_extract_items_dataset_confirmed", table_name="kg_extract_items")
    op.drop_index("ix_kg_extract_items_dataset_created", table_name="kg_extract_items")
    op.drop_index("ix_kg_extract_items_task_dataset", table_name="kg_extract_items")
    op.drop_table("kg_extract_items")
```

**AST 验证测试** (不连 PG):

```python
# packages/service/tests/migrations/test_kg_extract_items.py
"""kg_extract_items 迁移 AST 验证 + SQL 文本 (CLAUDE.md 禁真 PG)"""
import ast
from pathlib import Path


MIGRATION_FILE = Path("packages/service/src/storage/migrations/versions/20260701_kg_extract_items.py")


def test_migration_file_exists():
    """migration 文件存在"""
    assert MIGRATION_FILE.exists(), f"找不到 migration 文件: {MIGRATION_FILE}"


def test_migration_has_upgrade_and_downgrade():
    """必含 upgrade() + downgrade() 两条函数"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fns = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "upgrade" in fns
    assert "downgrade" in fns


def test_migration_uses_jsonb_not_sa_json():
    """v3: payload / corrected_payload 用 JSONB 不是 sa.JSON()"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    # 检查导入
    assert "from sqlalchemy.dialects.postgresql import JSONB" in source
    # 检查没用 sa.JSON()
    assert "sa.JSON()" not in source


def test_migration_has_dataset_field():
    """v3: 必含 dataset 字段 + CHECK 约束"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert '"dataset"' in source or "'dataset'" in source
    assert "dataset ~ " in source  # CHECK 约束


def test_migration_no_user_hash():
    """v3: 不要 user_hash 残留 (v1 设计, v3 已删)"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert "user_hash" not in source
```

```bash
cd packages/service && uv run pytest tests/migrations/test_kg_extract_items.py -v
git add packages/service/src/storage/migrations/versions/20260701_kg_extract_items.py packages/service/tests/migrations/test_kg_extract_items.py
git commit -m "feat(kg): alembic 迁移 kg_extract_items (JSONB + dataset 字段 + CHECK 约束, AST 验证禁真 PG)"
```

---

## PR2 收尾验证

```bash
cd packages/service
uv run pytest tests/kg/splitters/ tests/kg/extractors/ tests/kg/test_config_loader.py tests/migrations/ -v
uv run ruff format && uv run ruff check --fix && uv run pyright
```