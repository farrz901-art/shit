"""(2026-07-08 refactor) 段落标记主算法.

提取自 runner.py:510-615 私有方法 _extract_flagged_paragraphs + runner.py:87-108
私有类 CompiledRulePatterns. 输出 14 列 dict (spec §3.1):

  {matched_keywords, page, section, text,
   rule_categories (4 key: neg/obl/cond/perm),
   density, is_dense, raw_density, weighted_density,
   safe_hits, rec_hits, lemmas (JSON), token_count, language}

命中条件: 中文 in 子串 OR density > 0 (双轨并存, 中文 PDF 不退化).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .spacy_enhancer import _get_enhancer
from .splitter import split_paragraphs


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
    def from_config(cls, cfg: dict) -> CompiledRulePatterns:
        rp = cfg.get("rule_patterns", {}) or {}
        return cls(
            negation=re.compile(rp.get("negation", r"(?i)\bX\b")),
            obligation=re.compile(rp.get("obligation", r"(?i)\bX\b")),
            condition=re.compile(rp.get("condition", r"(?i)\bX\b")),
            permission=re.compile(rp.get("permission", r"(?i)\bX\b")),
        )


def extract_flagged_paragraphs(doc: Any, config: dict) -> list[dict]:
    """(2026-07-07 v3) 多语言 + 4 类正则 + safe/rec 权重 + 14 列 dict.

    Args:
      doc: pymupdf.Document (测试侧传 mock, 类型 Any 豁免)
      config: rule_keywords.yaml 反序列化字典

    Returns:
      list[dict] 14 keys (见模块 docstring).

    命中条件: 中文 in 子串 OR density > 0 (双轨并存, 中文 PDF 不退化).
    spacy enhance: 通过 _get_enhancer() 单例, 缺模型抛 RuntimeError 透传 (按 CLAUDE.md).
    """
    keywords = config.get("keywords", []) or []
    min_len = config.get("min_paragraph_length", 20)
    splitter_mode = config.get("paragraph_splitter", "blocks")
    max_sentence_chars = config.get("max_sentence_chars", 200)
    dense_threshold = config.get("dense_threshold", 3)
    safe_weight = config.get("safe_weight", 1.5)
    rec_weight = config.get("rec_weight", 0.5)
    compiled = CompiledRulePatterns.from_config(config)

    # safe / rec weight (不进入 rule_categories, 单独统计 + 加权)
    safe_pattern = re.compile(r"(?i)\b(danger|warning|caution|notice|safety|hazard|risk)\b")
    rec_pattern = re.compile(r"(?i)\b(recommend|advisable|usually|typically|suggested|preferred)\b")

    flagged: list[dict] = []
    for page_idx, page in enumerate(doc):
        # split_paragraphs 内部按 mode 调 page.get_text / page.get_text("blocks")
        paragraphs = split_paragraphs(page, splitter_mode, max_sentence_chars)

        for para_text in paragraphs:
            if len(para_text) < min_len:
                continue
            # 旧: 中文 in 子串 (兼容)
            matched = [kw for kw in keywords if kw in para_text]
            # 4 类 deontic
            rule_categories: dict[str, int] = {
                "neg": len(compiled.negation.findall(para_text)),
                "obl": len(compiled.obligation.findall(para_text)),
                "cond": len(compiled.condition.findall(para_text)),
                "perm": len(compiled.permission.findall(para_text)),
            }
            safe_hits = len(safe_pattern.findall(para_text))
            rec_hits = len(rec_pattern.findall(para_text))

            raw_density = sum(rule_categories.values())
            # 加权密度: safe +0.5/词, rec -0.5/词 (weight=1.5 → +0.5, weight=0.5 → -0.5)
            weighted_density = raw_density + safe_hits * (safe_weight - 1.0) + rec_hits * (rec_weight - 1.0)
            density = weighted_density
            is_dense = weighted_density >= dense_threshold

            if not (matched or density > 0):
                continue

            # v3 spacy 增强 (Task 4 后实化), 本步允许 enhancer 不存在
            enhancer = _get_enhancer()
            if enhancer is not None and hasattr(enhancer, "enhance"):
                enhanced = enhancer.enhance(para_text)
                # lemma 回扫 (mustn't → must not) — spec §4.4 第 432-433 行:
                # lemma_text = " ".join(lemmas), 然后用 re.findall(r"\bnot\b", lemma_text)
                # 替代原 "逐 token 精确等值比较", 因为 lemma 序列里 "not" 是单词,
                # 词边界 \bnot\b 在 " ".join 后必能匹配.
                lemmas = enhanced.get("lemmas", []) or []
                lemma_text = " ".join(lemmas)
                lemma_neg_extra = len(re.findall(r"\bnot\b", lemma_text))
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

            # cat_summary 必须在 lemma 回扫**之后**算 (spec §4.4 第 439 行),
            # 否则 CSV matched_keywords 列会漏掉 lemma 回扫贡献的 neg 命中
            cat_summary = ",".join(f"{k}={v}" for k, v in rule_categories.items() if v > 0)
            weight_summary: list[str] = []
            if safe_hits:
                weight_summary.append(f"safe={safe_hits}*{safe_weight}")
            if rec_hits:
                weight_summary.append(f"rec={rec_hits}*{rec_weight}")
            merged = matched + ([cat_summary] if cat_summary else []) + weight_summary

            flagged.append(
                {
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
                    "lemmas": lemmas_json,
                    "token_count": token_count,
                    "language": language,
                }
            )
    return flagged
