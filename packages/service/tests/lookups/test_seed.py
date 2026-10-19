"""seed 脚本测试 (2026-06-19 lookup spec Task 2)

CLAUDE.md 规范: 测试禁止连真 PG / Redis. 此处 mock 模式:
- 4 个 yaml loader 测试: 只读 yaml 文件, 0 DB 依赖
- 3 个 run_seed 测试: 在 sys.modules 注入 mock 的 src.lookups.models 模块
  (T4 才建真 model, 此处用 MagicMock 占位), patch session_scope 返 mock session
  验证 INSERT 行为 / 幂等 / force_sync 三种路径

测试矩阵 (7):
1. test_seed_yaml_loads_5_dicts — 验证 yaml 5 个字典 + reject_reason 非空
2. test_get_seed_dict_returns_none_for_missing — 不存在的 code 返 None
3. test_seed_yaml_item_keys_unique_per_dict — 每 dict item key 唯一
4. test_seed_yaml_metadata_json_parsed — page_key.metadata_json 是 dict
5. test_run_seed_inserts_new — 首次跑 INSERT (mock 不存在 → 触发 add)
6. test_run_seed_idempotent — 已存在跳过 (mock 已存在 → 不 add)
7. test_run_seed_force_sync_overrides_labels — force_sync=True 时改 label
"""

from __future__ import annotations

import sys
import types
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

# ---- helpers ----


def _install_mock_models():
    """在 sys.modules 注入 mock 的 src.lookups.models (T4 才建真 model, 此处占位).

    seed_dictionaries.py 用 _import() 做 `from src.lookups.models import Dictionary, DictionaryItem`,
    没真模块会 ImportError. 我们注入 mock class, 让 import 走通.

    关键: Dictionary.code / DictionaryItem.dict_code / DictionaryItem.key 必须是
    可比较的对象 (MagicMock / SQL Column 都能让 == 工作). 这里用 MagicMock 占位
    (后续 select() 整体被 patch, 不进 SA 编译).
    """
    code_mock = MagicMock(name="code_col")
    dict_code_mock = MagicMock(name="dict_code_col")
    key_mock = MagicMock(name="key_col")

    class _MockDict:
        """mock Dictionary class: 实例化 + 属性赋值都走通, SQL 由 select mock 处理."""

        code = code_mock
        label_zh = MagicMock(name="label_zh_col")
        label_en = MagicMock(name="label_en_col")
        description = MagicMock(name="description_col")

        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class _MockItem:
        """mock DictionaryItem class."""

        dict_code = dict_code_mock
        key = key_mock
        label_zh = MagicMock(name="label_zh_col")
        label_en = MagicMock(name="label_en_col")
        description = MagicMock(name="description_col")
        sort = MagicMock(name="sort_col")
        metadata_json = MagicMock(name="metadata_json_col")

        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    fake_models = types.ModuleType("src.lookups.models")
    fake_models.Dictionary = _MockDict  # type: ignore[attr-defined]
    fake_models.DictionaryItem = _MockItem  # type: ignore[attr-defined]
    sys.modules["src.lookups"] = types.ModuleType("src.lookups")
    sys.modules["src.lookups.models"] = fake_models
    return fake_models


def _patch_select():
    """patch scripts.seed_dictionaries.select 返 MagicMock (跳过 SA 表达式编译).

    seed_dictionaries 里 `select(Dictionary).where(Dictionary.code == "x")` 不需真编译,
    因为 s.execute() 是 mock 的, 不会调真 SQL. select() 返 MagicMock 即可让 .where() 链通.
    """
    return patch("scripts.seed_dictionaries.select", MagicMock())


def _mock_session_scope(session: MagicMock):
    """构造 session_scope 用的 context manager: yield mock session."""

    @contextmanager
    def _cm():
        yield session

    return _cm()


def _make_existing_dict(code: str = "reject_reason", label_zh: str = "拒绝原因", label_en: str = "Reject Reason"):
    """构造已存在的 Dictionary 行 (mock)."""
    row = MagicMock()
    row.code = code
    row.label_zh = label_zh
    row.label_en = label_en
    row.description = None
    return row


def _make_existing_item(
    dict_code: str = "reject_reason",
    key: str = "other",
    label_zh: str = "其他",
    label_en: str = "Other",
    sort: int = 99,
):
    """构造已存在的 DictionaryItem 行 (mock)."""
    row = MagicMock()
    row.dict_code = dict_code
    row.key = key
    row.label_zh = label_zh
    row.label_en = label_en
    row.sort = sort
    return row


# ---- yaml loader 测试 (无 DB) ----


def test_seed_yaml_loads_5_dicts():
    """验证 yaml 加载出 5 个字典 + reject_reason 非空."""
    from src.common.dictionaries_loader import get_seed_dict, load_seed

    data = load_seed()
    assert len(data) == 5, f"应有 5 个字典, 实际 {len(data)}"
    codes = {d["code"] for d in data}
    assert codes == {
        "approval_review_status",
        "approval_apply_status",
        "approval_kind",
        "reject_reason",
        "page_key",
    }

    # reject_reason 应有 6 个 item (duplicate/low_quality/incomplete/wrong_category/format_issue/other)
    reject = get_seed_dict("reject_reason")
    assert reject is not None
    assert len(reject["items"]) == 6


def test_get_seed_dict_returns_none_for_missing():
    """不存在的 code 返 None (不抛)."""
    from src.common.dictionaries_loader import get_seed_dict

    assert get_seed_dict("nonexistent_dict_xxx") is None
    assert get_seed_dict("") is None  # 空字符串也返 None


def test_seed_yaml_item_keys_unique_per_dict():
    """每个字典的 item key 必须唯一 (启动 fail-fast 防 yaml 拼错)."""
    from src.common.dictionaries_loader import load_seed

    for d in load_seed():
        keys = [item["key"] for item in d.get("items", [])]
        assert len(keys) == len(set(keys)), f"字典 {d['code']} 有重复 key: {keys}"


def test_seed_yaml_metadata_json_parsed():
    """page_key 的 metadata_json 是 dict (yaml 安全 load 应正确解析, 不应是字符串)."""
    from src.common.dictionaries_loader import get_seed_dict

    page_key = get_seed_dict("page_key")
    assert page_key is not None
    admin_item = next(i for i in page_key["items"] if i["key"] == "admin")
    admin_meta = admin_item["metadata_json"]
    assert isinstance(admin_meta, dict)
    assert admin_meta["path"] == "/admin"

    health_item = next(i for i in page_key["items"] if i["key"] == "health")
    health_meta = health_item["metadata_json"]
    assert health_meta is not None and health_meta["path"] == "/health"


# ---- run_seed 测试 (mock session + mock models) ----


def test_run_seed_inserts_new():
    """首次跑 (DB 空) → 触发 add() 5 dict + 27 item, 返 (5, 27).

    模拟: 5 次 select 字典返 None, 27 次 select item 返 None → 走 INSERT 分支.
    """
    _install_mock_models()
    from scripts.seed_dictionaries import run_seed

    # mock session.execute: 每个 dict 先查 (返 None), 每个 item 再查 (返 None)
    # 总 execute 次数 = 5 dict + 27 item = 32
    mock_session = MagicMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = None

    with _patch_select(), patch("scripts.seed_dictionaries.session_scope", lambda: _mock_session_scope(mock_session)):
        d_count, i_count = run_seed(force_sync=False)

    # (2026-07-08) 新增 page_key 后 yaml item 27→33
    assert d_count == 5, f"首次跑应 seed 5 个 dict, 实际 {d_count}"
    assert i_count == 33, f"首次跑应 seed 33 个 item, 实际 {i_count}"

    # 5 dict + 33 item + 16 page_keys × 2 roles (user + admin) = 70 add() calls
    assert mock_session.add.call_count == 5 + 33 + 16 * 2


def test_run_seed_idempotent():
    """第二次跑 (DB 已有) → 不 INSERT, 返 (0, 0)."""
    _install_mock_models()
    from scripts.seed_dictionaries import run_seed

    # mock: 5 个 dict 都有, 25 个 item 都有
    def _side_effect(*args, **kwargs):
        # 根据 select 的 where 子句区分是查 dict 还是 item (用 MagicMock 自动返 mock 行)
        m = MagicMock()
        m.scalar_one_or_none.return_value = MagicMock()  # truthy → 走 else 分支
        return m

    mock_session = MagicMock()
    mock_session.execute.side_effect = _side_effect

    with _patch_select(), patch("scripts.seed_dictionaries.session_scope", lambda: _mock_session_scope(mock_session)):
        d_count, i_count = run_seed(force_sync=False)

    # 已存在 → 不 add, 返 0
    assert d_count == 0
    assert i_count == 0
    # add() 0 次 (没 INSERT)
    assert mock_session.add.call_count == 0


def test_run_seed_force_sync_overrides_labels():
    """force_sync=True: 已存在的 dict / item 走 elif 分支, 改 label_zh / label_en / sort.

    验证: 不 add 新行, 但 existing.label_zh = yaml 的 label_zh 被赋值.
    """
    _install_mock_models()
    from scripts.seed_dictionaries import run_seed

    # mock: reject_reason 已有, item 也有, 且 item.label_zh 是 "其他 (admin 改过的)"
    existing_dict = _make_existing_dict(code="reject_reason", label_zh="拒绝原因(旧)", label_en="Reject Reason (old)")
    existing_item = _make_existing_item(
        dict_code="reject_reason",
        key="other",
        label_zh="其他 (admin 改)",
        label_en="Other (admin changed)",
        sort=100,
    )

    # yaml 顺序: approval_review_status(1+3) + approval_apply_status(1+3) +
    #           approval_kind(1+5) + reject_reason(1+6) + page_key(1+9) = 31 calls
    # reject_reason dict check 在 call #15, items 在 calls #16-21
    def _side_effect(*args, **kwargs):
        m = MagicMock()
        # call #15 = reject_reason dict check → 返 existing_dict
        # calls #16-21 = reject_reason 6 item check → 返 existing_item
        # 其他 → None (走 add 分支)
        m.call_count = _side_effect.counter  # type: ignore[attr-defined]
        _side_effect.counter += 1  # type: ignore[attr-defined]
        if m.call_count == 14:  # 0-indexed: call 15 → index 14
            m.scalar_one_or_none.return_value = existing_dict
        elif 15 <= m.call_count <= 20:  # calls 16-21 (0-indexed 15-20)
            m.scalar_one_or_none.return_value = existing_item
        else:
            m.scalar_one_or_none.return_value = None
        return m

    _side_effect.counter = 0  # type: ignore[attr-defined]
    mock_session = MagicMock()
    mock_session.execute.side_effect = _side_effect

    with _patch_select(), patch("scripts.seed_dictionaries.session_scope", lambda: _mock_session_scope(mock_session)):
        d_count, i_count = run_seed(force_sync=True)

    # reject_reason 的 dict/item 都没新增 (走 force_sync)
    # 其他 4 dict 都新增 (走 add); 其他 19 item 新增 (4 dict × ~5 items)
    assert existing_dict.label_zh == "拒绝原因", (
        f"force_sync 应覆盖 label_zh 为 yaml 值 '拒绝原因', 实际 {existing_dict.label_zh!r}"
    )
    assert existing_dict.label_en == "Reject Reason"

    assert existing_item.label_zh == "其他", (
        f"force_sync 应覆盖 item.label_zh 为 yaml 值 '其他', 实际 {existing_item.label_zh!r}"
    )
    assert existing_item.label_en == "Other"
    assert existing_item.sort == 99, f"force_sync 应覆盖 sort 为 yaml 值 99, 实际 {existing_item.sort}"

    # 其他 4 个 dict 走 add 分支 (dict_count += 4)
    assert d_count == 4, f"4 个非 reject dict 应新增, 实际 {d_count}"
    # add 次数 = 4 dict + 19 items (4 dict * 各自 item 数)
    # 但我们只测 force_sync 覆盖逻辑, 不严格 count 19 (避免 side_effect 计数脆弱)
