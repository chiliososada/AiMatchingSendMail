# -*- coding: utf-8 -*-
"""经验提取器"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
import re

from base.base_extractor import BaseExtractor
from base.constants import KEYWORDS


class ExperienceExtractor(BaseExtractor):
    """经验信息提取器"""

    def extract(self, all_data: List[Dict[str, Any]]) -> str:
        """提取经验年数

        Args:
            all_data: 包含所有sheet数据的列表

        Returns:
            经验年数字符串，如果未找到返回空字符串
        """
        candidates = []

        for data in all_data:
            df = data["df"]

            # 方法1: 查找经验关键词
            candidates.extend(self._extract_from_experience_labels(df))

            # 方法2: 从项目日期推算经验
            candidates.extend(self._extract_from_project_dates(df))

        if candidates:
            # 按置信度排序，选择最高的
            candidates.sort(key=lambda x: x[1], reverse=True)
            result = candidates[0][0].translate(self.trans_table)
            return result

        return ""

    def _extract_from_experience_labels(self, df: pd.DataFrame) -> List[tuple]:
        """从经验关键词附近提取经验值"""
        candidates = []

        for idx in range(min(60, len(df))):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if pd.notna(cell):
                    cell_str = str(cell)
                    if any(k in cell_str for k in KEYWORDS["experience"]):
                        # 排除说明文字
                        if self._is_explanation_text(cell_str):
                            continue

                        # 搜索数值
                        nearby_exp = self._search_experience_value(
                            df, idx, col, cell_str
                        )
                        candidates.extend(nearby_exp)

        return candidates

    def _extract_from_project_dates(self, df: pd.DataFrame) -> List[tuple]:
        """从项目日期推算经验"""
        candidates = []

        for idx in range(min(50, len(df))):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if isinstance(cell, datetime):
                    # 检查是否是项目开始日期
                    if 2015 <= cell.year <= 2024:
                        # 检查同行是否有项目描述
                        if self._has_project_context(df, idx):
                            # 从最早的项目日期推算经验年数
                            experience_years = 2024 - cell.year
                            if 1 <= experience_years <= 15:
                                # 对于合理的项目经验，给予更高置信度
                                confidence = 1.5 if experience_years >= 5 else 1.2
                                exp_str = f"{experience_years}年"
                                candidates.append((exp_str, confidence))

        return candidates

    def _search_experience_value(
        self, df: pd.DataFrame, row: int, col: int, cell_str: str
    ) -> List[tuple]:
        """搜索经验数值"""
        candidates = []

        for r_off in range(-3, 6):
            for c_off in range(-3, 30):
                r = row + r_off
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

        return candidates

    def _parse_experience_value(self, value: str) -> Optional[str]:
        """解析经验值"""
        value = str(value).strip()

        # 排除非经验值
        if any(exclude in value for exclude in ["以上", "未満", "◎", "○", "△", "経験"]):
            return None

        # 转换全角数字
        value = value.translate(self.trans_table)

        patterns = [
            (
                r"^(\d+)\s*年\s*(\d+)\s*ヶ月$",
                lambda m: f"{m.group(1)}年{m.group(2)}ヶ月",
            ),
            (
                r"^(\d+(?:\.\d+)?)\s*年$",
                lambda m: (
                    f"{float(m.group(1)):.0f}年"
                    if float(m.group(1)) == int(float(m.group(1)))
                    else f"{m.group(1)}年"
                ),
            ),
            (
                r"^(\d+(?:\.\d+)?)\s*$",
                lambda m: (
                    f"{float(m.group(1)):.0f}年"
                    if 1 <= float(m.group(1)) <= 40
                    else None
                ),
            ),
            (r"(\d+)\s*年\s*(\d+)\s*ヶ月", lambda m: f"{m.group(1)}年{m.group(2)}ヶ月"),
            (r"(\d+)\s*年", lambda m: f"{m.group(1)}年"),
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

    def _has_project_context(self, df: pd.DataFrame, row: int) -> bool:
        """检查是否有项目上下文"""
        row_data = df.iloc[row]
        row_text = " ".join([str(cell) for cell in row_data if pd.notna(cell)])

        project_keywords = ["システム", "開発", "業務", "プロジェクト"]
        return any(keyword in row_text for keyword in project_keywords)
