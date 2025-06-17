# app/services/extractors/base_extractor.py
from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional
import pandas as pd
import re


class BaseExtractor(ABC):
    """提取器基类"""

    def __init__(self):
        """初始化基类"""
        pass

    @abstractmethod
    def extract(self, all_data: List[Dict[str, Any]]) -> Any:
        """
        提取信息的抽象方法

        Args:
            all_data: 包含所有sheet数据的列表

        Returns:
            提取的信息
        """
        pass

    def _find_cell_position(
        self,
        df: pd.DataFrame,
        keywords: List[str],
        max_row: int = 20,
        max_col: int = 10,
    ) -> Optional[tuple]:
        """
        查找包含指定关键词的单元格位置

        Args:
            df: DataFrame
            keywords: 关键词列表
            max_row: 最大搜索行数
            max_col: 最大搜索列数

        Returns:
            (row, col) 或 None
        """
        search_rows = min(len(df), max_row)
        search_cols = min(len(df.columns), max_col)

        for row in range(search_rows):
            for col in range(search_cols):
                cell = df.iloc[row, col]
                if pd.notna(cell):
                    cell_str = str(cell).strip()
                    for keyword in keywords:
                        if keyword in cell_str:
                            return (row, col)
        return None

    def _get_adjacent_value(
        self, df: pd.DataFrame, row: int, col: int, direction: str = "right"
    ) -> Optional[str]:
        """
        获取相邻单元格的值

        Args:
            df: DataFrame
            row: 行索引
            col: 列索引
            direction: 方向 (right, down, left, up)

        Returns:
            单元格值或None
        """
        directions = {"right": (0, 1), "down": (1, 0), "left": (0, -1), "up": (-1, 0)}

        if direction not in directions:
            return None

        dr, dc = directions[direction]
        new_row = row + dr
        new_col = col + dc

        if 0 <= new_row < len(df) and 0 <= new_col < len(df.columns):
            cell = df.iloc[new_row, new_col]
            if pd.notna(cell):
                return str(cell).strip()

        return None

    def _clean_text(self, text: str) -> str:
        """清理文本"""
        if not text:
            return ""

        # 移除多余空白
        text = re.sub(r"\s+", " ", text)

        # 移除特殊字符
        text = text.replace("\u3000", " ")  # 全角空格
        text = text.replace("\xa0", " ")  # 不间断空格

        return text.strip()
