"""config 包 — 配置集中管理

包含:
- settings.py: env 变量集中管理 (ARCH-003 + ARCH-004)
  - 普通字段: env > settings > defaults 三级 fallback
  - 嵌套 dataclass: paths (input_dir / output_dir), cad_config (ODA 路径), archive_config (解压限制)
  - 业务代码: from src.config.settings import settings; settings.paths.output_dir

2026-06-29 ARCH-004 迁移: 删 config_legacy.py 跟 src/ingest/config.py 的 config.toml 加载器,
全部改走 env (settings.py). 唯一引用方 tests/test_config.py 同步删除.
"""

from src.config.settings import settings  # noqa: F401
