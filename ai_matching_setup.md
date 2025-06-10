# AI智能匹配功能部署说明

## 📋 功能概述

为aimachingsengmail项目新增三个核心AI匹配API：

1. **案件匹配简历** - 为特定案件找到最合适的简历候选人
2. **简历匹配案件** - 为特定简历推荐最合适的案件机会  
3. **批量智能匹配** - 大规模自动化匹配案件和简历

## 🏗️ 技术架构

- **AI模型**: paraphrase-multilingual-mpnet-base-v2 (768维向量)
- **向量数据库**: PostgreSQL + pgvector扩展
- **相似度算法**: Cosine Similarity (`<#>` 操作符)
- **匹配算法**: 多维度加权评分 + 语义相似度
- **数据库**: asyncpg连接池，高性能异步访问

## 📁 新增文件结构

```
aimachingsengmail/
├── app/
│   ├── schemas/
│   │   └── ai_matching_schemas.py          # ✨ 新增：AI匹配数据模型
│   ├── services/
│   │   └── ai_matching_service.py          # ✨ 新增：AI匹配核心服务
│   ├── api/
│   │   └── ai_matching_routes.py           # ✨ 新增：AI匹配API路由
│   └── main.py                             # 🔄 修改：添加路由注册
├── scripts/
│   ├── init_ai_matching_db.py              # ✨ 新增：数据库初始化脚本
│   └── generate_embeddings.py              # ✨ 新增：向量生成脚本
├── examples/
│   └── ai_matching_examples.py             # ✨ 新增：API使用示例
├── docs/
│   └── ai_matching_setup.md                # ✨ 新增：本文档
└── requirements.txt                        # 🔄 修改：添加AI相关依赖
```

## 🚀 部署步骤

### 1. 安装依赖

```bash
# 更新Python依赖
pip install -r requirements.txt

# 主要新增依赖：
# - sentence-transformers==2.2.2
# - torch==2.1.1  
# - transformers==4.36.2
# - numpy==1.24.4
# - pgvector==0.2.4
```

### 2. 数据库准备

```bash
# 确保PostgreSQL已安装pgvector扩展
# 在数据库中执行：CREATE EXTENSION IF NOT EXISTS vector;

# 运行数据库初始化脚本
cd aimachingsengmail
python scripts/init_ai_matching_db.py
```

**数据库变更说明：**
- 为`projects`表添加：`ai_match_paraphrase TEXT`, `ai_match_embedding VECTOR(768)`
- 为`engineers`表添加：`ai_match_paraphrase TEXT`, `ai_match_embedding VECTOR(768)`
- 新增表：`ai_matching_history` (匹配历史)
- 新增表：`project_engineer_matches` (匹配结果)
- 创建向量索引和业务索引

### 3. 生成Embedding数据

```bash
# 为现有数据生成embedding向量
python scripts/generate_embeddings.py --type both

# 只更新项目
python scripts/generate_embeddings.py --type projects

# 只更新简历  
python scripts/generate_embeddings.py --type engineers

# 强制更新所有记录
python scripts/generate_embeddings.py --force

# 查看统计信息
python scripts/generate_embeddings.py --stats-only
```

### 4. 启动服务

```bash
# 启动应用（包含新的AI匹配路由）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 验证部署

```bash
# 运行API示例测试
python examples/ai_matching_examples.py

# 访问API文档
# http://localhost:8000/docs
# 查看 "AI智能匹配" 标签下的API
```

## 📚 API接口说明

### 核心匹配API

#### 1. 案件匹配简历
```http
POST /api/v1/ai-matching/project-to-engineers
Content-Type: application/json

{
    "tenant_id": "uuid",
    "project_id": "uuid", 
    "max_matches": 10,
    "min_score": 0.7,
    "weights": {
        "skill_match": 0.3,
        "experience_match": 0.25,
        "japanese_level_match": 0.15,
        "location_match": 0.1
    },
    "filters": {
        "japanese_level": ["N1", "N2"],
        "current_status": ["available"]
    }
}
```

#### 2. 简历匹配案件
```http
POST /api/v1/ai-matching/engineer-to-projects  
Content-Type: application/json

{
    "tenant_id": "uuid",
    "engineer_id": "uuid",
    "max_matches": 10, 
    "min_score": 0.7,
    "filters": {
        "status": ["募集中"],
        "company_type": ["自社"]
    }
}
```

#### 3. 批量匹配
```http
POST /api/v1/ai-matching/bulk-matching
Content-Type: application/json

{
    "tenant_id": "uuid",
    "project_ids": ["uuid1", "uuid2"],  // 可选
    "engineer_ids": ["uuid3", "uuid4"], // 可选
    "max_matches": 5,
    "min_score": 0.7,
    "batch_size": 50,
    "generate_top_matches_only": true
}
```

### 管理API

```http
# 获取匹配历史
GET /api/v1/ai-matching/history/{tenant_id}?limit=20

# 获取匹配结果
GET /api/v1/ai-matching/matches/{tenant_id}/{history_id}

# 更新匹配状态
PUT /api/v1/ai-matching/matches/{tenant_id}/{match_id}/status?status=已保存

# 获取统计信息
GET /api/v1/ai-matching/statistics/{tenant_id}?days=30

# 系统健康检查
GET /api/v1/ai-matching/system/health
```

## 🎯 匹配算法说明

### 多维度评分

1. **技能匹配度** (30%) - 必需技能与候选人技能的重合度
2. **经验匹配度** (25%) - 相关工作经验的匹配程度  
3. **项目经验匹配度** (20%) - 类似项目经验的匹配度
4. **日语水平匹配度** (15%) - 日语能力与要求的匹配
5. **地点匹配度** (10%) - 工作地点的匹配程度
6. **语义相似度** (30%) - 基于AI模型的文本语义相似度

### 综合评分公式

```
最终分数 = (结构化匹配分数 × 0.7) + (语义相似度分数 × 0.3)
```

### 质量等级

- **高质量匹配**: 分数 ≥ 0.8
- **中等匹配**: 分数 0.6 - 0.8
- **低质量匹配**: 分数 < 0.6

## 🔧 配置和优化

### 环境变量

```bash
# 无需额外环境变量，使用现有数据库配置即可
DATABASE_URL="postgresql://user:pass@host:port/db"
```

### 性能优化

1. **向量索引优化**
   ```sql
   -- 数据量大时使用IVFFlat索引
   CREATE INDEX projects_embedding_cosine_idx 
   ON projects USING ivfflat (ai_match_embedding vector_cosine_ops)
   WITH (lists = 100);
   ```

2. **批处理优化**
   - 默认批处理大小：32（embedding生成）
   - 默认批处理大小：50（批量匹配）
   - 可根据服务器性能调整

3. **内存管理**
   - AI模型加载后常驻内存
   - 推荐至少4GB内存用于模型

### 定期维护

```bash
# 每日新数据生成embedding
python scripts/generate_embeddings.py

# 每周重新生成所有embedding（可选）
python scripts/generate_embeddings.py --force

# 清理过期匹配记录（可选）
# 在数据库中执行定期清理任务
```

## 📊 监控和日志

### 关键指标

- 匹配成功率
- 平均匹配分数  
- 高质量匹配率
- API响应时间
- Embedding生成速度

### 日志级别

```python
# 在app/main.py中配置日志
logging.getLogger("app.services.ai_matching_service").setLevel(logging.INFO)
```

### 健康检查

```bash
# 系统健康检查
curl http://localhost:8000/api/v1/ai-matching/system/health

# 模型状态检查
curl http://localhost:8000/api/v1/ai-matching/system/info
```

## 🚨 故障排除

### 常见问题

1. **模型加载失败**
   ```bash
   # 检查依赖安装
   pip install sentence-transformers torch
   
   # 检查网络连接（首次下载模型需要）
   # 或手动下载模型到本地
   ```

2. **向量索引错误**
   ```sql
   -- 确保pgvector扩展已安装
   CREATE EXTENSION IF NOT EXISTS vector;
   
   -- 检查向量字段类型
   SELECT column_name, data_type 
   FROM information_schema.columns 
   WHERE table_name = 'projects' AND column_name = 'ai_match_embedding';
   ```

3. **匹配结果为空**
   ```bash
   # 检查embedding数据
   python scripts/generate_embeddings.py --stats-only
   
   # 降低min_score阈值
   # 检查筛选条件是否过于严格
   ```

4. **性能问题**
   ```bash
   # 检查数据库连接池配置
   # 调整batch_size参数
   # 监控CPU和内存使用
   ```

### 日志分析

```bash
# 查看AI匹配相关日志
grep "ai_matching" app.log

# 查看错误日志  
grep "ERROR" app.log | grep -i "matching"
```

## 📈 扩展建议

### 未来优化

1. **模型升级**
   - 支持更大维度的向量模型
   - 领域特定的fine-tuned模型

2. **算法改进**
   - 机器学习优化权重
   - 用户反馈学习

3. **性能提升**
   - Redis缓存热门匹配
   - 预计算常用匹配组合

4. **功能扩展**
   - 匹配解释性AI
   - 个性化推荐算法
   - 实时匹配更新

### 集成建议

1. **前端集成**
   - 匹配结果可视化
   - 交互式筛选器
   - 批量操作界面

2. **通知系统**
   - 新匹配邮件通知
   - 匹配状态变更提醒

3. **分析报表**
   - 匹配效果分析
   - 用户行为统计
   - ROI分析报告

## 🎉 部署完成

完成以上步骤后，您的aimachingsengmail项目将具备强大的AI智能匹配功能！

- ✅ 支持三种核心匹配模式
- ✅ 高性能向量相似度计算  
- ✅ 多维度智能评分算法
- ✅ 完整的历史追踪和管理
- ✅ 丰富的统计分析功能
- ✅ RESTful API设计
- ✅ 详细的使用文档和示例

如有问题，请参考故障排除章节或查看详细日志。