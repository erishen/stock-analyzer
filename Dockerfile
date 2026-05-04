# Stock Analyzer Dockerfile
# 股票数据分析工具
# 使用华为云镜像加速

FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.13-slim as builder

WORKDIR /app

# 使用阿里云镜像源
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 使用阿里云 PyPI 镜像（国内稳定）
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set global.trusted-host mirrors.aliyun.com && \
    pip config set global.timeout 120 && \
    pip install --no-cache-dir --upgrade pip wheel setuptools

# 复制 investkit_utils 并安装
COPY investkit_utils /tmp/investkit_utils
RUN pip install --no-cache-dir --timeout 120 /tmp/investkit_utils && rm -rf /tmp/investkit_utils

# 复制 stock-analyzer 项目文件
COPY stock-analyzer /app

# 移除 pyproject.toml 中的 investkit-utils 本地依赖（已单独安装）
RUN sed -i '/investkit-utils @ file:/d' pyproject.toml

# 安装依赖（非可编辑模式）
RUN pip install --no-cache-dir --timeout 120 .

FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.13-slim

WORKDIR /app

# 使用阿里云镜像源
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制安装的包
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

RUN mkdir -p /app/cache /app/logs

ENV PYTHONUNBUFFERED=1
ENV STOCK_ANALYZER_ENV=production

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD stock-analyzer --help || exit 1

CMD ["stock-analyzer", "--help"]

LABEL maintainer="InvestKit Team"
LABEL version="1.0.0"
LABEL description="Stock Analyzer - 股票数据分析工具"
