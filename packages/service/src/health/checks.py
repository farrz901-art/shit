"""Health check 函数 (2026-06-11)

5 个独立 async 函数, 各返 CheckResult. 失败不抛异常, 字段 status="error" + error="<msg>".
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Literal

import psutil
import requests as _requests

from src.config.settings import settings

from ..storage import get_object_store as _get_object_store

# GPU 采样拆到独立模块 (2026-07-07). 见 src/health/gpu.py 设计说明.
from . import gpu as _gpu

# 模块加载时间戳, 算 uptime
_PROCESS_START_TIME = time.time()
_VERSION = "0.1.0"


@dataclass
class CheckResult:
    """单个 check 结果. latency_ms 是核心, 特有信息走 extra."""

    status: Literal["ok", "error"]
    latency_ms: float | None = None
    error: str | None = None
    extra: dict = field(default_factory=dict)


# ---------- Python 进程自身 ----------


def check_python() -> CheckResult:
    """读 _PROCESS_START_TIME 算 uptime. 本地读, latency=0."""
    return CheckResult(
        status="ok",
        latency_ms=0.0,
        error=None,
        extra={"uptime_s": int(time.time() - _PROCESS_START_TIME), "version": _VERSION},
    )


# ---------- 依赖注入 helper (单测 mock 切入点) ----------


def _get_dify_client():
    """构造 DifyClient 实例, 顶层 lazy import 避免循环依赖"""
    # 重依赖 lazy: Dify client 冷启动慢 (httpx client + 重试), 非健康检查路径不需要
    from src.integrations.dify_client import DifyClient  # noqa: E402

    return DifyClient()


def _get_neo4j_store():
    """从 src.kg.neo4j 拿 store"""
    # 重依赖 lazy: neo4j driver 启动慢 (~500ms), 非 Neo4j 健康检查路径不需要
    from src.kg.neo4j import get_neo4j_store  # noqa: E402

    return get_neo4j_store()


def _get_pg_engine():
    """直接 sqlalchemy create_engine, 不走 LC PGEngine (健康检查不需要 vector store 完整初始化).

    必须用 PGVectorConfig.from_env() 走 PG_* 环境变量, 绝不能 PGVectorConfig() 无参
    (后者走 dataclass 默认 password='postgres', 跟 docker/.env 实际密码 deyuan888
    对不上 → psycopg2.OperationalError 认证失败).
    """
    # 重依赖 lazy: 避免 health check 启动时立即 import sqlalchemy + vector_store 整套
    from sqlalchemy import create_engine  # noqa: E402

    # 重依赖 lazy: vector_store 触发 langchain_postgres 装载 (~1.2s)
    from src.retrieval.vector_store import PGVectorConfig  # noqa: E402

    cfg = PGVectorConfig.from_env()
    return create_engine(cfg.connection_string, pool_pre_ping=True)


# GPU 采样 (NVML + PCI 兜底) 拆到 gpu.py, 这里只 delegate 调用.
# 公共入口用模块级 alias 避免改 check_system body.
_sample_gpu = _gpu._sample_gpu
_sample_pci_gpus = _gpu._sample_pci_gpus


# ---------- Dify ----------


async def check_dify() -> CheckResult:
    """ping Dify 数据集端点, 算 latency.

    注: 不用 DifyClient (DifyClient 拿的是 DIFY_CHAT_API_KEY chatflow key,
    不能调数据集端点). 直接用 DIFY_DATASET_API_KEY (dataset key) + requests,
    跟 kg/router.py /api/kg/health 端点逻辑一致.
    """
    t0 = time.perf_counter()
    try:
        # 直接读 env 不走 settings 单例: settings 在 import 时 freeze,
        # test 用 patch.dict('os.environ') 改 DIFY_DATASET_API_KEY 需要 lazy 读
        base_url = os.getenv("DIFY_BASE_URL", settings.dify_base_url)
        api_key = os.getenv("DIFY_DATASET_API_KEY", "")
        if not api_key:
            return CheckResult(status="error", latency_ms=None, error="DIFY_DATASET_API_KEY 未配置")
        resp = await asyncio.to_thread(
            _requests.get,
            f"{base_url}/datasets?limit=1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5,
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0
        if resp.status_code >= 400:
            return CheckResult(status="error", latency_ms=None, error=f"HTTP {resp.status_code}")
        return CheckResult(status="ok", latency_ms=latency_ms)
    except Exception as e:
        return CheckResult(status="error", latency_ms=None, error=str(e))


# ---------- Neo4j ----------


async def check_neo4j() -> CheckResult:
    """Neo4jStore.verify_connectivity() (内部 driver.session().run)"""
    t0 = time.perf_counter()
    try:
        store = _get_neo4j_store()
        await asyncio.to_thread(store.verify_connectivity)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return CheckResult(status="ok", latency_ms=latency_ms)
    except Exception as e:
        return CheckResult(status="error", latency_ms=None, error=str(e))


# ---------- pgvector ----------


async def check_pgvector() -> CheckResult:
    """直接 sqlalchemy 跑 SELECT 1, 绕开 PGVectorStore 重初始化"""
    # 重依赖 lazy: sqlalchemy text 编译慢, 仅 health check 实际跑 SQL 时才需要
    from sqlalchemy import text as _text  # noqa: E402

    t0 = time.perf_counter()
    try:
        engine = _get_pg_engine()

        def _run():
            with engine.connect() as conn:
                result = conn.execute(_text("SELECT 1"))
                return result.scalar()

        val = await asyncio.to_thread(_run)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        if val != 1:
            return CheckResult(status="error", latency_ms=latency_ms, error=f"unexpected: {val}")
        return CheckResult(status="ok", latency_ms=latency_ms)
    except Exception as e:
        return CheckResult(status="error", latency_ms=None, error=str(e))


# ---------- 主机资源 ----------


async def check_system() -> CheckResult:
    """psutil CPU/内存 + NVIDIA NVML GPU + PCI 兜底. GPU 缺失优雅降级.

    GPU 采样策略 (2026-07-07):
    1. 先跑 NVML (nvidia-ml-py) — 拿得到就用, 数据最准 (含 util/mem_used)
    2. NVML 失败/空 → 跑 PCI sysfs 兜底 — 不依赖驱动, 列出硬件存在的 GPU
    3. 都空 → extra.gpu=[], extra.gpu_source="empty"
    NVML 错误 message 放进 extra.gpu_error, admin 能区分"驱动坏了"vs"真没 GPU".

    合并逻辑 (2026-07-07): NVML 只能识别 NVIDIA, 不会列 AMD/Intel 集显.
    因此 PCI 列表中 vendor 名以 "NVIDIA" 开头的条目视为 NVML 重复, 按 PCI name 跟
    NVML name 任一前缀匹配去重; 其余 (AMD/Intel) 追加. 这样 NVML 正常时, 独显
    走 NVML (数据最准), 集显走 PCI (admin 也能看到).
    """
    t0 = time.perf_counter()
    try:
        cpu_pct = psutil.cpu_percent(interval=0.1)  # Windows 必须 interval>=0.1
        mem = psutil.virtual_memory()
        gpus_nvml, nvml_err = await asyncio.to_thread(_sample_gpu)
        gpus_pci = await asyncio.to_thread(_sample_pci_gpus)
        # NVML 拿到的 NVIDIA name 集合 (用于 PCI 去重, vendor 不在集合的 PCI 条目保留)
        nvml_names = {g["name"] for g in gpus_nvml}
        # PCI 列表: 跳过已被 NVML 覆盖的 NVIDIA 设备 (按 vendor 前缀)
        # NVML 返 "NVIDIA GeForce RTX ..." 完整型号, PCI 返 "NVIDIA [0x2c05]" 设备 ID
        # 两者 name 不等, 用 PCI 条目 vendor 名以 "NVIDIA" 开头 + 任一 NVML name 也以 "NVIDIA" 开头判定
        has_nvml_nvidia = any(n.startswith("NVIDIA") for n in nvml_names)
        gpus_pci_filtered = [g for g in gpus_pci if not (has_nvml_nvidia and g["name"].startswith("NVIDIA "))]
        # 合并: NVML 优先 (数据最准), 追加 PCI 中非 NVIDIA 的 (AMD/Intel 集显)
        if gpus_nvml and gpus_pci_filtered:
            gpus = gpus_nvml + gpus_pci_filtered
            source = "nvml+pci"
        elif gpus_nvml:
            gpus = gpus_nvml
            source = "nvml"
        elif gpus_pci:
            gpus = gpus_pci
            source = "pci"
        else:
            gpus = []
            source = "empty"
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return CheckResult(
            status="ok",
            latency_ms=latency_ms,
            extra={
                "cpu_pct": cpu_pct,
                "mem_pct": mem.percent,
                "mem_used_mb": mem.used // (1024 * 1024),
                "mem_total_mb": mem.total // (1024 * 1024),
                "gpu": gpus,
                "gpu_error": nvml_err,
                "gpu_source": source,
            },
        )
    except Exception as e:
        return CheckResult(status="error", latency_ms=None, error=str(e))


# ---------- ObjectStore (MinIO) ----------


async def check_minio() -> CheckResult:
    """(2026-06-16) ping ObjectStore backend. (2026-07-07) 改 probe 文件模式.

    - local backend: status=ok + extra.skipped=True (不调 IO, 跟 G1 一致)
    - minio backend: 用 probe 文件 `s3://{bucket}/.health-probe/ready` 测可达.
      exists 命中 → ok; 缺失 → 自动 put_bytes 创建 → ok. 失败翻 error.

    设计依据: 旧实现走 `list_prefix(f"s3://{bucket}/")` 列根目录, 但
    `parse_uri("s3://rag-ingest/")` 的 path=`/`, lstrip 后变空 key → ValueError("URI 缺 key"),
    health check 永远 error 即使 MinIO 正常. probe 文件模式绕开根目录列前缀,
    测的是"能不能命中/创建已存在的 key"这个真实业务语义.
    """
    t0 = time.perf_counter()
    try:
        store = _get_object_store()
        if store.backend_name() == "local":
            return CheckResult(
                status="ok",
                latency_ms=0.0,
                extra={"backend": "local", "skipped": True},
            )

        # minio backend: probe 文件探测 (exists + 首次缺失自动 put_bytes)
        # MinioObjectStore 才有 _bucket / _endpoint, ABC 不声明; 实际 backend_name() != 'local' 时一定是 Minio impl
        def _probe():
            bucket = store._bucket  # type: ignore[attr-defined]
            probe_uri = f"s3://{bucket}/.health-probe/ready"
            if store.exists(probe_uri):
                return
            store.put_bytes(probe_uri, b"ok", mime="text/plain")

        await asyncio.to_thread(_probe)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return CheckResult(
            status="ok",
            latency_ms=latency_ms,
            extra={
                "backend": "minio",
                "bucket": store._bucket,  # type: ignore[attr-defined]
                "endpoint": store._endpoint,  # type: ignore[attr-defined]
            },
        )
    except Exception as e:
        return CheckResult(status="error", latency_ms=None, error=str(e))


# ---------- Redis ----------


def _get_redis_client():
    """构造 Redis 连接, 给 check_redis + 测试 mock 切入点.
    用 env 变量配置: REDIS_HOST (默认 localhost), REDIS_PORT (默认 6379), REDIS_PASSWORD.
    """
    # 重依赖 lazy: redis async 客户端延迟到 health check, 启动期不付出
    import redis as _redis  # noqa: E402

    host = settings.redis_host
    port = settings.redis_port
    password = settings.redis_password or None  # None = no auth
    return _redis.Redis(
        host=host,
        port=port,
        password=password,
        socket_connect_timeout=5,
        socket_timeout=5,
    )


async def check_redis() -> CheckResult:
    """ping Redis 服务器, 算 latency. 走 asyncio.to_thread + _get_redis_client().
    失败翻 status=error.
    """
    t0 = time.perf_counter()
    try:
        client = _get_redis_client()

        def _ping():
            return client.ping()

        ok = await asyncio.to_thread(_ping)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        if not ok:
            return CheckResult(status="error", latency_ms=latency_ms, error="Redis PING returned False")
        return CheckResult(status="ok", latency_ms=latency_ms)
    except Exception as e:
        return CheckResult(status="error", latency_ms=None, error=str(e))
