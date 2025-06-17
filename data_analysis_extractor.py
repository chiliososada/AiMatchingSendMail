# -*- coding: utf-8 -*-
"""数据分析版经验提取器 - 深度分析为什么提取不出来"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
import re

# 内置关键词
EXPERIENCE_KEYWORDS = [
    "経験年数",
    "実務経験",
    "開発経験",
    "ソフト関連業務経験年数",
    "IT経験",
    "業務経験",
    "経験",
    "実務年数",
    "エンジニア経験",
    "経験年月",
    "職歴",
    "IT経験年数",
    "プログラマー経験",
    "SE経験",
    "システム開発経験",
    "Web開発経験",
    "アプリ開発経験",
    # 添加更多可能的关键词
    "年数",
    "歴",
    "キャリア",
    "スキル",
    "技術",
    "習得",
    "知識",
]


class DataAnalysisExtractor:
    """数据分析版经验提取器 - 找出数据中到底有什么"""

    def __init__(self):
        self.trans_table = str.maketrans("０１２３４５６７８９", "0123456789")

    def extract(self, all_data: List[Dict[str, Any]]) -> str:
        """深度分析数据并提取经验"""

        print("\n" + "🔍" * 80)
        print("🔍 开始深度数据分析 - 找出为什么提取不出经验")
        print("🔍" * 80)

        # 第一步：完整数据扫描
        self._scan_all_data(all_data)

        # 第二步：关键词匹配分析
        keyword_matches = self._analyze_keyword_matches(all_data)

        # 第三步：数值分析
        number_analysis = self._analyze_numbers(all_data)

        # 第四步：上下文分析
        context_analysis = self._analyze_context(all_data)

        # 第五步：尝试所有可能的提取方法
        extraction_attempts = self._try_all_extraction_methods(all_data)

        # 最终分析和建议
        return self._final_analysis_and_recommendation(
            keyword_matches, number_analysis, context_analysis, extraction_attempts
        )

    def _scan_all_data(self, all_data: List[Dict[str, Any]]):
        """第一步：扫描所有数据"""
        print(f"\n📋 步骤1: 完整数据扫描")
        print("=" * 60)

        for sheet_idx, data in enumerate(all_data):
            df = data["df"]
            sheet_name = data.get("sheet_name", f"Sheet_{sheet_idx}")

            print(
                f"\n📊 表格 {sheet_idx+1}: '{sheet_name}' ({df.shape[0]}行 x {df.shape[1]}列)"
            )

            # 显示所有非空数据
            print("   所有非空内容:")
            for idx in range(len(df)):
                for col in range(len(df.columns)):
                    cell = df.iloc[idx, col]
                    if pd.notna(cell):
                        cell_str = str(cell).strip()
                        if cell_str:  # 不为空字符串
                            print(
                                f"     [{idx:2d},{col:2d}] {type(cell).__name__:10s} | '{cell_str}'"
                            )

                            # 检查是否包含数字
                            if re.search(r"\d", cell_str):
                                print(f"           └── 🔢 包含数字")

                            # 检查是否包含可能的经验关键词
                            found_exp_words = [
                                k for k in EXPERIENCE_KEYWORDS if k in cell_str
                            ]
                            if found_exp_words:
                                print(
                                    f"           └── 🎯 包含经验关键词: {found_exp_words}"
                                )

    def _analyze_keyword_matches(self, all_data: List[Dict[str, Any]]) -> Dict:
        """第二步：关键词匹配分析"""
        print(f"\n📋 步骤2: 关键词匹配分析")
        print("=" * 60)

        matches = {"exact_matches": [], "partial_matches": [], "nearby_numbers": []}

        for sheet_idx, data in enumerate(all_data):
            df = data["df"]
            sheet_name = data.get("sheet_name", f"Sheet_{sheet_idx}")

            print(f"\n   在表格 '{sheet_name}' 中搜索关键词...")

            for idx in range(len(df)):
                for col in range(len(df.columns)):
                    cell = df.iloc[idx, col]
                    if pd.notna(cell):
                        cell_str = str(cell)

                        # 完全匹配
                        exact_found = [
                            k for k in EXPERIENCE_KEYWORDS if k == cell_str.strip()
                        ]
                        if exact_found:
                            matches["exact_matches"].append(
                                {
                                    "sheet": sheet_name,
                                    "position": [idx, col],
                                    "keywords": exact_found,
                                    "content": cell_str,
                                }
                            )
                            print(
                                f"     ✅ 完全匹配 [{idx},{col}]: {exact_found} | '{cell_str}'"
                            )

                        # 部分匹配
                        partial_found = [
                            k for k in EXPERIENCE_KEYWORDS if k in cell_str
                        ]
                        if partial_found and not exact_found:
                            matches["partial_matches"].append(
                                {
                                    "sheet": sheet_name,
                                    "position": [idx, col],
                                    "keywords": partial_found,
                                    "content": cell_str,
                                }
                            )
                            print(
                                f"     🔍 部分匹配 [{idx},{col}]: {partial_found} | '{cell_str}'"
                            )

                            # 查找附近的数字
                            nearby_nums = self._find_nearby_numbers(df, idx, col)
                            if nearby_nums:
                                matches["nearby_numbers"].extend(nearby_nums)
                                print(f"       └── 附近数字: {nearby_nums}")

        print(f"\n   匹配统计:")
        print(f"     完全匹配: {len(matches['exact_matches'])} 个")
        print(f"     部分匹配: {len(matches['partial_matches'])} 个")
        print(f"     附近数字: {len(matches['nearby_numbers'])} 个")

        return matches

    def _analyze_numbers(self, all_data: List[Dict[str, Any]]) -> Dict:
        """第三步：数值分析"""
        print(f"\n📋 步骤3: 数值分析")
        print("=" * 60)

        number_analysis = {
            "integers": [],
            "floats": [],
            "year_patterns": [],
            "experience_patterns": [],
        }

        for sheet_idx, data in enumerate(all_data):
            df = data["df"]
            sheet_name = data.get("sheet_name", f"Sheet_{sheet_idx}")

            print(f"\n   分析表格 '{sheet_name}' 中的数值...")

            for idx in range(len(df)):
                for col in range(len(df.columns)):
                    cell = df.iloc[idx, col]
                    if pd.notna(cell):
                        cell_str = str(cell)

                        # 整数分析
                        if isinstance(cell, (int, float)) and not isinstance(
                            cell, bool
                        ):
                            if float(cell).is_integer() and 1 <= cell <= 50:
                                number_analysis["integers"].append(
                                    {
                                        "position": [idx, col],
                                        "value": cell,
                                        "type": "可能的经验年数",
                                    }
                                )
                                print(
                                    f"     🔢 [{idx},{col}] 整数: {cell} (可能是经验年数)"
                                )

                        # 字符串中的数字模式
                        # 年数模式
                        year_matches = re.findall(r"(\d+)\s*年", cell_str)
                        if year_matches:
                            for match in year_matches:
                                if 1 <= int(match) <= 50:
                                    number_analysis["year_patterns"].append(
                                        {
                                            "position": [idx, col],
                                            "value": f"{match}年",
                                            "original": cell_str,
                                        }
                                    )
                                    print(
                                        f"     📅 [{idx},{col}] 年数模式: {match}年 | 原文: '{cell_str}'"
                                    )

                        # 经验模式 (X年Y个月)
                        exp_matches = re.findall(
                            r"(\d+)\s*年\s*(\d+)\s*[ヶか]月", cell_str
                        )
                        if exp_matches:
                            for years, months in exp_matches:
                                number_analysis["experience_patterns"].append(
                                    {
                                        "position": [idx, col],
                                        "value": f"{years}年{months}ヶ月",
                                        "original": cell_str,
                                    }
                                )
                                print(
                                    f"     📊 [{idx},{col}] 经验模式: {years}年{months}ヶ月 | 原文: '{cell_str}'"
                                )

                        # 小数年数
                        decimal_matches = re.findall(r"(\d+\.\d+)\s*年?", cell_str)
                        if decimal_matches:
                            for match in decimal_matches:
                                if 1 <= float(match) <= 50:
                                    number_analysis["floats"].append(
                                        {
                                            "position": [idx, col],
                                            "value": f"{match}年",
                                            "original": cell_str,
                                        }
                                    )
                                    print(
                                        f"     💫 [{idx},{col}] 小数年数: {match} | 原文: '{cell_str}'"
                                    )

        print(f"\n   数值统计:")
        print(f"     整数: {len(number_analysis['integers'])} 个")
        print(f"     小数: {len(number_analysis['floats'])} 个")
        print(f"     年数模式: {len(number_analysis['year_patterns'])} 个")
        print(f"     经验模式: {len(number_analysis['experience_patterns'])} 个")

        return number_analysis

    def _analyze_context(self, all_data: List[Dict[str, Any]]) -> Dict:
        """第四步：上下文分析"""
        print(f"\n📋 步骤4: 上下文分析")
        print("=" * 60)

        context_info = {
            "possible_experience_areas": [],
            "skill_sections": [],
            "project_sections": [],
        }

        for sheet_idx, data in enumerate(all_data):
            df = data["df"]
            sheet_name = data.get("sheet_name", f"Sheet_{sheet_idx}")

            print(f"\n   分析表格 '{sheet_name}' 的上下文...")

            # 查找可能的经验区域
            for idx in range(len(df)):
                row_text = ""
                for col in range(len(df.columns)):
                    cell = df.iloc[idx, col]
                    if pd.notna(cell):
                        row_text += str(cell) + " "

                if row_text.strip():
                    # 检查是否包含技能相关内容
                    skill_keywords = [
                        "スキル",
                        "技能",
                        "技術",
                        "言語",
                        "ツール",
                        "フレームワーク",
                    ]
                    if any(k in row_text for k in skill_keywords):
                        context_info["skill_sections"].append(
                            {"row": idx, "content": row_text.strip()}
                        )
                        print(f"     🛠️  技能区域 行{idx}: {row_text.strip()[:50]}...")

                    # 检查是否包含项目相关内容
                    project_keywords = [
                        "プロジェクト",
                        "システム",
                        "開発",
                        "案件",
                        "業務",
                    ]
                    if any(k in row_text for k in project_keywords):
                        context_info["project_sections"].append(
                            {"row": idx, "content": row_text.strip()}
                        )
                        print(f"     📂 项目区域 行{idx}: {row_text.strip()[:50]}...")

                    # 检查是否是经验相关区域
                    if any(k in row_text for k in EXPERIENCE_KEYWORDS):
                        context_info["possible_experience_areas"].append(
                            {"row": idx, "content": row_text.strip()}
                        )
                        print(f"     🎯 经验区域 行{idx}: {row_text.strip()[:50]}...")

        return context_info

    def _try_all_extraction_methods(self, all_data: List[Dict[str, Any]]) -> Dict:
        """第五步：尝试所有可能的提取方法"""
        print(f"\n📋 步骤5: 尝试所有提取方法")
        print("=" * 60)

        results = {
            "method1_keyword_nearby": [],
            "method2_pattern_matching": [],
            "method3_number_context": [],
            "method4_loose_search": [],
        }

        for sheet_idx, data in enumerate(all_data):
            df = data["df"]
            sheet_name = data.get("sheet_name", f"Sheet_{sheet_idx}")

            print(f"\n   在表格 '{sheet_name}' 中尝试各种提取方法...")

            # 方法1：关键词附近搜索（原始方法）
            print("     🔍 方法1: 关键词附近搜索")
            for idx in range(len(df)):
                for col in range(len(df.columns)):
                    cell = df.iloc[idx, col]
                    if pd.notna(cell):
                        cell_str = str(cell)
                        if any(k in cell_str for k in EXPERIENCE_KEYWORDS):
                            nearby = self._search_all_nearby(df, idx, col)
                            if nearby:
                                results["method1_keyword_nearby"].extend(nearby)
                                print(f"       找到: {nearby}")

            # 方法2：模式匹配（不依赖关键词）
            print("     🔍 方法2: 纯模式匹配")
            for idx in range(len(df)):
                for col in range(len(df.columns)):
                    cell = df.iloc[idx, col]
                    if pd.notna(cell):
                        patterns = self._extract_all_patterns(str(cell))
                        if patterns:
                            results["method2_pattern_matching"].extend(
                                [
                                    {
                                        "position": [idx, col],
                                        "patterns": patterns,
                                        "original": str(cell),
                                    }
                                ]
                            )
                            print(f"       [{idx},{col}] 模式: {patterns}")

            # 方法3：数字+上下文
            print("     🔍 方法3: 数字上下文分析")
            for idx in range(len(df)):
                for col in range(len(df.columns)):
                    cell = df.iloc[idx, col]
                    if (
                        pd.notna(cell)
                        and isinstance(cell, (int, float))
                        and 1 <= cell <= 50
                    ):
                        context = self._get_surrounding_context(df, idx, col)
                        if self._is_likely_experience_context(context):
                            results["method3_number_context"].append(
                                {
                                    "position": [idx, col],
                                    "value": cell,
                                    "context": context,
                                }
                            )
                            print(f"       [{idx},{col}] 数字 {cell} 在经验上下文中")

            # 方法4：宽松搜索（任何包含数字的内容）
            print("     🔍 方法4: 宽松搜索")
            for idx in range(len(df)):
                for col in range(len(df.columns)):
                    cell = df.iloc[idx, col]
                    if pd.notna(cell):
                        cell_str = str(cell)
                        if re.search(r"\d", cell_str):
                            results["method4_loose_search"].append(
                                {
                                    "position": [idx, col],
                                    "content": cell_str,
                                    "numbers": re.findall(r"\d+(?:\.\d+)?", cell_str),
                                }
                            )

        # 打印各方法结果统计
        for method, result_list in results.items():
            print(f"     {method}: {len(result_list)} 个结果")

        return results

    def _final_analysis_and_recommendation(
        self, keyword_matches, number_analysis, context_analysis, extraction_attempts
    ) -> str:
        """最终分析和建议"""
        print(f"\n📋 最终分析和建议")
        print("=" * 60)

        # 统计所有可能的经验值
        all_candidates = []

        # 从各种方法中收集候选
        for method_results in extraction_attempts.values():
            if isinstance(method_results, list):
                for result in method_results:
                    if "patterns" in result:
                        for pattern in result["patterns"]:
                            all_candidates.append(("模式匹配", pattern))
                    elif "value" in result:
                        all_candidates.append(("数字上下文", f"{result['value']}年"))
                    elif "numbers" in result:
                        for num in result["numbers"]:
                            if 1 <= float(num) <= 50:
                                all_candidates.append(("宽松搜索", f"{num}年"))

        # 从数值分析中收集
        for pattern_list in number_analysis.values():
            for item in pattern_list:
                all_candidates.append(("数值分析", item["value"]))

        print(f"\n🎯 所有候选经验值:")
        if all_candidates:
            for method, value in all_candidates:
                print(f"     {method}: {value}")

            # 选择最可能的结果
            # 优先级：经验模式 > 年数模式 > 数字上下文
            best_candidate = None
            for method, value in all_candidates:
                if "年" in value and "月" in value:  # 优先选择 X年Y月 格式
                    best_candidate = value
                    break

            if not best_candidate:
                for method, value in all_candidates:
                    if "年" in value:
                        best_candidate = value
                        break

            if not best_candidate and all_candidates:
                best_candidate = all_candidates[0][1]

            if best_candidate:
                print(f"\n✅ 建议结果: {best_candidate}")
                return best_candidate

        # 如果没有找到任何候选
        print(f"\n❌ 未找到任何经验信息")
        print(f"\n🔍 可能的原因:")
        print(f"   1. 数据中确实没有经验年数信息")
        print(f"   2. 经验信息使用了我们没有覆盖的关键词")
        print(f"   3. 经验信息的格式与预期不符")
        print(f"   4. 数据在我们没有检查的位置")

        print(f"\n💡 调试建议:")
        print(f"   1. 检查原始Excel文件中是否真的包含经验年数")
        print(f"   2. 查看上面的完整数据扫描，确认所有内容")
        print(f"   3. 如果有经验信息但格式特殊，可以添加新的解析规则")

        return ""

    def _find_nearby_numbers(
        self, df: pd.DataFrame, row: int, col: int, radius: int = 5
    ) -> List[Dict]:
        """查找附近的数字"""
        numbers = []
        for r in range(max(0, row - radius), min(len(df), row + radius + 1)):
            for c in range(
                max(0, col - radius), min(len(df.columns), col + radius + 1)
            ):
                cell = df.iloc[r, c]
                if pd.notna(cell) and (r != row or c != col):
                    if isinstance(cell, (int, float)) and 1 <= cell <= 50:
                        numbers.append(
                            {
                                "position": [r, c],
                                "value": cell,
                                "distance": abs(r - row) + abs(c - col),
                            }
                        )
        return numbers

    def _search_all_nearby(self, df: pd.DataFrame, row: int, col: int) -> List[str]:
        """搜索附近所有可能的经验值"""
        candidates = []
        for r_off in range(-3, 6):
            for c_off in range(-5, 10):
                r, c = row + r_off, col + c_off
                if 0 <= r < len(df) and 0 <= c < len(df.columns):
                    cell = df.iloc[r, c]
                    if pd.notna(cell):
                        parsed = self._parse_any_experience_value(str(cell))
                        if parsed:
                            candidates.append(parsed)
        return candidates

    def _extract_all_patterns(self, text: str) -> List[str]:
        """提取所有可能的经验模式"""
        patterns = []
        text = text.translate(self.trans_table)  # 全角转半角

        # 各种可能的模式
        pattern_list = [
            (
                r"(\d+)\s*年\s*(\d+)\s*[ヶか]月",
                lambda m: f"{m.group(1)}年{m.group(2)}ヶ月",
            ),
            (r"(\d+\.\d+)\s*年", lambda m: f"{m.group(1)}年"),
            (r"(\d+)\s*年", lambda m: f"{m.group(1)}年"),
            (
                r"^(\d+)$",
                lambda m: f"{m.group(1)}年" if 1 <= int(m.group(1)) <= 50 else None,
            ),
        ]

        for pattern, formatter in pattern_list:
            matches = re.finditer(pattern, text)
            for match in matches:
                result = formatter(match)
                if result and result not in patterns:
                    patterns.append(result)

        return patterns

    def _parse_any_experience_value(self, value: str) -> Optional[str]:
        """解析任何可能的经验值（宽松版本）"""
        value = str(value).strip().translate(self.trans_table)

        patterns = [
            (
                r"(\d+)\s*年\s*(\d+)\s*[ヶか]月",
                lambda m: f"{m.group(1)}年{m.group(2)}ヶ月",
            ),
            (r"(\d+\.\d+)\s*年?", lambda m: f"{m.group(1)}年"),
            (r"(\d+)\s*年", lambda m: f"{m.group(1)}年"),
            (
                r"^(\d+)$",
                lambda m: f"{m.group(1)}年" if 1 <= int(m.group(1)) <= 50 else None,
            ),
        ]

        for pattern, formatter in patterns:
            match = re.search(pattern, value)
            if match:
                try:
                    result = formatter(match)
                    if result:
                        return result
                except:
                    continue
        return None

    def _get_surrounding_context(
        self, df: pd.DataFrame, row: int, col: int, radius: int = 3
    ) -> str:
        """获取周围上下文"""
        context = []
        for r in range(max(0, row - radius), min(len(df), row + radius + 1)):
            for c in range(
                max(0, col - radius), min(len(df.columns), col + radius + 1)
            ):
                cell = df.iloc[r, c]
                if pd.notna(cell):
                    context.append(str(cell))
        return " ".join(context)

    def _is_likely_experience_context(self, context: str) -> bool:
        """判断是否可能是经验相关的上下文"""
        experience_indicators = [
            "経験",
            "実務",
            "開発",
            "IT",
            "ソフト",
            "システム",
            "プログラム",
            "業務",
            "スキル",
            "技術",
            "年数",
            "歴",
            "習得",
        ]
        return any(indicator in context for indicator in experience_indicators)
