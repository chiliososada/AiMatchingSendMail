# ==========================================
# 邮件API系统 Dockerfile
# 多阶段构建，优化镜像大小和安全性
# ==========================================

# ==========================================
# 阶段1：基础镜像
# ==========================================
FROM python:3.11-slim as base

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.6.1

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    # 构建工具
    build-essential \
    gcc \
    g++ \
    # PostgreSQL客户端库
    libpq-dev \
    # 其他系统库
    libffi-dev \
    libssl-dev \
    # 文件类型检测
    libmagic1 \
    # 图像处理
    libjpeg-dev \
    libpng-dev \
    # 压缩库
    zlib1g-dev \
    # 清理APT缓存
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ==========================================
# 阶段2：依赖安装
# ==========================================
FROM base as dependencies

# 升级pip
RUN pip install --upgrade pip

# 复制依赖文件
COPY requirements.txt /tmp/requirements.txt

# 安装Python依赖
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# ==========================================
# 阶段3：应用构建
# ==========================================
FROM dependencies as builder

# 创建应用目录
WORKDIR /app

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p uploads/attachments uploads/temp logs

# 设置目录权限
RUN chmod -R 755 uploads logs

# ==========================================
# 阶段4：生产镜像
# ==========================================
FROM python:3.11-slim as production

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production \
    TZ=Asia/Tokyo

# 安装运行时依赖
RUN apt-get update && apt-get install -y \
    # PostgreSQL客户端库（运行时）
    libpq5 \
    # 文件类型检测
    libmagic1 \
    # 时区数据
    tzdata \
    # 健康检查工具
    curl \
    # 进程管理
    procps \
    # 清理APT缓存
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 设置时区
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 创建非root用户
RUN groupadd -r emailapi && useradd -r -g emailapi emailapi

# 创建应用目录
WORKDIR /app

# 从builder阶段复制依赖
COPY --from=dependencies /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=dependencies /usr/local/bin/ /usr/local/bin/

# 复制应用代码
COPY --from=builder /app .

# 创建并设置目录权限
RUN mkdir -p uploads/attachments uploads/temp logs \
    && chown -R emailapi:emailapi /app \
    && chmod -R 755 uploads logs

# 创建健康检查脚本
RUN echo '#!/bin/bash\ncurl -f http://localhost:8000/health || exit 1' > /healthcheck.sh \
    && chmod +x /healthcheck.sh

# 切换到非root用户
USER emailapi

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD /healthcheck.sh

# 设置默认命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ==========================================
# 开发镜像（可选）
# ==========================================
FROM production as development

# 切换回root用户安装开发工具
USER root

# 安装开发依赖
RUN apt-get update && apt-get install -y \
    # 开发工具
    git \
    vim \
    wget \
    # 网络调试工具
    iputils-ping \
    net-tools \
    # 系统监控工具
    htop \
    # 清理APT缓存
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 安装开发Python包
RUN pip install --no-cache-dir \
    pytest \
    pytest-asyncio \
    pytest-cov \
    black \
    flake8 \
    isort \
    mypy \
    watchfiles

# 切换回应用用户
USER emailapi

# 开发环境启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ==========================================
# 镜像元数据
# ==========================================
LABEL maintainer="your-email@domain.com"
LABEL version="2.0.0"
LABEL description="Email API Service with Attachment Support"
LABEL org.opencontainers.image.source="https://github.com/yourusername/email-api"
LABEL org.opencontainers.image.documentation="https://github.com/yourusername/email-api/README.md"
LABEL org.opencontainers.image.vendor="Your Company"
LABEL org.opencontainers.image.licenses="MIT"

# ==========================================
# 构建说明
# ==========================================

# 构建生产镜像：
# docker build --target production -t email-api:latest .

# 构建开发镜像：
# docker build --target development -t email-api:dev .

# 运行容器：
# docker run -d \
#   --name email-api \
#   -p 8000:8000 \
#   -e DATABASE_URL="postgresql://user:pass@db:5432/email_db" \
#   -e SECRET_KEY="your-secret-key" \
#   -e ENCRYPTION_KEY="your-encryption-key" \
#   -v email_uploads:/app/uploads \
#   email-api:latest

# 多平台构建（支持ARM64）：
# docker buildx build --platform linux/amd64,linux/arm64 -t email-api:latest . --push