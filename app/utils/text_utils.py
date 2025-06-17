# -*- coding: utf-8 -*-
"""文本处理工具"""

import pandas as pd
from typing import List


def dataframe_to_text(df: pd.DataFrame) -> str:
    """将DataFrame转换为文本

    Args:
        df: pandas DataFrame对象

    Returns:
        转换后的文本字符串
    """
    text_parts = []

    for idx, row in df.iterrows():
        row_text = " ".join([str(cell) for cell in row if pd.notna(cell)])
        if row_text.strip():
            text_parts.append(row_text)

    return "\n".join(text_parts)


def normalize_text(text: str) -> str:
    """标准化文本

    Args:
        text: 原始文本

    Returns:
        标准化后的文本
    """
    # 去除多余空格
    text = " ".join(text.split())

    # 全角转半角
    # 这里可以添加更多的标准化逻辑

    return text.strip()
