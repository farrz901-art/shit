"""lookups/exceptions.py 单元测试"""

from src.lookups.exceptions import LookupNotFoundError, LookupSafetyError


def test_lookup_not_found():
    e = LookupNotFoundError("status")
    assert "status" in str(e)


def test_lookup_safety_error():
    e = LookupSafetyError(409, "referenced")
    assert "referenced" in str(e)
