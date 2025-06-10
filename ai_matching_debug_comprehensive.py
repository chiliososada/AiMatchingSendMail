#!/usr/bin/env python3
# ai_matching_debug_comprehensive.py - 全面诊断AI匹配问题
import asyncio
import sys
from pathlib import Path
import numpy as np
import json

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.database import fetch_one, fetch_all, fetch_val


class AIMatchingDebugger:
    """AI匹配问题诊断工具"""

    def __init__(self):
        self.tenant_id = "33723dd6-cf28-4dab-975c-f883f5389d04"

    async def check_embedding_data_format(self):
        """检查embedding数据格式"""
        print("🔍 1. 检查embedding数据格式和内容")
        print("=" * 60)

        # 检查项目数据
        project = await fetch_one(
            """
            SELECT id, title, ai_match_embedding, ai_match_paraphrase
            FROM projects 
            WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
            ORDER BY created_at DESC LIMIT 1
            """,
            self.tenant_id,
        )

        # 检查工程师数据
        engineer = await fetch_one(
            """
            SELECT id, name, ai_match_embedding, ai_match_paraphrase
            FROM engineers 
            WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
            ORDER BY created_at DESC LIMIT 1
            """,
            self.tenant_id,
        )

        if not project or not engineer:
            print("❌ 没有找到有embedding的测试数据")
            return False

        print(f"✅ 找到测试数据:")
        print(f"   项目: {project['title']}")
        print(f"   工程师: {engineer['name']}")

        # 分析embedding数据
        project_emb = project["ai_match_embedding"]
        engineer_emb = engineer["ai_match_embedding"]

        print(f"\n📊 Embedding数据分析:")
        print(f"   项目embedding类型: {type(project_emb)}")
        print(f"   工程师embedding类型: {type(engineer_emb)}")

        if hasattr(project_emb, "__len__"):
            print(f"   项目embedding维度: {len(project_emb)}")
        if hasattr(engineer_emb, "__len__"):
            print(f"   工程师embedding维度: {len(engineer_emb)}")

        # 检查是否为相同的embedding（这可能是问题所在）
        if isinstance(project_emb, list) and isinstance(engineer_emb, list):
            if len(project_emb) == len(engineer_emb):
                # 计算向量是否完全相同
                are_identical = all(
                    abs(a - b) < 1e-10 for a, b in zip(project_emb, engineer_emb)
                )
                print(f"   🔍 向量是否完全相同: {are_identical}")

                if are_identical:
                    print("   ⚠️  警告：项目和工程师的embedding完全相同！")
                    print("   这可能是数据生成问题或使用了相同的文本内容")

                # 计算余弦相似度
                project_np = np.array(project_emb)
                engineer_np = np.array(engineer_emb)

                dot_product = np.dot(project_np, engineer_np)
                norm_p = np.linalg.norm(project_np)
                norm_e = np.linalg.norm(engineer_np)

                if norm_p > 0 and norm_e > 0:
                    cosine_sim = dot_product / (norm_p * norm_e)
                    print(f"   📏 手动计算余弦相似度: {cosine_sim:.6f}")
                    print(f"   📏 标准化相似度 [0,1]: {(cosine_sim + 1) / 2:.6f}")

        # 检查paraphrase内容
        print(f"\n📝 Paraphrase内容检查:")
        print(f"   项目paraphrase: {project.get('ai_match_paraphrase', 'None')}")
        print(f"   工程师paraphrase: {engineer.get('ai_match_paraphrase', 'None')}")

        return True

    async def test_database_similarity_queries(self):
        """测试数据库相似度查询"""
        print("\n🔬 2. 测试数据库相似度查询")
        print("=" * 60)

        # 获取测试数据
        project = await fetch_one(
            "SELECT * FROM projects WHERE tenant_id = $1 AND ai_match_embedding IS NOT NULL LIMIT 1",
            self.tenant_id,
        )

        engineers = await fetch_all(
            "SELECT id, name, ai_match_embedding FROM engineers WHERE tenant_id = $1 AND ai_match_embedding IS NOT NULL LIMIT 3",
            self.tenant_id,
        )

        if not project or not engineers:
            print("❌ 缺少测试数据")
            return

        print(f"测试项目: {project['title']}")
        print(f"测试工程师数量: {len(engineers)}")

        # 测试不同的pgvector操作符
        print(f"\n🧮 pgvector操作符测试:")

        for engineer in engineers:
            engineer_id = engineer["id"]
            engineer_name = engineer["name"]

            print(f"\n工程师: {engineer_name}")

            # 测试余弦距离 (<=>)
            try:
                distance = await fetch_val(
                    "SELECT ai_match_embedding <=> $1 FROM engineers WHERE id = $2",
                    project["ai_match_embedding"],
                    engineer_id,
                )
                if distance is not None:
                    similarity = 1 - distance
                    print(f"   <=> 余弦距离: {distance:.6f} → 相似度: {similarity:.6f}")
                else:
                    print(f"   <=> 操作返回None")
            except Exception as e:
                print(f"   <=> 操作失败: {str(e)}")

            # 测试负内积 (<#>)
            try:
                neg_dot = await fetch_val(
                    "SELECT ai_match_embedding <#> $1 FROM engineers WHERE id = $2",
                    project["ai_match_embedding"],
                    engineer_id,
                )
                if neg_dot is not None:
                    print(f"   <#> 负内积: {neg_dot:.6f}")
                else:
                    print(f"   <#> 操作返回None")
            except Exception as e:
                print(f"   <#> 操作失败: {str(e)}")

    async def test_matching_service_query(self):
        """测试匹配服务的实际查询"""
        print("\n🎯 3. 测试匹配服务实际查询")
        print("=" * 60)

        # 获取测试数据
        project = await fetch_one(
            "SELECT * FROM projects WHERE tenant_id = $1 AND ai_match_embedding IS NOT NULL LIMIT 1",
            self.tenant_id,
        )

        engineer_ids = await fetch_all(
            "SELECT id FROM engineers WHERE tenant_id = $1 AND ai_match_embedding IS NOT NULL LIMIT 5",
            self.tenant_id,
        )

        if not project or not engineer_ids:
            print("❌ 缺少测试数据")
            return

        engineer_id_list = [e["id"] for e in engineer_ids]
        print(f"测试项目: {project['title']}")
        print(f"候选工程师数量: {len(engineer_id_list)}")

        # 模拟AIMatchingDatabase.calculate_similarities_by_database方法
        print(f"\n🔧 模拟匹配服务查询:")

        # 测试不同的min_score设置
        min_scores = [0.0, 0.1, 0.5, 0.8]

        for min_score in min_scores:
            print(f"\n   最小分数阈值: {min_score}")

            query = """
            SELECT 
                id,
                name,
                1 - (ai_match_embedding <=> $1) as similarity_score
            FROM engineers
            WHERE id = ANY($2) 
                AND ai_match_embedding IS NOT NULL
                AND 1 - (ai_match_embedding <=> $1) >= $3
            ORDER BY ai_match_embedding <=> $1 ASC
            LIMIT 10
            """

            try:
                results = await fetch_all(
                    query,
                    project["ai_match_embedding"],
                    engineer_id_list,
                    min_score,
                )

                print(f"     查询结果数量: {len(results)}")
                for result in results:
                    score = result["similarity_score"]
                    name = result["name"]
                    print(f"     - {name}: {score:.6f}")

            except Exception as e:
                print(f"     查询失败: {str(e)}")

    async def check_data_consistency(self):
        """检查数据一致性问题"""
        print("\n🔍 4. 检查数据一致性问题")
        print("=" * 60)

        # 检查有多少项目和工程师有embedding
        project_count = await fetch_val(
            "SELECT COUNT(*) FROM projects WHERE tenant_id = $1 AND is_active = true",
            self.tenant_id,
        )

        project_with_embedding = await fetch_val(
            "SELECT COUNT(*) FROM projects WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL",
            self.tenant_id,
        )

        engineer_count = await fetch_val(
            "SELECT COUNT(*) FROM engineers WHERE tenant_id = $1 AND is_active = true",
            self.tenant_id,
        )

        engineer_with_embedding = await fetch_val(
            "SELECT COUNT(*) FROM engineers WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL",
            self.tenant_id,
        )

        print(f"📊 数据统计:")
        print(f"   项目总数: {project_count}")
        print(f"   有embedding的项目: {project_with_embedding}")
        print(f"   工程师总数: {engineer_count}")
        print(f"   有embedding的工程师: {engineer_with_embedding}")

        if project_with_embedding == 0:
            print("   ❌ 没有项目有embedding数据！")
        if engineer_with_embedding == 0:
            print("   ❌ 没有工程师有embedding数据！")

        # 检查是否有重复的embedding
        print(f"\n🔍 检查embedding重复情况:")

        # 检查项目embedding重复
        duplicate_projects = await fetch_val(
            """
            SELECT COUNT(*) FROM (
                SELECT ai_match_embedding, COUNT(*) 
                FROM projects 
                WHERE tenant_id = $1 AND ai_match_embedding IS NOT NULL
                GROUP BY ai_match_embedding
                HAVING COUNT(*) > 1
            ) duplicates
            """,
            self.tenant_id,
        )

        # 检查工程师embedding重复
        duplicate_engineers = await fetch_val(
            """
            SELECT COUNT(*) FROM (
                SELECT ai_match_embedding, COUNT(*) 
                FROM engineers 
                WHERE tenant_id = $1 AND ai_match_embedding IS NOT NULL
                GROUP BY ai_match_embedding
                HAVING COUNT(*) > 1
            ) duplicates
            """,
            self.tenant_id,
        )

        print(f"   重复项目embedding组: {duplicate_projects}")
        print(f"   重复工程师embedding组: {duplicate_engineers}")

        if duplicate_projects > 0 or duplicate_engineers > 0:
            print("   ⚠️  发现重复的embedding，这可能影响匹配结果")

    async def check_ai_matching_api_call(self):
        """检查AI匹配API调用"""
        print("\n🚀 5. 测试AI匹配API调用")
        print("=" * 60)

        try:
            from app.services.ai_matching_service import AIMatchingService
            from app.schemas.ai_matching_schemas import ProjectToEngineersMatchRequest
            from uuid import UUID

            # 获取测试数据
            project = await fetch_one(
                "SELECT * FROM projects WHERE tenant_id = $1 AND ai_match_embedding IS NOT NULL LIMIT 1",
                self.tenant_id,
            )

            if not project:
                print("❌ 没有可用的测试项目")
                return

            print(f"测试项目: {project['title']}")

            # 创建AI匹配服务
            matching_service = AIMatchingService()
            print(f"✅ AI匹配服务创建成功")

            # 创建请求
            request = ProjectToEngineersMatchRequest(
                tenant_id=UUID(self.tenant_id),
                project_id=project["id"],
                max_matches=10,
                min_score=0.0,  # 设为0以获取所有结果
                executed_by=None,
                matching_type="project_to_engineers",
                trigger_type="test",
                weights={},
                filters={},
            )

            print(f"📋 开始匹配...")
            result = await matching_service.match_project_to_engineers(request)

            print(f"✅ 匹配完成!")
            print(f"   总匹配数: {result.total_matches}")
            print(f"   高质量匹配: {result.high_quality_matches}")
            print(f"   处理时间: {result.processing_time_seconds}秒")

            if result.matches:
                print(f"\n📈 匹配结果 (前5名):")
                for i, match in enumerate(result.matches[:5], 1):
                    print(f"   {i}. {match.engineer_name}: {match.match_score:.6f}")
            else:
                print(f"\n❌ 没有匹配结果")

        except Exception as e:
            print(f"❌ API测试失败: {str(e)}")
            import traceback

            print(f"详细错误:\n{traceback.format_exc()}")

    async def generate_fix_recommendations(self):
        """生成修复建议"""
        print("\n💡 6. 修复建议")
        print("=" * 60)

        recommendations = [
            "1. 检查embedding生成脚本是否正确运行",
            "2. 确认不同项目/工程师的paraphrase文本是否真的不同",
            "3. 重新生成embedding数据：python generate_embeddings.py --force",
            "4. 检查pgvector扩展是否正确安装和配置",
            "5. 降低min_score阈值到0.0进行测试",
            "6. 检查数据库中的vector数据类型是否正确",
        ]

        for rec in recommendations:
            print(f"   {rec}")

        print(f"\n🔧 快速修复命令:")
        print(f"   # 重新生成所有embedding")
        print(f"   python generate_embeddings.py --type both --force")
        print(f"   ")
        print(f"   # 测试相似度计算")
        print(f"   python fix_similarity_calculation.py")
        print(f"   ")
        print(f"   # 运行API测试")
        print(f"   python test_ai_matching.py")

    async def run_complete_diagnosis(self):
        """运行完整诊断"""
        print("🔧 AI匹配问题全面诊断")
        print("=" * 80)

        try:
            # 1. 检查embedding数据格式
            format_ok = await self.check_embedding_data_format()

            if format_ok:
                # 2. 测试数据库查询
                await self.test_database_similarity_queries()

                # 3. 测试匹配服务查询
                await self.test_matching_service_query()

            # 4. 检查数据一致性
            await self.check_data_consistency()

            # 5. 测试API调用
            await self.check_ai_matching_api_call()

            # 6. 生成修复建议
            await self.generate_fix_recommendations()

        except Exception as e:
            print(f"❌ 诊断过程出错: {str(e)}")
            import traceback

            print(f"详细错误:\n{traceback.format_exc()}")

        print("\n" + "=" * 80)
        print("🎉 诊断完成！请查看上面的结果和建议")


async def main():
    """主函数"""
    debugger = AIMatchingDebugger()
    await debugger.run_complete_diagnosis()


if __name__ == "__main__":
    asyncio.run(main())
