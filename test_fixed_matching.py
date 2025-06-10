#!/usr/bin/env python3
# test_fixed_matching.py - 测试修复后的AI匹配API
import asyncio
import requests
import json
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FixedMatchingTester:
    """测试修复后的AI匹配功能"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_prefix = "/api/v1"
        self.test_tenant_id = "33723dd6-cf28-4dab-975c-f883f5389d04"

    def safe_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """安全的HTTP请求"""
        try:
            response = requests.request(method, url, timeout=30, **kwargs)

            if response.status_code >= 400:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text[:200],
                }

            return {
                "success": True,
                "status_code": response.status_code,
                "data": response.json(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_test_data(self):
        """获取测试数据"""
        try:
            from app.database import fetch_one

            # 获取测试项目
            project = await fetch_one(
                """
                SELECT * FROM projects 
                WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
                ORDER BY created_at DESC LIMIT 1
                """,
                self.test_tenant_id,
            )

            # 获取测试简历
            engineer = await fetch_one(
                """
                SELECT * FROM engineers 
                WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
                ORDER BY created_at DESC LIMIT 1
                """,
                self.test_tenant_id,
            )

            return project, engineer

        except Exception as e:
            logger.error(f"获取测试数据失败: {str(e)}")
            return None, None

    async def test_project_to_engineers_api(self):
        """测试案件匹配简历API"""
        print("\n🎯 测试1: 案件匹配简历API")
        print("=" * 60)

        project, _ = await self.get_test_data()
        if not project:
            print("❌ 没有可用的测试项目")
            return

        # 构建API请求
        request_data = {
            "tenant_id": self.test_tenant_id,
            "project_id": str(project["id"]),
            "max_matches": 10,
            "min_score": 0.0,  # 设为0以获取所有匹配
            "executed_by": None,
            "matching_type": "project_to_engineers",
            "trigger_type": "manual",  # 使用标准值
            "weights": {
                "skill_match": 1,
                "experience_match": 0,
                "japanese_level_match": 0,
            },
            "filters": {},
        }

        print(f"📋 测试项目: {project['title']}")
        print(f"📝 项目技能: {project.get('skills', [])}")

        # 调用API
        result = self.safe_request(
            "POST",
            f"{self.base_url}{self.api_prefix}/ai-matching/project-to-engineers",
            headers={"Content-Type": "application/json"},
            data=json.dumps(request_data),
        )

        if result["success"]:
            data = result["data"]
            matches = data.get("matches", [])

            print(f"✅ API调用成功")
            print(f"📊 总匹配数: {data.get('total_matches', 0)}")
            print(f"⭐ 高质量匹配: {data.get('high_quality_matches', 0)}")
            print(f"⏱️ 处理时间: {data.get('processing_time_seconds', 0)}秒")

            if matches:
                print(f"\n📈 匹配结果 (前5名):")
                print("-" * 80)
                for i, match in enumerate(matches[:5], 1):
                    score = match.get("match_score", 0)
                    confidence = match.get("confidence_score", 0)
                    skill_score = match.get("skill_match_score", 0)
                    exp_score = match.get("experience_match_score", 0)
                    jp_score = match.get("japanese_level_match_score", 0)
                    name = match.get("engineer_name", "未知")
                    matched_skills = match.get("matched_skills", [])

                    print(
                        f"{i:2d}. {name:<15} 总分: {score:.3f} 信心: {confidence:.3f}"
                    )
                    print(
                        f"    技能: {skill_score:.3f} 经验: {exp_score:.3f} 日语: {jp_score:.3f}"
                    )
                    print(f"    匹配技能: {matched_skills}")
                    print()

                # 验证分数范围
                all_scores = [m.get("match_score", 0) for m in matches]
                all_confidences = [m.get("confidence_score", 0) for m in matches]

                print(f"🔍 分数验证:")
                print(f"   匹配分数范围: {min(all_scores):.3f} - {max(all_scores):.3f}")
                print(
                    f"   信心分数范围: {min(all_confidences):.3f} - {max(all_confidences):.3f}"
                )

                # 检查是否在正常范围内
                if all(0 <= score <= 1 for score in all_scores):
                    print("   ✅ 匹配分数在正常范围内 (0-1)")
                else:
                    print("   ❌ 匹配分数超出正常范围")

                if all(0 <= conf <= 1 for conf in all_confidences):
                    print("   ✅ 信心分数在正常范围内 (0-1)")
                else:
                    print("   ❌ 信心分数超出正常范围")

            else:
                print("⚠️ 没有找到匹配结果")

        else:
            print(f"❌ API调用失败: {result.get('error', 'unknown')}")

    async def test_engineer_to_projects_api(self):
        """测试简历匹配案件API"""
        print("\n🎯 测试2: 简历匹配案件API")
        print("=" * 60)

        _, engineer = await self.get_test_data()
        if not engineer:
            print("❌ 没有可用的测试简历")
            return

        # 构建API请求
        request_data = {
            "tenant_id": self.test_tenant_id,
            "engineer_id": str(engineer["id"]),
            "max_matches": 10,
            "min_score": 0.0,
            "executed_by": None,
            "matching_type": "engineer_to_projects",
            "trigger_type": "manual",  # 使用标准值
            "weights": {
                "skill_match": 0.5,
                "experience_match": 0.3,
                "japanese_level_match": 0.2,
            },
            "filters": {},
        }

        print(f"👤 测试简历: {engineer['name']}")
        print(f"🔧 简历技能: {engineer.get('skills', [])}")
        print(f"🗾 日语水平: {engineer.get('japanese_level', '未知')}")

        # 调用API
        result = self.safe_request(
            "POST",
            f"{self.base_url}{self.api_prefix}/ai-matching/engineer-to-projects",
            headers={"Content-Type": "application/json"},
            data=json.dumps(request_data),
        )

        if result["success"]:
            data = result["data"]
            matches = data.get("matches", [])

            print(f"✅ API调用成功")
            print(f"📊 总匹配数: {data.get('total_matches', 0)}")
            print(f"⭐ 高质量匹配: {data.get('high_quality_matches', 0)}")

            if matches:
                print(f"\n📈 匹配结果 (前5名):")
                print("-" * 80)
                for i, match in enumerate(matches[:5], 1):
                    score = match.get("match_score", 0)
                    confidence = match.get("confidence_score", 0)
                    skill_score = match.get("skill_match_score", 0)
                    title = match.get("project_title", "未知项目")
                    matched_skills = match.get("matched_skills", [])

                    print(
                        f"{i:2d}. {title:<20} 总分: {score:.3f} 信心: {confidence:.3f}"
                    )
                    print(f"    技能匹配: {skill_score:.3f}")
                    print(f"    匹配技能: {matched_skills}")
                    print()

            else:
                print("⚠️ 没有找到匹配结果")

        else:
            print(f"❌ API调用失败: {result.get('error', 'unknown')}")

    async def test_system_health(self):
        """测试系统健康状态"""
        print("\n🏥 系统健康检查")
        print("=" * 60)

        # 测试AI匹配系统健康
        health_result = self.safe_request(
            "GET", f"{self.base_url}{self.api_prefix}/ai-matching/system/health"
        )

        if health_result["success"]:
            data = health_result["data"]
            status = data.get("status", "unknown")
            print(f"📊 系统状态: {status}")

            checks = data.get("checks", {})
            for check_name, check_info in checks.items():
                if isinstance(check_info, dict):
                    check_status = check_info.get("status", "unknown")
                    print(f"   ✅ {check_name}: {check_status}")
                else:
                    print(f"   ✅ {check_name}: {check_info}")
        else:
            print(f"❌ 健康检查失败: {health_result.get('error', 'unknown')}")

    async def run_all_tests(self):
        """运行所有测试"""
        print("🧪 AI匹配修复验证测试")
        print("=" * 80)
        print("测试修复后的API，验证分数是否在正常范围内 (0-1)")

        try:
            # 1. 系统健康检查
            await self.test_system_health()

            # 2. 测试案件匹配简历
            await self.test_project_to_engineers_api()

            # 3. 测试简历匹配案件
            await self.test_engineer_to_projects_api()

        except Exception as e:
            print(f"❌ 测试执行异常: {str(e)}")
            import traceback

            print(f"详细错误:\n{traceback.format_exc()}")

        print("\n" + "=" * 80)
        print("🎉 测试完成!")
        print("如果看到分数都在0-1范围内，说明修复成功")
        print("=" * 80)


async def main():
    """主函数"""
    tester = FixedMatchingTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
