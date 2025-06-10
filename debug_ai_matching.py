#!/usr/bin/env python3
# debug_ai_matching.py
import asyncio
import requests
import json
from app.config import settings


async def diagnose_ai_matching():
    """诊断AI匹配功能问题"""
    print("🔍 AI匹配功能诊断工具")
    print("=" * 50)

    base_url = "http://localhost:8000"

    # 1. 测试基础API连接
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        print(f"✅ 基础API连接: {response.status_code}")
        print(f"   响应内容类型: {response.headers.get('content-type', 'unknown')}")
    except Exception as e:
        print(f"❌ 基础API连接失败: {str(e)}")
        return

    # 2. 测试AI匹配系统信息API
    try:
        print("\n🧪 测试系统信息API...")
        response = requests.get(
            f"{base_url}/api/v1/ai-matching/system/info", timeout=10
        )
        print(f"   状态码: {response.status_code}")
        print(f"   内容类型: {response.headers.get('content-type', 'unknown')}")
        print(f"   响应长度: {len(response.text)}")

        if response.status_code == 200:
            try:
                data = response.json()
                print(f"✅ JSON解析成功")
                print(f"   服务: {data.get('service', 'unknown')}")
                print(f"   版本: {data.get('version', 'unknown')}")
                if "model" in data:
                    print(f"   模型状态: {data['model'].get('status', 'unknown')}")
            except json.JSONDecodeError as e:
                print(f"❌ JSON解析失败: {str(e)}")
                print(f"   原始响应: {response.text[:200]}...")
        else:
            print(f"❌ API返回错误状态码")
            print(f"   错误响应: {response.text[:200]}...")

    except Exception as e:
        print(f"❌ 系统信息API测试失败: {str(e)}")

    # 3. 测试健康检查API
    try:
        print("\n🏥 测试健康检查API...")
        response = requests.get(
            f"{base_url}/api/v1/ai-matching/system/health", timeout=10
        )
        print(f"   状态码: {response.status_code}")

        if response.status_code in [200, 503]:  # 503也是正常的（服务不可用）
            try:
                data = response.json()
                print(f"✅ JSON解析成功")
                print(f"   状态: {data.get('status', 'unknown')}")
                if "checks" in data:
                    for check_name, check_result in data["checks"].items():
                        print(
                            f"   {check_name}: {check_result.get('status', 'unknown')}"
                        )
            except json.JSONDecodeError as e:
                print(f"❌ JSON解析失败: {str(e)}")
                print(f"   原始响应: {response.text[:200]}...")
        else:
            print(f"❌ 健康检查API异常")
            print(f"   错误响应: {response.text[:200]}...")

    except Exception as e:
        print(f"❌ 健康检查API测试失败: {str(e)}")

    # 4. 检查数据库连接
    try:
        print("\n🗄️ 检查数据库连接...")
        from app.database import check_database_connection

        db_connected = await check_database_connection()
        print(f"   数据库连接: {'✅ 正常' if db_connected else '❌ 失败'}")

        if db_connected:
            # 检查AI匹配相关表
            from app.database import fetch_val

            try:
                count = await fetch_val("SELECT COUNT(*) FROM ai_matching_history")
                print(f"   ai_matching_history表: ✅ 可访问 ({count} 条记录)")
            except Exception as e:
                print(f"   ai_matching_history表: ❌ {str(e)}")

            try:
                count = await fetch_val("SELECT COUNT(*) FROM project_engineer_matches")
                print(f"   project_engineer_matches表: ✅ 可访问 ({count} 条记录)")
            except Exception as e:
                print(f"   project_engineer_matches表: ❌ {str(e)}")

    except Exception as e:
        print(f"❌ 数据库检查失败: {str(e)}")

    # 5. 检查AI模型
    try:
        print("\n🤖 检查AI模型...")
        from app.services.ai_matching_service import AIMatchingService

        ai_service = AIMatchingService()
        print(f"   模型实例: {'✅ 存在' if ai_service.model else '❌ 不存在'}")
        print(f"   模型版本: {ai_service.model_version}")

        if ai_service.model:
            # 测试embedding生成
            test_text = "测试文本"
            embeddings = ai_service.model.encode([test_text])
            print(f"   Embedding生成: ✅ 正常 (维度: {len(embeddings[0])})")
        else:
            print(f"   Embedding生成: ❌ 模型未加载")

    except Exception as e:
        print(f"❌ AI模型检查失败: {str(e)}")
        import traceback

        print(f"   详细错误: {traceback.format_exc()}")


if __name__ == "__main__":
    asyncio.run(diagnose_ai_matching())
