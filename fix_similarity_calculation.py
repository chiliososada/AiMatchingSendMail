#!/usr/bin/env python3
# fix_similarity_calculation.py - 修复相似度计算问题
import asyncio
import sys
from pathlib import Path
import numpy as np

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.database import fetch_one, fetch_all


async def diagnose_embedding_data():
    """诊断embedding数据问题"""
    print("🔍 诊断embedding数据问题")
    print("=" * 60)

    tenant_id = "33723dd6-cf28-4dab-975c-f883f5389d04"

    # 获取项目和简历的embedding数据
    project = await fetch_one(
        """
        SELECT id, title, ai_match_embedding
        FROM projects 
        WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
        ORDER BY created_at DESC LIMIT 1
        """,
        tenant_id,
    )

    engineers = await fetch_all(
        """
        SELECT id, name, ai_match_embedding
        FROM engineers 
        WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
        ORDER BY created_at DESC LIMIT 3
        """,
        tenant_id,
    )

    if not project or not engineers:
        print("❌ 缺少测试数据")
        return

    print(f"📋 项目: {project['title']}")
    print(f"👥 简历数: {len(engineers)}")

    # 分析embedding数据
    project_emb = project["ai_match_embedding"]
    print(f"\n📊 Embedding数据分析:")
    print(f"项目embedding长度: {len(project_emb)}")
    print(f"项目embedding类型: {type(project_emb)}")
    print(f"项目embedding范围: {min(project_emb):.4f} ~ {max(project_emb):.4f}")
    print(f"项目embedding均值: {np.mean(project_emb):.4f}")

    for i, engineer in enumerate(engineers[:2]):
        eng_emb = engineer["ai_match_embedding"]
        print(f"\n简历{i+1} ({engineer['name']}):")
        print(f"  长度: {len(eng_emb)}")
        print(f"  范围: {min(eng_emb):.4f} ~ {max(eng_emb):.4f}")
        print(f"  均值: {np.mean(eng_emb):.4f}")

        # 手动计算余弦相似度
        cosine_sim = np.dot(project_emb, eng_emb) / (
            np.linalg.norm(project_emb) * np.linalg.norm(eng_emb)
        )
        print(f"  手动计算余弦相似度: {cosine_sim:.4f}")


async def test_pgvector_queries():
    """测试pgvector查询"""
    print("\n🧮 测试pgvector查询")
    print("=" * 60)

    tenant_id = "33723dd6-cf28-4dab-975c-f883f5389d04"

    # 获取测试数据
    project = await fetch_one(
        "SELECT * FROM projects WHERE tenant_id = $1 AND ai_match_embedding IS NOT NULL LIMIT 1",
        tenant_id,
    )

    if not project:
        print("❌ 没有项目数据")
        return

    project_embedding = project["ai_match_embedding"]
    project_id = project["id"]

    print(f"📋 测试项目: {project['title']}")

    # 测试不同的pgvector查询方式
    print(f"\n🧪 测试各种pgvector查询:")

    # 1. 测试余弦距离 (<#>)
    print("1. 余弦距离 (<#>):")
    try:
        results = await fetch_all(
            """
            SELECT id, name, ai_match_embedding <#> $1 as cosine_distance
            FROM engineers 
            WHERE tenant_id = $2 AND ai_match_embedding IS NOT NULL
            ORDER BY cosine_distance ASC
            LIMIT 3
            """,
            project_embedding,
            tenant_id,
        )

        for result in results:
            distance = result["cosine_distance"]
            similarity = 1 - distance  # 转换为相似度
            print(f"   {result['name']}: 距离={distance:.4f}, 相似度={similarity:.4f}")

    except Exception as e:
        print(f"   ❌ 余弦距离查询失败: {str(e)}")

    # 2. 测试余弦相似度 (<=>)
    print("\n2. 余弦相似度 (<=>):")
    try:
        results = await fetch_all(
            """
            SELECT id, name, ai_match_embedding <=> $1 as cosine_similarity  
            FROM engineers 
            WHERE tenant_id = $2 AND ai_match_embedding IS NOT NULL
            ORDER BY cosine_similarity DESC
            LIMIT 3
            """,
            project_embedding,
            tenant_id,
        )

        for result in results:
            similarity = result["cosine_similarity"]
            print(f"   {result['name']}: 相似度={similarity:.4f}")

    except Exception as e:
        print(f"   ❌ 余弦相似度查询失败: {str(e)}")

    # 3. 测试内积 (<#>)
    print("\n3. 内积 (<#>):")
    try:
        results = await fetch_all(
            """
            SELECT id, name, ai_match_embedding <#> $1 as inner_product
            FROM engineers 
            WHERE tenant_id = $2 AND ai_match_embedding IS NOT NULL
            ORDER BY inner_product DESC  
            LIMIT 3
            """,
            project_embedding,
            tenant_id,
        )

        for result in results:
            inner_product = result["inner_product"]
            print(f"   {result['name']}: 内积={inner_product:.4f}")

    except Exception as e:
        print(f"   ❌ 内积查询失败: {str(e)}")


async def test_corrected_similarity():
    """测试修正的相似度计算"""
    print("\n🔧 测试修正的相似度计算")
    print("=" * 60)

    tenant_id = "33723dd6-cf28-4dab-975c-f883f5389d04"

    # 获取测试数据
    project = await fetch_one(
        "SELECT * FROM projects WHERE tenant_id = $1 AND ai_match_embedding IS NOT NULL LIMIT 1",
        tenant_id,
    )

    engineers = await fetch_all(
        "SELECT * FROM engineers WHERE tenant_id = $1 AND ai_match_embedding IS NOT NULL LIMIT 3",
        tenant_id,
    )

    if not project or not engineers:
        print("❌ 缺少测试数据")
        return

    project_embedding = project["ai_match_embedding"]
    engineer_ids = [e["id"] for e in engineers]

    print(f"测试项目: {project['title']}")
    print(f"测试简历数: {len(engineers)}")

    # 使用正确的pgvector查询
    try:
        query = """
        SELECT id, ai_match_embedding <#> $1 as similarity_distance
        FROM engineers
        WHERE id = ANY($2) AND ai_match_embedding IS NOT NULL
        ORDER BY similarity_distance ASC
        """

        similarities = await fetch_all(query, project_embedding, engineer_ids)

        print(f"\n📊 修正后的相似度结果:")
        for similarity in similarities:
            distance = similarity["similarity_distance"]
            # 确保距离在合理范围内
            distance = max(0, min(2, distance))
            # 转换为相似度分数
            similarity_score = 1 - distance
            # 确保相似度在0-1之间
            similarity_score = max(0, min(1, similarity_score))

            # 找到对应的简历名称
            engineer_name = next(
                e["name"] for e in engineers if e["id"] == similarity["id"]
            )

            print(
                f"   {engineer_name}: 距离={distance:.4f}, 相似度={similarity_score:.4f}"
            )

    except Exception as e:
        print(f"❌ 修正查询失败: {str(e)}")


async def main():
    """主函数"""
    print("🔧 相似度计算修复工具")
    print("=" * 80)

    await diagnose_embedding_data()
    await test_pgvector_queries()
    await test_corrected_similarity()

    print("\n" + "=" * 80)
    print("💡 修复建议:")
    print("1. 如果所有相似度都是1.0，可能是embedding数据有问题")
    print("2. 如果pgvector查询失败，需要检查数据库配置")
    print("3. 使用修正后的查询方式确保相似度在0-1范围内")
    print("4. 检查API层面是否有额外的过滤逻辑")


if __name__ == "__main__":
    asyncio.run(main())
