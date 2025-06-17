# -*- coding: utf-8 -*-
"""出生年月日提取器 - 针对劉ZY简历格式的修复版"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
import re

from base.base_extractor import BaseExtractor
from utils.date_utils import convert_excel_serial_to_date


class BirthdateExtractor(BaseExtractor):
    """出生年月日信息提取器 - 修复版"""

    def __init__(self):
        super().__init__()
        self.birthdate_keywords = [
            "生年月日",
            "生年月",
            "生年",
            "誕生日",
            "出生日期",
            "出生年月日",
            "Birth Date",
            "Birthday",
            "DOB",
            "Date of Birth",
        ]

    def extract(self, all_data: List[Dict[str, Any]]) -> Optional[str]:
        """提取出生年月日"""
        for data in all_data:
            df = data["df"]
            sheet_name = data.get("sheet_name", "Unknown")

            print(f"\n🔍 开始出生年月日提取 - Sheet: {sheet_name}")
            print(f"    表格大小: {df.shape[0]}行 x {df.shape[1]}列")

            # 查找生年月关键字位置
            keyword_positions = self._find_birthdate_keyword_positions(df)

            if not keyword_positions:
                print("    未找到生年月关键字，使用全表扫描")
                return self._extract_from_full_scan(df)

            print(f"    找到 {len(keyword_positions)} 个生年月关键字位置")

            # 对每个关键字位置进行详细搜索
            for pos in keyword_positions:
                result = self._extract_from_keyword_position_enhanced(df, pos)
                if result:
                    return result

        print("\n❌ 未能提取到出生年月日")
        return None

    def _find_birthdate_keyword_positions(self, df: pd.DataFrame) -> List[Dict]:
        """查找生年月关键字的位置"""
        positions = []

        for row in range(len(df)):
            for col in range(len(df.columns)):
                cell = df.iloc[row, col]
                if pd.notna(cell):
                    cell_str = str(cell).strip()
                    for keyword in self.birthdate_keywords:
                        if keyword in cell_str:
                            positions.append(
                                {
                                    "row": row,
                                    "col": col,
                                    "value": cell_str,
                                    "keyword": keyword,
                                }
                            )
                            print(f"      发现关键字 '{keyword}' 在: 行{row}, 列{col}")
                            break
        return positions

    def _extract_from_keyword_position_enhanced(
        self, df: pd.DataFrame, pos: Dict
    ) -> Optional[str]:
        """从关键字位置提取出生年月日 - 增强版"""
        print(
            f"\n    详细检查位置: 行{pos['row']}, 列{pos['col']}, 内容: '{pos['value']}'"
        )

        # 针对劉ZY简历的特殊格式进行搜索
        # 数据结构：生年月日标签在一行，年份在下一行，满年龄在再下一行

        base_row = pos["row"]
        base_col = pos["col"]

        # 详细记录搜索过程
        print(f"      基准位置: 行{base_row}, 列{base_col}")

        # 搜索范围：关键字下方5行，左右各5列
        for row_offset in range(1, 6):  # 下方1-5行
            for col_offset in range(-5, 6):  # 左右各5列
                search_row = base_row + row_offset
                search_col = base_col + col_offset

                if 0 <= search_row < len(df) and 0 <= search_col < len(df.columns):
                    cell = df.iloc[search_row, search_col]

                    if pd.notna(cell):
                        print(
                            f"        检查[{search_row},{search_col}]: {repr(cell)} (类型: {type(cell).__name__})"
                        )

                        # 提取年份信息
                        year_info = self._extract_year_from_cell_enhanced(cell)

                        if year_info:
                            print(f"        ✓ 找到年份信息: {year_info}")

                            # 尝试在附近寻找月份和日期信息
                            complete_date = self._try_build_complete_date(
                                df, search_row, search_col, year_info
                            )

                            if complete_date:
                                if self._validate_birthdate_relaxed(complete_date):
                                    print(f"\n✅ 成功提取出生年月日: {complete_date}")
                                    return complete_date
                                else:
                                    print(f"        日期验证失败: {complete_date}")

        return None

    def _extract_year_from_cell_enhanced(self, cell) -> Optional[Dict]:
        """从单元格提取年份信息 - 增强版"""
        try:
            # 处理日期对象
            if isinstance(cell, (datetime, pd.Timestamp)):
                if 1950 <= cell.year <= 2015:
                    return {
                        "year": cell.year,
                        "month": cell.month,
                        "day": cell.day,
                        "source": "datetime",
                    }

            # 处理Excel序列日期
            if isinstance(cell, (int, float)) and 18000 <= cell <= 50000:
                converted_date = convert_excel_serial_to_date(cell)
                if converted_date and 1950 <= converted_date.year <= 2015:
                    return {
                        "year": converted_date.year,
                        "month": converted_date.month,
                        "day": converted_date.day,
                        "source": "excel_serial",
                    }

            # 处理文本和数字
            cell_str = str(cell).strip()
            return self._extract_year_from_text_enhanced(cell_str)

        except Exception as e:
            print(f"          提取错误: {e}")
            return None

    def _extract_year_from_text_enhanced(self, text: str) -> Optional[Dict]:
        """从文本提取年份 - 增强版"""
        text = str(text).strip()

        # 模式1: 1994年格式 (针对劉ZY简历)
        match = re.search(r"(19[5-9]\d|20[0-1]\d)年", text)
        if match:
            year = int(match.group(1))
            return {"year": year, "source": "year_nen"}

        # 模式2: 完整日期格式
        patterns = [
            # yyyy年mm月dd日
            (
                r"(19[5-9]\d|20[0-1]\d)[年/](0?[1-9]|1[0-2])[月/](0?[1-9]|[12]\d|3[01])日?",
                lambda m: {
                    "year": int(m.group(1)),
                    "month": int(m.group(2)),
                    "day": int(m.group(3)),
                    "source": "full_date",
                },
            ),
            # yyyy.mm.dd
            (
                r"(19[5-9]\d|20[0-1]\d)[\.\-/](0?[1-9]|1[0-2])[\.\-/](0?[1-9]|[12]\d|3[01])",
                lambda m: {
                    "year": int(m.group(1)),
                    "month": int(m.group(2)),
                    "day": int(m.group(3)),
                    "source": "numeric_date",
                },
            ),
            # 只有年份
            (
                r"\b(19[5-9]\d|20[0-1]\d)\b",
                lambda m: {"year": int(m.group(1)), "source": "year_only"},
            ),
        ]

        for pattern, parser in patterns:
            match = re.search(pattern, text)
            if match:
                return parser(match)

        return None

    def _try_build_complete_date(
        self, df: pd.DataFrame, year_row: int, year_col: int, year_info: Dict
    ) -> Optional[str]:
        """尝试构建完整的出生日期"""
        year = year_info["year"]
        month = year_info.get("month", 1)
        day = year_info.get("day", 1)

        # 如果已经有完整日期，直接返回
        if "month" in year_info and "day" in year_info:
            try:
                date_obj = datetime(year, month, day)
                return date_obj.strftime("%Y-%m-%d")
            except ValueError:
                pass

        # 尝试在附近寻找月份和日期信息
        print(f"          尝试在年份位置[{year_row},{year_col}]附近寻找月日信息")

        # 搜索附近3x3区域
        for r_off in range(-1, 3):
            for c_off in range(-1, 3):
                r = year_row + r_off
                c = year_col + c_off

                if 0 <= r < len(df) and 0 <= c < len(df.columns):
                    cell = df.iloc[r, c]
                    if pd.notna(cell):
                        cell_str = str(cell).strip()
                        print(f"            检查附近[{r},{c}]: {repr(cell_str)}")

                        # 寻找月份信息
                        month_match = re.search(r"(\d{1,2})月", cell_str)
                        if month_match:
                            month = int(month_match.group(1))
                            print(f"            找到月份: {month}")

                        # 寻找日期信息
                        day_match = re.search(r"(\d{1,2})日", cell_str)
                        if day_match:
                            day = int(day_match.group(1))
                            print(f"            找到日期: {day}")

        # 构建最终日期
        try:
            # 验证月份和日期的合理性
            if not (1 <= month <= 12):
                month = 1
            if not (1 <= day <= 31):
                day = 1

            date_obj = datetime(year, month, day)
            result = date_obj.strftime("%Y-%m-%d")
            print(f"          构建的日期: {result}")
            return result

        except ValueError as e:
            print(f"          构建日期失败: {e}")
            # 如果构建失败，使用默认值
            try:
                date_obj = datetime(year, 1, 1)
                return date_obj.strftime("%Y-%m-%d")
            except ValueError:
                return None

    def _extract_from_full_scan(self, df: pd.DataFrame) -> Optional[str]:
        """全表扫描备用方案"""
        print("      执行全表扫描...")

        candidates = []

        # 扫描前20行寻找年份
        for row in range(min(20, len(df))):
            for col in range(len(df.columns)):
                cell = df.iloc[row, col]
                if pd.notna(cell):
                    year_info = self._extract_year_from_cell_enhanced(cell)
                    if year_info:
                        # 简单验证：年份在合理范围内
                        year = year_info["year"]
                        if 1950 <= year <= 2010:
                            # 计算年龄看是否合理
                            age = 2024 - year
                            if 15 <= age <= 75:
                                date_str = f"{year}-01-01"
                                candidates.append((date_str, age, row, col))
                                print(
                                    f"      候选: {date_str} (行{row},列{col}, 年龄{age})"
                                )

        if candidates:
            # 选择年龄最合理的候选（接近30岁的优先）
            best_candidate = min(candidates, key=lambda x: abs(x[1] - 30))
            print(
                f"\n✅ 全表扫描选择: {best_candidate[0]} (行{best_candidate[2]},列{best_candidate[3]})"
            )
            return best_candidate[0]

        return None

    def _validate_birthdate_relaxed(self, date_str: str) -> bool:
        """验证出生日期 - 放宽条件"""
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")

            # 检查年份范围
            if not (1950 <= date_obj.year <= 2015):
                print(f"          年份超出范围: {date_obj.year}")
                return False

            # 检查是否是未来日期
            if date_obj > datetime.now():
                print(f"          未来日期: {date_str}")
                return False

            # 检查年龄范围（10-80岁）
            age = datetime.now().year - date_obj.year
            if not (10 <= age <= 80):
                print(f"          年龄超出范围: {age}")
                return False

            return True

        except ValueError as e:
            print(f"          日期格式错误: {e}")
            return False
