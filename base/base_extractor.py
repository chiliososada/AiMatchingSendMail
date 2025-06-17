# -*- coding: utf-8 -*-
"""基础提取器类"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import pandas as pd


class BaseExtractor(ABC):
    """所有提取器的基类"""

    def __init__(self):
        """初始化基础提取器"""
        # 全角转半角的转换表
        self.trans_table = str.maketrans("０１２３４５６７８９", "0123456789")

    @abstractmethod
    def extract(self, all_data: List[Dict[str, Any]]) -> Any:
        """提取信息的抽象方法

        Args:
            all_data: 包含所有sheet数据的列表

        Returns:
            提取的信息
        """
        pass

    def has_nearby_keyword(
        self, df: pd.DataFrame, row: int, col: int, keywords: List[str], radius: int = 5
    ) -> bool:
        """检查附近是否有关键词

        Args:
            df: DataFrame对象
            row: 行索引
            col: 列索引
            keywords: 关键词列表
            radius: 搜索半径

        Returns:
            是否找到关键词
        """
        for r in range(max(0, row - radius), min(len(df), row + radius + 1)):
            for c in range(
                max(0, col - radius), min(len(df.columns), col + radius + 1)
            ):
                cell = df.iloc[r, c]
                if pd.notna(cell) and any(k in str(cell) for k in keywords):
                    return True
        return False

    def get_context_score(
        self, df: pd.DataFrame, row: int, col: int, context_keywords: List[str]
    ) -> float:
        """计算上下文评分

        Args:
            df: DataFrame对象
            row: 行索引
            col: 列索引
            context_keywords: 上下文关键词

        Returns:
            上下文评分
        """
        score = 0.0

        for r in range(max(0, row - 3), min(len(df), row + 4)):
            for c in range(max(0, col - 5), min(len(df.columns), col + 6)):
                cell = df.iloc[r, c]
                if pd.notna(cell):
                    cell_str = str(cell)
                    for keyword in context_keywords:
                        if keyword in cell_str:
                            score += 1.0

        return score
