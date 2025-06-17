# -*- coding: utf-8 -*-
"""来日年份提取器 - 修复版：避免混淆出生年份"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict
import pandas as pd
import re

from base.base_extractor import BaseExtractor
from base.constants import KEYWORDS
from utils.date_utils import convert_excel_serial_to_date


class ArrivalYearExtractor(BaseExtractor):
    """来日年份信息提取器 - 修复版"""

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
        birth_year = None
        if birthdate_result:
            try:
                birth_year = datetime.strptime(birthdate_result, "%Y-%m-%d").year
                print(f"    排除出生年份: {birth_year}")
            except:
                pass

        candidates = []

        for data in all_data:
            df = data["df"]
            sheet_name = data.get("sheet_name", "Unknown")

            print(f"\n🔍 开始来日年份提取 - Sheet: {sheet_name}")

            # 方法1: 查找"来日XX年"这样的表述
            years_candidates = self._extract_from_years_expression(df)
            if years_candidates:
                print(f"    从年数表述提取到 {len(years_candidates)} 个候选年份")
            candidates.extend(years_candidates)

            # 方法2: 查找来日关键词附近的年份（排除出生年份）
            label_candidates = self._extract_from_arrival_labels(df, birth_year)
            if label_candidates:
                print(f"    从来日标签提取到 {len(label_candidates)} 个候选年份")
            candidates.extend(label_candidates)

            # 方法3: 从日期对象中提取（排除出生年份）
            date_candidates = self._extract_from_date_objects(df, birth_year)
            if date_candidates:
                print(f"    从日期对象提取到 {len(date_candidates)} 个候选年份")
            candidates.extend(date_candidates)

            # 方法4: 扫描Excel序列日期数字（排除出生年份）
            serial_candidates = self._extract_from_serial_dates(df, birth_year)
            if serial_candidates:
                print(f"    从序列日期提取到 {len(serial_candidates)} 个候选年份")
            candidates.extend(serial_candidates)

        if candidates:
            # 统计每个年份的总置信度
            year_scores = defaultdict(float)
            for year, conf in candidates:
                year_scores[year] += conf

            if year_scores:
                best_year = max(year_scores.items(), key=lambda x: x[1])
                print(f"\n✅ 最终来日年份: {best_year[0]} (置信度: {best_year[1]:.2f})")
                return best_year[0]

        print("\n❌ 未能提取到来日年份")
        return None

    def _extract_from_years_expression(self, df: pd.DataFrame) -> List[tuple]:
        """提取"来日XX年"或"在日XX年"这样的表述"""
        candidates = []

        for idx in range(len(df)):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if pd.notna(cell):
                    cell_str = str(cell)

                    # 查找"来日XX年"、"在日XX年"等表述
                    patterns = [
                        (r"来日\s*(\d{1,2})\s*年", 4.0),
                        (r"在日\s*(\d{1,2})\s*年", 4.0),
                        (r"日本滞在\s*(\d{1,2})\s*年", 3.5),
                        (r"滞在年数\s*(\d{1,2})\s*年?", 3.5),
                        (r"日本.*?(\d{1,2})\s*年", 2.0),
                        (r"(\d{1,2})\s*年.*?日本", 2.0),
                    ]

                    for pattern, confidence in patterns:
                        match = re.search(pattern, cell_str)
                        if match:
                            years_in_japan = int(match.group(1))
                            if 1 <= years_in_japan <= 30:
                                # 从年数推算来日年份
                                arrival_year = 2024 - years_in_japan
                                candidates.append((str(arrival_year), confidence))
                                print(
                                    f"    行{idx}, 列{col}: 从'{cell_str}'推算来日年份: {arrival_year}"
                                )

        return candidates

    def _extract_from_arrival_labels(
        self, df: pd.DataFrame, birth_year: Optional[int]
    ) -> List[tuple]:
        """从来日标签附近提取年份（排除出生年份）"""
        candidates = []
        arrival_keywords = KEYWORDS.get("arrival", [])

        for idx in range(min(40, len(df))):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if pd.notna(cell):
                    cell_str = str(cell)
                    if any(k in cell_str for k in arrival_keywords):
                        nearby_years = self._search_year_nearby(
                            df, idx, col, birth_year
                        )
                        if nearby_years:
                            candidates.extend(nearby_years)
                            print(
                                f"    行{idx}, 列{col}: 在来日关键词附近找到 {len(nearby_years)} 个年份"
                            )
        return candidates

    def _search_year_nearby(
        self, df: pd.DataFrame, row: int, col: int, birth_year: Optional[int]
    ) -> List[tuple]:
        """在指定位置附近搜索年份值（排除出生年份）"""
        candidates = []

        for r_off in range(-2, 5):
            for c_off in range(-2, 25):
                r = row + r_off
                c = col + c_off

                if 0 <= r < len(df) and 0 <= c < len(df.columns):
                    value = df.iloc[r, c]
                    if pd.notna(value):
                        if isinstance(value, datetime):
                            year = value.year
                            if 1990 <= year <= 2024 and year != birth_year:
                                candidates.append((str(year), 2.0))
                        else:
                            year = self._parse_year_value(str(value))
                            if year and year != str(birth_year):
                                candidates.append((year, 1.8))

        return candidates

    def _parse_year_value(self, value: str) -> Optional[str]:
        """解析年份值"""
        value_str = str(value).strip()

        # 直接的年份格式
        if re.match(r"^20\d{2}$", value_str):
            return value_str

        # 年月格式
        match = re.search(r"(20\d{2})[年/月]", value_str)
        if match:
            return match.group(1)

        # 2016年4月格式
        match = re.search(r"(20\d{2})年\d+月", value_str)
        if match:
            return match.group(1)

        # 和暦
        if "平成" in value_str:
            match = re.search(r"平成\s*(\d+)", value_str)
            if match:
                return str(1988 + int(match.group(1)))
        elif "令和" in value_str:
            match = re.search(r"令和\s*(\d+)", value_str)
            if match:
                return str(2018 + int(match.group(1)))

        return None

    def _extract_from_date_objects(
        self, df: pd.DataFrame, birth_year: Optional[int]
    ) -> List[tuple]:
        """从Date对象中提取来日年份（排除出生年份）"""
        candidates = []

        for idx in range(min(30, len(df))):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if isinstance(cell, datetime):
                    if 1990 <= cell.year <= 2024 and cell.year != birth_year:
                        # 检查是否有来日相关上下文
                        has_arrival_context = self._has_arrival_context(df, idx, col)
                        has_age_context = self._has_age_context(df, idx, col)

                        if has_arrival_context:
                            # 如果也有年龄上下文，可能是生年月日，降低置信度
                            confidence = 1.5 if has_age_context else 2.5
                            candidates.append((str(cell.year), confidence))

        return candidates

    def _extract_from_serial_dates(
        self, df: pd.DataFrame, birth_year: Optional[int]
    ) -> List[tuple]:
        """从Excel序列日期中提取来日年份（排除出生年份）"""
        candidates = []

        for idx in range(min(30, len(df))):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if pd.notna(cell) and isinstance(cell, (int, float)):
                    # 检查是否可能是Excel序列日期（1982-2037年的范围）
                    if 30000 <= cell <= 50000:
                        converted_date = convert_excel_serial_to_date(cell)
                        if converted_date and 1990 <= converted_date.year <= 2024:
                            if (
                                converted_date.year != birth_year
                                and self._has_arrival_context(df, idx, col)
                            ):
                                candidates.append((str(converted_date.year), 3.0))

        return candidates

    def _has_arrival_context(self, df: pd.DataFrame, row: int, col: int) -> bool:
        """检查是否有来日相关的上下文"""
        arrival_keywords = KEYWORDS.get("arrival", [])
        return self.has_nearby_keyword(df, row, col, arrival_keywords, radius=5)

    def _has_age_context(self, df: pd.DataFrame, row: int, col: int) -> bool:
        """检查是否有年龄相关的上下文"""
        age_keywords = ["生年月", "年齢", "歳", "才"]
        return self.has_nearby_keyword(df, row, col, age_keywords, radius=5)
