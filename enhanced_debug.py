# -*- coding: utf-8 -*-
"""
增强版调试脚本 - 深度分析为什么 arrival_year_japan 和 experience 返回 None
"""

import asyncio
import sys
import traceback
import pandas as pd
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

try:
    from app.services.resume_parser_service import ResumeParserService
except ImportError as e:
    print(f"❌ 无法导入ResumeParserService: {e}")
    sys.exit(1)


async def deep_debug_extraction(test_file_path: str):
    """深度调试提取过程"""

    print("=== 深度调试提取过程 ===\n")

    if not Path(test_file_path).exists():
        print(f"❌ 测试文件不存在: {test_file_path}")
        return

    # 初始化服务
    parser = ResumeParserService()

    # 1. 先检查提取器的关键词状态
    print("🔍 检查提取器关键词状态:")

    # 检查 arrival_year_extractor
    arrival_extractor = parser.arrival_year_extractor
    print(f"\n📍 来日年份提取器: {arrival_extractor.__class__.__name__}")

    # 尝试访问关键词
    try:
        # 检查是否有KEYWORDS属性或相关导入
        if hasattr(arrival_extractor, "KEYWORDS"):
            print(f"   ✅ 提取器有 KEYWORDS 属性")
        else:
            print(f"   ❌ 提取器没有 KEYWORDS 属性")

        # 检查模块级别的KEYWORDS
        import inspect

        module = inspect.getmodule(arrival_extractor)
        if hasattr(module, "KEYWORDS"):
            keywords = getattr(module, "KEYWORDS")
            arrival_keywords = keywords.get("arrival", [])
            print(f"   ✅ 模块有 KEYWORDS，arrival关键词: {arrival_keywords[:3]}...")
        else:
            print(f"   ❌ 模块没有 KEYWORDS")

    except Exception as e:
        print(f"   ❌ 检查关键词时出错: {e}")

    # 检查 experience_extractor
    experience_extractor = parser.experience_extractor
    print(f"\n📍 经验提取器: {experience_extractor.__class__.__name__}")

    try:
        module = inspect.getmodule(experience_extractor)
        if hasattr(module, "KEYWORDS"):
            keywords = getattr(module, "KEYWORDS")
            experience_keywords = keywords.get("experience", [])
            print(
                f"   ✅ 模块有 KEYWORDS，experience关键词: {experience_keywords[:3]}..."
            )
        else:
            print(f"   ❌ 模块没有 KEYWORDS")
    except Exception as e:
        print(f"   ❌ 检查关键词时出错: {e}")

    # 2. 加载并分析Excel文件内容
    print(f"\n🔍 分析Excel文件内容: {test_file_path}")

    try:
        # 使用与解析器相同的方法加载数据
        all_data = await asyncio.to_thread(parser._load_excel_data, test_file_path)

        if not all_data:
            print("❌ 无法加载Excel数据")
            return

        print(f"✅ 成功加载 {len(all_data)} 个sheet")

        # 分析每个sheet的内容
        for i, data in enumerate(all_data):
            df = data["df"]
            sheet_name = data.get("sheet_name", f"Sheet{i}")

            print(f"\n📋 Sheet: {sheet_name} ({df.shape[0]}行 x {df.shape[1]}列)")

            # 显示前几行内容
            print("   前5行内容:")
            for row_idx in range(min(5, len(df))):
                row_data = []
                for col_idx in range(min(df.shape[1], 5)):
                    cell_value = df.iloc[row_idx, col_idx]
                    if pd.notna(cell_value):
                        cell_str = str(cell_value)[:20]  # 限制长度
                        row_data.append(f"'{cell_str}'")
                    else:
                        row_data.append("None")
                print(f"     行{row_idx}: {' | '.join(row_data)}")

            # 搜索关键词相关的内容
            print("   🔍 搜索相关关键词:")

            # 来日相关
            arrival_keywords = ["来日", "渡日", "入国", "滞在", "在日"]
            found_arrival = []

            for row_idx in range(len(df)):
                for col_idx in range(len(df.columns)):
                    cell = df.iloc[row_idx, col_idx]
                    if pd.notna(cell):
                        cell_str = str(cell)
                        for keyword in arrival_keywords:
                            if keyword in cell_str:
                                found_arrival.append(
                                    f"行{row_idx}列{col_idx}: '{cell_str}'"
                                )

            if found_arrival:
                print(f"     ✅ 找到来日相关内容 ({len(found_arrival)}个):")
                for item in found_arrival[:3]:  # 只显示前3个
                    print(f"       {item}")
            else:
                print(f"     ❌ 未找到来日相关内容")

            # 经验相关
            experience_keywords = ["経験", "実務", "経歴", "年数", "年"]
            found_experience = []

            for row_idx in range(len(df)):
                for col_idx in range(len(df.columns)):
                    cell = df.iloc[row_idx, col_idx]
                    if pd.notna(cell):
                        cell_str = str(cell)
                        for keyword in experience_keywords:
                            if keyword in cell_str:
                                found_experience.append(
                                    f"行{row_idx}列{col_idx}: '{cell_str}'"
                                )

            if found_experience:
                print(f"     ✅ 找到经验相关内容 ({len(found_experience)}个):")
                for item in found_experience[:3]:  # 只显示前3个
                    print(f"       {item}")
            else:
                print(f"     ❌ 未找到经验相关内容")

    except Exception as e:
        print(f"❌ 分析Excel文件时出错: {e}")
        traceback.print_exc()
        return

    # 3. 手动测试提取器
    print(f"\n🔧 手动测试提取器:")

    try:
        # 测试来日年份提取
        print("\n📍 测试来日年份提取器:")
        arrival_result = arrival_extractor.extract(all_data, None)
        print(f"   结果: {arrival_result}")
        print(f"   类型: {type(arrival_result)}")

        # 测试经验提取
        print("\n📍 测试经验提取器:")
        experience_result = experience_extractor.extract(all_data)
        print(f"   结果: {experience_result}")
        print(f"   类型: {type(experience_result)}")

    except Exception as e:
        print(f"❌ 手动测试提取器时出错: {e}")
        traceback.print_exc()


def check_extractor_source_code():
    """检查提取器源代码"""

    print("=== 检查提取器源代码 ===\n")

    try:
        from app.services.extractors.arrival_year_extractor import ArrivalYearExtractor
        from app.services.extractors.experience_extractor import ExperienceExtractor

        # 检查来日年份提取器
        print("🔍 来日年份提取器源代码检查:")

        # 检查文件内容
        import inspect

        arrival_file = inspect.getfile(ArrivalYearExtractor)
        print(f"   文件位置: {arrival_file}")

        # 读取前50行来查看导入语句
        with open(arrival_file, "r", encoding="utf-8") as f:
            lines = f.readlines()[:50]

        print("   导入语句:")
        for i, line in enumerate(lines):
            if "import" in line and ("KEYWORDS" in line or "constants" in line):
                print(f"     行{i+1}: {line.strip()}")

        # 检查经验提取器
        print("\n🔍 经验提取器源代码检查:")

        experience_file = inspect.getfile(ExperienceExtractor)
        print(f"   文件位置: {experience_file}")

        with open(experience_file, "r", encoding="utf-8") as f:
            lines = f.readlines()[:50]

        print("   导入语句:")
        for i, line in enumerate(lines):
            if "import" in line and ("KEYWORDS" in line or "constants" in line):
                print(f"     行{i+1}: {line.strip()}")

    except Exception as e:
        print(f"❌ 检查源代码时出错: {e}")
        traceback.print_exc()


def create_patched_extractors():
    """创建修补版本的提取器"""

    print("=== 创建修补版本的提取器 ===\n")

    # 创建修补版的来日年份提取器
    patched_arrival_content = '''# -*- coding: utf-8 -*-
"""来日年份提取器 - 修补版本：直接内置关键词"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
import re

# 直接定义关键词，避免导入问题
ARRIVAL_KEYWORDS = [
    "来日", "渡日", "入国", "日本滞在年数", "滞在年数", "在日年数",
    "来日年", "来日時期", "来日年月", "来日年度"
]

class ArrivalYearExtractorPatched:
    """来日年份信息提取器 - 修补版"""

    def __init__(self):
        self.trans_table = str.maketrans("０１２３４５６７８９", "0123456789")

    def extract(self, all_data: List[Dict[str, Any]], birthdate_result: Optional[str] = None) -> Optional[str]:
        """提取来日年份"""
        print(f"\\n🔍 修补版来日年份提取器开始工作")
        print(f"   关键词: {ARRIVAL_KEYWORDS}")
        
        birth_year = None
        if birthdate_result:
            try:
                birth_year = datetime.strptime(birthdate_result, "%Y-%m-%d").year
                print(f"   排除出生年份: {birth_year}")
            except:
                pass

        candidates = []

        for data in all_data:
            df = data["df"]
            sheet_name = data.get("sheet_name", "Unknown")
            print(f"   处理Sheet: {sheet_name}")

            # 方法1: 查找"来日XX年"表述
            for idx in range(min(40, len(df))):
                for col in range(len(df.columns)):
                    cell = df.iloc[idx, col]
                    if pd.notna(cell):
                        cell_str = str(cell)
                        
                        # 检查是否包含来日年数表述
                        patterns = [
                            (r"来日.*?(\\d{1,2})\\s*年", 3.5),
                            (r"在日.*?(\\d{1,2})\\s*年", 3.0),
                            (r"滞在.*?(\\d{1,2})\\s*年", 2.5),
                        ]

                        for pattern, confidence in patterns:
                            match = re.search(pattern, cell_str)
                            if match:
                                years_in_japan = int(match.group(1))
                                if 1 <= years_in_japan <= 30:
                                    arrival_year = 2024 - years_in_japan
                                    candidates.append((str(arrival_year), confidence))
                                    print(f"   ✅ 从'{cell_str}'推算来日年份: {arrival_year}")

            # 方法2: 查找关键词附近的年份
            for idx in range(min(40, len(df))):
                for col in range(len(df.columns)):
                    cell = df.iloc[idx, col]
                    if pd.notna(cell):
                        cell_str = str(cell)
                        if any(k in cell_str for k in ARRIVAL_KEYWORDS):
                            print(f"   🔍 在行{idx}列{col}找到关键词: '{cell_str}'")
                            
                            # 搜索附近的年份
                            for r_off in range(-2, 5):
                                for c_off in range(-2, 15):
                                    r = idx + r_off
                                    c = col + c_off
                                    
                                    if 0 <= r < len(df) and 0 <= c < len(df.columns):
                                        value = df.iloc[r, c]
                                        if pd.notna(value):
                                            year = self._parse_year(str(value))
                                            if year and 1990 <= year <= 2024 and year != birth_year:
                                                distance = abs(r_off) + abs(c_off)
                                                confidence = max(0.5, 2.0 - distance * 0.1)
                                                candidates.append((str(year), confidence))
                                                print(f"   ✅ 在附近找到年份: {year} (置信度: {confidence:.2f})")

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            best_candidate = candidates[0]
            result = best_candidate[0]
            print(f"\\n✅ 最佳来日年份: {result} (置信度: {best_candidate[1]:.2f})")
            return result

        print(f"\\n❌ 未能提取到来日年份")
        return None

    def _parse_year(self, value: str) -> Optional[int]:
        """解析年份值"""
        value = value.strip().translate(self.trans_table)
        match = re.search(r'\\b(19|20)\\d{2}\\b', value)
        if match:
            return int(match.group())
        return None
'''

    # 创建修补版的经验提取器
    patched_experience_content = '''# -*- coding: utf-8 -*-
"""经验提取器 - 修补版本：直接内置关键词"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
import re

# 直接定义关键词，避免导入问题
EXPERIENCE_KEYWORDS = [
    "経験年数", "実務経験", "開発経験", "ソフト関連業務経験年数", "IT経験",
    "業務経験", "経験", "実務年数", "エンジニア経験", "経験年月", "職歴", "IT経験年数"
]

class ExperienceExtractorPatched:
    """经验信息提取器 - 修补版"""

    def __init__(self):
        self.trans_table = str.maketrans("０１２３４５６７８９", "0123456789")

    def extract(self, all_data: List[Dict[str, Any]]) -> str:
        """提取经验年数"""
        print(f"\\n🔍 修补版经验提取器开始工作")
        print(f"   关键词: {EXPERIENCE_KEYWORDS[:5]}...")
        
        candidates = []

        for data in all_data:
            df = data["df"]
            sheet_name = data.get("sheet_name", "Unknown")
            print(f"   处理Sheet: {sheet_name}")

            # 查找经验关键词
            for idx in range(min(60, len(df))):
                for col in range(len(df.columns)):
                    cell = df.iloc[idx, col]
                    if pd.notna(cell):
                        cell_str = str(cell)
                        if any(k in cell_str for k in EXPERIENCE_KEYWORDS):
                            print(f"   🔍 在行{idx}列{col}找到关键词: '{cell_str}'")
                            
                            # 排除说明文字
                            if self._is_explanation_text(cell_str):
                                print(f"     跳过说明文字")
                                continue

                            # 搜索附近的经验值
                            for r_off in range(-3, 6):
                                for c_off in range(-3, 20):
                                    r = idx + r_off
                                    c = col + c_off

                                    if 0 <= r < len(df) and 0 <= c < len(df.columns):
                                        value = df.iloc[r, c]
                                        if pd.notna(value):
                                            exp = self._parse_experience_value(str(value))
                                            if exp:
                                                confidence = 1.0
                                                
                                                # 根据关键词类型调整置信度
                                                if "ソフト関連業務経験年数" in cell_str:
                                                    confidence *= 3.0
                                                elif "IT経験年数" in cell_str:
                                                    confidence *= 2.5
                                                elif "実務経験" in cell_str:
                                                    confidence *= 2.0

                                                candidates.append((exp, confidence))
                                                print(f"     ✅ 找到经验值: {exp} (置信度: {confidence:.2f})")

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            result = candidates[0][0]
            print(f"\\n✅ 最佳经验: {result}")
            return result

        print(f"\\n❌ 未能提取到经验信息")
        return ""

    def _parse_experience_value(self, value: str) -> Optional[str]:
        """解析经验值"""
        value = str(value).strip()

        # 排除非经验值
        if any(exclude in value for exclude in ["以上", "未満", "◎", "○", "△"]):
            return None

        # 转换全角数字
        value = value.translate(self.trans_table)

        patterns = [
            (r"^(\\d+)\\s*年\\s*(\\d+)\\s*ヶ月$", lambda m: f"{m.group(1)}年{m.group(2)}ヶ月"),
            (r"^(\\d+(?:\\.\\d+)?)\\s*年$", lambda m: f"{m.group(1)}年"),
            (r"^(\\d+(?:\\.\\d+)?)\\s*$", lambda m: f"{m.group(1)}年" if 1 <= float(m.group(1)) <= 40 else None),
            (r"(\\d+)\\s*年", lambda m: f"{m.group(1)}年"),
        ]

        for pattern, formatter in patterns:
            match = re.search(pattern, value)
            if match:
                result = formatter(match)
                if result:
                    return result

        return None

    def _is_explanation_text(self, text: str) -> bool:
        """判断是否是说明文字"""
        explanations = ["以上", "未満", "◎", "○", "△", "指導", "精通", "できる"]
        return any(ex in text for ex in explanations)
'''

    try:
        # 保存修补版本
        patches_dir = Path("debug_patches")
        patches_dir.mkdir(exist_ok=True)

        arrival_file = patches_dir / "arrival_year_extractor_patched.py"
        with open(arrival_file, "w", encoding="utf-8") as f:
            f.write(patched_arrival_content)

        experience_file = patches_dir / "experience_extractor_patched.py"
        with open(experience_file, "w", encoding="utf-8") as f:
            f.write(patched_experience_content)

        print(f"✅ 已创建修补版本:")
        print(f"   - {arrival_file}")
        print(f"   - {experience_file}")

        print(f"\\n💡 使用修补版本测试:")
        print(
            f"   from debug_patches.arrival_year_extractor_patched import ArrivalYearExtractorPatched"
        )
        print(
            f"   from debug_patches.experience_extractor_patched import ExperienceExtractorPatched"
        )

    except Exception as e:
        print(f"❌ 创建修补版本失败: {e}")


async def test_with_patched_extractors(test_file_path: str):
    """使用修补版本的提取器进行测试"""

    print("=== 使用修补版本提取器测试 ===\\n")

    if not Path(test_file_path).exists():
        print(f"❌ 测试文件不存在: {test_file_path}")
        return

    try:
        # 导入修补版本
        sys.path.append(str(Path("debug_patches")))
        from arrival_year_extractor_patched import ArrivalYearExtractorPatched
        from experience_extractor_patched import ExperienceExtractorPatched

        # 初始化修补版提取器
        arrival_extractor = ArrivalYearExtractorPatched()
        experience_extractor = ExperienceExtractorPatched()

        # 加载数据（使用原解析器的方法）
        parser = ResumeParserService()
        all_data = await asyncio.to_thread(parser._load_excel_data, test_file_path)

        if not all_data:
            print("❌ 无法加载Excel数据")
            return

        print(f"✅ 成功加载数据，开始使用修补版提取器测试...")

        # 测试来日年份提取
        arrival_result = arrival_extractor.extract(all_data, None)

        # 测试经验提取
        experience_result = experience_extractor.extract(all_data)

        print(f"\\n🎯 修补版提取器结果:")
        print(f"   arrival_year_japan: {arrival_result}")
        print(f"   experience: {experience_result}")

        if arrival_result or experience_result:
            print(f"\\n✅ 修补版提取器工作正常！问题确实是关键词导入。")
        else:
            print(f"\\n❌ 即使修补版也无法提取，可能是数据格式问题。")

    except Exception as e:
        print(f"❌ 测试修补版时出错: {e}")
        traceback.print_exc()


def main():
    """主函数"""
    print("🔧 增强版提取器调试工具")
    print("=" * 50)
    print("1. 深度调试提取过程（需要测试文件）")
    print("2. 检查提取器源代码")
    print("3. 创建修补版本的提取器")
    print("4. 使用修补版本测试（需要测试文件）")
    print("5. 退出")

    while True:
        choice = input("\\n请选择操作 (1-5): ").strip()

        if choice == "1":
            test_file = input("请输入测试文件路径: ").strip()
            if test_file:
                asyncio.run(deep_debug_extraction(test_file))
        elif choice == "2":
            check_extractor_source_code()
        elif choice == "3":
            create_patched_extractors()
        elif choice == "4":
            test_file = input("请输入测试文件路径: ").strip()
            if test_file:
                asyncio.run(test_with_patched_extractors(test_file))
        elif choice == "5":
            print("👋 退出调试工具")
            break
        else:
            print("❌ 无效选择，请输入 1-5")


if __name__ == "__main__":
    main()
