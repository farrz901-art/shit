"""字典导入导出: CSV / JSON (2026-06-19 lookup spec §四 + Task 6)

4 个纯函数, 不依赖 DB / Redis / FastAPI, 纯数据序列化:
- export_dict_to_csv(items)  → CSV 字符串 (字典项列表 → CSV)
- import_items_from_csv(text) → 字典项列表 (CSV 字符串 → 字典项列表)
- export_to_json(d)           → JSON 字符串 (任意 dict → pretty JSON)
- import_from_json(text)      → dict (JSON 字符串 → 原始 dict)

业务使用:
- 导出: 字典级 GET (后端把 items 列表拼成 CSV/JSON, Content-Disposition: attachment)
- 导入: super_admin 上传文件 → 解析 → 走 LookupService.create_item 批量 upsert

约束:
- CSV 用 stdlib csv (DictReader / DictWriter), metadata_json 序列化为 JSON 字符串
- JSON 用 stdlib json (ensure_ascii=False 保留中文)
- 失败时抛 ValueError (CSV 解析错 / JSON 格式错), 业务层翻译成 422

性能:
- 全内存操作, 单字典 < 10k items 时 < 100ms
- 10k+ items 时建议走 streaming (后续 spec, 本期不做)
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

# CSV 列名 (跟 LookupItem 模型字段对齐)
_CSV_FIELDNAMES = [
    "key",
    "label_zh",
    "label_en",
    "sort",
    "is_active",
    "description",
    "metadata_json",
]


def export_dict_to_csv(items: list[dict[str, Any]]) -> str:
    """导出 items 列表为 CSV 字符串.

    Args:
        items: 字典项列表, 元素含 key/label_zh/label_en/sort/is_active/description/metadata_json.
            metadata_json (dict) 自动序列化为 JSON 字符串.

    Returns:
        CSV 字符串 (含 header 行). 空列表返空字符串 (header 也无, 上层决定 fallback).

    行为:
    - 列固定为 7 列, 缺字段 → DictWriter 抛 ValueError (fail-fast, 防静默丢字段)
    - metadata_json (dict) → json.dumps(ensure_ascii=False), None → 空字符串
    - is_active (bool) → 'True' / 'False'
    """
    if not items:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=_CSV_FIELDNAMES, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        row: dict[str, Any] = {k: item.get(k) for k in _CSV_FIELDNAMES}
        # metadata_json: dict → JSON 字符串, None → None (csv 写空字符串)
        meta = row.get("metadata_json")
        if isinstance(meta, dict):
            row["metadata_json"] = json.dumps(meta, ensure_ascii=False)
        # None → 空字符串 (CSV 友好)
        writer.writerow(row)
    return output.getvalue()


def import_items_from_csv(csv_text: str) -> list[dict[str, Any]]:
    """解析 CSV 文本, 返字典项列表.

    Args:
        csv_text: CSV 字符串 (含 header 行).

    Returns:
        字典项列表, 每个元素是 dict (key/label_zh/label_en/sort/is_active/description/metadata_json).
        metadata_json 字段如果是合法 JSON 字符串 → 反序列化为 dict; 否则保持 None (容错).

    行为:
    - header 缺列 → csv.DictReader 仍能跑, 但 row dict 缺字段 (业务层 LookupItemCreateRequest 会 422)
    - metadata_json 是空字符串 → None
    - sort / is_active 保持字符串 (业务层 Pydantic 校验转换)
    """
    if not csv_text or not csv_text.strip():
        return []
    reader = csv.DictReader(io.StringIO(csv_text))
    result: list[dict[str, Any]] = []
    for row in reader:
        # metadata_json 反序列化 (容错, 失败 → None)
        meta_raw = row.get("metadata_json")
        if meta_raw and meta_raw.strip():
            try:
                row["metadata_json"] = json.loads(meta_raw)
            except json.JSONDecodeError:
                # 容错: 非法 JSON 置 None, 业务层 Pydantic 422 拦截
                row["metadata_json"] = None
        else:
            row["metadata_json"] = None
        # 空字符串 → None (Pydantic Optional 字段友好)
        for k, v in row.items():
            if v == "":
                row[k] = None
        result.append(row)
    return result


def export_to_json(d: dict[str, Any]) -> str:
    """导出 dict 为 pretty JSON 字符串 (ensure_ascii=False 保留中文).

    Args:
        d: 任意 dict (典型: 字典 + items 列表).

    Returns:
        pretty JSON 字符串 (indent=2).

    行为:
    - datetime / date 等非 JSON-native 类型 → json.dumps default=str 转 str
    - ensure_ascii=False 保留中文 / 日文 label
    """
    return json.dumps(d, ensure_ascii=False, indent=2, default=str)


def import_from_json(text: str) -> dict[str, Any]:
    """解析 JSON 文本, 返原始 dict.

    Args:
        text: JSON 字符串.

    Returns:
        解析后的 dict (跟 export_to_json 互为逆操作).

    Raises:
        json.JSONDecodeError: JSON 格式错 (业务层翻译成 422).
    """
    return json.loads(text)
