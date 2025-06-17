# -*- coding: utf-8 -*-
"""国籍提取器"""

from typing import List, Dict, Any, Optional
from collections import defaultdict
import pandas as pd

from base.base_extractor import BaseExtractor
from base.constants import KEYWORDS, VALID_NATIONALITIES


class NationalityExtractor(BaseExtractor):
    """国籍信息提取器"""

    def extract(self, all_data: List[Dict[str, Any]]) -> Optional[str]:
        """提取国籍

        Args:
            all_data: 包含所有sheet数据的列表

        Returns:
            国籍字符串，如果未找到返回None
        """
        candidates = []

        for data in all_data:
            df = data["df"]

            # 方法1: 扫描整个表格的所有国籍关键词
            candidates.extend(self._scan_for_nationalities(df))

            # 方法2: 查找国籍标签附近的值
            candidates.extend(self._search_near_labels(df))

        if candidates:
            # 统计每个国籍的总置信度
            nationality_scores = defaultdict(float)
            for nationality, conf in candidates:
                nationality_scores[nationality] += conf

            if nationality_scores:
                best_nationality = max(nationality_scores.items(), key=lambda x: x[1])
                return best_nationality[0]

        return None

    def _scan_for_nationalities(self, df: pd.DataFrame) -> List[tuple]:
        """扫描整个表格查找国籍"""
        candidates = []

        for idx in range(min(50, len(df))):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if pd.notna(cell):
                    cell_str = str(cell).strip()

                    # 直接检查是否是国籍值
                    if cell_str in VALID_NATIONALITIES:
                        # 计算上下文评分
                        context_score = self._calculate_context_score(df, idx, col)
                        total_confidence = max(1.0, context_score)
                        candidates.append((cell_str, total_confidence))

        return candidates

    def _search_near_labels(self, df: pd.DataFrame) -> List[tuple]:
        """在国籍标签附近搜索"""
        candidates = []

        for idx in range(min(40, len(df))):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if pd.notna(cell) and any(
                    k in str(cell) for k in KEYWORDS["nationality"]
                ):
                    # 搜索附近的国籍值
                    for r_off in range(-3, 6):
                        for c_off in range(-3, 15):
                            r = idx + r_off
                            c = col + c_off

                            if 0 <= r < len(df) and 0 <= c < len(df.columns):
                                value = df.iloc[r, c]
                                if pd.notna(value):
                                    value_str = str(value).strip()
                                    if value_str in VALID_NATIONALITIES:
                                        confidence = 3.0
                                        candidates.append((value_str, confidence))

        return candidates

    def _calculate_context_score(self, df: pd.DataFrame, row: int, col: int) -> float:
        """计算国籍的上下文评分"""
        context_score = 0

        # 检查同行是否有个人信息
        row_data = df.iloc[row]
        row_text = " ".join([str(cell) for cell in row_data if pd.notna(cell)])

        personal_keywords = ["氏名", "性別", "年齢", "最寄", "住所", "男", "女"]
        if any(keyword in row_text for keyword in personal_keywords):
            context_score += 2.0

        # 检查周围是否有个人信息
        for r_off in range(-3, 4):
            for c_off in range(-5, 6):
                r = row + r_off
                c = col + c_off

                if 0 <= r < len(df) and 0 <= c < len(df.columns):
                    nearby_cell = df.iloc[r, c]
                    if pd.notna(nearby_cell):
                        nearby_text = str(nearby_cell)
                        if any(
                            keyword in nearby_text
                            for keyword in ["氏名", "性別", "年齢", "学歴"]
                        ):
                            context_score += 1.0

        return context_score
