---
name: feedback-pg-host-no-scheme
description: "PG_HOST 必须裸 host/IP, 不能写 http:// 前缀; SA 解析 postgresql URL 时 _assert_port 会拿空 port 字符串炸 int('')"
metadata: 
  node_type: memory
  originSessionId: b1a94925-2e93-4b01-a14f-390f8aa9dc75
---

`PG_HOST` 是裸 host 字段, 跟 NEO4J_URI/DIFY_BASE_URL 不一样——后两者是整串 URL(`bolt://...` / `http://...`),由 client 自己解析;`PG_HOST/PORT/USER/PASSWORD/DATABASE` 5 个字段是裸分量,`src/common/db_url.py::get_rag_db_url()` 自己拼。

如果用户在 `.env.local` 写了 `PG_HOST=http://192.168.3.52`,最终 URL 会变成:

```
postgresql+psycopg://postgres:***@http://192.168.3.52:5432/rag
```

SA 的 `_parse_url` 看到 `http:` 把它当 drivername, 后面 host 变成 `//192.168.3.52`, port 直接空字符串 → `int('')` → `ValueError: invalid literal for int() with base 10: ''`。

**Why:** 2026-07-02 用户 alembic upgrade 撞这个, 报错信息跟"密码错 / PG 未启"长得一样, 完全不暗示 host scheme, 我从报错栈追到 SA `_assert_port` 再反推 env 才定位。同源 bug 还有 `REDIS_HOST=http://...`, 但 Redis client 自己用 host/port 字段, 错误信号更含糊, 没炸 alembic 用户没察觉。

**How to apply:**
- 不写 shim (剥 scheme) 兼容用户脏 env——违反 [[feedback-no-shim-no-minimal-changes]]
- alembic 入口诊断文案必须明示这个 case, 用户下次看错误信息就能自查 env
- 跟用户沟通时直接告诉他改 env: `PG_HOST=192.168.3.52` (去掉 http://)
- 模板参考: `.env.example` 里 `PG_HOST=localhost`、`REDIS_HOST=localhost`, 跟 `docker-compose.yml` 里覆盖 `PG_HOST: postgres` 一致
