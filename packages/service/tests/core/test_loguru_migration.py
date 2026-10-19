"""验证 9 个模块全部用 loguru, 不再用 stdlib logging (2026-06-18 sync)

用 grep 验证. 模式 1, 0 PG.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SERVICE_SRC = Path(__file__).parent.parent.parent / "src"

LOGURU_MIGRATED_FILES = [
    "chat_share/router.py",
    "chat_share/service.py",
    "memory/mem0_client.py",
    "memory/router.py",
    "memory/service.py",
    "storage/object_store.py",
    "auth/account_settings_service.py",
    "scheduler/deletion.py",
]


@pytest.mark.parametrize("rel_path", LOGURU_MIGRATED_FILES)
def test_module_uses_loguru_not_stdlib(rel_path: str):
    file = SERVICE_SRC / rel_path
    assert file.exists(), f"{rel_path} 不存在 (LOGURU_MIGRATED_FILES 列表过时, 删条目)"
    content = file.read_text(encoding="utf-8")
    assert "from loguru import logger" in content, f"{rel_path} 没 import loguru.logger"
    assert "logging.getLogger(__name__)" not in content, f"{rel_path} 还在用 stdlib logging.getLogger"


def test_no_logger_init_in_migrated_modules():
    for rel in LOGURU_MIGRATED_FILES:
        file = SERVICE_SRC / rel
        if not file.exists():
            continue
        content = file.read_text(encoding="utf-8")
        bad = re.findall(r"logger\s*=\s*logging\.getLogger", content)
        assert not bad, f"{rel} 含旧 logger init: {bad}"
