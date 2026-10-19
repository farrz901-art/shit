"""配置加载器 (2026-07-01 markdown extract KG spec)

读取 configs/extractors/*.yaml, env RAG_EXTRACTOR_CONFIG_DIR 可覆盖目录
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]  # src/kg/config_loader.py → packages/service
_CONFIG_DIR = Path(os.getenv("RAG_EXTRACTOR_CONFIG_DIR", str(_REPO_ROOT / "configs" / "extractors")))


def load_extractor_config(extractor_id: str) -> dict:
    """从 yaml 读 extractor 配置

    Args:
        extractor_id: e.g. "spacy_rule" / "llm_pydantic"

    Returns:
        dict (yaml 内容)
    """
    path = _CONFIG_DIR / f"{extractor_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"extractor config 不存在: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_extractor_ids() -> list[str]:
    """返 configs/extractors/ 下所有 .yaml 文件名 (sorted, 不含 .yaml 后缀)

    Returns:
        list[str], e.g. ["llm_pydantic", "spacy_rule"]
    """
    if not _CONFIG_DIR.exists():
        return []
    return sorted(p.stem for p in _CONFIG_DIR.glob("*.yaml") if p.stem)
