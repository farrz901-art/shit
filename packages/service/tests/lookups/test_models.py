"""lookups/models.py 单元测试"""

from src.lookups.models import Dictionary, DictionaryItem


def test_dictionary_defaults():
    d = Dictionary(code="status", label_zh="状态", label_en="Status")
    assert d.is_active is True
    assert d.is_readonly is False


def test_dictionary_item_defaults():
    item = DictionaryItem(key="active", label_zh="启用", label_en="Active", sort=1)
    assert item.is_active is True
