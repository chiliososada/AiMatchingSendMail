# -*- coding: utf-8 -*-
"""性别提取器"""

from typing import List, Dict, Any, Optional
import pandas as pd

from base.base_extractor import BaseExtractor
from base.constants import KEYWORDS


class GenderExtractor(BaseExtractor):
    """性别信息提取器"""

    def extract(self, all_data: List[Dict[str, Any]]) -> Optional[str]:
        """提取性别

        Args:
            all_data: 包含所有sheet数据的列表

        Returns:
            性别（"男性" 或 "女性"），如果未找到返回None
        """
        for data in all_data:
            df = data["df"]

            # 搜索性别信息
            for idx in range(min(30, len(df))):
                for col in range(len(df.columns)):
                    cell = df.iloc[idx, col]
                    if pd.notna(cell):
                        gender = self._check_gender_cell(df, idx, col, str(cell))
                        if gender:
                            return gender

        return None

    def _check_gender_cell(
        self, df: pd.DataFrame, row: int, col: int, cell_str: str
    ) -> Optional[str]:
        """检查单元格是否包含性别信息

        Args:
            df: DataFrame对象
            row: 行索引
            col: 列索引
            cell_str: 单元格内容

        Returns:
            性别字符串或None
        """
        cell_str = cell_str.strip()

        # 直接匹配性别值
        if cell_str in ["男", "男性"]:
            if self.has_nearby_keyword(df, row, col, KEYWORDS["gender"], radius=5):
                return "男性"
        elif cell_str in ["女", "女性"]:
            if self.has_nearby_keyword(df, row, col, KEYWORDS["gender"], radius=5):
                return "女性"

        # 如果单元格包含性别关键词，搜索附近的值
        elif any(k in cell_str for k in KEYWORDS["gender"]):
            return self._search_gender_value(df, row, col)

        return None

    def _search_gender_value(
        self, df: pd.DataFrame, row: int, col: int
    ) -> Optional[str]:
        """在指定位置附近搜索性别值

        Args:
            df: DataFrame对象
            row: 行索引
            col: 列索引

        Returns:
            性别字符串或None
        """
        for r_off in range(-2, 3):
            for c_off in range(-2, 10):
                r = row + r_off
                c = col + c_off

                if 0 <= r < len(df) and 0 <= c < len(df.columns):
                    value = df.iloc[r, c]
                    if pd.notna(value):
                        v_str = str(value).strip()
                        if v_str in ["男", "男性", "M", "Male"]:
                            return "男性"
                        elif v_str in ["女", "女性", "F", "Female"]:
                            return "女性"

        return None
