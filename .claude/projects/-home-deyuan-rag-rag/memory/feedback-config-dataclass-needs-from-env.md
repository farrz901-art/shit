---
name: feedback-config-dataclass-needs-from-env
description: "config dataclass 必须用 .from_env() classmethod 显式读 env, 不能 Config() 无参 (无参走 dataclass 默认值, 不读 env, 必翻车)"
metadata:
  node_type: memory
  type: feedback
  originSessionId: pgvector-auth-fix-2026-06-15
---

`config dataclass` 模式 (`@dataclass` with default values) 的安全用法 = **永远用 `.from_env()` classmethod 读 env**, 绝不能 `Config()` 无参.

`Config()` 无参走的是 dataclass 字段默认值 (例如 `password: str = "postgres"`), 跟 .env / docker 实际配的值脱钩. 在能 load_dotenv 的环境里, 看似"没人传参也能跑", 实则用的是 fake 默认值, 跟真服务认证信息对不上.

**真案 (2026-06-15):** `check_pgvector` 调 `PGVectorConfig()` 无参 → password = dataclass 默认 `"postgres"` → docker POSTGRES_PASSWORD=`deyuan888` → psycopg2 `password authentication failed for user "postgres"`. 修了 1 行 (改成 `PGVectorConfig.from_env()`), 写 3 个 unit test 钉死 (用 `engine.url.password` 验, 注意 `str(engine.url)` 会把密码 mask 成 `***`).

**Why:** dataclass 默认值是"占位", 不是"配置源". 真配置源永远是 env / config 文件 / 显式传参. `from_env()` 模式把"读 env"和"默认 fallback"集中在一处, 强制所有调用方走同一条路. `Config()` 静默用默认值, 调试时根本没线索.

**How to apply:**
- 写新 config dataclass 时, **强制**提供 `from_env(cls) -> Self` classmethod, 内部 `os.getenv("KEY", defaults.DEFAULT_KEY)`
- 文档/类型注解明确标"必须用 `.from_env()`"
- lint / code review: 看到 `Config()` 无参实例化 + 同文件存在 `from_env` → 标"必须改 from_env"
- 单元测试: `monkeypatch.setenv("KEY", "xxx")` + 验 `instance.field == "xxx"`, 必须用 `engine.url.password` 不要用 `str(url)` (后者 mask 密码)
- 现有可疑点: 任何 `from src.X.config import YConfig; YConfig()` 调用都该审计一遍, 改成 `YConfig.from_env()`
