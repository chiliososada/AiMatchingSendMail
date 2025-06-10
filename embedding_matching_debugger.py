#!/usr/bin/env python3
# fixed_embedding_matching_debugger.py - 修复pgvector兼容性问题
import asyncio
import sys
from pathlib import Path
import numpy as np
import json

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.database import fetch_one, fetch_all
from app.services.ai_matching_service import AIMatchingService
from app.schemas.ai_matching_schemas import ProjectToEngineersMatchRequest
from uuid import UUID


class FixedEmbeddingMatchingDebugger:
    """修复版：诊断相同embedding无法匹配的问题"""

    def __init__(self):
        self.tenant_id = "33723dd6-cf28-4dab-975c-f883f5389d04"
        self.matching_service = AIMatchingService()

    async def check_pgvector_setup(self):
        """检查pgvector扩展和设置"""
        print("🔍 检查pgvector扩展...")

        try:
            # 检查pgvector扩展
            extension_check = await fetch_one(
                """
                SELECT * FROM pg_extension WHERE extname = 'vector'
            """
            )

            if extension_check:
                print("✅ pgvector扩展已安装")
            else:
                print("❌ pgvector扩展未安装")
                return False

            # 检查vector相关函数
            functions_check = await fetch_all(
                """
                SELECT proname FROM pg_proc 
                WHERE proname IN ('vector_dims', 'cosine_distance', 'inner_product')
            """
            )

            available_functions = [f["proname"] for f in functions_check]
            print(f"可用函数: {available_functions}")

            # 测试vector操作
            test_result = await fetch_one(
                """
                SELECT '[1,2,3]'::vector as test_vector
            """
            )

            if test_result:
                print("✅ vector类型工作正常")

            return True

        except Exception as e:
            print(f"❌ pgvector检查失败: {str(e)}")
            return False

    async def check_database_consistency_fixed(self):
        """修复版：检查数据库一致性（兼容pgvector）"""
        print("\n🔍 检查数据库一致性")
        print("=" * 60)

        try:
            # 修复版项目统计（兼容vector类型）
            project_stats = await fetch_one(
                """
                SELECT 
                    COUNT(*) as total,
                    COUNT(ai_match_embedding) as with_embedding,
                    -- 使用vector_dims函数获取向量维度
                    (SELECT vector_dims(ai_match_embedding) 
                     FROM projects 
                     WHERE tenant_id = $1 AND ai_match_embedding IS NOT NULL 
                     LIMIT 1) as embedding_dims
                FROM projects 
                WHERE tenant_id = $1 AND is_active = true
            """,
                self.tenant_id,
            )

            # 修复版简历统计
            engineer_stats = await fetch_one(
                """
                SELECT 
                    COUNT(*) as total,
                    COUNT(ai_match_embedding) as with_embedding,
                    -- 使用vector_dims函数获取向量维度
                    (SELECT vector_dims(ai_match_embedding) 
                     FROM engineers 
                     WHERE tenant_id = $1 AND ai_match_embedding IS NOT NULL 
                     LIMIT 1) as embedding_dims
                FROM engineers 
                WHERE tenant_id = $1 AND is_active = true
            """,
                self.tenant_id,
            )

            print(f"项目统计:")
            print(f"  总数: {project_stats['total']}")
            print(f"  有embedding: {project_stats['with_embedding']}")
            print(f"  embedding维度: {project_stats['embedding_dims']}")

            print(f"\n简历统计:")
            print(f"  总数: {engineer_stats['total']}")
            print(f"  有embedding: {engineer_stats['with_embedding']}")
            print(f"  embedding维度: {engineer_stats['embedding_dims']}")

            # 检查匹配历史
            match_history = await fetch_one(
                """
                SELECT 
                    COUNT(*) as total_history,
                    COUNT(CASE WHEN execution_status = 'completed' THEN 1 END) as completed,
                    COUNT(CASE WHEN execution_status = 'failed' THEN 1 END) as failed
                FROM ai_matching_history 
                WHERE tenant_id = $1
            """,
                self.tenant_id,
            )

            print(f"\n匹配历史:")
            print(f"  总历史记录: {match_history['total_history']}")
            print(f"  成功完成: {match_history['completed']}")
            print(f"  失败: {match_history['failed']}")

            # 检查已保存的匹配
            saved_matches = await fetch_one(
                """
                SELECT 
                    COUNT(*) as total_matches,
                    AVG(match_score) as avg_score,
                    COUNT(CASE WHEN match_score >= 0.8 THEN 1 END) as high_quality
                FROM project_engineer_matches 
                WHERE tenant_id = $1 AND is_active = true
            """,
                self.tenant_id,
            )

            print(f"\n已保存匹配:")
            print(f"  总匹配数: {saved_matches['total_matches']}")
            print(
                f"  平均分数: {saved_matches['avg_score']:.4f}"
                if saved_matches["avg_score"]
                else "  平均分数: 0"
            )
            print(f"  高质量匹配: {saved_matches['high_quality']}")

            return True

        except Exception as e:
            print(f"❌ 数据库一致性检查失败: {str(e)}")
            import traceback

            print(f"详细错误:\n{traceback.format_exc()}")
            return False

    async def find_similar_embeddings_fixed(self):
        """修复版：查找相似的embedding（使用pgvector查询）"""
        print("\n🔍 查找相似的embedding...")

        try:
            # 获取一个测试项目
            test_project = await fetch_one(
                """
                SELECT id, title, ai_match_embedding, skills, experience, japanese_level
                FROM projects 
                WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
                ORDER BY created_at DESC LIMIT 1
            """,
                self.tenant_id,
            )

            if not test_project:
                print("❌ 没有找到测试项目")
                return []

            print(f"测试项目: {test_project['title']}")

            # 使用pgvector查找最相似的简历
            similar_engineers = await fetch_all(
                """
                SELECT 
                    id, name, ai_match_embedding,
                    skills, experience, japanese_level,
                    ai_match_embedding <#> $1 as cosine_distance,
                    1 - (ai_match_embedding <#> $1) as cosine_similarity
                FROM engineers 
                WHERE tenant_id = $2 AND is_active = true AND ai_match_embedding IS NOT NULL
                ORDER BY ai_match_embedding <#> $1 ASC
                LIMIT 10
            """,
                test_project["ai_match_embedding"],
                self.tenant_id,
            )

            print(f"找到 {len(similar_engineers)} 个相似简历")

            # 分析前3个最相似的
            for i, engineer in enumerate(similar_engineers[:3]):
                similarity = engineer["cosine_similarity"]
                distance = engineer["cosine_distance"]

                print(f"\n=== 相似简历 {i+1} ===")
                print(f"简历: {engineer['name']}")
                print(f"余弦距离: {distance:.6f}")
                print(f"余弦相似度: {similarity:.6f}")
                print(f"项目技能: {test_project['skills']}")
                print(f"简历技能: {engineer['skills']}")
                print(f"项目经验: {test_project['experience']}")
                print(f"简历经验: {engineer['experience']}")
                print(f"项目日语: {test_project['japanese_level']}")
                print(f"简历日语: {engineer['japanese_level']}")

                # 测试这对数据的匹配情况
                await self.debug_specific_pair_fixed(test_project, engineer)

            return similar_engineers

        except Exception as e:
            print(f"❌ 查找相似embedding失败: {str(e)}")
            import traceback

            print(f"详细错误:\n{traceback.format_exc()}")
            return []

    async def debug_specific_pair_fixed(self, project, engineer):
        """修复版：调试特定的项目-简历对"""
        print(f"\n🔍 调试匹配过程:")

        try:
            # 1. 验证pgvector相似度计算
            print("1. 验证pgvector相似度计算...")

            pgvector_result = await fetch_one(
                """
                SELECT 
                    ai_match_embedding <#> $1 as distance,
                    1 - (ai_match_embedding <#> $1) as similarity
                FROM engineers 
                WHERE id = $2
            """,
                project["ai_match_embedding"],
                engineer["id"],
            )

            if pgvector_result:
                distance = pgvector_result["distance"]
                similarity = pgvector_result["similarity"]
                print(f"   pgvector距离: {distance:.6f}")
                print(f"   pgvector相似度: {similarity:.6f}")
            else:
                print("   ❌ pgvector查询失败")
                return

            # 2. 测试详细分数计算
            print("2. 测试详细分数计算...")
            detailed_scores = self.matching_service._calculate_detailed_match_scores(
                project, engineer
            )

            for key, value in detailed_scores.items():
                if isinstance(value, (int, float)):
                    print(f"   {key}: {value:.4f}")
                else:
                    print(f"   {key}: {value}")

            # 3. 测试权重分数计算
            print("3. 测试权重分数计算...")
            weights = {
                "skill_match": 0.5,
                "experience_match": 0.3,
                "japanese_level_match": 0.2,
            }

            final_score = self.matching_service._calculate_weighted_score(
                detailed_scores, weights, similarity
            )

            print(f"   语义相似度: {similarity:.4f}")
            print(f"   最终分数: {final_score:.4f}")

            # 4. 分析为什么可能匹配不上
            print("4. 匹配失败原因分析...")

            # 计算每个维度对最终分数的贡献
            skill_contribution = (
                detailed_scores.get("skill_match", 0) * weights["skill_match"]
            )
            exp_contribution = (
                detailed_scores.get("experience_match", 0) * weights["experience_match"]
            )
            jp_contribution = (
                detailed_scores.get("japanese_level_match", 0)
                * weights["japanese_level_match"]
            )

            base_score = skill_contribution + exp_contribution + jp_contribution
            semantic_contribution = similarity * 0.3
            structural_contribution = base_score * 0.7

            print(
                f"   技能贡献: {skill_contribution:.4f} (权重{weights['skill_match']})"
            )
            print(
                f"   经验贡献: {exp_contribution:.4f} (权重{weights['experience_match']})"
            )
            print(
                f"   日语贡献: {jp_contribution:.4f} (权重{weights['japanese_level_match']})"
            )
            print(f"   结构化总分: {base_score:.4f}")
            print(f"   语义贡献: {semantic_contribution:.4f} (权重0.3)")
            print(f"   结构化贡献: {structural_contribution:.4f} (权重0.7)")
            print(f"   最终分数: {semantic_contribution + structural_contribution:.4f}")

            # 判断是否会被过滤
            common_thresholds = [0.0, 0.1, 0.3, 0.5, 0.6, 0.7, 0.8]
            print(f"   不同门槛下是否通过:")
            for threshold in common_thresholds:
                passed = final_score >= threshold
                status = "✅" if passed else "❌"
                print(f"     门槛{threshold}: {status}")

        except Exception as e:
            print(f"❌ 调试过程出错: {str(e)}")
            import traceback

            print(f"详细错误:\n{traceback.format_exc()}")

    async def test_direct_matching_fixed(self):
        """修复版：直接测试匹配功能"""
        print("\n🎯 直接测试匹配功能")
        print("=" * 60)

        # 获取测试数据
        project = await fetch_one(
            """
            SELECT * FROM projects 
            WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
            ORDER BY created_at DESC LIMIT 1
        """,
            self.tenant_id,
        )

        if not project:
            print("❌ 没有找到测试项目")
            return

        print(f"测试项目: {project['title']}")

        # 测试不同的配置
        test_configs = [
            {
                "name": "零门槛测试",
                "min_score": 0.0,
                "weights": {
                    "skill_match": 0.5,
                    "experience_match": 0.3,
                    "japanese_level_match": 0.2,
                },
            },
            {
                "name": "语义优先测试",
                "min_score": 0.1,
                "weights": {
                    "skill_match": 0.1,
                    "experience_match": 0.1,
                    "japanese_level_match": 0.05,
                },
            },
            {
                "name": "标准配置测试",
                "min_score": 0.6,
                "weights": {
                    "skill_match": 0.5,
                    "experience_match": 0.3,
                    "japanese_level_match": 0.2,
                },
            },
        ]

        for config in test_configs:
            print(f"\n🧪 {config['name']}:")
            print(f"   最小分数: {config['min_score']}")
            print(f"   权重配置: {config['weights']}")

            try:
                # 创建匹配请求
                request = ProjectToEngineersMatchRequest(
                    tenant_id=UUID(self.tenant_id),
                    project_id=project["id"],
                    max_matches=10,
                    min_score=config["min_score"],
                    executed_by=None,
                    matching_type="project_to_engineers",
                    trigger_type="debug",
                    weights=config["weights"],
                    filters={},
                )

                result = await self.matching_service.match_project_to_engineers(request)

                print(f"   ✅ 匹配完成:")
                print(f"   总匹配数: {result.total_matches}")
                print(f"   高质量匹配: {result.high_quality_matches}")
                print(f"   处理时间: {result.processing_time_seconds}秒")

                if result.matches:
                    print(f"   前3个匹配结果:")
                    for i, match in enumerate(result.matches[:3], 1):
                        print(f"   {i}. {match.engineer_name}: {match.match_score:.4f}")
                        print(f"      技能: {match.skill_match_score:.4f}")
                        print(f"      经验: {match.experience_match_score:.4f}")
                        print(f"      日语: {match.japanese_level_match_score:.4f}")
                else:
                    print("   ❌ 没有找到任何匹配")

            except Exception as e:
                print(f"   ❌ 测试失败: {str(e)}")

    async def generate_api_test_commands(self):
        """生成API测试命令"""
        print("\n📋 生成API测试命令")
        print("=" * 60)

        # 获取测试项目ID
        project = await fetch_one(
            """
            SELECT id, title FROM projects 
            WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
            ORDER BY created_at DESC LIMIT 1
        """,
            self.tenant_id,
        )

        if not project:
            print("❌ 没有找到测试项目")
            return

        project_id = str(project["id"])
        print(f"测试项目: {project['title']} ({project_id})")

        # 零门槛配置
        zero_threshold_config = {
            "tenant_id": self.tenant_id,
            "project_id": project_id,
            "max_matches": 20,
            "min_score": 0.0,
            "executed_by": None,
            "matching_type": "project_to_engineers",
            "trigger_type": "api_test",
            "weights": {
                "skill_match": 0.5,
                "experience_match": 0.3,
                "japanese_level_match": 0.2,
            },
            "filters": {},
        }

        # 语义优先配置
        semantic_first_config = {
            "tenant_id": self.tenant_id,
            "project_id": project_id,
            "max_matches": 20,
            "min_score": 0.0,
            "executed_by": None,
            "matching_type": "project_to_engineers",
            "trigger_type": "api_test",
            "weights": {
                "skill_match": 0.1,
                "experience_match": 0.1,
                "japanese_level_match": 0.05,
            },
            "filters": {},
        }

        import json

        print(f"\n1. 零门槛测试 (curl):")
        print(
            f"curl -X POST 'http://localhost:8000/api/v1/ai-matching/project-to-engineers' \\"
        )
        print(f"     -H 'Content-Type: application/json' \\")
        print(f"     -d '{json.dumps(zero_threshold_config)}'")

        print(f"\n2. 语义优先测试 (curl):")
        print(
            f"curl -X POST 'http://localhost:8000/api/v1/ai-matching/project-to-engineers' \\"
        )
        print(f"     -H 'Content-Type: application/json' \\")
        print(f"     -d '{json.dumps(semantic_first_config)}'")

        print(f"\n3. Python requests测试:")
        python_code = f"""
import requests
import json

# 零门槛配置
config = {json.dumps(zero_threshold_config, indent=4)}

response = requests.post(
    "http://localhost:8000/api/v1/ai-matching/project-to-engineers",
    json=config
)

print(f"状态码: {{response.status_code}}")
if response.status_code == 200:
    result = response.json()
    print(f"匹配数: {{result.get('total_matches', 0)}}")
    if result.get('matches'):
        print("前5个匹配:")
        for i, match in enumerate(result['matches'][:5], 1):
            print(f"{{i}}. {{match['engineer_name']}}: {{match['match_score']:.4f}}")
else:
    print(f"错误: {{response.text}}")
"""
        print(python_code)

    async def run_full_diagnosis_fixed(self):
        """运行完整诊断（修复版）"""
        print("🏥 AI匹配问题诊断工具 (修复版)")
        print("=" * 80)

        try:
            # 1. 检查pgvector设置
            pgvector_ok = await self.check_pgvector_setup()
            if not pgvector_ok:
                print("❌ pgvector设置有问题，请检查数据库配置")
                return

            # 2. 检查数据库一致性
            db_ok = await self.check_database_consistency_fixed()
            if not db_ok:
                print("❌ 数据库一致性检查失败")
                return

            # 3. 查找相似embedding
            similar_pairs = await self.find_similar_embeddings_fixed()

            # 4. 直接测试匹配
            await self.test_direct_matching_fixed()

            # 5. 生成API测试命令
            await self.generate_api_test_commands()

            # 6. 生成诊断报告
            self.generate_diagnosis_report_fixed(similar_pairs)

        except Exception as e:
            print(f"❌ 诊断过程出错: {str(e)}")
            import traceback

            print(f"详细错误:\n{traceback.format_exc()}")

    def generate_diagnosis_report_fixed(self, similar_pairs):
        """生成诊断报告（修复版）"""
        print("\n" + "=" * 80)
        print("📊 诊断报告")
        print("=" * 80)

        print(f"🔍 发现 {len(similar_pairs)} 个相似简历")

        if similar_pairs:
            high_similarity_count = len(
                [p for p in similar_pairs if p["cosine_similarity"] > 0.9]
            )
            print(f"🎯 高相似度 (>0.9): {high_similarity_count} 个")

            print("\n🔍 问题诊断:")
            print("1. ✅ pgvector扩展工作正常")
            print("2. ✅ embedding数据存在")
            print("3. ✅ 相似度计算正常")

            if high_similarity_count > 0:
                print("4. ⚠️  有高相似度数据但可能匹配失败")
                print("   原因分析:")
                print("   - 结构化匹配分数低（技能、经验、日语）")
                print("   - 权重分配：70%结构化 + 30%语义")
                print("   - 最小分数门槛过高")
            else:
                print("4. ℹ️  相似度普遍较低，这是正常现象")

        print("\n💡 解决建议:")
        print("1. 立即可行:")
        print("   - 使用零门槛测试 (min_score: 0.0)")
        print("   - 调整权重，降低结构化匹配权重")
        print("   - 使用语义优先配置")

        print("\n2. 长期优化:")
        print("   - 改进结构化匹配算法")
        print("   - 优化权重分配策略")
        print("   - 增加数据质量检查")

        print("\n🛠️ 下一步操作:")
        print("1. 使用上面的API测试命令验证")
        print("2. 检查具体的结构化匹配分数")
        print("3. 考虑调整匹配算法参数")


async def main():
    """主函数"""
    debugger = FixedEmbeddingMatchingDebugger()
    await debugger.run_full_diagnosis_fixed()


if __name__ == "__main__":
    asyncio.run(main())
