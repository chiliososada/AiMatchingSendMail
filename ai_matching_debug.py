#!/usr/bin/env python3
# debug_matching_api.py - 深度调试匹配API问题
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.database import fetch_one, fetch_all
from app.services.ai_matching_service import AIMatchingService
from app.schemas.ai_matching_schemas import ProjectToEngineersMatchRequest
from uuid import UUID


async def debug_matching_step_by_step():
    """逐步调试匹配过程"""
    print("🔍 深度调试匹配API问题")
    print("=" * 80)

    tenant_id = "33723dd6-cf28-4dab-975c-f883f5389d04"

    try:
        # 1. 获取测试数据
        print("📋 步骤1: 获取测试数据")
        project = await fetch_one(
            """
            SELECT * FROM projects 
            WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
            ORDER BY created_at DESC LIMIT 1
            """,
            tenant_id,
        )

        engineers = await fetch_all(
            """
            SELECT * FROM engineers 
            WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
            ORDER BY created_at DESC
            """,
            tenant_id,
        )

        if not project:
            print("❌ 没有找到测试项目")
            return

        if not engineers:
            print("❌ 没有找到测试简历")
            return

        print(f"✅ 找到项目: {project['title']}")
        print(f"✅ 找到 {len(engineers)} 个简历")

        # 2. 创建AI匹配服务
        print(f"\n🤖 步骤2: 创建AI匹配服务")
        matching_service = AIMatchingService()
        print(f"✅ AI模型加载: {matching_service.model_version}")

        # 3. 测试相似度计算
        print(f"\n📏 步骤3: 测试相似度计算")
        project_embedding = project["ai_match_embedding"]
        print(
            f"项目embedding长度: {len(project_embedding) if project_embedding else 0}"
        )

        similarities = await matching_service._calculate_similarities_batch(
            project_embedding, engineers, "engineers"
        )

        print(f"相似度计算结果: {len(similarities)} 个")
        for i, (engineer, similarity) in enumerate(similarities[:3]):
            print(f"  {i+1}. {engineer['name']}: {similarity:.4f}")

        # 4. 测试详细匹配分数计算
        print(f"\n🧮 步骤4: 测试详细匹配分数")
        if engineers:
            test_engineer = engineers[0]
            detailed_scores = matching_service._calculate_detailed_match_scores(
                project, test_engineer
            )

            print(f"测试简历: {test_engineer['name']}")
            print(f"技能匹配分数: {detailed_scores.get('skill_match', 0):.4f}")
            print(f"经验匹配分数: {detailed_scores.get('experience_match', 0):.4f}")
            print(f"日语匹配分数: {detailed_scores.get('japanese_level_match', 0):.4f}")
            print(f"匹配技能: {detailed_scores.get('matched_skills', [])}")

        # 5. 测试综合分数计算
        print(f"\n⚖️ 步骤5: 测试综合分数计算")
        if similarities:
            engineer, similarity_score = similarities[0]
            detailed_scores = matching_service._calculate_detailed_match_scores(
                project, engineer
            )

            final_score = matching_service._calculate_weighted_score(
                detailed_scores,
                {
                    "skill_match": 0.5,
                    "experience_match": 0.3,
                    "japanese_level_match": 0.2,
                },
                similarity_score,
            )

            print(f"语义相似度: {similarity_score:.4f}")
            print(f"综合分数: {final_score:.4f}")
            print(f"分数是否在0-1范围: {0 <= final_score <= 1}")

        # 6. 调用完整匹配流程
        print(f"\n🎯 步骤6: 调用完整匹配流程")

        # 创建请求对象
        request = ProjectToEngineersMatchRequest(
            tenant_id=UUID(tenant_id),
            project_id=project["id"],
            max_matches=10,
            min_score=0.0,  # 设为0以获取所有结果
            executed_by=None,
            matching_type="project_to_engineers",
            trigger_type="manual",
            weights={
                "skill_match": 0.5,
                "experience_match": 0.3,
                "japanese_level_match": 0.2,
            },
            filters={},
        )

        print("开始完整匹配流程...")

        # 手动调用匹配流程的各个步骤
        print("  - 获取项目信息...")
        project_info = await matching_service._get_project_info(
            request.project_id, request.tenant_id
        )
        print(f"    项目信息: {project_info['title'] if project_info else '未找到'}")

        print("  - 获取候选简历...")
        candidate_engineers = await matching_service._get_candidate_engineers(
            request.tenant_id, request.filters or {}
        )
        print(f"    候选简历数: {len(candidate_engineers)}")

        print("  - 执行匹配计算...")
        matches = await matching_service._calculate_project_engineer_matches(
            project_info,
            candidate_engineers,
            request.weights or {},
            request.max_matches,
            request.min_score,
            UUID("00000000-0000-0000-0000-000000000000"),  # 临时ID
        )

        print(f"    匹配结果数: {len(matches)}")

        if matches:
            print("    前3个匹配:")
            for i, match in enumerate(matches[:3]):
                print(f"    {i+1}. {match.engineer_name}: {match.match_score:.4f}")
        else:
            print("    ❌ 没有找到任何匹配")

            # 详细分析为什么没有匹配
            print("\n🔍 分析无匹配原因:")
            if not candidate_engineers:
                print("    - 没有候选简历")
            else:
                print(f"    - 有 {len(candidate_engineers)} 个候选简历")

                # 检查第一个候选的详细计算
                if candidate_engineers:
                    test_engineer = candidate_engineers[0]
                    print(f"    - 测试简历: {test_engineer['name']}")

                    # 检查embedding
                    if not test_engineer.get("ai_match_embedding"):
                        print("      ❌ 简历缺少embedding")
                    else:
                        print("      ✅ 简历有embedding")

                    # 计算相似度
                    test_similarities = (
                        await matching_service._calculate_similarities_batch(
                            project_info["ai_match_embedding"],
                            [test_engineer],
                            "engineers",
                        )
                    )

                    if test_similarities:
                        _, test_similarity = test_similarities[0]
                        print(f"      语义相似度: {test_similarity:.4f}")

                        # 计算详细分数
                        test_detailed = (
                            matching_service._calculate_detailed_match_scores(
                                project_info, test_engineer
                            )
                        )

                        # 计算最终分数
                        test_final = matching_service._calculate_weighted_score(
                            test_detailed, request.weights or {}, test_similarity
                        )

                        print(f"      最终分数: {test_final:.4f}")
                        print(f"      最小分数要求: {request.min_score}")
                        print(f"      是否通过: {test_final >= request.min_score}")
                    else:
                        print("      ❌ 相似度计算失败")

    except Exception as e:
        print(f"❌ 调试过程出错: {str(e)}")
        import traceback

        print(f"详细错误:\n{traceback.format_exc()}")


async def main():
    await debug_matching_step_by_step()


if __name__ == "__main__":
    asyncio.run(main())
