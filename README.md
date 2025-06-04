# 邮件发送API系统

一个功能强大的多租户邮件发送系统，基于FastAPI构建，支持附件上传、SMTP配置管理、邮件队列、发送状态跟踪等完整功能。

## 📋 目录

- [功能特性](#功能特性)
- [系统架构](#系统架构)
- [快速开始](#快速开始)
- [API文档](#api文档)
- [配置说明](#配置说明)
- [部署指南](#部署指南)
- [开发指南](#开发指南)
- [故障排除](#故障排除)
- [许可证](#许可证)

## ✨ 功能特性

### 🚀 核心功能

- **多租户支持** - 完整的租户隔离机制
- **SMTP配置管理** - 支持多种SMTP服务商，密码加密存储
- **单发/群发邮件** - 支持单个收件人和批量发送
- **附件支持** - 完整的文件上传、验证、存储和发送功能
- **邮件队列** - 异步邮件发送队列，支持优先级和重试
- **发送状态跟踪** - 实时跟踪邮件发送状态和日志

### 🔒 安全特性

- **密码加密** - 使用Fernet加密算法保护SMTP密码
- **文件验证** - 多层文件安全验证，防止恶意文件上传
- **访问控制** - 基于租户的数据隔离
- **安全头部** - 完整的HTTP安全头部配置
- **速率限制** - API请求速率限制和防护

### 📊 管理功能

- **邮件模板** - 支持动态邮件模板和变量替换
- **统计报告** - 发送成功率、失败统计等分析
- **日志审计** - 完整的操作日志和邮件发送记录
- **健康监控** - 系统健康检查和性能监控

### 🛠 技术特性

- **异步处理** - 基于asyncio的高性能异步处理
- **数据库支持** - 支持PostgreSQL和SQLite
- **缓存机制** - Redis缓存提升性能
- **容器化** - 完整的Docker支持
- **可扩展性** - 微服务架构，易于扩展

## 🏗 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端应用      │    │   移动应用      │    │   第三方系统    │
│  (React/Vue)    │    │ (React Native)  │    │     (API)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Nginx/LB      │  ← 负载均衡
                    └─────────────────┘
                                 │
                    ┌─────────────────┐
                    │   FastAPI       │  ← 主应用
                    │   (Email API)   │
                    └─────────────────┘
                                 │
                 ┌───────────────┼───────────────┐
                 │               │               │
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │   PostgreSQL    │ │     Redis       │ │   文件存储      │
    │   (数据库)      │ │   (缓存/队列)   │ │  (附件存储)     │
    └─────────────────┘ └─────────────────┘ └─────────────────┘
```

## 🚀 快速开始

### 1. 环境要求

- Python 3.11+
- PostgreSQL 13+ 或 SQLite
- Redis 6+ (可选)
- Docker & Docker Compose (推荐)

### 2. 使用Docker快速部署

```bash
# 克隆项目
git clone https://github.com/yourusername/email-api.git
cd email-api

# 复制环境变量配置
cp .env.example .env

# 编辑配置文件（必须修改数据库密码和密钥）
vim .env

# 启动服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f email-api
```

### 3. 本地开发环境

```bash
# 克隆项目
git clone https://github.com/yourusername/email-api.git
cd email-api

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 启动数据库（使用Docker）
docker run -d \
  --name email_api_db \
  -e POSTGRES_DB=email_api_db \
  -e POSTGRES_USER=emailapi \
  -e POSTGRES_PASSWORD=emailapi123 \
  -p 5432:5432 \
  postgres:15-alpine

# 启动应用
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 验证安装

访问以下URL验证系统运行状态：

- API文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health
- 系统信息: http://localhost:8000/info

## 📚 API文档

### 主要API端点

#### SMTP配置管理

```http
# 创建SMTP配置
POST /api/v1/email/smtp-settings
Content-Type: application/json

{
    "tenant_id": "uuid",
    "setting_name": "Gmail SMTP",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_username": "your-email@gmail.com",
    "smtp_password": "your-app-password",
    "security_protocol": "TLS",
    "from_email": "your-email@gmail.com",
    "from_name": "发送者名称",
    "is_default": true
}

# 获取SMTP配置列表
GET /api/v1/email/smtp-settings/{tenant_id}

# 测试SMTP连接
POST /api/v1/email/smtp-settings/test
```

#### 附件管理

```http
# 上传单个附件
POST /api/v1/email/attachments/upload
Content-Type: multipart/form-data

tenant_id: uuid
file: [binary]

# 批量上传附件
POST /api/v1/email/attachments/upload-multiple
Content-Type: multipart/form-data

tenant_id: uuid
files: [binary array]

# 删除附件
DELETE /api/v1/email/attachments/{tenant_id}/{attachment_id}?filename=file.pdf
```

#### 邮件发送

```http
# 发送普通邮件
POST /api/v1/email/send
Content-Type: application/json

{
    "tenant_id": "uuid",
    "to_emails": ["recipient@example.com"],
    "subject": "邮件主题",
    "body_text": "纯文本内容",
    "body_html": "<p>HTML内容</p>",
    "priority": 5
}

# 发送带附件的邮件
POST /api/v1/email/send-with-attachments
Content-Type: application/json

{
    "tenant_id": "uuid",
    "to_emails": ["recipient@example.com"],
    "subject": "带附件的邮件",
    "body_text": "邮件内容",
    "attachment_ids": ["attachment-uuid-1", "attachment-uuid-2"]
}

# 批量发送邮件
POST /api/v1/email/send-bulk
```

#### 状态查询

```http
# 查询邮件状态
GET /api/v1/email/queue/{tenant_id}/{queue_id}

# 获取邮件队列列表
GET /api/v1/email/queue/{tenant_id}?limit=50&offset=0

# 获取发送统计
GET /api/v1/email/statistics/{tenant_id}?days=30
```

### 完整API文档

启动服务后访问 http://localhost:8000/docs 查看完整的交互式API文档。

## ⚙️ 配置说明

### 环境变量配置

主要配置项说明：

```bash
# 数据库配置
DATABASE_URL="postgresql://user:pass@host:5432/dbname"

# 安全配置
SECRET_KEY="your-secret-key"  # JWT签名密钥
ENCRYPTION_KEY="your-fernet-key"  # SMTP密码加密密钥

# 文件上传限制
MAX_FILE_SIZE=26214400  # 25MB
MAX_FILES_PER_REQUEST=10
MAX_TOTAL_REQUEST_SIZE=104857600  # 100MB

# 邮件发送限制
MAX_RECIPIENTS_PER_EMAIL=100
MAX_BULK_EMAILS=1000
EMAIL_TIMEOUT_SECONDS=60

# 前端CORS配置
BACKEND_CORS_ORIGINS='["http://localhost:3000","https://yourdomain.com"]'
```

### SMTP服务商配置示例

#### Gmail配置

```json
{
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_username": "your-email@gmail.com",
    "smtp_password": "your-app-password",  // 需要开启2FA并生成应用密码
    "security_protocol": "TLS"
}
```

#### Outlook配置

```json
{
    "smtp_host": "smtp-mail.outlook.com",
    "smtp_port": 587,
    "smtp_username": "your-email@outlook.com",
    "smtp_password": "your-password",
    "security_protocol": "TLS"
}
```

#### 企业邮箱配置

```json
{
    "smtp_host": "smtp.exmail.qq.com",  // 腾讯企业邮箱
    "smtp_port": 587,
    "smtp_username": "your-email@yourdomain.com",
    "smtp_password": "your-password",
    "security_protocol": "TLS"
}
```

## 🚀 部署指南

### Docker部署（推荐）

#### 1. 基础部署

```bash
# 克隆代码
git clone https://github.com/yourusername/email-api.git
cd email-api

# 配置环境变量
cp .env.example .env
vim .env  # 修改必要的配置

# 构建并启动
docker-compose up -d

# 检查服务状态
docker-compose ps
docker-compose logs -f
```

#### 2. 生产环境部署

```bash
# 使用生产配置
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 包含所有服务（队列、监控等）
docker-compose --profile production --profile queue --profile monitoring up -d
```

#### 3. 扩容部署

```bash
# 水平扩展API服务
docker-compose up -d --scale email-api=3

# 使用负载均衡
docker-compose --profile production up -d
```

### 手动部署

#### 1. 系统准备

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv postgresql redis-server nginx

# CentOS/RHEL
sudo yum install python3.11 postgresql-server redis nginx
```

#### 2. 应用部署

```bash
# 创建用户
sudo useradd -m -s /bin/bash emailapi

# 部署代码
sudo -u emailapi git clone https://github.com/yourusername/email-api.git /home/emailapi/app
cd /home/emailapi/app

# 安装依赖
sudo -u emailapi python3.11 -m venv venv
sudo -u emailapi venv/bin/pip install -r requirements.txt

# 配置环境变量
sudo -u emailapi cp .env.example .env
sudo -u emailapi vim .env

# 配置systemd服务
sudo cp deployment/email-api.service /etc/systemd/system/
sudo systemctl enable email-api
sudo systemctl start email-api
```

#### 3. Nginx配置

```nginx
# /etc/nginx/sites-available/email-api
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /uploads/ {
        alias /home/emailapi/app/uploads/;
        expires 1d;
    }
}
```

### 云平台部署

#### AWS ECS部署

```bash
# 构建并推送镜像到ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com
docker build -t email-api .
docker tag email-api:latest 123456789.dkr.ecr.us-east-1.amazonaws.com/email-api:latest
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/email-api:latest

# 使用提供的ECS任务定义文件
aws ecs register-task-definition --cli-input-json file://deployment/ecs-task-definition.json
```

#### Kubernetes部署

```bash
# 应用Kubernetes配置
kubectl apply -f deployment/k8s/

# 检查部署状态
kubectl get pods -l app=email-api
kubectl get services
```

## 👨‍💻 开发指南

### 项目结构

```
email_api/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI应用入口
│   ├── config.py               # 配置管理
│   ├── database.py             # 数据库连接
│   ├── models/
│   │   ├── __init__.py
│   │   └── email_models.py     # 数据模型
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── email_schemas.py    # 请求/响应模型
│   ├── services/
│   │   ├── __init__.py
│   │   ├── email_service.py    # 邮件业务逻辑
│   │   └── smtp_service.py     # SMTP服务
│   ├── api/
│   │   ├── __init__.py
│   │   └── email_routes.py     # API路由
│   └── utils/
│       ├── __init__.py
│       └── security.py         # 安全工具
├── tests/                      # 测试文件
├── deployment/                 # 部署配置
├── docs/                       # 文档
├── requirements.txt            # Python依赖
├── docker-compose.yml          # Docker编排
├── Dockerfile                  # Docker构建
└── README.md                   # 项目说明
```

### 开发环境设置

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 代码格式化
black app/
isort app/

# 类型检查
mypy app/

# 运行测试
pytest

# 生成测试覆盖率报告
pytest --cov=app --cov-report=html
```

### 添加新功能

1. **数据模型** - 在 `models/` 中定义SQLAlchemy模型
2. **请求模型** - 在 `schemas/` 中定义Pydantic模型
3. **业务逻辑** - 在 `services/` 中实现业务逻辑
4. **API路由** - 在 `api/` 中添加FastAPI路由
5. **测试** - 在 `tests/` 中添加测试用例

### 数据库迁移

```bash
# 生成迁移文件
alembic revision --autogenerate -m "Add new feature"

# 应用迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

### 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_email_service.py

# 运行并生成覆盖率报告
pytest --cov=app

# 性能测试
pytest tests/performance/
```

## 🔧 故障排除

### 常见问题

#### 1. SMTP连接失败

**问题**: SMTP连接测试失败

**解决方案**:
- 检查SMTP服务器地址和端口
- 验证用户名和密码
- 确认安全协议设置（TLS/SSL）
- 检查防火墙设置
- 对于Gmail，确保使用应用密码

```bash
# 测试SMTP连接
curl -X POST "http://localhost:8000/api/v1/email/smtp-settings/test" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "your-tenant-id",
    "smtp_setting_id": "your-smtp-setting-id"
  }'
```

#### 2. 文件上传失败

**问题**: 附件上传失败或文件过大

**解决方案**:
- 检查文件大小是否超过限制（默认25MB）
- 验证文件类型是否在允许列表中
- 检查磁盘空间
- 确认上传目录权限

```bash
# 检查上传目录
ls -la uploads/attachments/
df -h  # 检查磁盘空间
```

#### 3. 数据库连接问题

**问题**: 无法连接到数据库

**解决方案**:
- 检查数据库服务是否运行
- 验证连接字符串格式
- 检查数据库用户权限
- 确认网络连接

```bash
# 测试数据库连接
psql "postgresql://user:pass@host:5432/dbname"

# 检查数据库服务状态
sudo systemctl status postgresql
```

#### 4. 邮件发送超时

**问题**: 邮件发送超时或失败

**解决方案**:
- 增加超时时间设置
- 检查网络连接
- 验证SMTP服务器状态
- 检查邮件内容大小

#### 5. 性能问题

**问题**: API响应慢或超时

**解决方案**:
- 启用Redis缓存
- 优化数据库查询
- 增加工作进程数
- 使用CDN加速静态文件

### 日志分析

```bash
# 查看应用日志
docker-compose logs -f email-api

# 查看错误日志
grep "ERROR" logs/app.log

# 查看SMTP相关日志
grep "SMTP" logs/app.log

# 实时监控日志
tail -f logs/app.log | grep -E "(ERROR|WARNING)"
```

### 监控和告警

```bash
# 检查系统状态
curl http://localhost:8000/health

# 检查邮件队列状态
curl http://localhost:8000/api/v1/email/queue/{tenant_id}

# 检查统计信息
curl http://localhost:8000/api/v1/email/statistics/{tenant_id}
```

## 🤝 贡献指南

1. Fork 本项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启Pull Request

### 代码规范

- 使用Black进行代码格式化
- 遵循PEP 8规范
- 添加类型注解
- 编写单元测试
- 更新文档

## 📄 许可证

本项目基于 MIT 许可证开源。详见 [LICENSE](LICENSE) 文件。

## 📞 支持与联系

- 📧 邮箱: support@email-api.com
- 📖 文档: https://docs.email-api.com
- 🐛 问题报告: https://github.com/yourusername/email-api/issues
- 💬 讨论: https://github.com/yourusername/email-api/discussions

## 🙏 致谢

感谢以下开源项目：

- [FastAPI](https://fastapi.tiangolo.com/) - 现代高性能Web框架
- [SQLAlchemy](https://www.sqlalchemy.org/) - Python SQL工具包
- [Pydantic](https://pydantic-docs.helpmanual.io/) - 数据验证库
- [aiosmtplib](https://aiosmtplib.readthedocs.io/) - 异步SMTP客户端
- [Cryptography](https://cryptography.io/) - 加密库

---

**如果这个项目对您有帮助，请给我们一个 ⭐️ Star！**