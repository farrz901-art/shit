---
name: feedback-sa-json-psycopg3-dict-not-str
description: "SA 2.0 + psycopg3 读 sa.JSON() 列可能给 dict 不给 str, json.loads(dict) → TypeError, 必须 isinstance 兜"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 623e8a0b-5f11-4892-8333-52384121101e
---

SQLAlchemy 2.0 + psycopg3 + `sa.JSON()` 列 (非 JSONB),业务代码假设读出是 `str` 然后 `json.loads(m.meta)`,**实际可能读出是 `dict`** → 抛 `TypeError: the JSON object must be str, bytes or bytearray, not dict` → global handler 接住返 500 `{"detail":"Internal server error"}`。

**Why**: 2026-06-24 实战, `packages/service/src/chat/service.py:116` `get_conversation` 拉 messages 表 meta 列时炸。`messages.meta` 字段 ORM 定义是 `sa.JSON()` (存时 string),但 DB 实际列类型可能是 JSONB (历史 migration 写错过) 或 SA 2.0 driver 在某场景下主动反序列化为 dict。跟 [[feedback-postgres-json-vs-jsonb-opclass]] 同一族坑, 区别是那个是类型不匹配, 这个是 ORM 读出行为不一致。

**How to apply**:
1. **任何 `sa.JSON()` 字段读出后**不要直接 `json.loads`, 先 `isinstance(x, dict)` 分支。
2. 修法: `m.meta if isinstance(m.meta, dict) else (json.loads(m.meta) if m.meta else None)`。
3. 排查信号: 500 + `JSON object must be str, bytes or bytearray, not dict` + service.py:NN json.loads 栈 → 一定是这个错。
4. **真正的根因排查**需要看 DB 实际列类型 (`\d messages` 看 meta 列 type), 改 model 用 `JSONB` 跟列对齐可彻底避免 — 但 isinstance 兜底更稳, 兼容历史脏数据。
5. uvicorn 默认 reload=True, 但**改 src/*.py 不会自动热更** (有 sandbox / file watcher 限制), 看到老 stack 仍报 → 手动 kill + restart。
