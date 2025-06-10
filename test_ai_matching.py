#!/usr/bin/env python3
# test_ai_matching_fixed.py - 修复版AI匹配测试脚本
import asyncio
import requests
import json
import logging
import time
from uuid import UUID
from typing import Dict, Any, List

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AIMatchingTester:
    """AI匹配功能测试器 - 修复版"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_prefix = "/api/v1"
        self.test_tenant_id = "33723dd6-cf28-4dab-975c-f883f5389d04"

    def safe_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """安全的HTTP请求包装器"""
        try:
            response = requests.request(method, url, timeout=30, **kwargs)

            # 检查内容类型
            content_type = response.headers.get("content-type", "")

            if response.status_code >= 400:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": f"HTTP {response.status_code}",
                    "content": (
                        response.text[:200] + "..."
                        if len(response.text) > 200
                        else response.text
                    ),
                }

            # 尝试解析JSON
            if "application/json" in content_type:
                try:
                    data = response.json()
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "data": data,
                    }
                except json.JSONDecodeError as e:
                    return {
                        "success": False,
                        "error": f"JSON解析失败: {str(e)}",
                        "content": response.text[:200] + "...",
                    }
            else:
                return {
                    "success": False,
                    "error": f"非JSON响应，内容类型: {content_type}",
                    "content": response.text[:200] + "...",
                }

        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"请求异常: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"未知错误: {str(e)}"}

    async def check_prerequisites(self) -> Dict[str, Any]:
        """检查测试前提条件"""
        logger.info("🔍 检查测试前提条件")

        results = {
            "api_accessible": False,
            "has_test_data": False,
            "has_embeddings": False,
            "project_count": 0,
            "engineer_count": 0,
            "projects_with_embedding": 0,
            "engineers_with_embedding": 0,
        }

        # 1. 检查API可访问性
        health_result = self.safe_request("GET", f"{self.base_url}/health")
        if health_result["success"]:
            results["api_accessible"] = True
            print("✅ API服务运行正常")
        else:
            print(f"❌ API服务异常: {health_result.get('error', 'unknown')}")
            return results

        # 2. 检查测试数据
        try:
            from app.database import fetch_val

            # 检查项目数据
            project_count = await fetch_val(
                "SELECT COUNT(*) FROM projects WHERE tenant_id = $1 AND is_active = true",
                self.test_tenant_id,
            )

            engineer_count = await fetch_val(
                "SELECT COUNT(*) FROM engineers WHERE tenant_id = $1 AND is_active = true",
                self.test_tenant_id,
            )

            # 检查embedding数据
            projects_with_embedding = await fetch_val(
                "SELECT COUNT(*) FROM projects WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL",
                self.test_tenant_id,
            )

            engineers_with_embedding = await fetch_val(
                "SELECT COUNT(*) FROM engineers WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL",
                self.test_tenant_id,
            )

            results.update(
                {
                    "project_count": project_count,
                    "engineer_count": engineer_count,
                    "projects_with_embedding": projects_with_embedding,
                    "engineers_with_embedding": engineers_with_embedding,
                    "has_test_data": project_count > 0 and engineer_count > 0,
                    "has_embeddings": projects_with_embedding > 0
                    and engineers_with_embedding > 0,
                }
            )

            if results["has_test_data"]:
                print(f"✅ 测试数据充足: 项目{project_count}个, 简历{engineer_count}个")
            else:
                print("❌ 缺少测试数据")

            if results["has_embeddings"]:
                print(
                    f"✅ Embedding数据完整: 项目{projects_with_embedding}个, 简历{engineers_with_embedding}个"
                )
                print(
                    f"📊 开始测试: {projects_with_embedding}个项目, {engineers_with_embedding}个简历"
                )
            else:
                print("❌ 缺少Embedding数据，请先运行 generate_embeddings.py")

        except Exception as e:
            print(f"❌ 数据检查失败: {str(e)}")

        return results

    def test_system_apis(self) -> Dict[str, Any]:
        """测试系统API"""
        logger.info("🔧 测试系统API")
        print("=" * 60)

        results = {}

        # 1. 测试系统信息
        info_result = self.safe_request(
            "GET", f"{self.base_url}{self.api_prefix}/ai-matching/system/info"
        )
        if info_result["success"]:
            data = info_result["data"]
            print(
                f"✅ 系统信息: {data.get('service', 'unknown')} v{data.get('version', 'unknown')}"
            )
            if "model" in data:
                model_status = data["model"].get("status", "unknown")
                model_name = data["model"].get("name", "unknown")
                print(f"   模型: {model_name} ({model_status})")
            results["system_info"] = True
        else:
            print(f"❌ 系统信息API失败: {info_result.get('error', 'unknown')}")
            results["system_info"] = False

        # 2. 测试健康检查
        health_result = self.safe_request(
            "GET", f"{self.base_url}{self.api_prefix}/ai-matching/system/health"
        )
        if health_result["success"]:
            data = health_result["data"]
            status = data.get("status", "unknown")
            print(f"✅ 健康检查: {status}")

            if "checks" in data:
                for check_name, check_info in data["checks"].items():
                    if isinstance(check_info, dict):
                        check_status = check_info.get("status", "unknown")
                        print(f"   ✅ {check_name}: {check_status}")
                    else:
                        print(f"   ✅ {check_name}: {check_info}")
            results["health_check"] = True
        else:
            print(f"❌ 健康检查API失败: {health_result.get('error', 'unknown')}")
            results["health_check"] = False

        return results

    async def test_project_to_engineers(self) -> Dict[str, Any]:
        """测试案件匹配简历"""
        logger.info("🎯 测试1: 案件匹配简历")

        try:
            # 获取测试项目
            from app.database import fetch_one

            project = await fetch_one(
                """
                SELECT * FROM projects 
                WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
                ORDER BY created_at DESC LIMIT 1
                """,
                self.test_tenant_id,
            )

            if not project:
                return {"success": False, "error": "没有可用的测试项目"}

            # 构建请求
            request_data = {
                "tenant_id": self.test_tenant_id,
                "project_id": str(project["id"]),
                "max_matches": 20,
                "min_score": 0.01,
                "executed_by": None,
                "matching_type": "project_to_engineers",
                "trigger_type": "test",
                "weights": {
                    "skill_match": 0.3,
                    "experience_match": 0.25,
                    "japanese_level_match": 0.2,
                    "location_match": 0.01,
                },
                "filters": {},
            }

            print(f"🎯 测试项目: {project['title']}")
            print(f"   项目ID: {project['id']}")

            # 发送请求
            result = self.safe_request(
                "POST",
                f"{self.base_url}{self.api_prefix}/ai-matching/project-to-engineers",
                headers={"Content-Type": "application/json"},
                data=json.dumps(request_data),
            )

            if result["success"]:
                data = result["data"]
                total_matches = data.get("total_matches", 0)
                high_quality = data.get("high_quality_matches", 0)
                processing_time = data.get("processing_time_seconds", 0)

                print(f"✅ 匹配成功!")
                print(f"   总匹配数: {total_matches}")
                print(f"   高质量匹配: {high_quality}")
                print(f"   处理时间: {processing_time}秒")

                if "matches" in data and data["matches"]:
                    print("   前3个匹配:")
                    for i, match in enumerate(data["matches"][:3], 1):
                        score = match.get("match_score", 0)
                        name = match.get("engineer_name", "未知")
                        print(f"   {i}. {name} (分数: {score:.3f})")

                return {
                    "success": True,
                    "matches": total_matches,
                    "processing_time": processing_time,
                }
            else:
                print(f"❌ 匹配失败: {result.get('error', 'unknown')}")
                return {"success": False, "error": result.get("error", "unknown")}

        except Exception as e:
            error_msg = f"测试执行异常: {str(e)}"
            print(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}

    async def test_engineer_to_projects(self) -> Dict[str, Any]:
        """测试简历匹配案件"""
        logger.info("🎯 测试2: 简历匹配案件")

        try:
            # 获取测试简历
            from app.database import fetch_one

            engineer = await fetch_one(
                """
                SELECT * FROM engineers 
                WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
                ORDER BY created_at DESC LIMIT 1
                """,
                self.test_tenant_id,
            )

            if not engineer:
                return {"success": False, "error": "没有可用的测试简历"}

            # 构建请求
            request_data = {
                "tenant_id": self.test_tenant_id,
                "engineer_id": str(engineer["id"]),
                "max_matches": 20,
                "min_score": 0.01,
                "executed_by": None,
                "matching_type": "engineer_to_projects",
                "trigger_type": "test",
                "weights": {
                    "skill_match": 0.35,
                    "experience_match": 0.3,
                    "budget_match": 0.2,
                    "location_match": 0.01,
                },
                "filters": {},
            }

            print(f"🎯 测试简历: {engineer['name']}")
            print(f"   简历ID: {engineer['id']}")

            # 发送请求
            result = self.safe_request(
                "POST",
                f"{self.base_url}{self.api_prefix}/ai-matching/engineer-to-projects",
                headers={"Content-Type": "application/json"},
                data=json.dumps(request_data),
            )

            if result["success"]:
                data = result["data"]
                total_matches = data.get("total_matches", 0)
                high_quality = data.get("high_quality_matches", 0)
                processing_time = data.get("processing_time_seconds", 0)

                print(f"✅ 匹配成功!")
                print(f"   总匹配数: {total_matches}")
                print(f"   高质量匹配: {high_quality}")
                print(f"   处理时间: {processing_time}秒")

                if "matches" in data and data["matches"]:
                    print("   前3个匹配:")
                    for i, match in enumerate(data["matches"][:3], 1):
                        score = match.get("match_score", 0)
                        title = match.get("project_title", "未知项目")
                        print(f"   {i}. {title} (分数: {score:.3f})")

                return {
                    "success": True,
                    "matches": total_matches,
                    "processing_time": processing_time,
                }
            else:
                print(f"❌ 匹配失败: {result.get('error', 'unknown')}")
                return {"success": False, "error": result.get("error", "unknown")}

        except Exception as e:
            error_msg = f"测试执行异常: {str(e)}"
            print(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}

    async def test_bulk_matching(self) -> Dict[str, Any]:
        """测试批量匹配"""
        logger.info("🎯 测试3: 批量匹配")

        try:
            # 构建批量匹配请求
            request_data = {
                "tenant_id": self.test_tenant_id,
                "project_ids": None,  # 匹配所有项目
                "engineer_ids": None,  # 匹配所有简历
                "max_matches": 3,
                "min_score": 0.6,
                "batch_size": 20,
                "generate_top_matches_only": True,
                "executed_by": None,
                "matching_type": "bulk_matching",
                "trigger_type": "test",
                "filters": {},
            }

            print("🎯 执行批量匹配 (高质量匹配)")

            # 发送请求
            result = self.safe_request(
                "POST",
                f"{self.base_url}{self.api_prefix}/ai-matching/bulk-matching",
                headers={"Content-Type": "application/json"},
                data=json.dumps(request_data),
            )

            if result["success"]:
                data = result["data"]
                total_matches = data.get("total_matches", 0)
                high_quality = data.get("high_quality_matches", 0)
                processing_time = data.get("processing_time_seconds", 0)

                print(f"✅ 批量匹配成功!")
                print(f"   总匹配数: {total_matches}")
                print(f"   高质量匹配: {high_quality}")
                print(f"   处理时间: {processing_time}秒")

                if "batch_summary" in data:
                    summary = data["batch_summary"]
                    print(f"   处理项目数: {summary.get('total_projects', 0)}")
                    print(f"   处理简历数: {summary.get('total_engineers', 0)}")
                    print(f"   平均分数: {summary.get('average_match_score', 0):.3f}")

                return {
                    "success": True,
                    "matches": total_matches,
                    "processing_time": processing_time,
                }
            else:
                print(f"❌ 批量匹配失败: {result.get('error', 'unknown')}")
                return {"success": False, "error": result.get("error", "unknown")}

        except Exception as e:
            error_msg = f"测试执行异常: {str(e)}"
            print(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}

    async def test_matching_history(self) -> Dict[str, Any]:
        """测试匹配历史查询"""
        logger.info("📚 测试4: 匹配历史查询")

        # 获取匹配历史
        result = self.safe_request(
            "GET",
            f"{self.base_url}{self.api_prefix}/ai-matching/history/{self.test_tenant_id}?limit=5",
        )

        if result["success"]:
            histories = result["data"]
            if isinstance(histories, list):
                print(f"✅ 匹配历史查询成功: 找到{len(histories)}条记录")

                for i, history in enumerate(histories[:3], 1):
                    match_type = history.get("matching_type", "unknown")
                    status = history.get("execution_status", "unknown")
                    matches = history.get("total_matches_generated", 0)
                    print(f"   {i}. {match_type} - {status} ({matches}个匹配)")

                return {"success": True, "history_count": len(histories)}
            else:
                print(f"❌ 返回数据格式异常: {type(histories)}")
                return {"success": False, "error": "数据格式错误"}
        else:
            print(f"❌ 匹配历史查询失败: {result.get('error', 'unknown')}")
            return {"success": False, "error": result.get("error", "unknown")}

    async def run_complete_test(self):
        """运行完整测试"""
        print("🧪 AI匹配功能完整测试")
        print("=" * 80)

        test_results = {
            "prerequisites": None,
            "system_apis": None,
            "project_to_engineers": None,
            "engineer_to_projects": None,
            "bulk_matching": None,
            "matching_history": None,
        }

        start_time = time.time()

        try:
            # 1. 检查前提条件
            prerequisites = await self.check_prerequisites()
            test_results["prerequisites"] = prerequisites

            if not prerequisites.get("api_accessible"):
                print("❌ API服务不可访问，停止测试")
                return test_results

            if not prerequisites.get("has_embeddings"):
                print("❌ 缺少Embedding数据，请先运行 generate_embeddings.py")
                return test_results

            # 2. 测试系统API
            system_apis = self.test_system_apis()
            test_results["system_apis"] = system_apis

            # 3. 测试案件匹配简历
            project_to_engineers = await self.test_project_to_engineers()
            test_results["project_to_engineers"] = project_to_engineers

            # 4. 测试简历匹配案件
            engineer_to_projects = await self.test_engineer_to_projects()
            test_results["engineer_to_projects"] = engineer_to_projects

            # 5. 测试批量匹配
            bulk_matching = await self.test_bulk_matching()
            test_results["bulk_matching"] = bulk_matching

            # 6. 测试匹配历史
            matching_history = await self.test_matching_history()
            test_results["matching_history"] = matching_history

        except Exception as e:
            print(f"❌ 测试执行异常: {str(e)}")
            import traceback

            print(f"详细错误信息:\n{traceback.format_exc()}")

        # 生成测试报告
        self.generate_test_report(test_results, time.time() - start_time)

        return test_results

    def generate_test_report(self, results: Dict[str, Any], total_time: float):
        """生成测试报告"""
        print("\n" + "=" * 80)
        print("📊 AI匹配功能测试报告")
        print("=" * 80)

        # 统计成功/失败
        tests = [
            (
                "前提条件检查",
                results["prerequisites"],
                ["api_accessible", "has_test_data", "has_embeddings"],
            ),
            ("系统API测试", results["system_apis"], ["system_info", "health_check"]),
            ("案件匹配简历", results["project_to_engineers"], ["success"]),
            ("简历匹配案件", results["engineer_to_projects"], ["success"]),
            ("批量匹配", results["bulk_matching"], ["success"]),
            ("匹配历史查询", results["matching_history"], ["success"]),
        ]

        passed = 0
        total = 0

        for test_name, test_result, check_keys in tests:
            if test_result:
                if isinstance(test_result, dict):
                    if len(check_keys) == 1 and check_keys[0] == "success":
                        # 简单成功检查
                        test_passed = test_result.get("success", False)
                    else:
                        # 多项检查
                        test_passed = all(
                            test_result.get(key, False) for key in check_keys
                        )
                else:
                    test_passed = bool(test_result)
            else:
                test_passed = False

            status = "✅ 通过" if test_passed else "❌ 失败"
            print(f"{test_name:.<30} {status}")

            if test_passed:
                passed += 1
            total += 1

        print(f"\n🎯 测试结果: {passed}/{total} 通过")
        print(f"⏱️ 总耗时: {total_time:.2f} 秒")

        # 详细信息
        if results.get("prerequisites"):
            prereq = results["prerequisites"]
            print(f"\n📊 数据统计:")
            print(f"   项目总数: {prereq.get('project_count', 0)}")
            print(f"   简历总数: {prereq.get('engineer_count', 0)}")
            print(f"   有Embedding的项目: {prereq.get('projects_with_embedding', 0)}")
            print(f"   有Embedding的简历: {prereq.get('engineers_with_embedding', 0)}")

        # 性能信息
        performance_tests = [
            ("案件匹配简历", results["project_to_engineers"]),
            ("简历匹配案件", results["engineer_to_projects"]),
            ("批量匹配", results["bulk_matching"]),
        ]

        print(f"\n⚡ 性能指标:")
        for test_name, test_result in performance_tests:
            if test_result and test_result.get("success"):
                processing_time = test_result.get("processing_time", 0)
                matches = test_result.get("matches", 0)
                print(f"   {test_name}: {processing_time:.2f}秒 ({matches}个匹配)")

        # 总结
        if passed == total:
            print("\n🎉 所有测试通过！AI匹配功能工作正常")
        else:
            print(f"\n⚠️ {total - passed}个测试失败，请检查相关功能")

        print("=" * 80)


async def main():
    """主函数"""
    tester = AIMatchingTester()
    await tester.run_complete_test()


if __name__ == "__main__":
    asyncio.run(main())
