"""dictionaries_loader.py 单元测试"""

from unittest.mock import patch

from src.common.dictionaries_loader import get_seed_dict, load_seed


def test_load_seed_returns_list(tmp_path):
    yml = tmp_path / "seed.yaml"
    yml.write_text(
        "dictionaries:\n  - code: status\n    label_zh: 状态\n    label_en: Status\n    items: []\n", encoding="utf-8"
    )
    with patch("src.common.dictionaries_loader.SEED_PATH", yml):
        result = load_seed()
        assert len(result) == 1
        assert result[0]["code"] == "status"


def test_load_seed_empty_file(tmp_path):
    yml = tmp_path / "seed.yaml"
    yml.write_text("", encoding="utf-8")
    with patch("src.common.dictionaries_loader.SEED_PATH", yml):
        result = load_seed()
        assert result == []


def test_load_seed_missing_dictionaries_key(tmp_path):
    yml = tmp_path / "seed.yaml"
    yml.write_text("other: data\n", encoding="utf-8")
    with patch("src.common.dictionaries_loader.SEED_PATH", yml):
        result = load_seed()
        assert result == []


def test_get_seed_dict_found(tmp_path):
    yml = tmp_path / "seed.yaml"
    yml.write_text(
        "dictionaries:\n  - code: status\n    label_zh: 状态\n    label_en: Status\n    items: []\n", encoding="utf-8"
    )
    with patch("src.common.dictionaries_loader.SEED_PATH", yml):
        result = get_seed_dict("status")
        assert result is not None
        assert result["code"] == "status"


def test_get_seed_dict_not_found(tmp_path):
    yml = tmp_path / "seed.yaml"
    yml.write_text(
        "dictionaries:\n  - code: other\n    label_zh: O\n    label_en: O\n    items: []\n", encoding="utf-8"
    )
    with patch("src.common.dictionaries_loader.SEED_PATH", yml):
        result = get_seed_dict("nonexistent")
        assert result is None
