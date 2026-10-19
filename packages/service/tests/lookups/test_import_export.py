"""import_export 4 函数测试 (2026-06-19 lookup spec Task 6, 模式 1 纯函数)

CLAUDE.md 规范: 纯函数测试, 不连 PG / Redis / FastAPI. 直接调用
src.lookups.import_export 的 4 个函数, 验证输入/输出.

测试矩阵 (8):
1. test_export_dict_to_csv_empty           — 空 items → 空字符串
2. test_export_dict_to_csv_with_items      — 正常 items → CSV 含 header + 行
3. test_export_dict_to_csv_serializes_metadata_json  — dict → JSON 字符串
4. test_import_items_from_csv_round_trip   — export → import 还原 items
5. test_import_items_from_csv_with_metadata_json      — JSON 字符串 → dict
6. test_import_items_from_csv_empty        — 空字符串 → []
7. test_export_to_json_round_trip         — JSON 含中文保留
8. test_import_from_json_returns_dict      — JSON → dict
"""

from __future__ import annotations

import csv
import io
import json

import pytest

from src.lookups.import_export import (
    export_dict_to_csv,
    export_to_json,
    import_from_json,
    import_items_from_csv,
)

# ==================== export_dict_to_csv ====================


def test_export_dict_to_csv_empty():
    """空 items → 空字符串 (不写 header)."""
    assert export_dict_to_csv([]) == ""


def test_export_dict_to_csv_with_items():
    """正常 items → CSV 含 header + 行 (列名固定 7 列)."""
    items = [
        {
            "key": "duplicate",
            "label_zh": "重复",
            "label_en": "Duplicate",
            "sort": 1,
            "is_active": True,
            "description": "完全重复内容",
            "metadata_json": None,
        },
        {
            "key": "other",
            "label_zh": "其他",
            "label_en": "Other",
            "sort": 99,
            "is_active": True,
            "description": None,
            "metadata_json": None,
        },
    ]
    csv_text = export_dict_to_csv(items)

    # 验证 header
    assert csv_text.startswith("key,label_zh,label_en,sort,is_active,description,metadata_json")
    # 验证行内容
    assert "duplicate" in csv_text
    assert "完全重复内容" in csv_text
    assert "重复" in csv_text
    # 验证能用 DictReader 解析回来
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["key"] == "duplicate"
    assert rows[0]["label_zh"] == "重复"
    assert rows[1]["key"] == "other"
    assert rows[1]["description"] == ""  # None → 空字符串


def test_export_dict_to_csv_serializes_metadata_json():
    """metadata_json (dict) → JSON 字符串 (ensure_ascii=False 保留中文)."""
    items = [
        {
            "key": "admin",
            "label_zh": "管理",
            "label_en": "Admin",
            "sort": 1,
            "is_active": True,
            "description": None,
            "metadata_json": {"path": "/admin", "icon": "设置"},
        }
    ]
    csv_text = export_dict_to_csv(items)
    # 验证 metadata_json 字段被序列化为 JSON 字符串 (DictWriter 自动 quote 含逗号的值)
    # 验证中文被保留 (ensure_ascii=False)
    assert "管理" in csv_text
    assert "设置" in csv_text
    # 验证能用 DictReader 解析回来, metadata_json 字段是 JSON 字符串
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    assert len(rows) == 1
    # raw metadata_json 是 JSON 字符串 (csv 解析保持), 反序列化验证
    meta_raw = rows[0]["metadata_json"]
    assert meta_raw is not None and meta_raw != ""
    parsed = json.loads(meta_raw)
    assert parsed == {"path": "/admin", "icon": "设置"}


# ==================== import_items_from_csv ====================


def test_import_items_from_csv_round_trip():
    """export → import 还原 items (除空字符串 → None 差异)."""
    original = [
        {
            "key": "duplicate",
            "label_zh": "重复",
            "label_en": "Duplicate",
            "sort": 1,
            "is_active": True,
            "description": "完全重复",
            "metadata_json": None,
        },
        {
            "key": "other",
            "label_zh": "其他",
            "label_en": "Other",
            "sort": 99,
            "is_active": True,
            "description": None,
            "metadata_json": None,
        },
    ]
    csv_text = export_dict_to_csv(original)
    imported = import_items_from_csv(csv_text)

    assert len(imported) == 2
    assert imported[0]["key"] == "duplicate"
    assert imported[0]["label_zh"] == "重复"
    assert imported[0]["sort"] == "1"  # csv 解析保持字符串
    assert imported[0]["is_active"] == "True"  # csv 解析保持字符串
    assert imported[0]["description"] == "完全重复"
    assert imported[0]["metadata_json"] is None
    assert imported[1]["key"] == "other"
    assert imported[1]["description"] is None  # 空字符串 → None


def test_import_items_from_csv_with_metadata_json():
    """metadata_json 字段合法 JSON → 反序列化为 dict.

    注: DictWriter 会把含逗号的字段 quote 起来 (CSV 标准), 反序列化要先用 DictReader 解析回原始 JSON 字符串.
    """
    # 用 export_dict_to_csv 生成 round-trip 友好的 CSV (而非手写)
    items_csv = export_dict_to_csv(
        [
            {
                "key": "admin",
                "label_zh": "管理",
                "label_en": "Admin",
                "sort": 1,
                "is_active": True,
                "description": None,
                "metadata_json": {"path": "/admin", "icon": "设置"},
            }
        ]
    )
    imported = import_items_from_csv(items_csv)

    assert len(imported) == 1
    assert imported[0]["key"] == "admin"
    # metadata_json 是 dict (import_items_from_csv 自动反序列化)
    assert imported[0]["metadata_json"] == {"path": "/admin", "icon": "设置"}


def test_import_items_from_csv_empty():
    """空字符串 / 仅空白 → []."""
    assert import_items_from_csv("") == []
    assert import_items_from_csv("   \n  \n  ") == []


# ==================== export_to_json / import_from_json ====================


def test_export_to_json_round_trip():
    """JSON 含中文 + pretty print (indent=2)."""
    d = {
        "code": "reject_reason",
        "label_zh": "拒绝原因",
        "items": [
            {"key": "duplicate", "label_zh": "重复"},
            {"key": "low_quality", "label_zh": "低质量"},
        ],
    }
    text = export_to_json(d)

    # 验证中文保留 (ensure_ascii=False)
    assert "拒绝原因" in text
    assert "重复" in text
    # 验证 pretty print (含换行 + 缩进)
    assert "\n" in text
    assert "  " in text
    # 验证 round-trip
    parsed = json.loads(text)
    assert parsed == d


def test_import_from_json_returns_dict():
    """JSON 字符串 → 原始 dict (跟 export_to_json 互为逆)."""
    d = {"code": "page_key", "items": [{"key": "admin"}, {"key": "chat"}]}
    text = export_to_json(d)
    parsed = import_from_json(text)

    assert parsed == d
    assert parsed["code"] == "page_key"
    assert len(parsed["items"]) == 2


def test_import_from_json_raises_on_invalid():
    """非法 JSON → json.JSONDecodeError (业务层翻译成 422)."""
    with pytest.raises(json.JSONDecodeError):
        import_from_json("not valid json {")
