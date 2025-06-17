# -*- coding: utf-8 -*-
"""来日年份提取器 - 增强调试版本：添加详细的控制台输出"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict
import pandas as pd
import re

from app.base.constants import KEYWORDS
from app.base.base_extractor import BaseExtractor
from app.utils.date_utils import convert_excel_serial_to_date


class ArrivalYearExtractor(BaseExtractor):
    """来日年份信息提取器 - 增强调试版本"""

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
        print("🔍 开始来日年份提取器执行流程")
        print("=" * 60)

        # 首先检查关键词导入状态
        print("\n📋 步骤1: 检查关键词导入状态")
        try:
            arrival_keywords = KEYWORDS.get("arrival", [])
            print(f"✅ 成功获取来日关键词: {arrival_keywords}")
            if not arrival_keywords:
                print("⚠️  警告: 来日关键词列表为空!")
        except Exception as e:
            print(f"❌ 关键词导入失败: {e}")
            print("🔧 尝试使用备用关键词...")
            arrival_keywords = [
                "来日",
                "渡日",
                "入国",
                "日本滞在年数",
                "滞在年数",
                "在日年数",
            ]
            print(f"🆘 使用备用关键词: {arrival_keywords}")

        # 处理出生年份
        print("\n📋 步骤2: 处理出生年份信息")
        birth_year = None
        if birthdate_result:
            try:
                birth_year = datetime.strptime(birthdate_result, "%Y-%m-%d").year
                print(f"✅ 解析出生年份: {birth_year} (将排除此年份)")
            except Exception as e:
                print(f"⚠️  生年月日解析失败: {e}")
                print(f"   输入值: '{birthdate_result}'")
        else:
            print("ℹ️  未提供生年月日信息")

        candidates = []

        print(f"\n📋 步骤3: 开始处理 {len(all_data)} 个数据表")

        for sheet_idx, data in enumerate(all_data):
            df = data["df"]
            sheet_name = data.get("sheet_name", f"Sheet_{sheet_idx}")

            print(f"\n📊 处理数据表 {sheet_idx+1}/{len(all_data)}: '{sheet_name}'")
            print(f"   表格大小: {len(df)} 行 x {len(df.columns)} 列")

            # 方法1: 查找"来日XX年"这样的表述
            print(f"\n   🔍 方法1: 查找年数表述...")
            years_candidates = self._extract_from_years_expression(df)
            if years_candidates:
                print(
                    f"   ✅ 从年数表述提取到 {len(years_candidates)} 个候选年份: {years_candidates}"
                )
            else:
                print(f"   ❌ 未从年数表述中找到候选年份")
            candidates.extend(years_candidates)

            # 方法2: 查找来日关键词附近的年份（排除出生年份）
            print(f"\n   🔍 方法2: 查找来日关键词附近的年份...")
            label_candidates = self._extract_from_arrival_labels(df, birth_year)
            if label_candidates:
                print(
                    f"   ✅ 从来日标签提取到 {len(label_candidates)} 个候选年份: {label_candidates}"
                )
            else:
                print(f"   ❌ 未从来日标签中找到候选年份")
            candidates.extend(label_candidates)

            # 方法3: 从日期对象中提取（排除出生年份）
            print(f"\n   🔍 方法3: 从日期对象中提取...")
            date_candidates = self._extract_from_date_objects(df, birth_year)
            if date_candidates:
                print(
                    f"   ✅ 从日期对象提取到 {len(date_candidates)} 个候选年份: {date_candidates}"
                )
            else:
                print(f"   ❌ 未从日期对象中找到候选年份")
            candidates.extend(date_candidates)

            # 方法4: 扫描Excel序列日期数字（排除出生年份）
            print(f"\n   🔍 方法4: 扫描Excel序列日期...")
            serial_candidates = self._extract_from_serial_dates(df, birth_year)
            if serial_candidates:
                print(
                    f"   ✅ 从序列日期提取到 {len(serial_candidates)} 个候选年份: {serial_candidates}"
                )
            else:
                print(f"   ❌ 未从序列日期中找到候选年份")
            candidates.extend(serial_candidates)

        print(f"\n📋 步骤4: 汇总所有候选结果")
        print(f"   总候选数量: {len(candidates)}")
        if candidates:
            print(f"   所有候选: {candidates}")

            # 统计每个年份的总置信度
            year_scores = defaultdict(float)
            for year, conf in candidates:
                year_scores[year] += conf
                print(f"   年份 {year}: 置信度 +{conf}")

            if year_scores:
                print(f"\n📋 步骤5: 计算最终结果")
                for year, total_conf in year_scores.items():
                    print(f"   {year}年: 总置信度 {total_conf:.2f}")

                best_year = max(year_scores.items(), key=lambda x: x[1])
                print(f"\n🎯 最终结果: {best_year[0]} (总置信度: {best_year[1]:.2f})")
                print("=" * 60)
                return best_year[0]

        print(f"\n❌ 未能提取到来日年份")
        print("=" * 60)
        return None

    def _extract_from_years_expression(self, df: pd.DataFrame) -> List[tuple]:
        """提取"来日XX年"或"在日XX年"这样的表述"""
        print(f"      🔎 正在查找年数表述...")
        candidates = []

        for idx in range(min(40, len(df))):
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
                                    f"      ✅ [{idx},{col}] 从'{cell_str}'推算来日年份: {arrival_year} (模式: {pattern})"
                                )

        return candidates

    def _extract_from_arrival_labels(
        self, df: pd.DataFrame, birth_year: Optional[int]
    ) -> List[tuple]:
        """从来日标签附近提取年份（排除出生年份）"""
        print(f"      🔎 正在查找来日关键词附近的年份...")
        candidates = []

        try:
            arrival_keywords = KEYWORDS.get("arrival", [])
        except:
            arrival_keywords = [
                "来日",
                "渡日",
                "入国",
                "日本滞在年数",
                "滞在年数",
                "在日年数",
            ]

        print(f"      使用关键词: {arrival_keywords}")

        for idx in range(min(40, len(df))):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if pd.notna(cell):
                    cell_str = str(cell)
                    found_keywords = [k for k in arrival_keywords if k in cell_str]

                    if found_keywords:
                        print(
                            f"      🎯 [{idx},{col}] 发现关键词 {found_keywords} 在: '{cell_str}'"
                        )
                        nearby_years = self._search_year_nearby(
                            df, idx, col, birth_year
                        )
                        if nearby_years:
                            candidates.extend(nearby_years)
                            print(
                                f"      ✅ 在附近找到 {len(nearby_years)} 个年份: {nearby_years}"
                            )
                        else:
                            print(f"      ❌ 附近未找到有效年份")
        return candidates

    def _search_year_nearby(
        self, df: pd.DataFrame, row: int, col: int, birth_year: Optional[int]
    ) -> List[tuple]:
        """在指定位置附近搜索年份值（排除出生年份）"""
        candidates = []
        print(f"        🔍 搜索 [{row},{col}] 附近的年份...")

        for r_off in range(-2, 5):
            for c_off in range(-2, 25):
                r = row + r_off
                c = col + c_off
                if 0 <= r < len(df) and 0 <= c < len(df.columns):
                    cell = df.iloc[r, c]
                    if pd.notna(cell):
                        # 尝试提取4位年份
                        cell_str = str(cell)
                        year_matches = re.findall(r"\b(19\d{2}|20[0-2]\d)\b", cell_str)

                        for year_str in year_matches:
                            year = int(year_str)
                            if 1990 <= year <= 2024 and year != birth_year:
                                candidates.append((year_str, 2.0))
                                print(
                                    f"        ✅ [{r},{c}] 找到年份: {year} (值:'{cell_str}')"
                                )
                            elif year == birth_year:
                                print(f"        ⚠️  [{r},{c}] 跳过出生年份: {year}")

        return candidates

    def _extract_from_date_objects(
        self, df: pd.DataFrame, birth_year: Optional[int]
    ) -> List[tuple]:
        """从日期对象中提取来日年份（排除出生年份）"""
        print(f"      🔎 正在查找日期对象...")
        candidates = []

        for idx in range(min(30, len(df))):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if pd.notna(cell) and hasattr(cell, "year"):
                    if 1990 <= cell.year <= 2024 and cell.year != birth_year:
                        # 检查是否有来日相关上下文
                        has_arrival_context = self._has_arrival_context(df, idx, col)
                        has_age_context = self._has_age_context(df, idx, col)

                        print(f"      📅 [{idx},{col}] 发现日期: {cell.year}")
                        print(f"        来日上下文: {has_arrival_context}")
                        print(f"        年龄上下文: {has_age_context}")

                        if has_arrival_context:
                            # 如果也有年龄上下文，可能是生年月日，降低置信度
                            confidence = 1.5 if has_age_context else 2.5
                            candidates.append((str(cell.year), confidence))
                            print(
                                f"        ✅ 添加候选: {cell.year} (置信度: {confidence})"
                            )

        return candidates

    def _extract_from_serial_dates(
        self, df: pd.DataFrame, birth_year: Optional[int]
    ) -> List[tuple]:
        """从Excel序列日期中提取来日年份（排除出生年份）"""
        print(f"      🔎 正在查找Excel序列日期...")
        candidates = []

        for idx in range(min(30, len(df))):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if pd.notna(cell) and isinstance(cell, (int, float)):
                    # 检查是否可能是Excel序列日期（1982-2037年的范围）
                    if 30000 <= cell <= 50000:
                        converted_date = convert_excel_serial_to_date(cell)
                        if converted_date and 1990 <= converted_date.year <= 2024:
                            print(
                                f"      📊 [{idx},{col}] 序列日期 {cell} → {converted_date.year}"
                            )

                            if (
                                converted_date.year != birth_year
                                and self._has_arrival_context(df, idx, col)
                            ):
                                candidates.append((str(converted_date.year), 3.0))
                                print(f"        ✅ 添加候选: {converted_date.year}")
                            else:
                                print(f"        ❌ 跳过: 出生年份或无来日上下文")

        return candidates

    def _has_arrival_context(self, df: pd.DataFrame, row: int, col: int) -> bool:
        """检查是否有来日相关的上下文"""
        try:
            arrival_keywords = KEYWORDS.get("arrival", [])
        except:
            arrival_keywords = [
                "来日",
                "渡日",
                "入国",
                "日本滞在年数",
                "滞在年数",
                "在日年数",
            ]

        has_context = self.has_nearby_keyword(df, row, col, arrival_keywords, radius=5)
        print(f"        🔍 检查来日上下文 [{row},{col}]: {has_context}")
        return has_context

    def _has_age_context(self, df: pd.DataFrame, row: int, col: int) -> bool:
        """检查是否有年龄相关的上下文"""
        age_keywords = ["生年月", "年齢", "歳", "才"]
        has_context = self.has_nearby_keyword(df, row, col, age_keywords, radius=5)
        print(f"        🔍 检查年龄上下文 [{row},{col}]: {has_context}")
        return has_context
