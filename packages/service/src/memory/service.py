"""MemoryService 业务核心: user_id 解析 + 降级兜底 (2026-06-16)

整个 memory 模块的"什么也不会坏"保证: 任何 mem0 异常都被 try/except 吞掉,
返空或静默 log, 主聊天流不感知.

日志约定 (2026-06-17): service 层不打印常规 INFO, 入口/出口在 router 层记;
service 只在异常 / 异常兜底时打 WARNING. 避免 router + service 双层重复.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from enum import Enum, auto
from typing import Any

from loguru import logger

from ..middleware.auth import CurrentUser
from .mem0_client import Memory, _default_mem0_factory
from .schemas import MemoryHit


class ErrorKind(Enum):
    """memory 模块错误分类.

    BUSINESS_RECOVERABLE: 业务可恢复 (返空列表)
    SYSTEM: 系统故障 (raise 500)
    """

    BUSINESS_RECOVERABLE = auto()
    SYSTEM = auto()


class MemoryServiceError(Exception):
    """memory 模块自定义异常, 携带分类标志."""

    kind: ErrorKind

    def __init__(self, message: str, kind: ErrorKind = ErrorKind.SYSTEM):
        self.kind = kind
        super().__init__(message)


# GBK→UTF-8 二次编码产生的损坏块 (上游 chat 内容在传给 mem0 之前被错误编码过).
# 表现: 连续 2+ 个 ASCII '?' 或 Unicode replacement char (U+FFFD '�').
# 折叠成单个 '?', 减少 LLM 拒抽概率 (不能恢复原字符, 原字节已丢).
_GARBLED_RUN = re.compile(r"[?�]{2,}")
# 判定"有可记内容": 任何 Unicode 字母 / 数字 (\w 不行 — 它在 Python re 默认仅 ASCII).
# (2026-06-24) 旧规则 [A-Za-z0-9一-鿿]+ 只放 ASCII + CJK 汉字, 误伤阿拉伯 / 俄语 /
# 希伯来 / 假名 / 泰语等所有"非汉字非拉丁"文字 → 整条消息被判纯乱码丢弃.
# re.UNICODE 让 \w 匹配所有 Unicode letter/digit/_, 去掉 _ 后跟"有内容"语义一致.
_MEANINGFUL_KEEP = re.compile(r"[^\W_]+", re.UNICODE)


def _sanitize_content(text: str | None) -> str | None:
    """把损坏块 (?? / ��) 折叠成单个 ?, 透传 None/空串.

    不能恢复原字符 (原字节已丢), 只能减少 ? 噪声, 让 LLM 不被纯乱文本吓退.
    """
    if not text:
        return text
    return _GARBLED_RUN.sub("?", text)


def _is_pure_garbage(text: str | None) -> bool:
    """剥掉 ?/标点/空白/损坏块后, 没有任何 Unicode 字母 / 数字, 算纯乱码 → 丢.

    'hi' 不算 (有字母), 'I love coffee' 不算, '用户喜欢喝咖啡' 不算,
    'مرحبا' (阿拉伯语) 不算, 'Привет' (俄语) 不算, 'こんにちは' (日语) 不算.
    '????' 算 (纯损坏块), '   ' 算 (纯空白), None/'' 算 (无内容).
    短正常消息 ('hi', '好') 不会被误丢, 短到不短到是 LLM 抽不抽得到的事, 不是清洗的事.
    """
    if not text:
        return True
    meaningful = _MEANINGFUL_KEEP.findall(_GARBLED_RUN.sub("", text))
    return len(meaningful) == 0


def _resolve_mem0_user_id(current: CurrentUser) -> str:
    """账号优先 (Account.id), anon fallback User.id. 都用 str 跟 mem0 user_id 类型对齐."""
    return str(current.account_id) if current.account_id is not None else str(current.id)


def _unwrap_results_envelope(raw: Any) -> list[Any]:
    """mem0 self-host v1.1+ search/get_all 可能返 dict {"results": [...]} 包装.

    不解包直接 for-in dict 会迭代 key 字符串 (e.g. "results"), 进而被当成裸 memory text
    → 产生 id="" text="results" 的伪命中 (2026-06-17 真实 bug).

    返 list[dict] | list[str] | [], 跟 mem0 文档列的两种格式对齐.
    """
    if isinstance(raw, dict):
        return list(raw.get("results", []) or [])
    return list(raw or [])


class MemoryService:
    """按 user_id 缓存 Memory 实例 + 降级兜底.

    factory 参数允许测试注入 mock factory; 运行时走 _default_mem0_factory (self-host pgvector).
    """

    def __init__(self, mem0_factory: Callable[[str], Memory] | None = None):
        self._factory = mem0_factory or _default_mem0_factory
        self._cache: dict[str, Memory] = {}
        # (2026-06-23) mem0 启动失败标记: _get_memory 抛过 RuntimeError 的 user_id
        # 后续请求直接返 None, 不再触发 factory 重试, 避免每个请求都卡 5s warmup
        self._unavailable: set[str] = set()

    def _get_memory(self, user_id: str) -> Memory | None:
        """拿 user_id 对应的 Memory 实例. mem0 不可用 → 返 None (调用方降级).

        (2026-06-23) 加失败缓存: factory 抛 RuntimeError 后记 _unavailable, 后续请求
        直接返 None 不重试. 防止 mem0 warmup 慢 (5s) × N 用户 = 雪崩.
        """
        if user_id in self._unavailable:
            return None
        if user_id not in self._cache:
            try:
                self._cache[user_id] = self._factory(user_id)
            except RuntimeError:
                # mem0 启动失败 (key 错 / spacy 缺 / pgvector 不可达), 标记并降级
                self._unavailable.add(user_id)
                logger.error(
                    "mem0 不可用 user_id={} 该用户后续记忆请求将降级返空, 修配置后需重启服务",
                    user_id,
                )
                return None
        return self._cache[user_id]

    def search(self, current: CurrentUser, query: str, limit: int = 5) -> list[MemoryHit]:
        user_id = _resolve_mem0_user_id(current)
        try:
            m = self._get_memory(user_id)
            if m is None:
                # mem0 不可用, 降级返空
                return []
            results: list[Any] = _unwrap_results_envelope(
                m.search(query=query, filters={"user_id": user_id}, top_k=limit)
            )
            hits: list[MemoryHit] = []
            for r in results:
                if not isinstance(r, dict):
                    # mem0 self-host 偶尔返裸字符串, 包成 dict
                    r = {"memory": str(r)}
                row: dict[str, Any] = r
                hits.append(
                    MemoryHit(
                        id=str(row.get("id", "")),
                        text=row.get("memory", ""),
                        score=row.get("score"),
                        metadata=row.get("metadata"),
                    )
                )
            return hits
        except MemoryServiceError as e:
            if e.kind == ErrorKind.BUSINESS_RECOVERABLE:
                logger.warning("search 可恢复 user_id={} query={} err={}", user_id, query, e)
                return []
            raise  # SYSTEM → 500
        except Exception:
            # 兜底降级: pgvector / 网络 / mem0 内部异常都 log+返空, 不影响主聊天流
            logger.opt(exception=True).warning("search 系统异常降级返空 user_id={} query={}", user_id, query)
            return []

    def add(self, current: CurrentUser, messages: list[dict], conversation_id: str | None) -> None:
        """写入记忆. 静默兜底, 但 0 抽事实时 WARNING (LLM 拒抽, 多半上游内容损坏).

        预处理 (2026-06-17): 上游 chat 流经常传进来 GBK 二次编码损坏的 content
        (一堆连续 ?/�), LLM 看到纯乱码直接不抽事实. 入口折叠损坏块 + 跳无意义消息.
        """
        user_id = _resolve_mem0_user_id(current)
        try:
            m = self._get_memory(user_id)
            if m is None:
                # mem0 不可用, 静默降级 (add 是 fire-and-forget, 调用方不感知)
                return
            cleaned, dropped = self._clean_messages(messages)
            if dropped:
                logger.warning(
                    "add 跳过 {} 条无意义消息 user_id={} (纯空白 / 纯标点 / 纯损坏块 ?/�)",
                    dropped,
                    user_id,
                )
            if not cleaned:
                logger.warning(
                    "add 全部消息被清洗 user_id={} (上游 chat 内容全坏, 看 Dify/decoder 响应)",
                    user_id,
                )
                return
            kwargs: dict[str, Any] = {"messages": cleaned, "user_id": user_id, "infer": True}
            if conversation_id:
                kwargs["metadata"] = {"conversation_id": conversation_id}
            # (2026-06-24) DEBUG: 打 mem0 实际收到的 messages + LLM 返回, 排查"未抽到事实"
            logger.info(
                "memory.add 调用 mem0 user_id={} msgs_count={} contents={} conversation_id={}",
                user_id,
                len(cleaned),
                [{"role": m.get("role"), "content": (m.get("content") or "")[:200]} for m in cleaned],
                conversation_id,
            )
            ret = m.add(**kwargs)
            unwrapped = _unwrap_results_envelope(ret)
            logger.info(
                "memory.add mem0 返回 user_id={} raw_type={} raw_keys={} extracted={}",
                user_id,
                type(ret).__name__,
                list(ret.keys()) if isinstance(ret, dict) else None,
                unwrapped,
            )
            if not unwrapped:
                logger.warning(
                    "add LLM 未抽到事实 user_id={} msgs={} (上游内容可能仍损坏, 看 Dify/decoder)",
                    user_id,
                    len(cleaned),
                )
        except Exception as e:
            logger.opt(exception=True).warning("add failed user_id={} err={}", user_id, e)
            # 静默: 不重抛, 不写错误响应

    @staticmethod
    def _clean_messages(messages: list[dict] | None) -> tuple[list[dict], int]:
        """清洗 messages: 折叠损坏块 (?/�) + 跳过无意义消息 (全 ?/纯空白/太短).

        返 (cleaned, dropped_count). cleaned 是新 list, 不改入参.
        """
        cleaned: list[dict] = []
        dropped = 0
        for msg in messages or []:
            content = msg.get("content") or ""
            sanitized = _sanitize_content(content) or ""
            if _is_pure_garbage(sanitized):
                dropped += 1
            else:
                cleaned.append({**msg, "content": sanitized})
        return cleaned, dropped

    # ---- Phase 2 (2026-06-16): 记忆管理 ----

    def _assert_owned(self, memory_dict: dict | None, user_id: str, memory_id: str) -> None:
        """mem0 delete/update 不验 user_id (跨租户漏洞), service 层必须先校验.

        memory 拿不到 OR user_id 不匹配 → 统一抛 PermissionError (不区分, 防 ID 探测).
        """
        if not memory_dict or memory_dict.get("user_id") != user_id:
            raise PermissionError(f"无权访问记忆 {memory_id}")

    def list_memories(self, current: CurrentUser, limit: int = 200) -> list[MemoryHit]:
        """列当前用户所有记忆 (按 mem0 默认顺序, 倒序). 失败降级返 [].

        mem0 get_all 走 filters={user_id} 隔离, 不需要 _assert_owned.
        """
        user_id = _resolve_mem0_user_id(current)
        try:
            m = self._get_memory(user_id)
            if m is None:
                return []
            raw: Any = m.get_all(filters={"user_id": user_id}, top_k=limit)
            results: list[Any] = _unwrap_results_envelope(raw)
            hits: list[MemoryHit] = []
            for r in results:
                if not isinstance(r, dict):
                    r = {"memory": str(r)}
                row: dict[str, Any] = r
                hits.append(
                    MemoryHit(
                        id=str(row.get("id", "")),
                        text=row.get("memory", ""),
                        score=row.get("score"),
                        metadata=row.get("metadata"),
                    )
                )
            return hits
        except MemoryServiceError as e:
            if e.kind == ErrorKind.BUSINESS_RECOVERABLE:
                logger.warning("list 可恢复 user_id={} err={}", user_id, e)
                return []
            raise  # SYSTEM → 500
        except Exception:
            # 兜底降级: pgvector / 网络 / mem0 内部异常都 log+返空, 列表页不爆 500
            logger.opt(exception=True).warning("list 系统异常降级返空 user_id={}", user_id)
            return []

    def update_memory(self, current: CurrentUser, memory_id: str, text: str) -> None:
        """编辑单条记忆 text. 跨用户 → PermissionError (router 翻译 403). 其它异常 → 上抛 500.

        **跟 search/add 降级不同**: 这是用户主动操作, 失败要让前端感知.
        """
        user_id = _resolve_mem0_user_id(current)
        try:
            m = self._get_memory(user_id)
            if m is None:
                raise RuntimeError("记忆服务不可用, 请稍后重试或联系管理员")
            self._assert_owned(m.get(memory_id), user_id, memory_id)
            m.update(memory_id, text, None)
        except PermissionError:
            raise  # 隔离异常不吞
        except Exception as e:
            logger.opt(exception=True).warning("update failed user_id={} id={} err={}", user_id, memory_id, e)
            raise

    def delete_memory(self, current: CurrentUser, memory_id: str) -> None:
        """删单条. 跨用户 → PermissionError. 其它异常 → 上抛."""
        user_id = _resolve_mem0_user_id(current)
        try:
            m = self._get_memory(user_id)
            if m is None:
                raise RuntimeError("记忆服务不可用, 请稍后重试或联系管理员")
            self._assert_owned(m.get(memory_id), user_id, memory_id)
            m.delete(memory_id)
        except PermissionError:
            raise
        except Exception as e:
            logger.opt(exception=True).warning("delete failed user_id={} id={} err={}", user_id, memory_id, e)
            raise

    def delete_all_memories(self, current: CurrentUser) -> int:
        """清空当前用户所有记忆. m.delete_all(user_id=user_id) 自带隔离. 失败 → 上抛.

        mem0 delete_all 返 dict {"message": "..."}, 不返 count, 占位返 0.
        """
        user_id = _resolve_mem0_user_id(current)
        try:
            m = self._get_memory(user_id)
            if m is None:
                raise RuntimeError("记忆服务不可用, 请稍后重试或联系管理员")
            m.delete_all(user_id=user_id)
            return 0
        except Exception as e:
            logger.opt(exception=True).warning("delete_all failed user_id={} err={}", user_id, e)
            raise


def get_memory_service() -> MemoryService:
    """工厂函数: 每次返回新的 MemoryService 实例.

    替代模块级单例模式, 避免线程安全问题.
    """
    return MemoryService()
