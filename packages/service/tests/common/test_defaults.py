"""common.defaults 测试

只测一件事: src/rag 下没有私自写的魔法字符串默认值。
存在性 + 字面值正确性都是 Python 自身的保证, 写测试反而是"重复源文件"。
"""

import re
from pathlib import Path

import pytest

# 集中地本身允许出现这些字面量
_DEFAULTS_PY = "defaults.py"

# 必须从 src/rag/common/defaults.py 读, 禁止在其它文件里硬编码
_FORBIDDEN = [
    (r'os\.getenv\([^)]+,\s*["\']', "os.getenv 字面量默认值"),
    (r'["\']bolt://', "neo4j URI 字面量"),
    (r'["\']http://localhost:\d+/', "localhost URL 字面量"),
    (r'["\']BAAI/bge-', "bge 模型名字面量 (HF 已移除)"),
    (r'["\']text-embedding-3-', "openai embed 模型名字面量"),
    (r'["\']gpt-4o-mini["\']', "gpt-4o-mini 字面量"),
    (r'["\']llama3["\']', "llama3 字面量"),
]


def _iter_python_files():
    return (p for p in Path("src/rag").rglob("*.py") if "__pycache__" not in str(p))


@pytest.mark.parametrize("pattern,reason", _FORBIDDEN)
def test_no_magic_string_default_outside_defaults_py(pattern, reason):
    """src/rag 下除 defaults.py 之外, 不准写魔法字符串默认值"""
    offenders: list[str] = []
    for py_file in _iter_python_files():
        if py_file.name == _DEFAULTS_PY:
            continue
        for lineno, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if re.search(pattern, line):
                offenders.append(f"  {py_file}:{lineno}: {line.strip()}")
    assert not offenders, f"魔法字符串默认值 ({reason}) 必须改用 src.common.defaults:\n" + "\n".join(offenders)


def test_defaults_module_exports_expected_constants():
    """defaults.py 必须有这些常量 (防止改名/误删)"""
    from src.common import defaults

    expected = [
        # OpenAI
        "DEFAULT_OPENAI_API_KEY",
        "DEFAULT_OPENAI_BASE_URL",
        "DEFAULT_LLM_MODEL_OPENAI",
        "DEFAULT_LLM_TYPE",
        # Ollama
        "DEFAULT_LLM_MODEL_OLLAMA",
        "DEFAULT_OLLAMA_BASE_URL",
        # Embed (2026-06-16: HF 已移除, 只剩 OpenAI 兼容)
        "DEFAULT_EMBED_MODEL_OPENAI",
        "DEFAULT_EMBED_BATCH_SIZE",
        # pgvector
        "DEFAULT_PG_HOST",
        "DEFAULT_PG_PORT",
        "DEFAULT_PG_USER",
        "DEFAULT_PG_PASSWORD",
        "DEFAULT_PG_DATABASE",
        # neo4j
        "DEFAULT_NEO4J_URI",
        "DEFAULT_NEO4J_USER",
        "DEFAULT_NEO4J_PASSWORD",
        "DEFAULT_NEO4J_DATABASE",
        # mem0 (self-host)
        "DEFAULT_MEM0_COLLECTION_NAME",
        "DEFAULT_LLM_MODEL",
        "DEFAULT_MEM0_SEARCH_LIMIT",
        "DEFAULT_MEM0_EMBED_PROVIDER",
        "DEFAULT_MEM0_EMBED_MODEL",
        # langfuse
        "DEFAULT_LANGFUSE_PUBLIC_KEY",
        "DEFAULT_LANGFUSE_SECRET_KEY",
        "DEFAULT_LANGFUSE_HOST",
        # ODA (CAD DWG 转换器路径)
        "DEFAULT_ODA_WIN_PATH",
        "DEFAULT_ODA_UNIX_PATH",
    ]
    missing = [name for name in expected if not hasattr(defaults, name)]
    assert not missing, f"defaults.py 缺少常量: {missing}"


def test_int_defaults_are_int_type():
    """数字默认值必须是 int, 避免 str(32) 这种 int(os.getenv(..., '32')) 的丑陋代码"""
    from src.common import defaults

    for name in (
        "DEFAULT_PG_PORT",
        "DEFAULT_EMBED_BATCH_SIZE",
    ):
        value = getattr(defaults, name)
        assert isinstance(value, int), f"{name} 必须是 int, 实际 {type(value).__name__}"
