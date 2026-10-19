"""MemoryService 单测: user_id 解析 + 降级 + 参数透传 (2026-06-16)
+ Phase 2 记忆管理: list/update/delete + 跨用户隔离"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# ---- _resolve_mem0_user_id ----


def test_resolve_mem0_user_id_prefers_account_id():
    """有账号时 user_id = str(account_id)"""
    from src.memory.service import _resolve_mem0_user_id
    from src.middleware.auth import CurrentUser

    user = CurrentUser(id=42, public_token="t", account_id=7, is_account=True)
    assert _resolve_mem0_user_id(user) == "7"


def test_resolve_mem0_user_id_fallback_to_user_id():
    """anon (account_id=None) 时 user_id = str(user.id)"""
    from src.memory.service import _resolve_mem0_user_id
    from src.middleware.auth import CurrentUser

    user = CurrentUser(id=42, public_token="t", account_id=None, is_account=False)
    assert _resolve_mem0_user_id(user) == "42"


# ---- MemoryService.search 降级 ----


def test_search_returns_empty_on_exception(monkeypatch):
    """mem0 抛任何异常 → 返 [] + log warning, 不冒泡"""
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    fake_memory.search.side_effect = RuntimeError("pgvector 不可达")
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=1, public_token="t", account_id=None)
    result = svc.search(user, "query", limit=3)
    assert result == []


def test_search_passes_filters_and_top_k():
    """search 走 mem0 self-host API: filters={user_id}, top_k"""
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    fake_memory.search.return_value = [
        {"id": "1", "memory": "用户叫张三", "score": 0.9, "metadata": {"src": "x"}},
    ]
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    results = svc.search(user, "用户叫什么", limit=3)

    assert len(results) == 1
    assert results[0].id == "1"
    assert results[0].text == "用户叫张三"
    assert results[0].score == 0.9
    assert results[0].metadata == {"src": "x"}
    fake_memory.search.assert_called_once_with(query="用户叫什么", filters={"user_id": "42"}, top_k=3)


def test_search_caches_memory_per_user():
    """同一 user 多次 search 复用 Memory 实例"""
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    fake_memory.search.return_value = []
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    svc.search(user, "q1")
    svc.search(user, "q2")

    fake_factory.assert_called_once_with("42")


def test_search_separate_cache_per_user():
    """不同 user 各自缓存 Memory"""
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    m1, m2 = MagicMock(), MagicMock()
    m1.search.return_value = []
    m2.search.return_value = []
    factory = MagicMock(side_effect=[m1, m2])
    svc = MemoryService(mem0_factory=factory)

    u1 = CurrentUser(id=1, public_token="t1", account_id=None)
    u2 = CurrentUser(id=2, public_token="t2", account_id=None)
    svc.search(u1, "q")
    svc.search(u2, "q")

    assert factory.call_count == 2
    assert factory.call_args_list[0][0][0] == "1"
    assert factory.call_args_list[1][0][0] == "2"


def test_search_handles_dict_results_envelope():
    """mem0 self-host v1.1+ search 返 dict{'results': [...]} 包装, 必须解包再迭代.

    回归 bug (2026-06-17): dict 直接被 for 遍历得到 key 字符串,
    旧代码产生 text='results' 的伪命中. 跟 list_memories:132-134 同样的守卫要补到 search.
    """
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    # 模拟 mem0 v1.1+ search 的 dict 包装返回 (跟 get_all 同款)
    fake_memory.search.return_value = {
        "results": [
            {"id": "1", "memory": "用户喜欢吃苹果", "score": 0.9, "metadata": {"src": "x"}},
            {"id": "2", "memory": "用户叫张三", "score": 0.8, "metadata": None},
        ]
    }
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    results = svc.search(user, "用户喜欢什么", limit=5)

    assert len(results) == 2
    assert results[0].id == "1"
    assert results[0].text == "用户喜欢吃苹果"
    assert results[0].score == 0.9
    assert results[0].metadata == {"src": "x"}
    assert results[1].id == "2"
    assert results[1].text == "用户叫张三"
    # 关键回归断言: 不应该有 text='results' 的伪命中 (dict key 被误当 memory text)
    assert not any(r.text == "results" for r in results), "dict key 被当成 memory text, 说明没解包"


def test_search_handles_empty_dict_results_envelope():
    """mem0 v1.1 search 返 {'results': []} → 返 [], 不产生伪命中"""
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    fake_memory.search.return_value = {"results": []}
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    results = svc.search(user, "x", limit=5)

    assert results == []


# ---- MemoryService.add 降级 + metadata 透传 ----


def test_add_silent_on_exception(monkeypatch):
    """add 抛异常 → log warning, 不重抛"""
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    fake_memory.add.side_effect = RuntimeError("LLM 限流")
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=1, public_token="t", account_id=None)
    # 必须不抛
    svc.add(user, [{"role": "user", "content": "hi"}], conversation_id="c1")


def test_add_passes_messages_and_user_id():
    """add 透传 messages + user_id"""
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    msgs = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    svc.add(user, msgs, conversation_id=None)

    fake_memory.add.assert_called_once_with(messages=msgs, user_id="42", infer=True)
    # 没 conversation_id 时不传 metadata
    assert "metadata" not in fake_memory.add.call_args[1]


def test_add_includes_conversation_id_in_metadata():
    """add 带 conversation_id 时透传到 metadata"""
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    svc.add(user, [{"role": "user", "content": "hi"}], conversation_id="conv-abc")

    fake_memory.add.assert_called_once_with(
        messages=[{"role": "user", "content": "hi"}],
        user_id="42",
        infer=True,
        metadata={"conversation_id": "conv-abc"},
    )


# =============================================================================
# Phase 2 (2026-06-16): list / update / delete / delete_all + 跨用户隔离
# =============================================================================


# ---- list_memories ----


def test_list_memories_passes_user_id_and_top_k():
    """list_memories 走 mem0 get_all(filters={user_id}, top_k=200)"""
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    fake_memory.get_all.return_value = [
        {"id": "m1", "memory": "用户叫张三", "metadata": {"src": "x"}},
        {"id": "m2", "memory": "用户住北京"},
    ]
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    results = svc.list_memories(user)

    assert len(results) == 2
    assert results[0].id == "m1"
    assert results[0].text == "用户叫张三"
    assert results[0].metadata == {"src": "x"}
    fake_memory.get_all.assert_called_once_with(filters={"user_id": "42"}, top_k=200)


def test_list_memories_returns_empty_on_exception():
    """mem0 get_all 抛错 → 返 [], log warning"""
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    fake_memory.get_all.side_effect = RuntimeError("pgvector 不可达")
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=1, public_token="t", account_id=None)
    result = svc.list_memories(user)
    assert result == []


# ---- update_memory + 跨用户隔离 (关键安全) ----


def test_update_memory_owns_check_passes_then_calls_mem0():
    """update 前先 m.get 校验 user_id 匹配, 再 m.update"""
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    # m.get(id) 返带 user_id 字段的 dict (mem0 promoted_payload_keys 暴露)
    fake_memory.get.return_value = {"id": "m1", "memory": "old", "user_id": "42"}
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    svc.update_memory(user, "m1", "new text")

    fake_memory.get.assert_called_once_with("m1")
    fake_memory.update.assert_called_once_with("m1", "new text", None)


def test_update_memory_raises_on_cross_user_access():
    """**关键安全测试**: 别人的 memory_id → 抛 PermissionError, mem0.update 不被调"""
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    fake_memory.get.return_value = {"id": "m1", "memory": "old", "user_id": "99"}  # 别人的
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    with pytest.raises(PermissionError):
        svc.update_memory(user, "m1", "hijack text")

    fake_memory.update.assert_not_called()


def test_update_memory_raises_on_not_found():
    """memory 不存在 → 抛 PermissionError (跟无权访问同一异常, 防 ID 探测)"""
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    fake_memory.get.return_value = None
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    with pytest.raises(PermissionError):
        svc.update_memory(user, "nonexistent", "text")


# ---- delete_memory + 跨用户隔离 ----


def test_delete_memory_owns_check_passes_then_calls_mem0():
    """delete 前先 m.get 校验 user_id, 再 m.delete"""
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    fake_memory.get.return_value = {"id": "m1", "user_id": "42"}
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    svc.delete_memory(user, "m1")

    fake_memory.delete.assert_called_once_with("m1")


def test_delete_memory_raises_on_cross_user_access():
    """**关键安全测试**: 别人的 memory_id → 抛 PermissionError, mem0.delete 不被调"""
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    fake_memory.get.return_value = {"id": "m1", "user_id": "99"}
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=42, public_token="t", account_id=None)
    with pytest.raises(PermissionError):
        svc.delete_memory(user, "m1")

    fake_memory.delete.assert_not_called()


# ---- 跨用户回归: 用户隔离端到端 (防止后续 refactor 漏掉隔离) ----


def test_user_a_cannot_list_user_b_memories():
    """**显式隔离测试**: user A 调 list_memories → m.get_all 必传 filters={user_id: A}."""
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    # 即使 mem0 内部返了别人的记忆 (mock 不过滤, 模拟 mem0 漏洞), service 不该让 A 看到
    fake_memory.get_all.return_value = [
        {"id": "m1", "memory": "B 的记忆", "user_id": "99"},  # 别人的
    ]
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user_a = CurrentUser(id=42, public_token="t", account_id=None)
    svc.list_memories(user_a)

    # 验证: 必须传 filters={user_id: "42"}, 绝不能传空 filters 或别的 user_id
    fake_memory.get_all.assert_called_once_with(filters={"user_id": "42"}, top_k=200)


def test_user_a_cannot_delete_all_user_b_memories():
    """**显式隔离测试**: user A 调 delete_all_memories → m.delete_all 必须传 user_id=A."""
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user_a = CurrentUser(id=42, public_token="t", account_id=None)
    svc.delete_all_memories(user_a)

    # 验证: 必须传 user_id="42" 给 m.delete_all, 不能传 None 或别的
    fake_memory.delete_all.assert_called_once_with(user_id="42")


def test_service_does_not_accept_user_id_from_caller():
    """**类型安全测试**: service 方法签名不接 user_id 参数, 只能从 CurrentUser 解析.
    防 refactor 时误加 user_id: str 参数 → 攻击者就能伪造身份.
    """
    import inspect

    from src.memory.service import MemoryService

    # 5 个方法都不应接受 user_id 作为位置/关键字参数
    for method_name in [
        "search",
        "add",
        "list_memories",
        "update_memory",
        "delete_memory",
        "delete_all_memories",
    ]:
        sig = inspect.signature(getattr(MemoryService, method_name))
        for param_name in sig.parameters:
            assert param_name not in (
                "user_id",
                "target_user_id",
                "actor_id",
            ), f"{method_name} 接受 {param_name} 参数 = 安全漏洞!"


# =============================================================================
# 字符清洗 (2026-06-17): 上游 chat 流损坏 content (?/� 二次编码)
# 多语言保留 (2026-06-24): 阿拉伯 / 俄语 / 假名等非 CJK 非拉丁文字不能被误判
# =============================================================================


def test_sanitize_collapses_ascii_question_runs():
    """连续 ASCII '?' 折叠成单个"""
    from src.memory.service import _sanitize_content

    assert _sanitize_content("hello ????world") == "hello ?world"


def test_sanitize_collapses_replacement_char_runs():
    """连续 U+FFFD '�' 折叠成单个"""
    from src.memory.service import _sanitize_content

    assert _sanitize_content("hello ����world") == "hello ?world"


def test_sanitize_preserves_single_question_mark_and_chinese():
    """单个 '?' 不动 (原文本里的真问号), 中文不动"""
    from src.memory.service import _sanitize_content

    assert _sanitize_content("what is your name?") == "what is your name?"
    assert _sanitize_content("用户喜欢喝咖啡") == "用户喜欢喝咖啡"


def test_sanitize_none_and_empty_passthrough():
    """None/空串透传"""
    from src.memory.service import _sanitize_content

    assert _sanitize_content(None) is None
    assert _sanitize_content("") == ""


def test_pure_garbage_true_for_pure_garbage():
    """纯 ?/�/空白/标点 算纯乱码 (True = 丢)"""
    from src.memory.service import _is_pure_garbage

    assert _is_pure_garbage("????") is True
    assert _is_pure_garbage("����") is True
    assert _is_pure_garbage("   ") is True
    assert _is_pure_garbage("?!?!?!") is True


def test_pure_garbage_false_for_normal_text():
    """正常中英文不算纯乱码 (False = 保留)"""
    from src.memory.service import _is_pure_garbage

    assert _is_pure_garbage("I love coffee") is False
    assert _is_pure_garbage("用户喜欢喝咖啡") is False
    # 短正常消息也算保留 (短不短是 LLM 的事, 不是清洗的事)
    assert _is_pure_garbage("hi") is False
    assert _is_pure_garbage("好") is False


def test_pure_garbage_false_for_non_cjk_non_latin_scripts():
    """(2026-06-24) 阿拉伯 / 俄语 / 希伯来 / 日语假名 / 泰语等不算纯乱码.

    旧规则 [A-Za-z0-9一-鿿]+ 只放 ASCII + CJK 汉字, 误伤其他语言 →
    阿拉伯用户对话被全部丢弃 + 误报 "GBK 二次编码损坏".
    """
    from src.memory.service import _is_pure_garbage

    assert _is_pure_garbage("مرحبا كيف حالك") is False  # 阿拉伯
    assert _is_pure_garbage("Привет мир") is False  # 俄语
    assert _is_pure_garbage("שלום עולם") is False  # 希伯来
    assert _is_pure_garbage("こんにちは") is False  # 日语假名
    assert _is_pure_garbage("สวัสดี") is False  # 泰语
    assert _is_pure_garbage("안녕하세요") is False  # 韩语谚文


def test_pure_garbage_false_for_partial_garbage():
    """含损坏块但还有正经字符 → 不丢"""
    from src.memory.service import _is_pure_garbage

    assert _is_pure_garbage("1LE1001-0BB32-2GA4????") is False
    assert _is_pure_garbage("hello ����world") is False


def test_pure_garbage_true_for_none_and_empty():
    """None/空串算纯乱码"""
    from src.memory.service import _is_pure_garbage

    assert _is_pure_garbage(None) is True
    assert _is_pure_garbage("") is True


def test_clean_messages_drops_pure_garbage_keeps_good():
    """混合批量: 好的留下, 纯 ? 的丢"""
    from src.memory.service import MemoryService

    msgs = [
        {"role": "user", "content": "I love coffee"},
        {"role": "user", "content": "????"},
        {"role": "assistant", "content": "Noted"},
    ]
    cleaned, dropped = MemoryService._clean_messages(msgs)
    assert dropped == 1
    assert len(cleaned) == 2
    assert cleaned[0]["content"] == "I love coffee"
    assert cleaned[1]["content"] == "Noted"


def test_clean_messages_sanitizes_partial_garbage():
    """部分损坏的消息清洗后保留, 不丢"""
    from src.memory.service import MemoryService

    msgs = [{"role": "user", "content": "1LE1001-0BB32-2GA4????"}]
    cleaned, dropped = MemoryService._clean_messages(msgs)
    # 折叠 ???? → ?, 剩 "1LE1001-0BB32-2GA4?" 含 ≥ 4 有意义字符, 保留
    assert dropped == 0
    assert len(cleaned) == 1
    assert cleaned[0]["content"] == "1LE1001-0BB32-2GA4?"


def test_clean_messages_does_not_mutate_input():
    """原 list / dict 不被改 (返新 dict)"""
    from src.memory.service import MemoryService

    original_msg = {"role": "user", "content": "1LE1001-0BB32-2GA4????"}
    msgs = [original_msg]
    MemoryService._clean_messages(msgs)
    assert original_msg["content"] == "1LE1001-0BB32-2GA4????"
    assert len(msgs) == 1


def test_clean_messages_empty_input():
    """空 / None 入参返 ([], 0)"""
    from src.memory.service import MemoryService

    cleaned, dropped = MemoryService._clean_messages([])
    assert cleaned == [] and dropped == 0
    cleaned, dropped = MemoryService._clean_messages(None)
    assert cleaned == [] and dropped == 0


def test_add_does_not_call_mem0_when_all_messages_garbage():
    """所有消息都被清洗 → 不调 mem0.add, 静默 return (不会污染 mem0)"""
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=1, public_token="t", account_id=None)
    svc.add(user, [{"role": "user", "content": "????"}], conversation_id="c1")
    fake_memory.add.assert_not_called()


def test_add_calls_mem0_with_cleaned_messages():
    """混合批量: 清洗后调 mem0.add, 传的 messages 是清洗版"""
    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    fake_memory.add.return_value = {"results": [{"memory": "x"}]}
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=1, public_token="t", account_id=None)
    msgs = [
        {"role": "user", "content": "hello ????world"},
        {"role": "user", "content": "????"},
    ]
    svc.add(user, msgs, conversation_id="c1")
    fake_memory.add.assert_called_once()
    passed_msgs = fake_memory.add.call_args.kwargs["messages"]
    assert len(passed_msgs) == 1
    assert passed_msgs[0]["content"] == "hello ?world"


def test_add_warns_when_llm_extracts_zero_facts():
    """mem0 返 0 抽事实时 WARNING"""
    from loguru import logger as _loguru

    from src.memory.service import MemoryService
    from src.middleware.auth import CurrentUser

    fake_memory = MagicMock()
    fake_memory.add.return_value = {"results": []}
    fake_factory = MagicMock(return_value=fake_memory)
    svc = MemoryService(mem0_factory=fake_factory)

    user = CurrentUser(id=1, public_token="t", account_id=None)
    # 用 loguru handler 捕获 WARNING 级别日志, 替代 caplog
    records: list[str] = []
    handler_id = _loguru.add(lambda msg: records.append(str(msg)), level="WARNING", format="{message}")
    try:
        svc.add(user, [{"role": "user", "content": "I love coffee"}], conversation_id=None)
    finally:
        _loguru.remove(handler_id)
    assert any("LLM 未抽到事实" in r for r in records)
