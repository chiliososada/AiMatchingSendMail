# 🚀 多租户邮件发送API系统

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://postgresql.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com)

一个功能强大的企业级多租户邮件发送API系统，基于FastAPI构建，支持高并发邮件发送、SMTP配置管理、附件处理、队列管理和实时统计分析。

## ✨ 核心特性

### 🎯 邮件发送服务
- **高性能发送**：基于asyncpg连接池的异步邮件发送
- **多租户支持**：完整的租户隔离和数据安全保障
- **智能队列**：支持优先级、重试机制和调度发送
- **批量发送**：支持个性化内容的大批量邮件发送
- **实时跟踪**：完整的发送状态跟踪和日志记录

### 🔧 SMTP管理
- **多账户管理**：支持多个SMTP服务商配置
- **密码安全**：使用Fernet加密算法保护SMTP密码
- **兼容性强**：与aimachingmail项目完全兼容
- **连接测试**：一键测试SMTP连接状态
- **负载均衡**：智能选择最优SMTP服务器

### 📎 附件处理
- **多格式支持**：支持25+种文件格式
- **安全验证**：多层文件安全检查和病毒扫描
- **批量上传**：支持一次性上传多个附件
- **存储管理**：自动清理过期文件和存储优化
- **CDN加速**：支持附件CDN分发（可选）

### 📊 统计分析
- **实时监控**：邮件发送成功率、失败率实时统计
- **性能分析**：发送耗时、队列状态分析
- **数据可视化**：支持图表展示和数据导出
- **告警通知**：异常情况自动告警
- **历史追踪**：完整的邮件发送历史记录

## 🏗️ 技术架构

```mermaid
graph TB
    A[客户端应用] --> B[负载均衡器]
    B --> C[FastAPI服务集群]
    C --> D[asyncpg连接池]
    D --> E[PostgreSQL数据库]
    C --> F[Redis缓存]
    C --> G[文件存储]
    C --> H[SMTP服务商]
    
    subgraph "核心服务"
        C1[邮件发送服务]
        C2[SMTP管理服务]
        C3[附件管理服务]
        C4[队列管理服务]
        C5[统计分析服务]
    end
```

### 核心技术栈
- **后端框架**：FastAPI 0.104+ (异步高性能)
- **数据库**：PostgreSQL 15+ (asyncpg连接池)
- **缓存**：Redis 6+ (可选)
- **邮件发送**：aiosmtplib (异步SMTP)
- **加密算法**：Fernet (AES 128位加密)
- **文件处理**：多格式支持和安全验证
- **容器化**：Docker + Docker Compose

## 🚀 快速开始

### 环境要求
- Python 3.11+
- PostgreSQL 15+
- Redis 6+ (可选)
- Docker & Docker Compose (推荐)

### 1. Docker快速部署（推荐）

```bash
# 克隆项目
git clone https://github.com/yourusername/email-api-system.git
cd email-api-system

# 生成配置文件
python generate_keys.py

# 启动服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f email-api
```

### 2. 本地开发环境

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，设置数据库连接等配置

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

### 3. 验证安装

访问以下URL验证系统运行状态：

```bash
# API文档
curl http://localhost:8000/docs

# 健康检查
curl http://localhost:8000/health

# 快速功能测试
curl http://localhost:8000/quick-test

# SMTP解密服务测试
curl http://localhost:8000/api/v1/smtp/health
```

## 📚 API文档

### 核心API端点

#### 🔧 SMTP配置管理
```http
# 创建SMTP配置
POST /api/v1/email/smtp-settings
{
    "tenant_id": "uuid",
    "setting_name": "Gmail SMTP",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_username": "your-email@gmail.com",
    "smtp_password": "your-app-password",
    "security_protocol": "TLS",
    "from_email": "your-email@gmail.com",
    "from_name": "发送者名称"
}

# 获取SMTP配置（含解密密码）
GET /api/v1/smtp/config/{tenant_id}/default

# 测试SMTP连接
POST /api/v1/smtp/test
{
    "tenant_id": "uuid",
    "setting_id": "uuid"
}
```

#### 📎 附件管理
```http
# 上传附件
POST /api/v1/email/attachments/upload
Content-Type: multipart/form-data

# 批量上传附件
POST /api/v1/email/attachments/upload-multiple

# 获取附件列表
GET /api/v1/email/attachments/{tenant_id}
```

#### 📧 邮件发送
```http
# 发送普通邮件
POST /api/v1/email/send
{
    "tenant_id": "uuid",
    "to_emails": ["recipient@example.com"],
    "subject": "邮件主题",
    "body_text": "纯文本内容",
    "body_html": "<p>HTML内容</p>",
    "priority": 5
}

# 发送带附件邮件
POST /api/v1/email/send-with-attachments
{
    "tenant_id": "uuid",
    "to_emails": ["recipient@example.com"],
    "subject": "带附件的邮件",
    "body_text": "邮件内容",
    "attachment_ids": ["attachment-uuid-1", "attachment-uuid-2"]
}
```

#### 📊 队列和统计
```http
# 查询邮件状态
GET /api/v1/email/queue/{tenant_id}/{queue_id}

# 获取发送统计
GET /api/v1/email/statistics/{tenant_id}?days=30
```

### 完整API文档
启动服务后访问 `http://localhost:8000/docs` 查看完整的交互式API文档。

## ⚙️ 配置说明

### 环境变量配置

```bash
# 数据库配置
DATABASE_URL="postgresql://user:pass@host:5432/dbname"

# 安全配置
SECRET_KEY="your-secret-key"
ENCRYPTION_KEY="your-fernet-key"  # 用于SMTP密码加密

# 文件上传限制
MAX_FILE_SIZE=26214400  # 25MB
MAX_FILES_PER_REQUEST=10

# 邮件发送限制
MAX_RECIPIENTS_PER_EMAIL=100
MAX_BULK_EMAILS=1000

# CORS配置
BACKEND_CORS_ORIGINS='["http://localhost:3000","https://yourdomain.com"]'
```

### SMTP服务商配置示例

<details>
<summary>📧 Gmail配置</summary>

```json
{
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_username": "your-email@gmail.com",
    "smtp_password": "your-app-password",
    "security_protocol": "TLS"
}
```
> 注意：Gmail需要开启2FA并生成应用专用密码
</details>

<details>
<summary>📧 Outlook配置</summary>

```json
{
    "smtp_host": "smtp-mail.outlook.com",
    "smtp_port": 587,
    "smtp_username": "your-email@outlook.com",
    "smtp_password": "your-password",
    "security_protocol": "TLS"
}
```
</details>

<details>
<summary>📧 企业邮箱配置</summary>

```json
{
    "smtp_host": "smtp.exmail.qq.com",
    "smtp_port": 587,
    "smtp_username": "your-email@yourdomain.com",
    "smtp_password": "your-password",
    "security_protocol": "TLS"
}
```
</details>

## 🚀 部署指南

### Docker部署（生产环境）

```bash
# 使用生产配置
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 扩容部署
docker-compose up -d --scale email-api=3

# 使用负载均衡
docker-compose --profile production up -d
```

### Kubernetes部署

```bash
# 应用Kubernetes配置
kubectl apply -f deployment/k8s/

# 检查部署状态
kubectl get pods -l app=email-api
kubectl get services
```

### 云平台部署

<details>
<summary>☁️ AWS ECS部署</summary>

```bash
# 构建并推送镜像到ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com
docker build -t email-api .
docker tag email-api:latest 123456789.dkr.ecr.us-east-1.amazonaws.com/email-api:latest
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/email-api:latest
```
</details>

## 🔒 安全特性

### 密码加密
- 使用Fernet对称加密算法
- 与aimachingmail项目完全兼容
- 支持密钥轮换和升级

### 文件安全
- 多层文件类型验证
- 病毒扫描集成
- 文件大小和数量限制
- 安全文件名处理

### 访问控制
- 基于租户的数据隔离
- API密钥认证
- 速率限制保护
- SQL注入防护

## 📊 性能特性

### 高并发支持
- asyncpg连接池：支持1000+并发连接
- 异步邮件发送：支持每秒1000+邮件发送
- 智能队列：支持百万级邮件队列

### 性能优化
- 数据库连接池优化
- Redis缓存加速
- CDN文件分发
- 压缩和缓存策略

## 🔧 故障排除

### 常见问题

<details>
<summary>🚨 SMTP连接失败</summary>

**问题**：SMTP连接测试失败

**解决方案**：
```bash
# 检查SMTP配置
curl -X POST "http://localhost:8000/api/v1/smtp/test" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "your-tenant-id", "setting_id": "your-setting-id"}'

# 验证网络连接
telnet smtp.gmail.com 587

# 检查防火墙设置
sudo ufw status
```
</details>

<details>
<summary>🚨 文件上传失败</summary>

**问题**：附件上传失败或文件过大

**解决方案**：
```bash
# 检查文件大小限制
echo "当前限制: 25MB"

# 检查磁盘空间
df -h

# 检查上传目录权限
ls -la uploads/attachments/
```
</details>

<details>
<summary>🚨 数据库连接问题</summary>

**问题**：无法连接到数据库

**解决方案**：
```bash
# 测试数据库连接
psql "postgresql://user:pass@host:5432/dbname"

# 检查数据库服务状态
sudo systemctl status postgresql

# 查看连接池状态
curl http://localhost:8000/health
```
</details>

### 日志分析

```bash
# 查看应用日志
docker-compose logs -f email-api

# 查看错误日志
grep "ERROR" logs/app.log

# 实时监控
tail -f logs/app.log | grep -E "(ERROR|WARNING)"
```

## 🤝 开发指南

### 项目结构
```
email_api/
├── app/
│   ├── main.py              # FastAPI应用入口
│   ├── config.py            # 配置管理
│   ├── database.py          # asyncpg数据库连接
│   ├── models/              # 数据模型
│   ├── schemas/             # 请求/响应模型
│   ├── services/            # 业务逻辑
│   ├── api/                 # API路由
│   └── utils/               # 工具函数
├── tests/                   # 测试文件
├── deployment/              # 部署配置
├── docker-compose.yml       # Docker编排
└── requirements.txt         # Python依赖
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
pytest --cov=app
```

### 添加新功能

1. **数据模型**：在 `models/` 中定义SQLAlchemy模型
2. **请求模型**：在 `schemas/` 中定义Pydantic模型
3. **业务逻辑**：在 `services/` 中实现业务逻辑
4. **API路由**：在 `api/` 中添加FastAPI路由
5. **测试用例**：在 `tests/` 中添加测试用例

## 🔗 集成指南

### 与aimachingmail项目集成

本系统完全兼容aimachingmail项目，可作为SMTP配置和密码解密服务使用：

```python
# 从aimachingmail调用SMTP配置
import requests

# 获取默认SMTP配置（含解密密码）
response = requests.get(
    f"http://your-email-api:8000/api/v1/smtp/config/{tenant_id}/default"
)
smtp_config = response.json()

# 直接用于SMTP连接
smtp = aiosmtplib.SMTP(
    hostname=smtp_config['smtp_host'],
    port=smtp_config['smtp_port'],
    use_tls=smtp_config['security_protocol'] == 'TLS'
)
```

### React Native集成示例

详见 `examples/react-native-example.js` 文件，包含完整的移动端集成示例。

## 📈 监控和告警

### 性能监控
- 邮件发送成功率监控
- API响应时间监控
- 数据库连接池状态监控
- 文件存储使用情况监控

### 告警配置
- SMTP连接失败告警
- 邮件发送失败率告警
- 系统资源使用告警
- 安全异常行为告警

## 🛣️ 发展路线图

### v2.1（计划中）
- [ ] 邮件模板系统
- [ ] Webhook回调支持
- [ ] 多语言邮件支持
- [ ] 高级统计报表

### v2.2（计划中）
- [ ] 人工智能反垃圾邮件
- [ ] 邮件个性化推荐
- [ ] 区块链邮件验证
- [ ] 边缘节点部署

### v3.0（远期规划）
- [ ] 微服务架构重构
- [ ] GraphQL API支持
- [ ] 实时邮件协作
- [ ] 企业级SSO集成

## 📄 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。

## 🙏 致谢

感谢以下开源项目的支持：

- [FastAPI](https://fastapi.tiangolo.com/) - 现代高性能Web框架
- [asyncpg](https://github.com/MagicStack/asyncpg) - 高性能PostgreSQL驱动
- [aiosmtplib](https://aiosmtplib.readthedocs.io/) - 异步SMTP客户端
- [Cryptography](https://cryptography.io/) - 现代加密库

## 📞 支持与联系

- 📧 邮箱：support@email-api.com
- 📖 文档：https://docs.email-api.com
- 🐛 问题报告：https://github.com/yourusername/email-api-system/issues
- 💬 讨论区：https://github.com/yourusername/email-api-system/discussions

---

**⭐ 如果这个项目对您有帮助，请给我们一个 Star！**

<div align="center">
  <img src="https://img.shields.io/github/stars/yourusername/email-api-system?style=social" alt="GitHub stars">
  <img src="https://img.shields.io/github/forks/yourusername/email-api-system?style=social" alt="GitHub forks">
  <img src="https://img.shields.io/github/watchers/yourusername/email-api-system?style=social" alt="GitHub watchers">
</div>