#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深度调试 arrival_year_japan 和 experience 提取失败的问题
"""

import asyncio
import sys
import traceback
import pandas as pd
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))


async def deep_debug():
    """深度调试提取器问题"""

    print("=== 深度调试 AiMatchingSendMail 提取器 ===\n")

    # 1. 首先验证导入是否正常
    print("1️⃣ 验证导入状态")
    print("-" * 50)

    try:
        from app.base.constants import KEYWORDS

        print("✅ 成功导入 KEYWORDS")

        # 检查 KEYWORDS 内容
        if isinstance(KEYWORDS, dict):
            print(f"   KEYWORDS 是字典，包含 {len(KEYWORDS)} 个类别")

            # 重点检查 arrival 和 experience 关键词
            arrival_keywords = KEYWORDS.get("arrival", [])
            experience_keywords = KEYWORDS.get("experience", [])

            print(f"\n   📍 arrival 关键词 ({len(arrival_keywords)}个):")
            for kw in arrival_keywords[:5]:  # 显示前5个
                print(f"      - '{kw}'")
            if len(arrival_keywords) > 5:
                print(f"      ... 还有 {len(arrival_keywords) - 5} 个")

            print(f"\n   📍 experience 关键词 ({len(experience_keywords)}个):")
            for kw in experience_keywords[:5]:  # 显示前5个
                print(f"      - '{kw}'")
            if len(experience_keywords) > 5:
                print(f"      ... 还有 {len(experience_keywords) - 5} 个")
        else:
            print(f"❌ KEYWORDS 不是字典类型: {type(KEYWORDS)}")

    except ImportError as e:
        print(f"❌ 导入 KEYWORDS 失败: {e}")
        return

    # 2. 导入并初始化服务
    print("\n2️⃣ 初始化简历解析服务")
    print("-" * 50)

    try:
        from app.services.resume_parser_service import ResumeParserService

        parser = ResumeParserService()
        print("✅ 解析服务初始化成功")

        # 检查提取器是否正确初始化
        print("\n   检查提取器状态:")
        print(
            f"   - arrival_year_extractor: {parser.arrival_year_extractor.__class__.__name__}"
        )
        print(
            f"   - experience_extractor: {parser.experience_extractor.__class__.__name__}"
        )

    except Exception as e:
        print(f"❌ 初始化服务失败: {e}")
        traceback.print_exc()
        return

    # 3. 创建测试数据
    print("\n3️⃣ 创建测试数据")
    print("-" * 50)

    # 创建包含明确的来日年份和经验的测试数据
    test_data = pd.DataFrame(
        {
            "A": ["氏名", "来日", "経験年数", "技術"],
            "B": ["张三", "2016年", "5年", "Java, Python"],
            "C": ["", "来日年", "IT経験", ""],
            "D": ["", "2016", "5年", ""],
        }
    )

    print("测试数据:")
    print(test_data)

    # 模拟解析器的数据格式
    all_data = [{"df": test_data, "sheet_name": "TestSheet"}]

    # 4. 直接测试提取器
    print("\n4️⃣ 直接测试提取器")
    print("-" * 50)

    # 测试 arrival_year_extractor
    print("\n📍 测试 arrival_year_extractor:")
    try:
        # 检查提取器内部是否能访问 KEYWORDS
        extractor = parser.arrival_year_extractor

        # 尝试直接访问提取器使用的关键词
        print("   检查提取器是否能访问关键词...")

        # 手动调用 extract 方法
        result = extractor.extract(all_data, None)
        print(f"   提取结果: {result}")

        if result is None:
            print("   ❌ 提取失败，尝试调试内部逻辑...")

            # 检查是否是 _extract_from_arrival_labels 方法的问题
            if hasattr(extractor, "_extract_from_arrival_labels"):
                print("   提取器有 _extract_from_arrival_labels 方法")

                # 尝试手动检查关键词匹配
                df = test_data
                found_keywords = []
                for idx in range(len(df)):
                    for col in df.columns:
                        cell = df.iloc[idx, col]
                        if pd.notna(cell):
                            cell_str = str(cell)
                            for kw in ["来日", "渡日", "入国"]:  # 使用一些常见关键词
                                if kw in cell_str:
                                    found_keywords.append((idx, col, cell_str, kw))

                if found_keywords:
                    print(f"   找到关键词: {found_keywords}")
                else:
                    print("   未找到任何关键词匹配")

    except Exception as e:
        print(f"   ❌ 测试 arrival_year_extractor 出错: {e}")
        traceback.print_exc()

    # 测试 experience_extractor
    print("\n📍 测试 experience_extractor:")
    try:
        extractor = parser.experience_extractor
        result = extractor.extract(all_data)
        print(f"   提取结果: {result}")

        if result is None:
            print("   ❌ 提取失败，检查关键词匹配...")

            # 手动检查经验关键词
            df = test_data
            found_keywords = []
            for idx in range(len(df)):
                for col in df.columns:
                    cell = df.iloc[idx, col]
                    if pd.notna(cell):
                        cell_str = str(cell)
                        for kw in ["経験年数", "IT経験", "実務経験"]:
                            if kw in cell_str:
                                found_keywords.append((idx, col, cell_str, kw))

            if found_keywords:
                print(f"   找到关键词: {found_keywords}")
            else:
                print("   未找到任何关键词匹配")

    except Exception as e:
        print(f"   ❌ 测试 experience_extractor 出错: {e}")
        traceback.print_exc()

    # 5. 测试完整的解析流程
    print("\n5️⃣ 测试完整解析流程")
    print("-" * 50)

    # 保存测试文件
    test_file = "test_resume_debug.xlsx"
    test_data.to_excel(test_file, index=False)
    print(f"已创建测试文件: {test_file}")

    try:
        # 使用 parse_excel 方法
        result = await parser.parse_excel(test_file)
        print("\n解析结果:")
        for key, value in result.items():
            print(f"   {key}: {value}")

        # 清理测试文件
        import os

        os.remove(test_file)

    except Exception as e:
        print(f"❌ 完整解析测试失败: {e}")
        traceback.print_exc()

    # 6. 检查提取器源代码
    print("\n6️⃣ 检查提取器源代码中的导入")
    print("-" * 50)

    extractors_to_check = [
        "app/services/extractors/arrival_year_extractor.py",
        "app/services/extractors/experience_extractor.py",
    ]

    for file_path in extractors_to_check:
        if Path(file_path).exists():
            print(f"\n📄 {file_path}:")
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()[:20]  # 只看前20行

            for i, line in enumerate(lines):
                if "import" in line and ("KEYWORDS" in line or "constants" in line):
                    print(f"   行{i+1}: {line.strip()}")

    # 7. 提供修复建议
    print("\n7️⃣ 可能的问题和解决方案")
    print("-" * 50)

    print(
        """
可能的原因：
1. KEYWORDS 没有被正确导入到提取器中
2. 提取器内部逻辑有问题
3. Excel 数据格式与预期不符

建议的解决步骤：
1. 确认所有提取器文件的导入路径都已更新为:
   from app.base.constants import KEYWORDS
   from app.base.base_extractor import BaseExtractor

2. 在提取器的 extract 方法开头添加调试代码：
   print(f"KEYWORDS available: {'arrival' in KEYWORDS}")
   print(f"Arrival keywords: {KEYWORDS.get('arrival', [])[:3]}")

3. 检查实际的 Excel 文件格式，确保关键词能被识别

4. 如果还是不行，可能需要在提取器内部直接定义关键词作为临时解决方案
"""
    )


if __name__ == "__main__":
    asyncio.run(deep_debug())
