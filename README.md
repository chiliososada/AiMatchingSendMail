# 🚀 AI智能邮件匹配发送系统 (AiMatchingSendMail)

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://postgresql.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com)

一个集成AI智能匹配功能的企业级多租户邮件发送API系统，专为招聘场景设计。基于FastAPI构建，不仅支持传统的邮件发送功能，还提供AI驱动的项目与工程师/简历智能匹配功能，大幅提升招聘效率。

## ✨ 核心特性

### 🤖 AI智能匹配
- **项目-工程师匹配**：基于sentence-transformers的语义匹配算法
- **批量匹配**：支持大规模项目与工程师的批量匹配
- **相似度计算**：使用pgvector进行高效的向量相似度搜索
- **简历解析**：智能提取简历关键信息（技能、经验、日语等级等）
- **匹配调试**：提供详细的匹配过程分析和调试工具

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

### 📄 简历处理
- **多格式支持**：支持PDF、DOCX、TXT等格式简历
- **智能提取器**：专业的信息提取器（姓名、技能、经验、国籍等）
- **批量处理**：支持批量简历解析和信息提取
- **数据标准化**：自动标准化提取的数据格式
- **调试工具**：提供提取器调试和测试工具

### 📊 统计分析
- **匹配分析**：AI匹配结果统计和分析
- **邮件监控**：发送成功率、失败率实时统计
- **性能分析**：发送耗时、队列状态分析
- **数据可视化**：支持图表展示和数据导出
- **历史追踪**：完整的操作历史记录

## 🏗️ 技术架构

```mermaid
graph TB
    A[客户端应用] --> B[负载均衡器]
    B --> C[FastAPI服务集群]
    C --> D[asyncpg连接池]
    D --> E[PostgreSQL + pgvector]
    C --> F[Supabase存储]
    C --> G[文件存储]
    C --> H[SMTP服务商]
    C --> I[AI匹配引擎]
    
    subgraph "核心服务"
        C1[AI匹配服务]
        C2[简历解析服务]
        C3[邮件发送服务]
        C4[SMTP管理服务]
        C5[队列管理服务]
        C6[统计分析服务]
    end
```

### 核心技术栈
- **后端框架**：FastAPI 0.104+ (异步高性能)
- **数据库**：PostgreSQL 15+ + pgvector (AI向量存储)
- **AI/ML**：sentence-transformers, torch, numpy
- **存储**：Supabase (云存储和数据库)
- **邮件发送**：aiosmtplib (异步SMTP)
- **加密算法**：Fernet (AES 128位加密)
- **文件处理**：pandas, openpyxl (数据处理)
- **容器化**：Docker + Docker Compose

## 🚀 快速开始

### 环境要求
- Python 3.11+
- PostgreSQL 15+ (需要pgvector扩展)
- Supabase账号 (数据库和存储)
- Docker & Docker Compose (推荐)

### 1. Docker快速部署（推荐）

```bash
# 克隆项目
git clone https://github.com/yourusername/AiMatchingSendMail.git
cd AiMatchingSendMail

# 生成配置文件
python generate_keys.py

# 启动服务
docker-compose up -d

# 启动带管理工具的服务
docker-compose --profile admin up -d

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

# 生成加密密钥
python generate_keys.py

# 初始化AI匹配数据库
python init_ai_matching_db.py

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

# AI匹配服务测试
python test_ai_matching.py
```

## 📚 API文档

### 核心API端点

#### 🤖 AI匹配管理
```http
# 单个项目匹配
POST /api/v1/ai-matching/match-single
{
    "project_description": "项目描述",
    "limit": 10
}

# 批量项目匹配
POST /api/v1/ai-matching/match-batch
{
    "projects": [
        {"id": "1", "description": "项目1描述"},
        {"id": "2", "description": "项目2描述"}
    ],
    "limit": 5
}

# 更新工程师嵌入
PUT /api/v1/ai-matching/engineer/{engineer_id}/embedding
{
    "description": "工程师技能描述"
}
```

#### 📄 简历解析
```http
# 解析简历
POST /api/v1/resume-parser/parse
Content-Type: multipart/form-data

# 批量解析简历
POST /api/v1/resume-parser/parse-batch
Content-Type: multipart/form-data

# 获取解析结果
GET /api/v1/resume-parser/result/{task_id}
```

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

# Supabase配置
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_ANON_KEY="your-supabase-anon-key"
SUPABASE_SERVICE_ROLE_KEY="your-supabase-service-role-key"

# 安全配置
SECRET_KEY="your-secret-key"
ENCRYPTION_KEY="your-fernet-key"  # 用于SMTP密码加密
API_KEY="your-api-key"
REQUIRE_API_KEY=true

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
- 文件大小和数量限制
- 安全文件名处理
- 简历文件自动清理

### 访问控制
- 基于租户的数据隔离
- API密钥认证 (X-API-Key)
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
AiMatchingSendMail/
├── app/
│   ├── main.py              # FastAPI应用入口
│   ├── config.py            # 配置管理
│   ├── database.py          # asyncpg数据库连接
│   ├── models/              # 数据模型
│   ├── schemas/             # 请求/响应模型
│   ├── services/            # 业务逻辑
│   │   └── extractors/      # 简历信息提取器
│   ├── api/                 # API路由
│   └── utils/               # 工具函数
├── tests/                   # 测试文件
├── examples/                # 集成示例
├── docker-compose.yml       # Docker编排
├── init_ai_matching_db.py   # AI数据库初始化
├── generate_embeddings.py   # 生成AI嵌入向量
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

1. **数据模型**：在 `models/` 中定义数据库模型
2. **请求模型**：在 `schemas/` 中定义Pydantic模型
3. **业务逻辑**：在 `services/` 中实现业务逻辑
4. **API路由**：在 `api/` 中添加FastAPI路由
5. **测试用例**：在 `tests/` 中添加测试用例

### 添加简历提取器

1. 创建新的提取器类继承 `base_extractor.py`
2. 实现提取逻辑（正则/ML模式）
3. 在 `resume_parser_service.py` 中添加到提取管道
4. 使用 `debug_extractors.py` 进行测试

## 🔗 集成指南

### 与aimachingmail项目集成

本系统完全兼容aimachingmail项目，可作为SMTP配置和密码解密服务使用：

```python
# 从aimachingmail调用SMTP配置
import requests

# 获取默认SMTP配置（含解密密码）
response = requests.get(
    f"http://your-email-api:8000/api/v1/smtp/config/{tenant_id}/default",
    headers={"X-API-Key": "your-api-key"}
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

### AI匹配服务集成

```python
# 使用AI匹配服务
import requests

# 单个项目匹配
response = requests.post(
    "http://your-api:8000/api/v1/ai-matching/match-single",
    headers={"X-API-Key": "your-api-key"},
    json={
        "project_description": "React + Node.js全栈开发",
        "limit": 10
    }
)
matches = response.json()
```

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
- [ ] 更多语言简历支持
- [ ] AI匹配算法优化
- [ ] 邮件模板系统
- [ ] Webhook回调支持

### v2.2（计划中）
- [ ] 智能简历评分系统
- [ ] 自动化面试安排
- [ ] AI对话式简历筛选
- [ ] 多模态简历解析

### v3.0（远期规划）
- [ ] 大语言模型集成
- [ ] 智能招聘助手
- [ ] 全流程招聘自动化
- [ ] 企业级SSO集成

## 📄 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。

## 🙏 致谢

感谢以下开源项目的支持：

- [FastAPI](https://fastapi.tiangolo.com/) - 现代高性能Web框架
- [asyncpg](https://github.com/MagicStack/asyncpg) - 高性能PostgreSQL驱动
- [sentence-transformers](https://www.sbert.net/) - 文本嵌入生成
- [pgvector](https://github.com/pgvector/pgvector) - PostgreSQL向量扩展
- [Supabase](https://supabase.com/) - 开源Firebase替代方案
- [aiosmtplib](https://aiosmtplib.readthedocs.io/) - 异步SMTP客户端
- [Cryptography](https://cryptography.io/) - 现代加密库

## 📞 支持与联系

- 📧 邮箱：support@aimatchingsendmail.com
- 📖 文档：https://docs.aimatchingsendmail.com
- 🐛 问题报告：https://github.com/yourusername/AiMatchingSendMail/issues
- 💬 讨论区：https://github.com/yourusername/AiMatchingSendMail/discussions

---

**⭐ 如果这个项目对您有帮助，请给我们一个 Star！**

<div align="center">
  <img src="https://img.shields.io/github/stars/yourusername/AiMatchingSendMail?style=social" alt="GitHub stars">
  <img src="https://img.shields.io/github/forks/yourusername/AiMatchingSendMail?style=social" alt="GitHub forks">
  <img src="https://img.shields.io/github/watchers/yourusername/AiMatchingSendMail?style=social" alt="GitHub watchers">
</div>