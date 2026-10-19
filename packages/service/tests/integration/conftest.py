"""集成测试 conftest

(2026-06-29) 删除 db_session fixture: 真连 PG 违反 CLAUDE.md §强制测试隔离, 整个 fixture 死代码.
CI 集成测 (模式 2) 改走 tests/integration/test_*_e2e.py + 真外部服务 (MinIO / Docker),
全部走各自的 pytestmark.skipif 守卫 (OBJECT_STORE_BACKEND=minio / _docker_daemon_alive).

本文件保留空 conftest 给 pytest fixture 机制 (pytest 不跨 sibling 找 conftest).
"""
