# syntax=docker/dockerfile:1
# ============================================================
# Stock Analyzer — invest-kit monorepo member
# Build context: invest-kit/（仓库根，见 .dockerignore）
# 数据目录（data/ 内三个 DB）不进镜像，运行时由宿主机 bind mount 共享
# ============================================================

# ---------- Stage 1: 前端构建（产物进 src/web/static，FastAPI 直接托管） ----------
FROM node:22-slim AS frontend

ARG PNPM_REGISTRY=https://registry.npmmirror.com

WORKDIR /build

# 先装依赖（利用缓存层）
COPY apps/stock-analyzer/frontend/package.json apps/stock-analyzer/frontend/pnpm-lock.yaml ./frontend/
RUN corepack enable \
    && cd frontend \
    && pnpm install --frozen-lockfile --registry=${PNPM_REGISTRY} --allow-build=esbuild

# 再拷贝源码并构建
COPY apps/stock-analyzer/frontend/ ./frontend/
RUN cd frontend && pnpm build
# vite outDir 为 '../src/web/static' → 产物位于 /build/src/web/static

# ---------- Stage 2: Python 运行时 ----------
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

RUN pip install --no-cache-dir uv \
    && mkdir -p /app/apps/stock-analyzer/{data,output,logs}

WORKDIR /app

# uv workspace 元数据 + stock-analyzer 依赖树所需源码（仅本 member）
COPY pyproject.toml uv.lock ./
COPY libs/investkit_utils/ ./libs/investkit_utils/
COPY apps/stock-analyzer/pyproject.toml ./apps/stock-analyzer/
COPY apps/stock-analyzer/src/ ./apps/stock-analyzer/src/
COPY apps/stock-analyzer/scripts/ ./apps/stock-analyzer/scripts/

WORKDIR /app/apps/stock-analyzer
RUN uv sync --extra web --no-dev --no-cache

# 前端静态产物（git 已提交的旧 build 会被此层覆盖为最新）
COPY --from=frontend /build/src/web/static ./src/web/static

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8001/api/enabled',timeout=5)"

# 数据路径由 compose 注入（/app/apps/stock-analyzer/data 挂载宿主 data/）
CMD ["uv", "run", "stock-analyzer", "web", "--host", "0.0.0.0", "--port", "8001"]
