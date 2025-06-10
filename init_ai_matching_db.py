#!/usr/bin/env python3
# scripts/init_ai_matching_db.py
"""
AI匹配数据库初始化脚本

确保：
1. pgvector扩展已启用
2. 必要的表结构存在
3. 索引已创建
4. 示例数据（可选）
"""

import asyncio
import asyncpg
import logging
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def init_database():
    """初始化AI匹配数据库"""
    try:
        # 连接数据库
        logger.info("连接数据库...")
        conn = await asyncpg.connect(settings.DATABASE_URL)

        try:
            # 1. 启用pgvector扩展
            logger.info("启用pgvector扩展...")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            logger.info("✅ pgvector扩展已启用")

            # 2. 创建或更新projects表的向量字段
            logger.info("检查projects表的向量字段...")

            # 检查ai_match_embedding列是否存在
            embedding_exists = await conn.fetchval(
                """
                SELECT COUNT(*) FROM information_schema.columns 
                WHERE table_name = 'projects' AND column_name = 'ai_match_embedding'
            """
            )

            if not embedding_exists:
                await conn.execute(
                    """
                    ALTER TABLE projects 
                    ADD COLUMN ai_match_paraphrase TEXT,
                    ADD COLUMN ai_match_embedding VECTOR(768);
                """
                )
                logger.info("✅ projects表添加向量字段")
            else:
                logger.info("✅ projects表向量字段已存在")

            # 3. 创建或更新engineers表的向量字段
            logger.info("检查engineers表的向量字段...")

            embedding_exists = await conn.fetchval(
                """
                SELECT COUNT(*) FROM information_schema.columns 
                WHERE table_name = 'engineers' AND column_name = 'ai_match_embedding'
            """
            )

            if not embedding_exists:
                await conn.execute(
                    """
                    ALTER TABLE engineers 
                    ADD COLUMN ai_match_paraphrase TEXT,
                    ADD COLUMN ai_match_embedding VECTOR(768);
                """
                )
                logger.info("✅ engineers表添加向量字段")
            else:
                logger.info("✅ engineers表向量字段已存在")

            # 4. 创建ai_matching_history表
            logger.info("创建ai_matching_history表...")
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_matching_history (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL,
                    executed_by UUID,
                    matching_type TEXT DEFAULT 'auto',
                    trigger_type TEXT,
                    execution_status TEXT DEFAULT 'pending',
                    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    completed_at TIMESTAMP WITH TIME ZONE,
                    total_projects_input INTEGER DEFAULT 0,
                    total_engineers_input INTEGER DEFAULT 0,
                    project_ids UUID[] DEFAULT '{}',
                    engineer_ids UUID[] DEFAULT '{}',
                    total_matches_generated INTEGER DEFAULT 0,
                    high_quality_matches INTEGER DEFAULT 0,
                    processing_time_seconds INTEGER,
                    error_message TEXT,
                    ai_config JSONB DEFAULT '{}',
                    ai_model_version TEXT,
                    statistics JSONB DEFAULT '{}',
                    filters JSONB DEFAULT '{}'
                );
            """
            )
            logger.info("✅ ai_matching_history表创建完成")

            # 5. 创建project_engineer_matches表
            logger.info("创建project_engineer_matches表...")
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS project_engineer_matches (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL,
                    project_id UUID NOT NULL,
                    engineer_id UUID NOT NULL,
                    matching_history_id UUID,
                    status TEXT DEFAULT '未保存',
                    match_score NUMERIC,
                    confidence_score NUMERIC,
                    skill_match_score NUMERIC,
                    experience_match_score NUMERIC,
                    project_experience_match_score NUMERIC,
                    japanese_level_match_score NUMERIC,
                    budget_match_score NUMERIC,
                    location_match_score NUMERIC,
                    matched_skills TEXT[] DEFAULT '{}',
                    missing_skills TEXT[] DEFAULT '{}',
                    matched_experiences TEXT[] DEFAULT '{}',
                    missing_experiences TEXT[] DEFAULT '{}',
                    project_experience_match TEXT[] DEFAULT '{}',
                    missing_project_experience TEXT[] DEFAULT '{}',
                    match_reasons TEXT[] DEFAULT '{}',
                    concerns TEXT[] DEFAULT '{}',
                    comment TEXT,
                    ai_match_data JSONB DEFAULT '{}',
                    reviewed_by UUID,
                    reviewed_at TIMESTAMP WITH TIME ZONE,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    deleted_at TIMESTAMP WITH TIME ZONE,
                    
                    -- 外键约束
                    FOREIGN KEY (project_id) REFERENCES projects(id),
                    FOREIGN KEY (engineer_id) REFERENCES engineers(id),
                    FOREIGN KEY (matching_history_id) REFERENCES ai_matching_history(id)
                );
            """
            )
            logger.info("✅ project_engineer_matches表创建完成")

            # 6. 创建向量索引
            logger.info("创建向量索引...")

            # projects表向量索引
            try:
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS projects_embedding_cosine_idx 
                    ON projects USING ivfflat (ai_match_embedding vector_cosine_ops)
                    WITH (lists = 100);
                """
                )
                logger.info("✅ projects向量索引创建完成")
            except Exception as e:
                # 如果数据不足，创建简单索引
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS projects_embedding_idx 
                    ON projects (ai_match_embedding);
                """
                )
                logger.info("✅ projects简单向量索引创建完成")

            # engineers表向量索引
            try:
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS engineers_embedding_cosine_idx 
                    ON engineers USING ivfflat (ai_match_embedding vector_cosine_ops)
                    WITH (lists = 100);
                """
                )
                logger.info("✅ engineers向量索引创建完成")
            except Exception as e:
                # 如果数据不足，创建简单索引
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS engineers_embedding_idx 
                    ON engineers (ai_match_embedding);
                """
                )
                logger.info("✅ engineers简单向量索引创建完成")

            # 7. 创建业务索引
            logger.info("创建业务索引...")

            # ai_matching_history索引
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ai_matching_history_tenant_id 
                ON ai_matching_history(tenant_id);
                
                CREATE INDEX IF NOT EXISTS idx_ai_matching_history_started_at 
                ON ai_matching_history(started_at);
                
                CREATE INDEX IF NOT EXISTS idx_ai_matching_history_status 
                ON ai_matching_history(execution_status);
            """
            )

            # project_engineer_matches索引
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_project_engineer_matches_tenant_id 
                ON project_engineer_matches(tenant_id);
                
                CREATE INDEX IF NOT EXISTS idx_project_engineer_matches_project_id 
                ON project_engineer_matches(project_id);
                
                CREATE INDEX IF NOT EXISTS idx_project_engineer_matches_engineer_id 
                ON project_engineer_matches(engineer_id);
                
                CREATE INDEX IF NOT EXISTS idx_project_engineer_matches_history_id 
                ON project_engineer_matches(matching_history_id);
                
                CREATE INDEX IF NOT EXISTS idx_project_engineer_matches_score 
                ON project_engineer_matches(match_score DESC);
                
                CREATE INDEX IF NOT EXISTS idx_project_engineer_matches_status 
                ON project_engineer_matches(status);
                
                CREATE INDEX IF NOT EXISTS idx_project_engineer_matches_created_at 
                ON project_engineer_matches(created_at);
            """
            )

            logger.info("✅ 所有业务索引创建完成")

            # 8. 验证表结构
            logger.info("验证表结构...")

            # 检查表是否存在
            tables_to_check = [
                "projects",
                "engineers",
                "ai_matching_history",
                "project_engineer_matches",
            ]

            for table in tables_to_check:
                exists = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = $1
                    );
                """,
                    table,
                )

                if exists:
                    logger.info(f"✅ 表 {table} 存在")
                else:
                    logger.error(f"❌ 表 {table} 不存在")

            # 检查向量字段
            for table in ["projects", "engineers"]:
                embedding_col = await conn.fetchval(
                    """
                    SELECT data_type FROM information_schema.columns 
                    WHERE table_name = $1 AND column_name = 'ai_match_embedding'
                """,
                    table,
                )

                if embedding_col:
                    logger.info(f"✅ 表 {table} 的向量字段类型: {embedding_col}")
                else:
                    logger.error(f"❌ 表 {table} 缺少向量字段")

            logger.info("🎉 AI匹配数据库初始化完成！")

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"❌ 数据库初始化失败: {str(e)}")
        raise


async def create_sample_data():
    """创建示例数据（可选）"""
    try:
        logger.info("创建示例数据...")
        conn = await asyncpg.connect(settings.DATABASE_URL)

        try:
            # 检查是否已有数据
            project_count = await conn.fetchval("SELECT COUNT(*) FROM projects")
            engineer_count = await conn.fetchval("SELECT COUNT(*) FROM engineers")

            if project_count == 0 or engineer_count == 0:
                logger.info("数据库为空，建议手动添加一些项目和简历数据以测试匹配功能")
            else:
                logger.info(
                    f"数据库已有 {project_count} 个项目和 {engineer_count} 个简历"
                )

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"检查示例数据失败: {str(e)}")


async def test_vector_operations():
    """测试向量操作"""
    try:
        logger.info("测试向量操作...")
        conn = await asyncpg.connect(settings.DATABASE_URL)

        try:
            # 测试向量距离计算
            test_vector = [0.1] * 768  # 创建一个测试向量

            # 测试cosine距离
            result = await conn.fetchval(
                """
                SELECT $1::vector <#> $2::vector as cosine_distance
            """,
                test_vector,
                test_vector,
            )

            logger.info(f"向量cosine距离测试结果: {result} (应该接近0)")

            if abs(result) < 0.001:
                logger.info("✅ 向量操作测试通过")
            else:
                logger.warning("⚠️ 向量操作结果异常")

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"向量操作测试失败: {str(e)}")


def main():
    """主函数"""
    print("🚀 AI匹配数据库初始化工具")
    print("=" * 50)

    try:
        # 运行初始化
        asyncio.run(init_database())

        # 创建示例数据
        asyncio.run(create_sample_data())

        # 测试向量操作
        asyncio.run(test_vector_operations())

        print("\n" + "=" * 50)
        print("🎉 初始化完成！")
        print("\n📝 下一步：")
        print("1. 为项目和简历生成embedding数据")
        print("2. 运行AI匹配API测试")
        print("3. 检查匹配结果")
        print("\n💡 提示：")
        print("- 确保有足够的项目和简历数据用于测试")
        print("- 向量索引在数据量大时效果更好")
        print("- 定期更新embedding以保持匹配准确性")

    except Exception as e:
        print(f"\n❌ 初始化失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
