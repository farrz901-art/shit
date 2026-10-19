"""验证 hook 已加 @audited (grep 验证, 模式 1)

覆盖 2026-06-18 sync 版 spec §9 P0+P1+P2+P3 全表.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SERVICE_SRC = Path(__file__).parent.parent.parent / "src"

# (file, action, target_type) — 2026-06-18 sync: 按实际代码重对齐
EXPECTED_HOOKS = [
    # P0 账户安全
    ("auth/account_settings_router.py", "email.change", "user"),
    ("auth/account_settings_router.py", "password.change", "user"),
    ("auth/account_settings_router.py", "account.delete", "user"),
    ("auth/account_settings_router.py", "avatar.delete", "avatar"),
    ("auth/account_settings_router.py", "deletion.cancel", "user"),
    ("auth/auth_account_router.py", "password.reset", "user"),
    ("auth/router.py", "api_key.create", "api_key"),
    ("auth/router.py", "api_key.revoke", "api_key"),
    ("auth/auth_admin_router.py", "role.change", "user"),
    ("auth/auth_admin_router.py", "account.disable", "user"),
    ("auth/auth_admin_router.py", "account.enable", "user"),
    # P1 数据操作
    ("eval/router.py", "evaluation.run", "evaluation"),
    ("eval/router.py", "evaluation.cancel", "evaluation"),
    # P2 资源访问
    ("ingest/pdf_processing/router.py", "files.bulk_download", "file"),
    # P3 业务
    ("auth/auth_invite_router.py", "user.invite", "user"),
    ("memory/router.py", "memory.purge_all", "memory"),
    ("memory/router.py", "memory.delete", "memory"),
]


@pytest.mark.parametrize("rel_path,action,target_type", EXPECTED_HOOKS)
def test_hook_present(rel_path: str, action: str, target_type: str):
    """文件含 @audited("action", target_type="...")"""
    file = SERVICE_SRC / rel_path
    assert file.exists(), f"{rel_path} 不存在 (这是开发期错配, 应进 EXPECTED_HOOKS 之前先 mkdir)"
    content = file.read_text(encoding="utf-8")
    pattern = re.compile(
        rf'@audited\(\s*[\'"]{re.escape(action)}[\'"]\s*,\s*target_type\s*=\s*[\'"]{re.escape(target_type)}[\'"]'
    )
    assert pattern.search(content), f"{rel_path} 缺 @audited('{action}', target_type='{target_type}')"


def test_audit_import_in_endpoint_files():
    """每个加了 hook 的文件必须 import @audited"""
    files = {h[0] for h in EXPECTED_HOOKS}
    for rel in files:
        file = SERVICE_SRC / rel
        if not file.exists():
            continue
        content = file.read_text(encoding="utf-8")
        assert (
            "from src.core.audit import" in content
            or "from ..core.audit import" in content
            or "from ...core.audit import" in content
        ), f"{rel} 没 import audited"
