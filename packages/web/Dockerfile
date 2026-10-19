# syntax=docker/dockerfile:1.7
# ============================================================
#  Next.js 16 生产镜像 (bun + standalone 多阶段构建)
#  前置: next.config.ts 启用 output: 'standalone'
#  构建: docker build -t rag-web .
#  运行: docker run -p 3000:3000 rag-web
# ============================================================

# ---------- 阶段 1: 依赖安装 ----------
# 用官方 oven/bun 镜像装依赖, 配合 --frozen-lockfile 保证可复现
FROM oven/bun:1-alpine AS deps
WORKDIR /app

# 仅复制 lock 和 manifest, 利用 Docker 层缓存 (源码变动不重装依赖)
COPY package.json bun.lock* ./
RUN bun install --frozen-lockfile

# ---------- 阶段 2: 构建产物 ----------
FROM oven/bun:1-alpine AS builder
WORKDIR /app

# 复用 deps 阶段的 node_modules
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# 关闭 Next.js 遥测上报 (容器内无意义且产生噪音)
ENV NEXT_TELEMETRY_DISABLED=1

# NEXT_PUBLIC_* 变量在 build 时被烤进浏览器端 JS 包, 运行时 env 对它无效,
# 所以必须在 `bun run build` 之前, 通过 build arg 接收并声明成 ENV.
# 聊天 CSRF 校验要求 NEXT_PUBLIC_CHAT_TOKEN == 后端 CHAT_PUBLIC_TOKEN, 两者必须一致.
#
# 设计权衡 (Next.js 官方 environment-variables 指南):
#   - 官方原文: build+deploy 单镜像到多环境时, 所有 NEXT_PUBLIC_* 会在 build 时被"冻结",
#     换环境需重新 build. 详见 node_modules/next/dist/docs/01-app/02-guides/environment-variables.md (§Runtime)
#   - 官方"最优"方案是运行时注入 (服务端 process.env + 自建 API 吐给浏览器), 好处是一个镜像跑遍
#     dev/staging/prod. 但那要改客户端代码 (lib/api/chat.ts 客户端读) + 加 API, 是为 CI/CD 多环境晋升设计的.
#   - 本项目单机 compose 自建, token 值几乎不变, 用 build arg 是官方明确列出的合规常规做法, 不是 hack.
#     故意选它: 避免为一个极少变的 token 上运行时注入的过度工程.
#   - 改了此值必须重新 build (docker compose build web), 光 restart 不生效.
ARG NEXT_PUBLIC_CHAT_TOKEN
ENV NEXT_PUBLIC_CHAT_TOKEN=${NEXT_PUBLIC_CHAT_TOKEN}

# 生成 .next 生产构建 (next-intl / Tailwind v4 等均在构建期生效)
#  standalone 模式会在 .next/standalone/ 输出自包含的 Node 服务
RUN bun run build

# ---------- 阶段 3: 运行时 ----------
# standalone 输出已含最小化 node_modules + server.js, 基础镜像只需 bun 运行时
FROM oven/bun:1-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
# 监听所有网卡, 让容器外能访问 (next start 默认只绑 localhost)
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

# 用非 root 用户运行, 容器逃逸时降权
RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

# 复制 standalone 主体 (含 server.js + 最小化 node_modules + 源码 build 输出)
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
# 静态资源 (CSS/JS chunks/图片) 需单独复制, standalone 默认不含
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
# public 目录同理
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000

# 直接执行 standalone 自带的 server.js (含 Next.js server + 追踪到的依赖)
CMD ["bun", "server.js"]
