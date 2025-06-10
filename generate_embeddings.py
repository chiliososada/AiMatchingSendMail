#!/usr/bin/env python3
# scripts/generate_embeddings.py
"""
Embedding生成和更新脚本

为projects和engineers表生成ai_match_embedding向量数据
支持增量更新和批量重新生成
"""

import asyncio
import asyncpg
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import json

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
except ImportError:
    print("❌ 缺少依赖库，请运行: pip install sentence-transformers torch numpy")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Embedding生成器"""

    def __init__(self):
        self.model_name = "paraphrase-multilingual-mpnet-base-v2"
        self.model = None
        self.batch_size = 32

    def load_model(self):
        """加载模型"""
        try:
            logger.info(f"加载模型: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info("✅ 模型加载成功")
        except Exception as e:
            logger.error(f"❌ 模型加载失败: {str(e)}")
            raise

    def create_project_paraphrase(self, project: Dict[str, Any]) -> str:
        """创建项目的paraphrase文本"""
        parts = []

        # 标题
        if project.get("title"):
            parts.append(f"项目: {project['title']}")

        # 描述
        if project.get("description"):
            parts.append(f"描述: {project['description']}")

        if project.get("detail_description"):
            parts.append(f"详细描述: {project['detail_description']}")

        # 技能要求
        if project.get("skills"):
            skills = project["skills"]
            if isinstance(skills, list):
                parts.append(f"技能要求: {', '.join(skills)}")

        # 关键技术
        if project.get("key_technologies"):
            parts.append(f"关键技术: {project['key_technologies']}")

        # 经验要求
        if project.get("experience"):
            parts.append(f"经验要求: {project['experience']}")

        # 工作地点
        if project.get("location"):
            parts.append(f"工作地点: {project['location']}")

        # 工作类型
        if project.get("work_type"):
            parts.append(f"工作类型: {project['work_type']}")

        # 日语水平
        if project.get("japanese_level"):
            parts.append(f"日语要求: {project['japanese_level']}")

        # 预算
        if project.get("budget"):
            parts.append(f"预算: {project['budget']}")

        # 公司类型
        if project.get("company_type"):
            parts.append(f"公司类型: {project['company_type']}")

        # 客户公司
        if project.get("client_company"):
            parts.append(f"客户: {project['client_company']}")

        return " | ".join(parts)

    def create_engineer_paraphrase(self, engineer: Dict[str, Any]) -> str:
        """创建简历的paraphrase文本"""
        parts = []

        # 基本信息
        if engineer.get("name"):
            parts.append(f"姓名: {engineer['name']}")

        # 技能
        if engineer.get("skills"):
            skills = engineer["skills"]
            if isinstance(skills, list):
                parts.append(f"技能: {', '.join(skills)}")

        # 经验
        if engineer.get("experience"):
            parts.append(f"经验: {engineer['experience']}")

        # 工作经验
        if engineer.get("work_experience"):
            parts.append(f"工作经验: {engineer['work_experience']}")

        # 工作范围
        if engineer.get("work_scope"):
            parts.append(f"工作范围: {engineer['work_scope']}")

        # 日语水平
        if engineer.get("japanese_level"):
            parts.append(f"日语水平: {engineer['japanese_level']}")

        # 英语水平
        if engineer.get("english_level"):
            parts.append(f"英语水平: {engineer['english_level']}")

        # 当前状态
        if engineer.get("current_status"):
            parts.append(f"状态: {engineer['current_status']}")

        # 公司类型
        if engineer.get("company_type"):
            parts.append(f"公司类型: {engineer['company_type']}")

        # 国籍
        if engineer.get("nationality"):
            parts.append(f"国籍: {engineer['nationality']}")

        # 学历
        if engineer.get("education"):
            parts.append(f"学历: {engineer['education']}")

        # 认证
        if engineer.get("certifications"):
            certs = engineer["certifications"]
            if isinstance(certs, list):
                parts.append(f"认证: {', '.join(certs)}")

        # 自我推荐
        if engineer.get("self_promotion"):
            parts.append(f"自我推荐: {engineer['self_promotion']}")

        # 技术关键词
        if engineer.get("technical_keywords"):
            keywords = engineer["technical_keywords"]
            if isinstance(keywords, list):
                parts.append(f"技术关键词: {', '.join(keywords)}")

        return " | ".join(parts)

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """生成embedding向量"""
        if not self.model:
            raise Exception("模型未加载")

        # 过滤空文本
        valid_texts = [text if text else "无内容" for text in texts]

        # 生成embeddings
        embeddings = self.model.encode(valid_texts, batch_size=self.batch_size)

        # 转换为列表格式
        return [emb.tolist() for emb in embeddings]


async def update_projects_embeddings(
    generator: EmbeddingGenerator,
    tenant_id: Optional[str] = None,
    force_update: bool = False,
    limit: Optional[int] = None,
):
    """更新项目embeddings"""
    try:
        logger.info("开始更新项目embeddings...")

        conn = await asyncpg.connect(settings.DATABASE_URL)

        try:
            # 构建查询条件
            where_conditions = ["is_active = true"]
            params = []

            if tenant_id:
                where_conditions.append(f"tenant_id = ${len(params) + 1}")
                params.append(tenant_id)

            if not force_update:
                where_conditions.append("ai_match_embedding IS NULL")

            # 构建查询
            query = f"""
            SELECT * FROM projects 
            WHERE {' AND '.join(where_conditions)}
            ORDER BY created_at DESC
            """

            if limit:
                query += f" LIMIT {limit}"

            # 获取需要更新的项目
            projects = await conn.fetch(query, *params)
            logger.info(f"找到 {len(projects)} 个需要更新的项目")

            if not projects:
                logger.info("没有需要更新的项目")
                return

            # 批量处理
            updated_count = 0

            for i in range(0, len(projects), generator.batch_size):
                batch = projects[i : i + generator.batch_size]

                # 生成paraphrase文本
                paraphrases = []
                project_ids = []

                for project in batch:
                    paraphrase = generator.create_project_paraphrase(dict(project))
                    paraphrases.append(paraphrase)
                    project_ids.append(project["id"])

                # 生成embeddings
                logger.info(f"生成第 {i//generator.batch_size + 1} 批embeddings...")
                embeddings = generator.generate_embeddings(paraphrases)

                # 更新数据库
                for j, (project_id, paraphrase, embedding) in enumerate(
                    zip(project_ids, paraphrases, embeddings)
                ):
                    try:
                        await conn.execute(
                            """
                            UPDATE projects 
                            SET ai_match_paraphrase = $1, ai_match_embedding = $2, updated_at = NOW()
                            WHERE id = $3
                        """,
                            paraphrase,
                            embedding,
                            project_id,
                        )
                        updated_count += 1
                    except Exception as e:
                        logger.error(f"更新项目 {project_id} 失败: {str(e)}")

                logger.info(
                    f"已处理 {min(i + generator.batch_size, len(projects))}/{len(projects)} 个项目"
                )

            logger.info(f"✅ 项目embeddings更新完成: {updated_count}/{len(projects)}")

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"❌ 更新项目embeddings失败: {str(e)}")
        raise


async def update_engineers_embeddings(
    generator: EmbeddingGenerator,
    tenant_id: Optional[str] = None,
    force_update: bool = False,
    limit: Optional[int] = None,
):
    """更新简历embeddings"""
    try:
        logger.info("开始更新简历embeddings...")

        conn = await asyncpg.connect(settings.DATABASE_URL)

        try:
            # 构建查询条件
            where_conditions = ["is_active = true"]
            params = []

            if tenant_id:
                where_conditions.append(f"tenant_id = ${len(params) + 1}")
                params.append(tenant_id)

            if not force_update:
                where_conditions.append("ai_match_embedding IS NULL")

            # 构建查询
            query = f"""
            SELECT * FROM engineers 
            WHERE {' AND '.join(where_conditions)}
            ORDER BY created_at DESC
            """

            if limit:
                query += f" LIMIT {limit}"

            # 获取需要更新的简历
            engineers = await conn.fetch(query, *params)
            logger.info(f"找到 {len(engineers)} 个需要更新的简历")

            if not engineers:
                logger.info("没有需要更新的简历")
                return

            # 批量处理
            updated_count = 0

            for i in range(0, len(engineers), generator.batch_size):
                batch = engineers[i : i + generator.batch_size]

                # 生成paraphrase文本
                paraphrases = []
                engineer_ids = []

                for engineer in batch:
                    paraphrase = generator.create_engineer_paraphrase(dict(engineer))
                    paraphrases.append(paraphrase)
                    engineer_ids.append(engineer["id"])

                # 生成embeddings
                logger.info(f"生成第 {i//generator.batch_size + 1} 批embeddings...")
                embeddings = generator.generate_embeddings(paraphrases)

                # 更新数据库
                for j, (engineer_id, paraphrase, embedding) in enumerate(
                    zip(engineer_ids, paraphrases, embeddings)
                ):
                    try:
                        await conn.execute(
                            """
                            UPDATE engineers 
                            SET ai_match_paraphrase = $1, ai_match_embedding = $2, updated_at = NOW()
                            WHERE id = $3
                        """,
                            paraphrase,
                            embedding,
                            engineer_id,
                        )
                        updated_count += 1
                    except Exception as e:
                        logger.error(f"更新简历 {engineer_id} 失败: {str(e)}")

                logger.info(
                    f"已处理 {min(i + generator.batch_size, len(engineers))}/{len(engineers)} 个简历"
                )

            logger.info(f"✅ 简历embeddings更新完成: {updated_count}/{len(engineers)}")

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"❌ 更新简历embeddings失败: {str(e)}")
        raise


async def show_embedding_statistics():
    """显示embedding统计信息"""
    try:
        logger.info("获取embedding统计信息...")

        conn = await asyncpg.connect(settings.DATABASE_URL)

        try:
            # 项目统计
            project_stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total,
                    COUNT(ai_match_embedding) as with_embedding,
                    COUNT(ai_match_paraphrase) as with_paraphrase
                FROM projects 
                WHERE is_active = true
            """
            )

            # 简历统计
            engineer_stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total,
                    COUNT(ai_match_embedding) as with_embedding,
                    COUNT(ai_match_paraphrase) as with_paraphrase
                FROM engineers 
                WHERE is_active = true
            """
            )

            print("\n📊 Embedding统计信息:")
            print("=" * 40)
            print(f"项目:")
            print(f"  总数: {project_stats['total']}")
            print(f"  有embedding: {project_stats['with_embedding']}")
            print(f"  有paraphrase: {project_stats['with_paraphrase']}")
            print(
                f"  完成率: {project_stats['with_embedding']/project_stats['total']*100:.1f}%"
                if project_stats["total"] > 0
                else "  完成率: 0%"
            )

            print(f"\n简历:")
            print(f"  总数: {engineer_stats['total']}")
            print(f"  有embedding: {engineer_stats['with_embedding']}")
            print(f"  有paraphrase: {engineer_stats['with_paraphrase']}")
            print(
                f"  完成率: {engineer_stats['with_embedding']/engineer_stats['total']*100:.1f}%"
                if engineer_stats["total"] > 0
                else "  完成率: 0%"
            )

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"获取统计信息失败: {str(e)}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="生成和更新AI匹配用的embedding向量")
    parser.add_argument(
        "--type",
        choices=["projects", "engineers", "both"],
        default="both",
        help="更新类型 (默认: both)",
    )
    parser.add_argument("--tenant-id", help="指定租户ID")
    parser.add_argument("--force", action="store_true", help="强制更新所有记录")
    parser.add_argument("--limit", type=int, help="限制处理数量")
    parser.add_argument("--stats-only", action="store_true", help="只显示统计信息")

    args = parser.parse_args()

    print("🚀 AI匹配Embedding生成工具")
    print("=" * 50)

    try:
        # 只显示统计信息
        if args.stats_only:
            asyncio.run(show_embedding_statistics())
            return

        # 创建生成器并加载模型
        generator = EmbeddingGenerator()
        generator.load_model()

        start_time = time.time()

        # 执行更新
        if args.type in ["projects", "both"]:
            asyncio.run(
                update_projects_embeddings(
                    generator,
                    tenant_id=args.tenant_id,
                    force_update=args.force,
                    limit=args.limit,
                )
            )

        if args.type in ["engineers", "both"]:
            asyncio.run(
                update_engineers_embeddings(
                    generator,
                    tenant_id=args.tenant_id,
                    force_update=args.force,
                    limit=args.limit,
                )
            )

        # 显示统计信息
        asyncio.run(show_embedding_statistics())

        end_time = time.time()

        print(f"\n⏱️ 总耗时: {end_time - start_time:.2f} 秒")
        print("\n🎉 Embedding生成完成！")
        print("\n💡 提示:")
        print("- 新增项目或简历后，运行此脚本更新embedding")
        print("- 定期重新生成以保持匹配准确性")
        print("- 可以使用 --stats-only 查看当前状态")

    except Exception as e:
        print(f"\n❌ 执行失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
