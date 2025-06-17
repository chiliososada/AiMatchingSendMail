# -*- coding: utf-8 -*-
"""来日年份提取器 - 修补版本：直接内置关键词"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
import re

# 直接定义关键词，避免导入问题
ARRIVAL_KEYWORDS = [
    "来日", "渡日", "入国", "日本滞在年数", "滞在年数", "在日年数",
    "来日年", "来日時期", "来日年月", "来日年度"
]

class ArrivalYearExtractorPatched:
    """来日年份信息提取器 - 修补版"""

    def __init__(self):
        self.trans_table = str.maketrans("０１２３４５６７８９", "0123456789")

    def extract(self, all_data: List[Dict[str, Any]], birthdate_result: Optional[str] = None) -> Optional[str]:
        """提取来日年份"""
        print(f"\n🔍 修补版来日年份提取器开始工作")
        print(f"   关键词: {ARRIVAL_KEYWORDS}")
        
        birth_year = None
        if birthdate_result:
            try:
                birth_year = datetime.strptime(birthdate_result, "%Y-%m-%d").year
                print(f"   排除出生年份: {birth_year}")
            except:
                pass

        candidates = []

        for data in all_data:
            df = data["df"]
            sheet_name = data.get("sheet_name", "Unknown")
            print(f"   处理Sheet: {sheet_name}")

            # 方法1: 查找"来日XX年"表述
            for idx in range(min(40, len(df))):
                for col in range(len(df.columns)):
                    cell = df.iloc[idx, col]
                    if pd.notna(cell):
                        cell_str = str(cell)
                        
                        # 检查是否包含来日年数表述
                        patterns = [
                            (r"来日.*?(\d{1,2})\s*年", 3.5),
                            (r"在日.*?(\d{1,2})\s*年", 3.0),
                            (r"滞在.*?(\d{1,2})\s*年", 2.5),
                        ]

                        for pattern, confidence in patterns:
                            match = re.search(pattern, cell_str)
                            if match:
                                years_in_japan = int(match.group(1))
                                if 1 <= years_in_japan <= 30:
                                    arrival_year = 2024 - years_in_japan
                                    candidates.append((str(arrival_year), confidence))
                                    print(f"   ✅ 从'{cell_str}'推算来日年份: {arrival_year}")

            # 方法2: 查找关键词附近的年份
            for idx in range(min(40, len(df))):
                for col in range(len(df.columns)):
                    cell = df.iloc[idx, col]
                    if pd.notna(cell):
                        cell_str = str(cell)
                        if any(k in cell_str for k in ARRIVAL_KEYWORDS):
                            print(f"   🔍 在行{idx}列{col}找到关键词: '{cell_str}'")
                            
                            # 搜索附近的年份
                            for r_off in range(-2, 5):
                                for c_off in range(-2, 15):
                                    r = idx + r_off
                                    c = col + c_off
                                    
                                    if 0 <= r < len(df) and 0 <= c < len(df.columns):
                                        value = df.iloc[r, c]
                                        if pd.notna(value):
                                            year = self._parse_year(str(value))
                                            if year and 1990 <= year <= 2024 and year != birth_year:
                                                distance = abs(r_off) + abs(c_off)
                                                confidence = max(0.5, 2.0 - distance * 0.1)
                                                candidates.append((str(year), confidence))
                                                print(f"   ✅ 在附近找到年份: {year} (置信度: {confidence:.2f})")

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            best_candidate = candidates[0]
            result = best_candidate[0]
            print(f"\n✅ 最佳来日年份: {result} (置信度: {best_candidate[1]:.2f})")
            return result

        print(f"\n❌ 未能提取到来日年份")
        return None

    def _parse_year(self, value: str) -> Optional[int]:
        """解析年份值"""
        value = value.strip().translate(self.trans_table)
        match = re.search(r'\b(19|20)\d{2}\b', value)
        if match:
            return int(match.group())
        return None
