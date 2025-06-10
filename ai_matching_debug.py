#!/usr/bin/env python3
# ai_matching_debug.py - AI匹配问题诊断和修复脚本
import asyncio
import asyncpg
import logging
import sys
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.config import settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AIMatchingDebugger:
    """AI匹配问题诊断器"""

    def __init__(self):
        self.test_tenant_id = "33723dd6-cf28-4dab-975c-f883f5389d04"

    async def connect_db(self):
        """连接数据库"""
        return await asyncpg.connect(settings.DATABASE_URL)

    async def check_data_quality(self):
        """检查数据质量"""
        print("🔍 检查数据质量")
        print("=" * 60)

        conn = await self.connect_db()
        try:
            # 1. 检查基础数据
            project_stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total,
                    COUNT(ai_match_embedding) as with_embedding,
                    COUNT(ai_match_paraphrase) as with_paraphrase,
                    COUNT(CASE WHEN array_length(skills, 1) > 0 THEN 1 END) as with_skills
                FROM projects 
                WHERE tenant_id = $1 AND is_active = true
            """,
                self.test_tenant_id,
            )

            engineer_stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total,
                    COUNT(ai_match_embedding) as with_embedding,
                    COUNT(ai_match_paraphrase) as with_paraphrase,
                    COUNT(CASE WHEN array_length(skills, 1) > 0 THEN 1 END) as with_skills
                FROM engineers 
                WHERE tenant_id = $1 AND is_active = true
            """,
                self.test_tenant_id,
            )

            print(f"📊 项目数据:")
            print(f"   总数: {project_stats['total']}")
            print(f"   有embedding: {project_stats['with_embedding']}")
            print(f"   有paraphrase: {project_stats['with_paraphrase']}")
            print(f"   有技能: {project_stats['with_skills']}")

            print(f"\n📊 简历数据:")
            print(f"   总数: {engineer_stats['total']}")
            print(f"   有embedding: {engineer_stats['with_embedding']}")
            print(f"   有paraphrase: {engineer_stats['with_paraphrase']}")
            print(f"   有技能: {engineer_stats['with_skills']}")

            if (
                project_stats["with_embedding"] == 0
                or engineer_stats["with_embedding"] == 0
            ):
                print("❌ 缺少embedding数据，请先运行 generate_embeddings.py")
                return False

            return True

        finally:
            await conn.close()

    async def test_embedding_similarity(self):
        """测试embedding相似度计算"""
        print("\n🧮 测试embedding相似度计算")
        print("=" * 60)

        conn = await self.connect_db()
        try:
            # 获取两个有embedding的项目
            projects = await conn.fetch(
                """
                SELECT id, title, ai_match_embedding, ai_match_paraphrase
                FROM projects 
                WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
                LIMIT 5
            """,
                self.test_tenant_id,
            )

            engineers = await conn.fetch(
                """
                SELECT id, name, ai_match_embedding, ai_match_paraphrase
                FROM engineers 
                WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
                LIMIT 5
            """,
                self.test_tenant_id,
            )

            if not projects or not engineers:
                print("❌ 没有足够的测试数据")
                return

            print(f"🎯 测试数据: {len(projects)}个项目, {len(engineers)}个简历")

            # 测试项目之间的相似度
            if len(projects) >= 2:
                p1, p2 = projects[0], projects[1]
                similarity = await conn.fetchval(
                    """
                    SELECT 1 - (ai_match_embedding <#> $1) as similarity
                    FROM projects WHERE id = $2
                """,
                    p1["ai_match_embedding"],
                    p2["id"],
                )

                print(f"\n📏 项目间相似度测试:")
                print(f"   项目1: {p1['title'][:30]}...")
                print(f"   项目2: {p2['title'][:30]}...")
                print(f"   相似度: {similarity:.4f}")

            # 测试项目和简历的相似度
            if projects and engineers:
                p = projects[0]
                e = engineers[0]

                # 使用正确的相似度计算
                similarity_raw = await conn.fetchval(
                    """
                    SELECT $1::vector <#> $2::vector as distance
                """,
                    p["ai_match_embedding"],
                    e["ai_match_embedding"],
                )

                similarity = 1 - similarity_raw  # 转换距离为相似度

                print(f"\n🎯 项目-简历相似度测试:")
                print(f"   项目: {p['title'][:30]}...")
                print(f"   简历: {e['name']}")
                print(f"   余弦距离: {similarity_raw:.4f}")
                print(f"   相似度分数: {similarity:.4f}")

                # 测试批量相似度计算
                print(f"\n🔄 批量相似度计算测试:")
                engineer_ids = [e["id"] for e in engineers]
                similarities = await conn.fetch(
                    """
                    SELECT id, name, 1 - (ai_match_embedding <#> $1) as similarity
                    FROM engineers 
                    WHERE id = ANY($2) AND ai_match_embedding IS NOT NULL
                    ORDER BY similarity DESC
                """,
                    p["ai_match_embedding"],
                    engineer_ids,
                )

                for i, sim in enumerate(similarities[:3], 1):
                    print(f"   {i}. {sim['name']}: {sim['similarity']:.4f}")

        finally:
            await conn.close()

    async def test_detailed_matching_logic(self):
        """测试详细匹配逻辑"""
        print("\n🔧 测试详细匹配逻辑")
        print("=" * 60)

        conn = await self.connect_db()
        try:
            # 获取测试项目和简历
            project = await conn.fetchrow(
                """
                SELECT * FROM projects 
                WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
                AND array_length(skills, 1) > 0
                LIMIT 1
            """,
                self.test_tenant_id,
            )

            engineer = await conn.fetchrow(
                """
                SELECT * FROM engineers 
                WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
                AND array_length(skills, 1) > 0
                LIMIT 1
            """,
                self.test_tenant_id,
            )

            if not project or not engineer:
                print("❌ 没有足够的测试数据")
                return

            print(f"🎯 测试匹配:")
            print(f"   项目: {project['title']}")
            print(f"   简历: {engineer['name']}")

            # 测试技能匹配
            project_skills = set(project["skills"] or [])
            engineer_skills = set(engineer["skills"] or [])

            matched_skills = project_skills.intersection(engineer_skills)
            missing_skills = project_skills - engineer_skills
            skill_match_score = (
                len(matched_skills) / len(project_skills) if project_skills else 0.5
            )

            print(f"\n🛠️ 技能匹配分析:")
            print(f"   项目技能: {list(project_skills)}")
            print(f"   简历技能: {list(engineer_skills)}")
            print(f"   匹配技能: {list(matched_skills)}")
            print(f"   缺失技能: {list(missing_skills)}")
            print(f"   技能匹配分数: {skill_match_score:.3f}")

            # 测试语义相似度
            similarity_distance = await conn.fetchval(
                """
                SELECT $1::vector <#> $2::vector
            """,
                project["ai_match_embedding"],
                engineer["ai_match_embedding"],
            )

            similarity_score = max(0, 1 - similarity_distance)

            print(f"\n🧠 语义相似度:")
            print(f"   余弦距离: {similarity_distance:.4f}")
            print(f"   相似度分数: {similarity_score:.4f}")

            # 计算综合分数
            weights = {"skill_match": 0.3, "similarity": 0.3, "other_factors": 0.4}

            # 简化的其他因素分数
            other_score = 0.7  # 假设其他因素的平均分数

            final_score = (
                skill_match_score * weights["skill_match"]
                + similarity_score * weights["similarity"]
                + other_score * weights["other_factors"]
            )

            print(f"\n🎯 综合评分:")
            print(f"   技能权重分: {skill_match_score * weights['skill_match']:.3f}")
            print(f"   相似度权重分: {similarity_score * weights['similarity']:.3f}")
            print(f"   其他因素权重分: {other_score * weights['other_factors']:.3f}")
            print(f"   最终分数: {final_score:.3f}")

            return final_score

        finally:
            await conn.close()

    async def test_candidate_filtering(self):
        """测试候选过滤逻辑"""
        print("\n🔍 测试候选过滤逻辑")
        print("=" * 60)

        conn = await self.connect_db()
        try:
            # 测试获取候选简历的查询
            total_engineers = await conn.fetchval(
                """
                SELECT COUNT(*) FROM engineers 
                WHERE tenant_id = $1 AND is_active = true
            """,
                self.test_tenant_id,
            )

            engineers_with_embedding = await conn.fetchval(
                """
                SELECT COUNT(*) FROM engineers 
                WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
            """,
                self.test_tenant_id,
            )

            print(f"📊 简历筛选统计:")
            print(f"   总活跃简历: {total_engineers}")
            print(f"   有embedding的简历: {engineers_with_embedding}")
            print(
                f"   筛选率: {engineers_with_embedding/total_engineers*100:.1f}%"
                if total_engineers > 0
                else "   筛选率: 0%"
            )

            # 测试不同的筛选条件
            filters_tests = [
                ("无筛选", {}),
                ("日语水平筛选", {"japanese_level": ["N1", "N2"]}),
                ("状态筛选", {"current_status": ["available"]}),
            ]

            for filter_name, filters in filters_tests:
                base_query = """
                    SELECT COUNT(*) FROM engineers 
                    WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
                """
                params = [self.test_tenant_id]
                conditions = []

                if "japanese_level" in filters:
                    conditions.append(f"japanese_level = ANY(${len(params) + 1})")
                    params.append(filters["japanese_level"])

                if "current_status" in filters:
                    conditions.append(f"current_status = ANY(${len(params) + 1})")
                    params.append(filters["current_status"])

                if conditions:
                    query = base_query + " AND " + " AND ".join(conditions)
                else:
                    query = base_query

                count = await conn.fetchval(query, *params)
                print(f"   {filter_name}: {count}个候选")

        finally:
            await conn.close()

    async def run_enhanced_matching_test(self):
        """运行增强的匹配测试"""
        print("\n🚀 运行增强的匹配测试")
        print("=" * 60)

        conn = await self.connect_db()
        try:
            # 获取测试项目
            project = await conn.fetchrow(
                """
                SELECT * FROM projects 
                WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
                ORDER BY created_at DESC LIMIT 1
            """,
                self.test_tenant_id,
            )

            if not project:
                print("❌ 没有可用的测试项目")
                return

            # 获取候选简历（降低门槛）
            engineers = await conn.fetch(
                """
                SELECT * FROM engineers 
                WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
                ORDER BY created_at DESC LIMIT 20
            """,
                self.test_tenant_id,
            )

            if not engineers:
                print("❌ 没有可用的测试简历")
                return

            print(f"🎯 测试项目: {project['title']}")
            print(f"📋 候选简历: {len(engineers)}个")

            # 计算匹配分数
            matches = []

            for engineer in engineers:
                try:
                    # 计算相似度
                    similarity_distance = await conn.fetchval(
                        """
                        SELECT $1::vector <#> $2::vector
                    """,
                        project["ai_match_embedding"],
                        engineer["ai_match_embedding"],
                    )

                    similarity_score = max(0, 1 - similarity_distance)

                    # 计算技能匹配
                    project_skills = set(project["skills"] or [])
                    engineer_skills = set(engineer["skills"] or [])

                    if project_skills:
                        matched_skills = project_skills.intersection(engineer_skills)
                        skill_match_score = len(matched_skills) / len(project_skills)
                    else:
                        skill_match_score = 0.5

                    # 简化的综合分数计算
                    final_score = (
                        similarity_score * 0.4 + skill_match_score * 0.4 + 0.2 * 0.7
                    )

                    matches.append(
                        {
                            "engineer_id": engineer["id"],
                            "engineer_name": engineer["name"],
                            "similarity_score": similarity_score,
                            "skill_match_score": skill_match_score,
                            "final_score": final_score,
                            "matched_skills": list(
                                project_skills.intersection(engineer_skills)
                            ),
                        }
                    )

                except Exception as e:
                    print(f"   ❌ 计算匹配失败: {engineer['name']} - {str(e)}")
                    continue

            # 排序并显示结果
            matches.sort(key=lambda x: x["final_score"], reverse=True)

            print(f"\n📈 匹配结果 (前10名):")
            print("-" * 80)

            for i, match in enumerate(matches[:10], 1):
                print(
                    f"{i:2d}. {match['engineer_name']:<20} "
                    f"总分: {match['final_score']:.3f} "
                    f"相似度: {match['similarity_score']:.3f} "
                    f"技能: {match['skill_match_score']:.3f} "
                    f"匹配技能: {match['matched_skills']}"
                )

            # 分析低分原因
            if matches:
                avg_similarity = np.mean([m["similarity_score"] for m in matches])
                avg_skill = np.mean([m["skill_match_score"] for m in matches])
                avg_final = np.mean([m["final_score"] for m in matches])

                print(f"\n📊 分数分析:")
                print(f"   平均相似度分数: {avg_similarity:.3f}")
                print(f"   平均技能分数: {avg_skill:.3f}")
                print(f"   平均最终分数: {avg_final:.3f}")

                # 检查是否有高分匹配
                high_score_count = len([m for m in matches if m["final_score"] >= 0.6])
                medium_score_count = len(
                    [m for m in matches if 0.3 <= m["final_score"] < 0.6]
                )
                low_score_count = len([m for m in matches if m["final_score"] < 0.3])

                print(f"\n🎯 分数分布:")
                print(f"   高分 (≥0.6): {high_score_count}个")
                print(f"   中分 (0.3-0.6): {medium_score_count}个")
                print(f"   低分 (<0.3): {low_score_count}个")

                if high_score_count == 0:
                    print("\n⚠️ 建议:")
                    if avg_similarity < 0.3:
                        print("   - 语义相似度过低，考虑改善embedding质量")
                    if avg_skill < 0.3:
                        print("   - 技能匹配度过低，检查技能数据完整性")
                    print("   - 考虑降低min_score阈值到0.2-0.4")
                    print("   - 调整权重配置，增加相似度权重")

            return len(matches), matches[:5] if matches else []

        finally:
            await conn.close()

    async def generate_recommendations(self):
        """生成优化建议"""
        print("\n💡 优化建议")
        print("=" * 60)

        recommendations = []

        # 1. 检查数据质量
        data_ok = await self.check_data_quality()
        if not data_ok:
            recommendations.append("首先确保所有项目和简历都有embedding数据")
            recommendations.append(
                "运行: python generate_embeddings.py --type both --force"
            )
            return recommendations

        # 2. 测试匹配效果
        match_count, top_matches = await self.run_enhanced_matching_test()

        if match_count == 0:
            recommendations.extend(
                [
                    "没有找到任何匹配，建议:",
                    "1. 检查embedding生成是否正确",
                    "2. 验证数据库中的vector字段格式",
                    "3. 确认tenant_id是否正确",
                ]
            )
        elif not any(m["final_score"] >= 0.6 for m in top_matches):
            avg_score = (
                np.mean([m["final_score"] for m in top_matches]) if top_matches else 0
            )
            recommendations.extend(
                [
                    f"匹配分数普遍较低 (平均: {avg_score:.3f})，建议:",
                    "1. 降低min_score阈值到0.2-0.4",
                    "2. 调整权重配置，增加语义相似度权重",
                    "3. 改善项目和简历的描述质量",
                    "4. 检查技能标签的一致性",
                ]
            )
        else:
            recommendations.append("✅ 匹配效果良好，系统工作正常")

        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")

        return recommendations


async def main():
    """主函数"""
    print("🔍 AI匹配问题诊断工具")
    print("=" * 80)

    debugger = AIMatchingDebugger()

    try:
        # 1. 检查数据质量
        await debugger.check_data_quality()

        # 2. 测试embedding相似度
        await debugger.test_embedding_similarity()

        # 3. 测试详细匹配逻辑
        await debugger.test_detailed_matching_logic()

        # 4. 测试候选过滤
        await debugger.test_candidate_filtering()

        # 5. 运行增强测试
        await debugger.run_enhanced_matching_test()

        # 6. 生成建议
        await debugger.generate_recommendations()

    except Exception as e:
        print(f"❌ 诊断过程中出现错误: {str(e)}")
        import traceback

        print(f"详细错误信息:\n{traceback.format_exc()}")


if __name__ == "__main__":
    asyncio.run(main())
