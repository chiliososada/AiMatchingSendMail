#!/usr/bin/env python3
# scripts/test_ai_matching.py
"""
AI匹配功能自动化测试脚本

完整测试三个匹配API的准确性和性能
验证匹配结果的合理性
"""

import asyncio
import aiohttp
import asyncpg
import json
import time
from typing import Dict, List, Any
import logging
from pathlib import Path
import sys

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 测试配置
API_BASE_URL = "http://localhost:8000/api/v1"
AI_MATCHING_URL = f"{API_BASE_URL}/ai-matching"
TEST_TENANT_ID = "33723dd6-cf28-4dab-975c-f883f5389d04"


class AIMatchingTester:
    """AI匹配测试器"""

    def __init__(self):
        self.session = None
        self.test_results = {
            "project_to_engineers": [],
            "engineer_to_projects": [],
            "bulk_matching": [],
            "summary": {},
        }

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_test_data(self):
        """获取测试数据"""
        try:
            conn = await asyncpg.connect(settings.DATABASE_URL)

            # 获取测试项目
            projects = await conn.fetch(
                "SELECT * FROM projects WHERE tenant_id = $1 AND is_active = true",
                TEST_TENANT_ID,
            )

            # 获取测试简历
            engineers = await conn.fetch(
                "SELECT * FROM engineers WHERE tenant_id = $1 AND is_active = true",
                TEST_TENANT_ID,
            )

            await conn.close()

            return [dict(p) for p in projects], [dict(e) for e in engineers]

        except Exception as e:
            logger.error(f"获取测试数据失败: {str(e)}")
            return [], []

    async def test_project_to_engineers(
        self, projects: List[Dict], engineers: List[Dict]
    ):
        """测试案件匹配简历"""
        logger.info("🎯 测试1: 案件匹配简历")
        print("=" * 60)

        for project in projects:
            try:
                print(f"\n📁 测试项目: {project['title']}")
                print(f"   技能要求: {', '.join(project['skills'][:5])}")

                # 调用API
                start_time = time.time()
                url = f"{AI_MATCHING_URL}/project-to-engineers"
                payload = {
                    "tenant_id": TEST_TENANT_ID,
                    "project_id": str(project["id"]),
                    "max_matches": 5,
                    "min_score": 0.5,
                    "matching_type": "auto",
                    "trigger_type": "test",
                }

                async with self.session.post(url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        end_time = time.time()

                        # 分析结果
                        matches = result.get("matches", [])
                        processing_time = end_time - start_time

                        print(
                            f"   ✅ 找到 {len(matches)} 个匹配 (耗时: {processing_time:.2f}秒)"
                        )

                        # 显示前3个匹配
                        for i, match in enumerate(matches[:3], 1):
                            print(
                                f"   {i}. {match['engineer_name']} - 分数: {match['match_score']:.3f}"
                            )
                            if match["matched_skills"]:
                                print(
                                    f"      匹配技能: {', '.join(match['matched_skills'][:3])}"
                                )
                            if match["match_reasons"]:
                                print(f"      匹配原因: {match['match_reasons'][0]}")

                        # 验证匹配合理性
                        validation = self._validate_project_matches(
                            project, matches, engineers
                        )
                        print(f"   📊 匹配质量: {validation['quality']}")

                        # 保存测试结果
                        self.test_results["project_to_engineers"].append(
                            {
                                "project_title": project["title"],
                                "matches_count": len(matches),
                                "top_score": (
                                    matches[0]["match_score"] if matches else 0
                                ),
                                "processing_time": processing_time,
                                "validation": validation,
                            }
                        )

                    else:
                        error_text = await response.text()
                        print(f"   ❌ API调用失败: {response.status} - {error_text}")

            except Exception as e:
                print(f"   ❌ 测试失败: {str(e)}")
                logger.error(f"项目匹配测试失败: {project['title']}, 错误: {str(e)}")

    async def test_engineer_to_projects(
        self, projects: List[Dict], engineers: List[Dict]
    ):
        """测试简历匹配案件"""
        logger.info("👤 测试2: 简历匹配案件")
        print("=" * 60)

        for engineer in engineers:
            try:
                print(f"\n👥 测试简历: {engineer['name']}")
                print(f"   技能: {', '.join(engineer['skills'][:5])}")

                # 调用API
                start_time = time.time()
                url = f"{AI_MATCHING_URL}/engineer-to-projects"
                payload = {
                    "tenant_id": TEST_TENANT_ID,
                    "engineer_id": str(engineer["id"]),
                    "max_matches": 5,
                    "min_score": 0.5,
                    "matching_type": "auto",
                    "trigger_type": "test",
                }

                async with self.session.post(url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        end_time = time.time()

                        # 分析结果
                        matches = result.get("matches", [])
                        processing_time = end_time - start_time

                        print(
                            f"   ✅ 找到 {len(matches)} 个匹配 (耗时: {processing_time:.2f}秒)"
                        )

                        # 显示前3个匹配
                        for i, match in enumerate(matches[:3], 1):
                            print(
                                f"   {i}. {match['project_title']} - 分数: {match['match_score']:.3f}"
                            )
                            if match["matched_skills"]:
                                print(
                                    f"      匹配技能: {', '.join(match['matched_skills'][:3])}"
                                )
                            if match["match_reasons"]:
                                print(f"      匹配原因: {match['match_reasons'][0]}")

                        # 验证匹配合理性
                        validation = self._validate_engineer_matches(
                            engineer, matches, projects
                        )
                        print(f"   📊 匹配质量: {validation['quality']}")

                        # 保存测试结果
                        self.test_results["engineer_to_projects"].append(
                            {
                                "engineer_name": engineer["name"],
                                "matches_count": len(matches),
                                "top_score": (
                                    matches[0]["match_score"] if matches else 0
                                ),
                                "processing_time": processing_time,
                                "validation": validation,
                            }
                        )

                    else:
                        error_text = await response.text()
                        print(f"   ❌ API调用失败: {response.status} - {error_text}")

            except Exception as e:
                print(f"   ❌ 测试失败: {str(e)}")
                logger.error(f"简历匹配测试失败: {engineer['name']}, 错误: {str(e)}")

    async def test_bulk_matching(self, projects: List[Dict], engineers: List[Dict]):
        """测试批量匹配"""
        logger.info("🔄 测试3: 批量匹配")
        print("=" * 60)

        try:
            print(
                f"\n🔄 批量匹配测试: {len(projects)} 个项目 × {len(engineers)} 个简历"
            )

            # 调用API
            start_time = time.time()
            url = f"{AI_MATCHING_URL}/bulk-matching"
            payload = {
                "tenant_id": TEST_TENANT_ID,
                "max_matches": 3,
                "min_score": 0.5,
                "batch_size": 20,
                "generate_top_matches_only": True,
                "matching_type": "bulk_matching",
                "trigger_type": "test",
            }

            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    end_time = time.time()

                    # 分析结果
                    total_matches = result.get("total_matches", 0)
                    high_quality_matches = result.get("high_quality_matches", 0)
                    processing_time = end_time - start_time
                    batch_summary = result.get("batch_summary", {})

                    print(f"   ✅ 批量匹配完成 (耗时: {processing_time:.2f}秒)")
                    print(f"   📊 总匹配数: {total_matches}")
                    print(f"   🌟 高质量匹配: {high_quality_matches}")
                    print(
                        f"   📈 平均分数: {batch_summary.get('average_match_score', 0):.3f}"
                    )
                    print(
                        f"   🎯 成功率: {batch_summary.get('match_success_rate', 0):.1%}"
                    )

                    # 显示部分匹配结果
                    matches = result.get("matches", [])
                    print(f"\n   📋 部分匹配结果:")
                    for i, match in enumerate(matches[:5], 1):
                        print(
                            f"   {i}. {match['project_title']} ↔ {match['engineer_name']}"
                        )
                        print(f"      分数: {match['match_score']:.3f}")

                    # 验证批量匹配合理性
                    validation = self._validate_bulk_matches(
                        matches, projects, engineers
                    )
                    print(f"   📊 整体匹配质量: {validation['quality']}")

                    # 保存测试结果
                    self.test_results["bulk_matching"] = {
                        "total_matches": total_matches,
                        "high_quality_matches": high_quality_matches,
                        "processing_time": processing_time,
                        "average_score": batch_summary.get("average_match_score", 0),
                        "success_rate": batch_summary.get("match_success_rate", 0),
                        "validation": validation,
                    }

                else:
                    error_text = await response.text()
                    print(f"   ❌ API调用失败: {response.status} - {error_text}")

        except Exception as e:
            print(f"   ❌ 测试失败: {str(e)}")
            logger.error(f"批量匹配测试失败: {str(e)}")

    def _validate_project_matches(
        self, project: Dict, matches: List[Dict], engineers: List[Dict]
    ) -> Dict:
        """验证案件匹配的合理性"""
        if not matches:
            return {"quality": "无匹配", "details": "没有找到匹配的简历"}

        project_skills = set(project.get("skills", []))

        # 检查顶级匹配的技能重合度
        top_match = matches[0]
        engineer = next(
            (e for e in engineers if str(e["id"]) == top_match["engineer_id"]), None
        )

        if engineer:
            engineer_skills = set(engineer.get("skills", []))
            skill_overlap = len(project_skills & engineer_skills)
            total_required = len(project_skills)

            if skill_overlap >= total_required * 0.8:
                quality = "优秀"
            elif skill_overlap >= total_required * 0.6:
                quality = "良好"
            elif skill_overlap >= total_required * 0.4:
                quality = "一般"
            else:
                quality = "较差"

            return {
                "quality": quality,
                "skill_overlap": skill_overlap,
                "total_required": total_required,
                "overlap_rate": (
                    skill_overlap / total_required if total_required > 0 else 0
                ),
                "top_score": top_match["match_score"],
            }

        return {"quality": "无法验证", "details": "找不到对应的简历数据"}

    def _validate_engineer_matches(
        self, engineer: Dict, matches: List[Dict], projects: List[Dict]
    ) -> Dict:
        """验证简历匹配的合理性"""
        if not matches:
            return {"quality": "无匹配", "details": "没有找到匹配的案件"}

        engineer_skills = set(engineer.get("skills", []))

        # 检查顶级匹配的技能重合度
        top_match = matches[0]
        project = next(
            (p for p in projects if str(p["id"]) == top_match["project_id"]), None
        )

        if project:
            project_skills = set(project.get("skills", []))
            skill_overlap = len(engineer_skills & project_skills)
            total_project_skills = len(project_skills)

            if skill_overlap >= total_project_skills * 0.8:
                quality = "优秀"
            elif skill_overlap >= total_project_skills * 0.6:
                quality = "良好"
            elif skill_overlap >= total_project_skills * 0.4:
                quality = "一般"
            else:
                quality = "较差"

            return {
                "quality": quality,
                "skill_overlap": skill_overlap,
                "total_project_skills": total_project_skills,
                "overlap_rate": (
                    skill_overlap / total_project_skills
                    if total_project_skills > 0
                    else 0
                ),
                "top_score": top_match["match_score"],
            }

        return {"quality": "无法验证", "details": "找不到对应的项目数据"}

    def _validate_bulk_matches(
        self, matches: List[Dict], projects: List[Dict], engineers: List[Dict]
    ) -> Dict:
        """验证批量匹配的合理性"""
        if not matches:
            return {"quality": "无匹配", "details": "没有找到任何匹配"}

        # 统计分析
        total_matches = len(matches)
        high_score_matches = len([m for m in matches if m["match_score"] >= 0.8])
        medium_score_matches = len(
            [m for m in matches if 0.6 <= m["match_score"] < 0.8]
        )
        low_score_matches = len([m for m in matches if m["match_score"] < 0.6])

        high_ratio = high_score_matches / total_matches

        if high_ratio >= 0.6:
            quality = "优秀"
        elif high_ratio >= 0.4:
            quality = "良好"
        elif high_ratio >= 0.2:
            quality = "一般"
        else:
            quality = "较差"

        return {
            "quality": quality,
            "total_matches": total_matches,
            "high_score_matches": high_score_matches,
            "medium_score_matches": medium_score_matches,
            "low_score_matches": low_score_matches,
            "high_score_ratio": high_ratio,
            "average_score": sum(m["match_score"] for m in matches) / total_matches,
        }

    async def test_system_apis(self):
        """测试系统API"""
        logger.info("🔧 测试系统API")
        print("=" * 60)

        try:
            # 测试系统信息
            async with self.session.get(f"{AI_MATCHING_URL}/system/info") as response:
                if response.status == 200:
                    info = await response.json()
                    print(f"✅ 系统信息: {info['service']} v{info['version']}")
                    print(
                        f"   模型: {info['model']['name']} ({info['model']['status']})"
                    )
                else:
                    print(f"❌ 系统信息获取失败: {response.status}")

            # 测试健康检查
            async with self.session.get(f"{AI_MATCHING_URL}/system/health") as response:
                health = await response.json()
                print(f"✅ 健康检查: {health['status']}")

                if "checks" in health:
                    for check_name, check_result in health["checks"].items():
                        status_icon = (
                            "✅" if check_result["status"] == "healthy" else "❌"
                        )
                        print(
                            f"   {status_icon} {check_name}: {check_result['status']}"
                        )

            # 测试统计API
            async with self.session.get(
                f"{AI_MATCHING_URL}/statistics/{TEST_TENANT_ID}"
            ) as response:
                if response.status == 200:
                    stats = await response.json()
                    print(f"✅ 统计信息: {stats['total_matching_sessions']} 次匹配会话")
                else:
                    print(f"❌ 统计信息获取失败: {response.status}")

        except Exception as e:
            print(f"❌ 系统API测试失败: {str(e)}")

    def generate_test_report(self):
        """生成测试报告"""
        logger.info("📊 生成测试报告")
        print("\n" + "=" * 80)
        print("📋 AI匹配功能测试报告")
        print("=" * 80)

        # 案件匹配简历测试结果
        project_tests = self.test_results["project_to_engineers"]
        if project_tests:
            print(f"\n🎯 案件匹配简历测试结果:")
            print(f"   测试项目数: {len(project_tests)}")
            avg_matches = sum(t["matches_count"] for t in project_tests) / len(
                project_tests
            )
            avg_score = sum(t["top_score"] for t in project_tests) / len(project_tests)
            avg_time = sum(t["processing_time"] for t in project_tests) / len(
                project_tests
            )

            print(f"   平均匹配数: {avg_matches:.1f}")
            print(f"   平均最高分: {avg_score:.3f}")
            print(f"   平均响应时间: {avg_time:.2f}秒")

            # 质量分析
            quality_counts = {}
            for test in project_tests:
                quality = test["validation"]["quality"]
                quality_counts[quality] = quality_counts.get(quality, 0) + 1

            print(f"   匹配质量分布: {dict(quality_counts)}")

        # 简历匹配案件测试结果
        engineer_tests = self.test_results["engineer_to_projects"]
        if engineer_tests:
            print(f"\n👤 简历匹配案件测试结果:")
            print(f"   测试简历数: {len(engineer_tests)}")
            avg_matches = sum(t["matches_count"] for t in engineer_tests) / len(
                engineer_tests
            )
            avg_score = sum(t["top_score"] for t in engineer_tests) / len(
                engineer_tests
            )
            avg_time = sum(t["processing_time"] for t in engineer_tests) / len(
                engineer_tests
            )

            print(f"   平均匹配数: {avg_matches:.1f}")
            print(f"   平均最高分: {avg_score:.3f}")
            print(f"   平均响应时间: {avg_time:.2f}秒")

        # 批量匹配测试结果
        bulk_test = self.test_results["bulk_matching"]
        if bulk_test:
            print(f"\n🔄 批量匹配测试结果:")
            print(f"   总匹配数: {bulk_test['total_matches']}")
            print(f"   高质量匹配数: {bulk_test['high_quality_matches']}")
            print(f"   平均分数: {bulk_test['average_score']:.3f}")
            print(f"   成功率: {bulk_test['success_rate']:.1%}")
            print(f"   处理时间: {bulk_test['processing_time']:.2f}秒")
            print(f"   整体质量: {bulk_test['validation']['quality']}")

        # 总结
        print(f"\n🎉 测试总结:")
        total_tests = len(project_tests) + len(engineer_tests) + (1 if bulk_test else 0)
        print(f"   完成测试数: {total_tests}")

        if project_tests and engineer_tests:
            overall_avg_score = (
                sum(t["top_score"] for t in project_tests)
                + sum(t["top_score"] for t in engineer_tests)
            ) / (len(project_tests) + len(engineer_tests))
            print(f"   整体平均分数: {overall_avg_score:.3f}")

        print(f"\n💡 建议:")
        if project_tests and engineer_tests:
            if overall_avg_score >= 0.8:
                print("   ✅ 匹配质量优秀，算法工作正常")
            elif overall_avg_score >= 0.6:
                print("   ⚠️ 匹配质量良好，可考虑调整权重优化")
            else:
                print("   ❌ 匹配质量偏低，需要检查数据质量和算法参数")

        print("   📈 可通过增加训练数据和调整匹配权重来进一步优化")
        print("   🔍 建议定期监控匹配质量并根据用户反馈调整")


async def check_prerequisites():
    """检查测试前提条件"""
    logger.info("🔍 检查测试前提条件")

    try:
        # 检查API服务
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{AI_MATCHING_URL}/system/health", timeout=5
                ) as response:
                    if response.status == 200:
                        print("✅ API服务运行正常")
                    else:
                        print(f"❌ API服务状态异常: {response.status}")
                        return False
            except Exception as e:
                print(f"❌ 无法连接API服务: {str(e)}")
                print("请确保服务正在运行: uvicorn app.main:app --reload")
                return False

        # 检查数据库连接
        try:
            conn = await asyncpg.connect(settings.DATABASE_URL)

            # 检查测试数据
            project_count = await conn.fetchval(
                "SELECT COUNT(*) FROM projects WHERE tenant_id = $1", TEST_TENANT_ID
            )
            engineer_count = await conn.fetchval(
                "SELECT COUNT(*) FROM engineers WHERE tenant_id = $1", TEST_TENANT_ID
            )

            await conn.close()

            if project_count == 0 or engineer_count == 0:
                print(f"❌ 测试数据不足: 项目{project_count}个, 简历{engineer_count}个")
                print("请先运行: python scripts/create_test_data.py")
                return False

            print(f"✅ 测试数据充足: 项目{project_count}个, 简历{engineer_count}个")

            # 检查embedding数据
            embedding_count = await asyncpg.connect(settings.DATABASE_URL)
            project_embedding_count = await embedding_count.fetchval(
                "SELECT COUNT(*) FROM projects WHERE tenant_id = $1 AND ai_match_embedding IS NOT NULL",
                TEST_TENANT_ID,
            )
            engineer_embedding_count = await embedding_count.fetchval(
                "SELECT COUNT(*) FROM engineers WHERE tenant_id = $1 AND ai_match_embedding IS NOT NULL",
                TEST_TENANT_ID,
            )
            await embedding_count.close()

            if project_embedding_count == 0 or engineer_embedding_count == 0:
                print(
                    f"❌ Embedding数据缺失: 项目{project_embedding_count}个, 简历{engineer_embedding_count}个"
                )
                print("请先运行: python scripts/generate_embeddings.py --type both")
                return False

            print(
                f"✅ Embedding数据完整: 项目{project_embedding_count}个, 简历{engineer_embedding_count}个"
            )

        except Exception as e:
            print(f"❌ 数据库连接失败: {str(e)}")
            return False

        return True

    except Exception as e:
        logger.error(f"前提条件检查失败: {str(e)}")
        return False


async def main():
    """主测试流程"""
    print("🧪 AI匹配功能自动化测试")
    print("=" * 80)

    # 检查前提条件
    if not await check_prerequisites():
        print("\n❌ 前提条件不满足，测试终止")
        print("\n📝 请按以下顺序执行:")
        print("1. uvicorn app.main:app --reload  # 启动服务")
        print("2. python scripts/create_test_data.py  # 创建测试数据")
        print("3. python scripts/generate_embeddings.py --type both  # 生成embedding")
        print("4. python scripts/test_ai_matching.py  # 运行测试")
        return

    # 开始测试
    start_time = time.time()

    async with AIMatchingTester() as tester:
        # 获取测试数据
        projects, engineers = await tester.get_test_data()

        if not projects or not engineers:
            print("❌ 无法获取测试数据")
            return

        print(f"\n📊 开始测试: {len(projects)}个项目, {len(engineers)}个简历")

        # 执行各项测试
        await tester.test_system_apis()
        await tester.test_project_to_engineers(projects, engineers)
        await tester.test_engineer_to_projects(projects, engineers)
        await tester.test_bulk_matching(projects, engineers)

        # 生成测试报告
        tester.generate_test_report()

    total_time = time.time() - start_time
    print(f"\n⏱️ 测试总耗时: {total_time:.2f}秒")
    print("\n🎉 AI匹配功能测试完成!")


if __name__ == "__main__":
    asyncio.run(main())
