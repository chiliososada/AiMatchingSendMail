# -*- coding: utf-8 -*-
"""来日年份提取器 - 修复版本：解决关键词匹配和年份提取问题"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict
import pandas as pd
import re

# 🔥 修复1: 直接定义完整的关键词，避免导入依赖问题
ARRIVAL_KEYWORDS = [
    "来日",
    "渡日",
    "入国",
    "日本滞在年数",
    "滞在年数",
    "在日年数",
    "来日年",
    "来日時期",
    "来日年月",
    "来日年度",  # 🆕 添加了 "来日年月"
    "滞在期間",
    "在留期間",
    "入日",
    "日本入国",
    "来日時",
    "渡日時期",
]

try:
    from app.base.constants import KEYWORDS
    from app.base.base_extractor import BaseExtractor
    from app.utils.date_utils import convert_excel_serial_to_date

    # 如果能成功导入，补充现有关键词
    if isinstance(KEYWORDS, dict) and "arrival" in KEYWORDS:
        ARRIVAL_KEYWORDS.extend(KEYWORDS["arrival"])
        ARRIVAL_KEYWORDS = list(set(ARRIVAL_KEYWORDS))  # 去重

    print("✅ 成功导入项目关键词，已合并")
except ImportError as e:
    print(f"⚠️  项目关键词导入失败，使用备用关键词: {e}")

    # 备用基类
    class BaseExtractor:
        pass


class ArrivalYearExtractor(BaseExtractor):
    """来日年份信息提取器 - 修复版本"""

    def extract(
        self, all_data: List[Dict[str, Any]], birthdate_result: Optional[str] = None
    ) -> Optional[str]:
        """提取来日年份，避免与出生年份混淆

        Args:
            all_data: 包含所有sheet数据的列表
            birthdate_result: 已提取的生年月日信息，用于排除出生年份

        Returns:
            来日年份字符串，如果未找到返回None
        """
        print("\n" + "=" * 60)
        print("🔍 开始来日年份提取器执行流程 (修复版)")
        print("=" * 60)

        print(f"\n📋 使用关键词: {ARRIVAL_KEYWORDS}")

        # 处理出生年份
        birth_year = None
        if birthdate_result:
            try:
                birth_year = datetime.strptime(birthdate_result, "%Y-%m-%d").year
                print(f"✅ 解析出生年份: {birth_year} (将排除此年份)")
            except Exception as e:
                print(f"⚠️  生年月日解析失败: {e}")

        candidates = []

        print(f"\n📋 开始处理 {len(all_data)} 个数据表")

        for sheet_idx, data in enumerate(all_data):
            df = data["df"]
            sheet_name = data.get("sheet_name", f"Sheet_{sheet_idx}")

            print(f"\n📊 处理数据表 {sheet_idx+1}/{len(all_data)}: '{sheet_name}'")
            print(f"   表格大小: {len(df)} 行 x {len(df.columns)} 列")

            # 🔥 修复2: 优化关键词匹配逻辑
            sheet_candidates = self._extract_from_sheet(df, birth_year)
            if sheet_candidates:
                candidates.extend(sheet_candidates)
                print(f"   ✅ 本表提取到 {len(sheet_candidates)} 个候选年份")
            else:
                print(f"   ❌ 本表未找到有效年份")

        if not candidates:
            print(f"\n❌ 所有表格都未找到来日年份")
            return None

        # 选择最佳候选
        best_candidate = self._select_best_candidate(candidates, birth_year)

        if best_candidate:
            print(f"\n🎯 最终选择: {best_candidate}")
            return best_candidate
        else:
            print(f"\n❌ 未找到合适的来日年份")
            return None

    def _extract_from_sheet(
        self, df: pd.DataFrame, birth_year: Optional[int]
    ) -> List[tuple]:
        """从单个表格提取来日年份候选"""
        candidates = []

        print(f"      🔍 开始扫描表格...")

        # 🔥 修复3: 遍历所有单元格，寻找关键词和年份
        for idx in range(min(50, len(df))):  # 前50行通常包含基本信息
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if pd.notna(cell):
                    cell_str = str(cell).strip()

                    # 检查是否包含来日关键词
                    found_keywords = [k for k in ARRIVAL_KEYWORDS if k in cell_str]

                    if found_keywords:
                        print(
                            f"         🎯 行{idx+1}列{col+1}: 发现关键词 {found_keywords} 在 '{cell_str}'"
                        )

                        # 🔥 修复4: 在关键词附近搜索年份
                        nearby_years = self._search_year_nearby(
                            df, idx, col, birth_year
                        )
                        if nearby_years:
                            candidates.extend(nearby_years)
                            print(
                                f"            ✅ 找到附近年份: {[y[0] for y in nearby_years]}"
                            )

                    # 🔥 修复5: 直接检查单元格是否包含年份格式
                    year_matches = self._extract_year_from_cell(cell_str, birth_year)
                    if year_matches:
                        # 检查这个单元格是否在来日相关的行
                        if self._is_arrival_related_row(df, idx):
                            candidates.extend(year_matches)
                            print(
                                f"         📅 行{idx+1}列{col+1}: 直接提取年份 {[y[0] for y in year_matches]} 从 '{cell_str}'"
                            )

        return candidates

    def _search_year_nearby(
        self, df: pd.DataFrame, row: int, col: int, birth_year: Optional[int]
    ) -> List[tuple]:
        """在指定位置附近搜索年份值"""
        candidates = []

        # 搜索范围：上下3行，左右20列
        for r_off in range(-3, 4):
            for c_off in range(-5, 21):
                r, c = row + r_off, col + c_off

                if 0 <= r < len(df) and 0 <= c < len(df.columns):
                    cell = df.iloc[r, c]
                    if pd.notna(cell):
                        cell_str = str(cell).strip()
                        year_matches = self._extract_year_from_cell(
                            cell_str, birth_year
                        )

                        if year_matches:
                            # 根据距离设置置信度
                            distance = abs(r_off) + abs(c_off)
                            for year, base_confidence in year_matches:
                                # 距离越近置信度越高
                                adjusted_confidence = base_confidence * (
                                    1.0 - distance * 0.1
                                )
                                candidates.append((year, max(adjusted_confidence, 0.1)))

        return candidates

    def _extract_year_from_cell(
        self, cell_str: str, birth_year: Optional[int]
    ) -> List[tuple]:
        """从单元格中提取年份"""
        candidates = []

        # 🔥 修复6: 增强年份识别模式
        year_patterns = [
            # "2016年4月" -> 2016
            (r"(\d{4})\s*年\s*\d{1,2}\s*月", 4.0),
            # "2016年" -> 2016
            (r"(\d{4})\s*年", 3.5),
            # "2016/4" -> 2016
            (r"(\d{4})\s*/\s*\d{1,2}", 3.0),
            # "2016-04" -> 2016
            (r"(\d{4})\s*-\s*\d{1,2}", 3.0),
            # 纯数字年份（需要在合理范围内）
            (r"\b(\d{4})\b", 2.0),
        ]

        for pattern, confidence in year_patterns:
            matches = re.finditer(pattern, cell_str)
            for match in matches:
                year_str = match.group(1)
                year = int(year_str)

                # 🔥 修复7: 年份合理性检查
                if self._is_valid_arrival_year(year, birth_year):
                    candidates.append((year_str, confidence))
                    print(
                        f"            📅 提取年份: {year_str} (模式: {pattern}, 置信度: {confidence})"
                    )

        return candidates

    def _is_valid_arrival_year(self, year: int, birth_year: Optional[int]) -> bool:
        """检查年份是否为有效的来日年份"""
        # 基本范围检查
        if year < 1980 or year > 2025:
            return False

        # 排除出生年份
        if birth_year and year == birth_year:
            print(f"            ⚠️  排除出生年份: {year}")
            return False

        # 来日年份应该在一个合理的范围内
        if birth_year:
            # 来日年份应该在出生后至少10年，最多50年内
            if year < birth_year + 10 or year > birth_year + 50:
                print(f"            ⚠️  年份不合理: {year} (出生年份: {birth_year})")
                return False

        return True

    def _is_arrival_related_row(self, df: pd.DataFrame, row_idx: int) -> bool:
        """检查这一行是否与来日相关"""
        # 检查整行的内容
        row_content = ""
        for col in range(len(df.columns)):
            cell = df.iloc[row_idx, col]
            if pd.notna(cell):
                row_content += str(cell) + " "

        # 如果行内容包含来日关键词，则认为相关
        return any(keyword in row_content for keyword in ARRIVAL_KEYWORDS)

    def _select_best_candidate(
        self, candidates: List[tuple], birth_year: Optional[int]
    ) -> Optional[str]:
        """选择最佳的来日年份候选"""
        if not candidates:
            return None

        print(f"\n📊 候选年份分析:")

        # 按置信度排序
        sorted_candidates = sorted(candidates, key=lambda x: x[1], reverse=True)

        # 显示所有候选
        for year, confidence in sorted_candidates[:5]:  # 显示前5个
            print(f"   {year}: 置信度 {confidence:.2f}")

        # 选择置信度最高的
        best_year, best_confidence = sorted_candidates[0]

        if best_confidence >= 2.0:  # 置信度阈值
            return str(best_year)
        else:
            print(f"   ⚠️  最高置信度 {best_confidence} 低于阈值 2.0")
            return None
