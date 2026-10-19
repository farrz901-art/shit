"""buyer_profile/extractor.py: LLM 提取引擎 (2026-06-22)

从对话历史中提取买家结构化画像字段.
由 service.try_extract 触发, fire-and-forget 模式.
"""

from __future__ import annotations

import json
from typing import Any


def _build_extraction_prompt(
    configs: list[dict],
    existing: dict,
    messages: list[dict],
) -> str:
    """构建 LLM 提取提示, 包含已有画像 / 待提取字段 / 对话历史."""
    field_descs: list[str] = []
    for cfg in configs:
        hint = cfg.get("extraction_prompt") or "Extract " + cfg["label"]
        field_descs.append(
            f"- {cfg['code']} ({cfg['label']}, type={cfg['field_type']}): {hint}",
        )

    existing_json = json.dumps(existing, ensure_ascii=False)[:2000]
    conv_lines = "\n".join(f"{m.get('role', '?')}: {m.get('content', '')}" for m in messages[-10:])

    return f"""You are a procurement analyst. Extract buyer profile fields from the conversation.

Existing profile (keep unchanged if no new info):
{existing_json}

Configured fields:
{chr(10).join(field_descs)}

Conversation:
{conv_lines}

Output JSON with field codes as keys and extracted values. Use null for no info.
For tags type, value is an array. Only output JSON, no extra text."""


def _call_llm(prompt: str) -> dict[str, Any]:
    """调用 LLM 提取字段, 解析 JSON 返回.

    (2026-06-29 LC 替换) OpenAILLM 内部已切到 ChatOpenAI, API 从
    `.complete + .text` 改 `.invoke + .content`. 支持 deepseek 等 OpenAI 兼容端点.
    """
    # 推迟副作用: 测试 monkeypatch `src.generation.llm.OpenAILLM`, 顶层 import 会把真 OpenAILLM
    # 绑定到 extractor 模块名, 后续 patch 失效 → _call_llm 走真 LLM 调用. 函数内 import
    # 每次调用时再解析 src.generation.llm.OpenAILLM 名字, monkeypatch 命中.
    from src.generation.llm import OpenAILLM  # noqa: E402

    llm = OpenAILLM().llm
    resp = llm.invoke(prompt)  # 返 AIMessage
    # AIMessage.content 类型是 `str | list[...]` (multi-modal 可能 list), 我们只 prompt
    # 纯文本所以一定 str, 这里 isinstance 守卫 + str() 兜底让 pyright narrow.
    raw = resp.content if hasattr(resp, "content") else resp
    text = raw if isinstance(raw, str) else str(raw)

    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    result = json.loads(cleaned)
    if not isinstance(result, dict):
        return {}
    return {k: v for k, v in result.items() if v is not None}


def extract_fields(
    configs: list[dict],
    existing: dict,
    messages: list[dict],
) -> dict[str, Any]:
    """从对话中提取画像字段.

    参数:
        configs:   get_active_configs 返回的字段配置列表
        existing:  当前已有 profile_data (dict)
        messages:  对话消息列表 [{role, content}, ...]

    返回:
        {field_code: value} dict, None 值的 key 被过滤.
    """
    prompt = _build_extraction_prompt(configs, existing, messages)
    return _call_llm(prompt)
