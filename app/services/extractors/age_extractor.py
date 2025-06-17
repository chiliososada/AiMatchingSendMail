# -*- coding: utf-8 -*-
"""年龄提取器 - 修复版：支持从生年月日计算年龄"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict
import pandas as pd
import re

from base.base_extractor import BaseExtractor
from base.constants import KEYWORDS
from utils.date_utils import convert_excel_serial_to_date, calculate_age_from_birthdate


class AgeExtractor(BaseExtractor):
    """年龄信息提取器 - 修复版"""

    def extract(
        self, all_data: List[Dict[str, Any]], birthdate_result: Optional[str] = None
    ) -> str:
        """提取年龄，如果没有直接年龄信息，则从生年月日计算

        Args:
            all_data: 包含所有sheet数据的列表
            birthdate_result: 已提取的生年月日信息

        Returns:
            年龄字符串，如果未找到返回空字符串
        """
        candidates = []

        for data in all_data:
            df = data["df"]
            sheet_name = data.get("sheet_name", "Unknown")

            print(f"\n🔍 开始年龄提取 - Sheet: {sheet_name}")

            # 方法1: 扫描所有Date对象
            date_candidates = self._extract_from_date_objects(df)
            if date_candidates:
                print(f"    从日期对象提取到 {len(date_candidates)} 个候选年龄")
            candidates.extend(date_candidates)

            # 方法2: 扫描Excel序列日期数字
            serial_candidates = self._extract_from_serial_dates(df)
            if serial_candidates:
                print(f"    从序列日期提取到 {len(serial_candidates)} 个候选年龄")
            candidates.extend(serial_candidates)

            # 方法3: 传统的年龄标签搜索
            label_candidates = self._extract_from_age_labels(df)
            if label_candidates:
                print(f"    从年龄标签提取到 {len(label_candidates)} 个候选年龄")
            candidates.extend(label_candidates)

            # 方法4: 查找跨单元格的年龄信息
            cross_candidates = self._extract_from_cross_cells(df)
            if cross_candidates:
                print(f"    从跨单元格提取到 {len(cross_candidates)} 个候选年龄")
            candidates.extend(cross_candidates)

            # 方法5: 从整行文本中提取
            row_candidates = self._extract_from_row_text(df)
            if row_candidates:
                print(f"    从行文本提取到 {len(row_candidates)} 个候选年龄")
            candidates.extend(row_candidates)

        # 如果找到了直接的年龄信息，使用它
        if candidates:
            # 统计每个年龄的总置信度
            age_scores = defaultdict(float)
            for age, conf in candidates:
                age_scores[age] += conf

            # 选择置信度最高的年龄
            best_age = max(age_scores.items(), key=lambda x: x[1])
            print(f"\n✅ 从直接提取获得年龄: {best_age[0]} (置信度: {best_age[1]:.2f})")
            return best_age[0]

        # 如果没有直接年龄信息，但有生年月日，则计算年龄
        if birthdate_result:
            calculated_age = self._calculate_age_from_birthdate(birthdate_result)
            if calculated_age:
                print(f"\n✅ 从生年月日计算得到年龄: {calculated_age}")
                return calculated_age

        print("\n❌ 未能提取到年龄")
        return ""

    def _calculate_age_from_birthdate(self, birthdate_str: str) -> Optional[str]:
        """从生年月日计算年龄"""
        try:
            birthdate = datetime.strptime(birthdate_str, "%Y-%m-%d")
            current_date = datetime.now()

            age = current_date.year - birthdate.year
            if (current_date.month, current_date.day) < (
                birthdate.month,
                birthdate.day,
            ):
                age -= 1

            # 验证年龄合理性
            if 15 <= age <= 80:
                print(f"    计算年龄: {birthdate_str} → {age}岁")
                return str(age)
            else:
                print(f"    计算出的年龄不合理: {age}")
                return None

        except ValueError as e:
            print(f"    生年月日格式错误: {e}")
            return None

    def _extract_from_row_text(self, df: pd.DataFrame) -> List[tuple]:
        """从整行文本中提取年龄（处理跨单元格的情况）"""
        candidates = []

        # 只搜索前30行
        for row in range(min(30, len(df))):
            # 将整行合并为文本
            row_text = ""
            for col in range(len(df.columns)):
                cell = df.iloc[row, col]
                if pd.notna(cell):
                    row_text += str(cell).strip() + " "

            if not row_text.strip():
                continue

            # 定义多种年龄模式
            patterns = [
                (r"満\s*(\d{1,2})\s*[才歳歲]", 3.5),  # "満 30 才"
                (r"満\s*(\d{1,2})(?:\s|$)", 3.0),  # "満 30"
                (r"(\d{1,2})\s*[才歳歲]", 2.5),  # "30 才"
                (r"年齢[：:]\s*(\d{1,2})", 2.5),  # "年齢：30"
                (r"年齢\s*(\d{1,2})", 2.0),  # "年齢 30"
                (r"(?:^|\s)(\d{1,2})(?:\s|$)", 1.0),  # 独立的数字
            ]

            for pattern, confidence in patterns:
                matches = re.finditer(pattern, row_text)
                for match in matches:
                    age_str = match.group(1)
                    age = int(age_str)
                    if 18 <= age <= 65:
                        # 检查是否有年龄相关上下文
                        if self._has_age_keywords_in_row(row_text) or confidence >= 2.5:
                            candidates.append((str(age), confidence))
                            print(
                                f"    行{row}: 在行文本中找到年龄 {age} (模式: {pattern})"
                            )
                            break  # 每行只取第一个匹配

        return candidates

    def _has_age_keywords_in_row(self, row_text: str) -> bool:
        """检查行文本中是否包含年龄相关关键词"""
        age_keywords = ["年齢", "年龄", "満", "满", "歳", "才", "歲", "Age", "生年月"]
        return any(keyword in row_text for keyword in age_keywords)

    def _extract_from_cross_cells(self, df: pd.DataFrame) -> List[tuple]:
        """从跨单元格的年龄信息中提取年龄"""
        candidates = []

        # 搜索包含"満"或年龄相关关键词的位置
        for idx in range(min(30, len(df))):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if pd.notna(cell):
                    cell_str = str(cell).strip()

                    # 检查是否包含"満"字
                    if "満" in cell_str or "满" in cell_str:
                        # 搜索右侧相邻的单元格
                        age_found = self._search_age_in_adjacent_cells(df, idx, col)
                        if age_found:
                            candidates.append((age_found, 3.0))
                            print(
                                f"    行{idx}, 列{col}: 在'満'右侧找到年龄 {age_found}"
                            )

                    # 检查是否是纯数字（可能的年龄）
                    if re.match(r"^\d{1,2}$", cell_str):
                        age_val = int(cell_str)
                        if 18 <= age_val <= 65:
                            # 检查周围是否有年龄相关上下文
                            if self._has_age_context_nearby(df, idx, col):
                                candidates.append((str(age_val), 2.5))
                                print(
                                    f"    行{idx}, 列{col}: 找到独立数字年龄 {age_val}"
                                )

                    # 检查是否包含年龄关键词
                    if any(k in cell_str for k in KEYWORDS["age"]):
                        # 搜索附近的数字
                        nearby_ages = self._search_numbers_nearby_age_keyword(
                            df, idx, col
                        )
                        if nearby_ages:
                            candidates.extend(nearby_ages)
                            print(
                                f"    行{idx}, 列{col}: 在年龄关键词附近找到 {len(nearby_ages)} 个年龄"
                            )

        return candidates

    def _search_age_in_adjacent_cells(
        self, df: pd.DataFrame, row: int, col: int
    ) -> Optional[str]:
        """在相邻单元格中搜索年龄数值"""
        # 搜索右侧的几个单元格
        for c_offset in range(1, 5):  # 扩大搜索范围到右侧5个单元格
            c = col + c_offset
            if c < len(df.columns):
                cell = df.iloc[row, c]
                if pd.notna(cell):
                    cell_str = str(cell).strip()

                    # 检查是否是数字
                    match = re.match(r"^(\d{1,2})$", cell_str)
                    if match:
                        age = int(match.group(1))
                        if 18 <= age <= 65:
                            # 再检查是否有"才"或"歳"在附近
                            if self._has_age_unit_nearby(df, row, c):
                                return str(age)
                            # 即使没有单位，如果左侧有"満"，也认为是年龄
                            elif col >= 0 and pd.notna(df.iloc[row, col]):
                                left_cell = str(df.iloc[row, col])
                                if "満" in left_cell or "满" in left_cell:
                                    return str(age)

                    # 检查是否包含数字和单位
                    match = re.search(r"(\d{1,2})\s*[歳才歲]", cell_str)
                    if match:
                        age = int(match.group(1))
                        if 18 <= age <= 65:
                            return str(age)

        return None

    def _search_numbers_nearby_age_keyword(
        self, df: pd.DataFrame, row: int, col: int
    ) -> List[tuple]:
        """在年龄关键词附近搜索数字"""
        candidates = []

        # 扩大搜索范围
        for r_offset in range(-3, 4):
            for c_offset in range(-5, 10):  # 向右搜索更多列
                r = row + r_offset
                c = col + c_offset

                if 0 <= r < len(df) and 0 <= c < len(df.columns):
                    cell = df.iloc[r, c]
                    if pd.notna(cell):
                        cell_str = str(cell).strip()

                        # 纯数字检查
                        if re.match(r"^\d{1,2}$", cell_str):
                            age = int(cell_str)
                            if 18 <= age <= 65:
                                # 计算距离，越近置信度越高
                                distance = abs(r_offset) + abs(c_offset)
                                confidence = 2.0 / (1 + distance * 0.2)
                                candidates.append((str(age), confidence))

        return candidates

    def _has_age_unit_nearby(self, df: pd.DataFrame, row: int, col: int) -> bool:
        """检查附近是否有年龄单位（才、歳）"""
        age_units = ["才", "歳", "歲"]

        # 检查右侧单元格
        for c_offset in range(1, 3):
            c = col + c_offset
            if c < len(df.columns):
                cell = df.iloc[row, c]
                if pd.notna(cell):
                    if any(unit in str(cell) for unit in age_units):
                        return True

        # 检查同一单元格（可能数字和单位在一起）
        cell = df.iloc[row, col]
        if pd.notna(cell) and any(unit in str(cell) for unit in age_units):
            return True

        return False

    def _has_age_context_nearby(self, df: pd.DataFrame, row: int, col: int) -> bool:
        """检查附近是否有年龄相关上下文（增强版）"""
        age_keywords = ["生年月", "年齢", "年龄", "歳", "才", "歲", "満", "满", "Age"]

        # 检查更大的范围
        for r_off in range(-3, 4):
            for c_off in range(-8, 8):
                r = row + r_off
                c = col + c_off
                if 0 <= r < len(df) and 0 <= c < len(df.columns):
                    context_cell = df.iloc[r, c]
                    if pd.notna(context_cell):
                        context_str = str(context_cell)
                        if any(k in context_str for k in age_keywords):
                            return True

        return False

    def _extract_from_date_objects(self, df: pd.DataFrame) -> List[tuple]:
        """从Date对象中提取年龄"""
        candidates = []

        for idx in range(min(30, len(df))):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if isinstance(cell, datetime) or isinstance(cell, pd.Timestamp):
                    if 1950 <= cell.year <= 2010:
                        age = calculate_age_from_birthdate(cell)
                        if age:
                            context_score = self._get_age_context_score(df, idx, col)
                            confidence = 2.0 + context_score * 0.5
                            candidates.append((str(age), confidence))

        return candidates

    def _extract_from_serial_dates(self, df: pd.DataFrame) -> List[tuple]:
        """从Excel序列日期中提取年龄"""
        candidates = []

        for idx in range(min(30, len(df))):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if pd.notna(cell) and isinstance(cell, (int, float)):
                    # 检查是否可能是Excel序列日期
                    if 18000 <= cell <= 50000:
                        converted_date = convert_excel_serial_to_date(cell)
                        if converted_date:
                            age = calculate_age_from_birthdate(converted_date)
                            if age:
                                # 检查上下文
                                if self._has_age_context(df, idx, col):
                                    candidates.append((str(age), 3.0))

        return candidates

    def _extract_from_age_labels(self, df: pd.DataFrame) -> List[tuple]:
        """从年龄标签附近提取年龄"""
        candidates = []

        for idx in range(min(30, len(df))):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if pd.notna(cell):
                    cell_str = str(cell)
                    if any(k in cell_str for k in KEYWORDS["age"]):
                        # 搜索附近的年龄值
                        nearby_ages = self._search_age_nearby(df, idx, col)
                        candidates.extend(nearby_ages)

        return candidates

    def _search_age_nearby(self, df: pd.DataFrame, row: int, col: int) -> List[tuple]:
        """在指定位置附近搜索年龄值"""
        candidates = []

        # 扩大搜索范围
        for r_offset in range(-2, 6):
            for c_offset in range(-2, 15):  # 向右搜索更多
                r = row + r_offset
                c = col + c_offset

                if 0 <= r < len(df) and 0 <= c < len(df.columns):
                    value = df.iloc[r, c]
                    if pd.notna(value):
                        if isinstance(value, datetime) or isinstance(
                            value, pd.Timestamp
                        ):
                            age = calculate_age_from_birthdate(value)
                            if age:
                                candidates.append((str(age), 2.5))
                        else:
                            age = self._parse_age_value(str(value))
                            if age:
                                candidates.append((age, 2.0))

        return candidates

    def _parse_age_value(self, value: str) -> Optional[str]:
        """解析年龄值"""
        value = str(value).strip()

        # 排除明显不是年龄的内容
        if len(value) > 15 or "年月" in value or "西暦" in value or "19" in value:
            return None

        # 多种年龄格式的匹配
        patterns = [
            (r"満\s*(\d{1,2})\s*[歳才歲]", 1),  # "満 30 歳"
            (r"満\s*(\d{1,2})(?:\s|$)", 1),  # "満 30"
            (r"(\d{1,2})\s*[歳才歲]", 1),  # "30歳"
            (r"^(\d{1,2})$", 1),  # 纯数字
        ]

        for pattern, group_idx in patterns:
            match = re.search(pattern, value)
            if match:
                age = int(match.group(group_idx))
                if 18 <= age <= 65:
                    return str(age)

        return None

    def _has_age_context(self, df: pd.DataFrame, row: int, col: int) -> bool:
        """检查是否有年龄相关的上下文"""
        age_keywords = ["生年月", "年齢", "年龄", "歳", "才", "歲", "満", "满"]

        for r_off in range(-2, 3):
            for c_off in range(-5, 5):
                r = row + r_off
                c = col + c_off
                if 0 <= r < len(df) and 0 <= c < len(df.columns):
                    context_cell = df.iloc[r, c]
                    if pd.notna(context_cell):
                        context_str = str(context_cell)
                        if any(k in context_str for k in age_keywords):
                            return True

        return False

    def _get_age_context_score(self, df: pd.DataFrame, row: int, col: int) -> float:
        """获取年龄上下文评分"""
        personal_keywords = (
            KEYWORDS["name"]
            + KEYWORDS["gender"]
            + KEYWORDS["age"]
            + [
                "学歴",
                "最終学歴",
                "住所",
                "最寄駅",
                "最寄",
                "経験",
                "実務",
                "国籍",
                "来日",
            ]
        )

        return self.get_context_score(df, row, col, personal_keywords)
