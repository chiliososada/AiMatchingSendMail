#!/usr/bin/env python3
"""
基础结构测试脚本 - 不加载AI模型
测试自动向量生成功能的基础结构
"""

import logging
import sys
from pathlib import Path
from uuid import uuid4

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.embedding_generator_service import embedding_service
from app.services.ai_matching_service import AIMatchingService

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_basic_structure():
    """测试基础结构"""
    logger.info("🧪 测试基础结构...")
    
    try:
        # 测试单例模式
        service1 = embedding_service
        from app.services.embedding_generator_service import embedding_service as service2
        assert service1 is service2, "单例模式失败"
        logger.info("✅ 单例模式正常")
        
        # 测试模型信息（不加载模型）
        model_info = embedding_service.get_model_info()
        logger.info(f"模型信息: {model_info}")
        assert model_info["model_loaded"] is False, "模型不应该被加载"
        logger.info("✅ 延迟加载正常")
        
        # 测试文本生成功能
        project_data = {
            "title": "Python Web开发项目",
            "description": "使用FastAPI开发REST API",
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
            "preferred_skills": ["Docker", "Redis"],
            "experience_required": "3年以上",
            "japanese_level_required": "N3"
        }
        
        project_text = embedding_service.create_project_paraphrase(project_data)
        logger.info(f"项目文本: {project_text}")
        assert "Python Web开发项目" in project_text, "项目文本生成失败"
        logger.info("✅ 项目文本生成正常")
        
        # 测试工程师文本生成
        engineer_data = {
            "name": "张三",
            "skills": ["Python", "Django", "MySQL"],
            "experience": "5年Python开发经验",
            "japanese_level": "N2",
            "current_status": "在职",
            "work_scope": "后端开发",
            "role": "高级开发工程师"
        }
        
        engineer_text = embedding_service.create_engineer_paraphrase(engineer_data)
        logger.info(f"工程师文本: {engineer_text}")
        assert "张三" in engineer_text, "工程师文本生成失败"
        logger.info("✅ 工程师文本生成正常")
        
        # 测试AI匹配服务
        ai_service = AIMatchingService()
        logger.info("✅ AI匹配服务初始化正常")
        
        # 测试批次处理
        test_items = list(range(100))
        batches = ai_service._batch_items(test_items, batch_size=32)
        assert len(batches) == 4, f"批次数量错误: {len(batches)}"
        assert len(batches[0]) == 32, f"第一批数量错误: {len(batches[0])}"
        assert len(batches[-1]) == 4, f"最后一批数量错误: {len(batches[-1])}"
        logger.info("✅ 批次处理正常")
        
        # 测试空数据处理
        empty_batches = ai_service._batch_items([])
        assert len(empty_batches) == 0, "空数据批次处理失败"
        logger.info("✅ 空数据处理正常")
        
        logger.info("🎉 所有基础结构测试通过！")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 基础结构测试失败: {str(e)}")
        import traceback
        logger.error(f"详细错误:\n{traceback.format_exc()}")
        return False


def main():
    """主函数"""
    logger.info("🚀 开始基础结构测试")
    
    success = test_basic_structure()
    
    if success:
        print("\n" + "="*60)
        print("🎯 自动向量生成功能基础结构测试通过！")
        print("="*60)
        print("📝 已验证功能:")
        print("1. ✅ 单例模式实现正确")
        print("2. ✅ 延迟加载机制正常")
        print("3. ✅ 项目文本生成功能")
        print("4. ✅ 工程师文本生成功能")
        print("5. ✅ AI匹配服务初始化")
        print("6. ✅ 批次处理功能")
        print("7. ✅ 边界情况处理")
        print("\n🔧 下一步:")
        print("- 运行完整的API测试（需要数据库）")
        print("- 使用 test_auto_embedding.py 进行完整测试（会下载AI模型）")
        print("- 在真实环境中测试匹配API")
        print("="*60)
    else:
        print("❌ 基础结构测试失败，请检查代码")
        sys.exit(1)


if __name__ == "__main__":
    main()