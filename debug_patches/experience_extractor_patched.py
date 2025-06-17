# -*- coding: utf-8 -*-
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
        print(f"\n🔍 修补版经验提取器开始工作")
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
            print(f"\n✅ 最佳经验: {result}")
            return result

        print(f"\n❌ 未能提取到经验信息")
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
            (r"^(\d+)\s*年\s*(\d+)\s*ヶ月$", lambda m: f"{m.group(1)}年{m.group(2)}ヶ月"),
            (r"^(\d+(?:\.\d+)?)\s*年$", lambda m: f"{m.group(1)}年"),
            (r"^(\d+(?:\.\d+)?)\s*$", lambda m: f"{m.group(1)}年" if 1 <= float(m.group(1)) <= 40 else None),
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
