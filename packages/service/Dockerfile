# syntax=docker/dockerfile:1.7
# ============================================================
#  RAG FastAPI 后端生产镜像 (uv 多阶段构建)
#  前置: pyproject.toml + uv.lock 已就绪
#  构建: docker build -t rag-service .
#  运行: docker run -p 8000:8000 --env-file .env.local rag-service
#  监控: curl http://localhost:8000/health  (src/kg/router.py:116)
# ============================================================

# ---------- 阶段 1: 依赖构建 ----------
# 用官方 uv 镜像, 自带 Python 3.14 + uv, 不用单独装 pip / venv
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder
WORKDIR /app

# uv 默认用 hardlink 跨 stage 同步 .venv, 改成 copy 避免 COPY --from 拿到的链接悬空
ENV UV_LINK_MODE=copy
# 预编译 .pyc 到 .venv, 启动少做一次 lazy compile
ENV UV_COMPILE_BYTECODE=1

# 仅复制依赖清单, 利用 Docker 层缓存 (源码变动不重装依赖)
COPY pyproject.toml uv.lock ./

# 装 prod 依赖到 .venv, --no-dev 排除 pytest/ruff/pyright 等
# --no-install-project: 不把当前项目当 wheel 装, 后面单独 COPY 源码即可 (main.py 用 sys.path 找 src/)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# (2026-07-07) 下载 spacy 模型 (~40MB), 给 PreAnalysisRunner.spacy 增强器 / KG router 用
# 跟 src/kg/router.py:720 的 zh_core_web_sm 并列, 跟 src/ingest/pre_analysis/runner.py 的 en 用
RUN uv run spacy download en_core_web_sm

# 源码 + 必要配置 (prompts/configs 是代码引用, 必须跟镜像走; scripts/ 是工具脚本不进镜像)
COPY src ./src
COPY main.py alembic.ini pyproject.toml ./
COPY prompts ./prompts
COPY configs ./configs
COPY config.toml ./

# ---------- 阶段 2: 运行时 ----------
FROM python:3.14-slim AS runner
WORKDIR /app

# Python 容器默认缓冲 stdout, 设 unbuffered 让 docker logs 实时刷
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# 监听所有网卡 (uvicorn 默认绑 localhost)
ENV HOST=0.0.0.0
ENV PORT=8000
# 让 venv 的 python / uvicorn / fastapi 优先于系统
ENV PATH="/app/.venv/bin:$PATH"

# 用非 root 用户运行, 容器逃逸时降权
RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --home /app app

# 从 builder 复制 venv + 源码 (venv 含解释器+所有 prod 依赖, 体积大头)
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src
COPY --from=builder --chown=app:app /app/main.py /app/main.py
COPY --from=builder --chown=app:app /app/alembic.ini /app/alembic.ini
COPY --from=builder --chown=app:app /app/prompts /app/prompts
COPY --from=builder --chown=app:app /app/configs /app/configs
COPY --from=builder --chown=app:app /app/config.toml /app/config.toml

# 运行时写数据的目录 (用 volume mount 覆盖, 别让容器写进镜像层)
RUN mkdir -p /app/data /app/ingest_uploads /app/reports \
    && chown -R app:app /app/data /app/ingest_uploads /app/reports

USER app
EXPOSE 8000

# 监控检查用 stdlib urllib, 不用装 curl (start-period 留 15s 给 uvicorn 起来 + 模型 warmup)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3).read()" || exit 1

# 默认走 serve 模式 (main.py:64-66 没指定子命令 → serve)
# 想跑 ingest 时: docker run ... rag-service python main.py ingest /data
CMD ["python", "main.py"]
