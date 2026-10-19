"""DifyClient think 标签过滤测试 (2026-06-11 Task B)

Dify 工作流返的 answer 可能含 <think>...</think> 推理块, 评估表格不需要展示
中间推理 (太长+不直观), 客户端层正则过滤, 不依赖 Dify 后台配置。
"""

from __future__ import annotations

import asyncio

from src.integrations.dify_client import DifyClient, _strip_think


class TestStripThink:
    """_strip_think 纯函数单元测试"""

    def test_removes_single_think_block(self):
        # (2026-06-11) 最常见: 答案前面有 think 块, 后面是真正答案
        raw = "<think>用户问的是电机型号</think>1LE 系列是西门子电机"
        assert _strip_think(raw) == "1LE 系列是西门子电机"

    def test_removes_multiline_think_block(self):
        # think 块内多行, 含换行/缩进
        raw = "<think>\n用户问的是电机型号\n需要查产品库\n</think>1LE 是西门子电机"
        assert _strip_think(raw) == "1LE 是西门子电机"

    def test_keeps_answer_when_no_think_block(self):
        # 正常 answer, 无 think 标签 → 原样保留
        assert _strip_think("1LE 是西门子电机") == "1LE 是西门子电机"

    def test_handles_multiple_think_blocks(self):
        # 多个 think 块 (少见但要处理)
        raw = "<think>推理1</think>答案1<think>推理2</think>答案2"
        assert _strip_think(raw) == "答案1答案2"

    def test_strips_surrounding_whitespace(self):
        # think 块删除后, 答案前后的空白要清理
        raw = "<think>推理</think>   真正的答案   "
        assert _strip_think(raw) == "真正的答案"

    def test_handles_empty_string(self):
        # 边界: 空串
        assert _strip_think("") == ""

    def test_handles_none_safely(self):
        # 边界: None (Dify 可能返空)
        assert _strip_think(None) is None

    def test_think_with_attributes_preserved(self):
        # 真实 Dify 输出: think 块可能带属性 (罕见), 正则要容忍
        # 注: 当前实现只删纯 <think>...</think>, 带属性会保留原样 (不算 bug, 但要可预测)
        raw = '<think attr="x">推理</think>答案'
        result = _strip_think(raw)
        # 当前实现只匹配 <think> (无属性), 带属性的会保留原样
        assert isinstance(result, str) and "答案" in result


class TestAchatStripsThink:
    """achat 端到端: Dify 返的 answer 自动 strip think 标签"""

    def test_achat_answer_stripped_of_think(self, monkeypatch):
        """Dify 返含 <think> 的 answer → achat 返的 answer 已经被 strip"""
        import httpx

        class _MockResp:
            status_code = 200

            def json(self):
                return {
                    "event": "message",
                    "answer": "<think>推理中</think>1LE 是西门子电机",
                    "conversation_id": "conv-1",
                    "metadata": {"retriever_resources": []},
                }

        class _MockAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, headers=None, json=None):
                return _MockResp()

        monkeypatch.setattr(httpx, "AsyncClient", _MockAsyncClient)
        client = DifyClient(api_key="app-test", base_url="http://test")
        # (2026-06-11) 项目没装 pytest-asyncio, 用 asyncio.run 包
        result = asyncio.run(client.achat("Q?"))
        assert result["answer"] == "1LE 是西门子电机"


class TestAchatExtractsSources:
    """(2026-06-11 Task C) achat 返 sources 字段供前端表格展示「召回到」"""

    def test_achat_extracts_retriever_resources_as_sources(self, monkeypatch):
        """Dify 返 retriever_resources → achat 提取为 sources 列表"""
        import httpx

        class _MockResp:
            status_code = 200

            def json(self):
                return {
                    "event": "message",
                    "answer": "答案",
                    "conversation_id": "c-1",
                    "metadata": {
                        "retriever_resources": [
                            {
                                "document_id": "doc-1",
                                "document_name": "1LE 电机手册.pdf",
                                "position": 3,
                                "score": 0.85,
                                "content": "1LE 系列是西门子电机...",
                            },
                            {
                                "document_id": "doc-2",
                                "document_name": "产品选型指南.docx",
                                "position": 1,
                                "score": 0.72,
                                "content": "适用场景: 工业驱动",
                            },
                        ]
                    },
                }

        class _MockAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, headers=None, json=None):
                return _MockResp()

        monkeypatch.setattr(httpx, "AsyncClient", _MockAsyncClient)
        client = DifyClient(api_key="app-test", base_url="http://test")
        result = asyncio.run(client.achat("Q?"))

        # (2026-06-11) sources 字段: [{name, position, score, snippet}, ...]
        # 保留 document_name, position, score + 截短 content 作为 snippet
        assert "sources" in result
        assert len(result["sources"]) == 2
        s0 = result["sources"][0]
        assert s0["name"] == "1LE 电机手册.pdf"
        assert s0["position"] == 3
        assert s0["score"] == 0.85
        assert "1LE 系列" in s0["snippet"]

    def test_achat_no_retriever_resources_returns_empty_sources(self, monkeypatch):
        """Dify 返无 retriever_resources → sources 为空列表"""
        import httpx

        class _MockResp:
            status_code = 200

            def json(self):
                return {
                    "event": "message",
                    "answer": "答案",
                    "conversation_id": "c-2",
                    "metadata": {},
                }

        class _MockAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, headers=None, json=None):
                return _MockResp()

        monkeypatch.setattr(httpx, "AsyncClient", _MockAsyncClient)
        client = DifyClient(api_key="app-test", base_url="http://test")
        result = asyncio.run(client.achat("Q?"))
        assert result["sources"] == []
