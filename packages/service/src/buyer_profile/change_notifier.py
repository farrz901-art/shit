"""buyer_profile/change_notifier.py: 字段变更检测 + 通知 (2026-06-22)

在 update_profile_fields 中被调用:
1. detect_changes: 比较 old / new 找出变更
2. log_changes:    写入 profile_change_logs 表
3. check_and_notify: 根据 notify_on_change 规则触发通知 (Phase 1 仅 log)
"""

from __future__ import annotations

import json

from loguru import logger
from sqlalchemy import text

from src.storage.session import session_scope


def detect_changes(old_data: dict, new_values: dict) -> list[dict]:
    """比较旧的 profile_data 和新的提取值, 返回变更列表.

    每个 change 包含:
        field_code: 字段 code
        old_value:  旧值 (或 None)
        new_value:  新值
    """
    changes: list[dict] = []
    for code, new_val in new_values.items():
        if new_val is None:
            continue
        old_entry = old_data.get(code, {})
        old_val = old_entry.get("value") if isinstance(old_entry, dict) else old_entry
        if str(old_val) != str(new_val):
            changes.append(
                {
                    "field_code": code,
                    "old_value": old_val,
                    "new_value": new_val,
                }
            )
    return changes


def log_changes(
    account_id: int,
    profile_id: str,
    changes: list[dict],
    source: str = "auto",
    conv_id: str | None = None,
) -> None:
    """将变更记录写入 profile_change_logs 表."""
    if not changes:
        return
    query = """INSERT INTO profile_change_logs
        (account_id, profile_id, field_code, old_value, new_value, source, conv_id)
        VALUES (:aid, :pid, :code, :old, :new, :src, :conv)"""
    with session_scope() as sess:
        for ch in changes:
            sess.execute(
                text(query),
                {
                    "aid": account_id,
                    "pid": profile_id,
                    "code": ch["field_code"],
                    "old": json.dumps(ch.get("old_value")),
                    "new": json.dumps(ch.get("new_value")),
                    "src": source,
                    "conv": conv_id,
                },
            )


def check_and_notify(
    account_id: int,
    changes: list[dict],
    configs: list[dict],
) -> None:
    """检查变更是否触发通知规则.

    Phase 1: 仅 log 通知事件 (不实际发送).
    Phase 2: 接入 email / webhook 等.

    通知规则定义在 profile_field_configs.notify_on_change JSONB 列:
        [{"type": "value_in", "values": ["high_priority", ...]}]
    """
    for change in changes:
        cfg = next(
            (c for c in configs if c["code"] == change["field_code"]),
            None,
        )
        if not cfg:
            continue
        rules = cfg.get("notify_on_change") or []
        for rule in rules:
            if isinstance(rule, dict) and rule.get("type") == "value_in":
                if change["new_value"] in (rule.get("values") or []):
                    logger.info(
                        "资料变更触发通知 aid={} field={} new={}",
                        account_id,
                        change["field_code"],
                        change["new_value"],
                    )
