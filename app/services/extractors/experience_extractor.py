# -*- coding: utf-8 -*-
"""经验提取器 - 修正版：正确搜索项目日期范围"""

from typing import List, Dict, Any, Optional
from datetime import datetime, date
import pandas as pd
import re

from app.base.base_extractor import BaseExtractor


class ExperienceExtractor(BaseExtractor):
    """经验信息提取器 - 修正版"""

    def extract(self, all_data: List[Dict[str, Any]]) -> str:
        """提取经验年数

        Args:
            all_data: 包含所有sheet数据的列表

        Returns:
            经验年数字符串，如果未找到返回空字符串
        """
        print("\n" + "=" * 60)
        print("🔍 开始基于项目日期计算经验年数 (修正版)")
        print("=" * 60)

        all_dates = []

        for sheet_idx, data in enumerate(all_data):
            df = data["df"]
            sheet_name = data.get("sheet_name", f"Sheet_{sheet_idx}")

            print(f"\n📊 处理数据表 {sheet_idx+1}/{len(all_data)}: '{sheet_name}'")
            print(f"   表格大小: {len(df)} 行 x {len(df.columns)} 列")

            # 步骤1: 找到设计阶段关键词所在的行号
            design_rows = self._find_design_rows(df)

            if design_rows:
                print(f"   ✅ 找到设计阶段行: {design_rows}")
                # 修正：扩大搜索范围，从第一个设计行开始，而不是最后一个
                start_row = min(design_rows)  # 从最早的设计行开始
                search_end = len(df)  # 搜索到表格末尾
                dates = self._extract_dates_in_range(df, start_row, search_end)
            else:
                print(f"   ❌ 未找到设计阶段关键词，全表搜索")
                dates = self._extract_dates_from_all_rows(df)

            if dates:
                print(f"   ✅ 提取到 {len(dates)} 个项目日期")
                all_dates.extend(dates)
            else:
                print(f"   ❌ 未找到项目日期")

        # 步骤3: 计算经验年数
        if all_dates:
            experience_years = self._calculate_experience_from_dates(all_dates)
            if experience_years:
                print(f"\n🎯 计算结果: {experience_years}")
                return experience_years

        print(f"\n❌ 无法计算经验年数")
        return ""

    def _find_design_rows(self, df: pd.DataFrame) -> List[int]:
        """查找包含设计阶段关键词的行号"""
        print(f"     🔍 查找设计阶段关键词...")

        design_keywords = [
            "基本設計",
            "詳細設計",
            "基本设计",
            "详细设计",
            "要件定義",
            "要求定义",
            "需求定义",
            "製造",
            "制造",
            "开发",
            "実装",
            "实装",
            "単体テスト",
            "結合テスト",
            "総合テスト",
            "单体测试",
            "结合测试",
            "总合测试",
            "测试",
            # 添加更多项目相关关键词
            "開発",
            "システム",
            "API",
            "バッチ",
            "プロジェクト",
        ]

        design_rows = []

        for idx in range(len(df)):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if pd.notna(cell):
                    cell_str = str(cell)
                    for keyword in design_keywords:
                        if keyword in cell_str:
                            if idx not in design_rows:
                                design_rows.append(idx)
                                print(
                                    f"       找到 '{keyword}' 在行 {idx}: '{cell_str[:50]}...'"
                                )
                            break

        return sorted(design_rows)

    def _extract_dates_in_range(
        self, df: pd.DataFrame, start_row: int, end_row: int
    ) -> List[datetime]:
        """在指定范围内提取项目日期"""
        print(f"     🔍 在指定范围搜索项目日期...")
        print(f"       搜索范围: 行 {start_row} - {end_row}")

        dates = []

        # 重点关注前几列，特别是第2列（索引1）和第3列（索引2）
        focus_columns = [0, 1, 2, 3, 4]  # 重点搜索前5列

        for idx in range(start_row, min(end_row, len(df))):
            # 先搜索重点列
            for col in focus_columns:
                if col < len(df.columns):
                    row_dates = self._extract_dates_from_cell(df, idx, col)
                    if row_dates:
                        dates.extend(row_dates)
                        print(
                            f"       行 {idx}, 列 {col} 找到日期: {[d.strftime('%Y/%m') for d in row_dates]}"
                        )

            # 如果前几列没找到，再搜索其他列
            if not dates or len(dates) < 3:  # 如果日期太少，继续搜索
                for col in range(5, len(df.columns)):
                    row_dates = self._extract_dates_from_cell(df, idx, col)
                    if row_dates:
                        dates.extend(row_dates)
                        print(
                            f"       行 {idx}, 列 {col} 找到日期: {[d.strftime('%Y/%m') for d in row_dates]}"
                        )

        return dates

    def _extract_dates_from_all_rows(self, df: pd.DataFrame) -> List[datetime]:
        """从全表搜索项目日期"""
        print(f"     🔍 全表搜索项目日期...")

        dates = []

        for idx in range(len(df)):
            for col in range(len(df.columns)):
                row_dates = self._extract_dates_from_cell(df, idx, col)
                if row_dates:
                    dates.extend(row_dates)
                    print(
                        f"       行 {idx}, 列 {col} 找到日期: {[d.strftime('%Y/%m') for d in row_dates]}"
                    )

        return dates

    def _extract_dates_from_cell(
        self, df: pd.DataFrame, row_idx: int, col_idx: int
    ) -> List[datetime]:
        """从单个单元格提取日期"""
        dates = []
        cell = df.iloc[row_idx, col_idx]

        # 方法1: 直接的datetime对象
        if isinstance(cell, (datetime, date)):
            if 2010 <= cell.year <= 2025:  # 扩大合理的项目年份范围
                if hasattr(cell, "month"):
                    dates.append(datetime(cell.year, cell.month, 1))
                else:
                    dates.append(datetime(cell.year, 1, 1))

        # 方法2: 字符串中的日期模式
        elif pd.notna(cell):
            cell_str = str(cell)
            extracted_dates = self._parse_date_patterns(cell_str)
            dates.extend(extracted_dates)

        return dates

    def _parse_date_patterns(self, text: str) -> List[datetime]:
        """从文本中解析各种日期模式"""
        dates = []

        # 转换全角数字
        text = text.translate(self.trans_table)

        # 各种日期模式 - 扩展更多格式
        date_patterns = [
            # 年月日格式
            (
                r"(\d{4})[年/\-.](\d{1,2})[月/\-.](\d{1,2})",
                lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))),
            ),
            # 年月格式
            (
                r"(\d{4})[年/\-.](\d{1,2})",
                lambda m: datetime(int(m.group(1)), int(m.group(2)), 1),
            ),
            (
                r"(\d{4})/(\d{1,2})",
                lambda m: datetime(int(m.group(1)), int(m.group(2)), 1),
            ),
            (
                r"(\d{4})\.(\d{1,2})",
                lambda m: datetime(int(m.group(1)), int(m.group(2)), 1),
            ),
            (
                r"(\d{4})-(\d{1,2})",
                lambda m: datetime(int(m.group(1)), int(m.group(2)), 1),
            ),
            # 期间格式：2020/04～2021/03
            (
                r"(\d{4})/(\d{1,2})\s*[～〜~\-]\s*(\d{4})/(\d{1,2})",
                lambda m: [
                    datetime(int(m.group(1)), int(m.group(2)), 1),
                    datetime(int(m.group(3)), int(m.group(4)), 1),
                ],
            ),
            # 年份格式（更严格的条件）
            (
                r"\b(\d{4})\b",
                lambda m: (
                    datetime(int(m.group(1)), 1, 1)
                    if 2010 <= int(m.group(1)) <= 2025
                    else None
                ),
            ),
        ]

        for pattern, converter in date_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                try:
                    result = converter(match)
                    if isinstance(result, list):
                        # 处理期间格式返回的列表
                        for date_obj in result:
                            if date_obj and 2010 <= date_obj.year <= 2025:
                                dates.append(date_obj)
                    elif result and 2010 <= result.year <= 2025:
                        dates.append(result)
                except (ValueError, TypeError):
                    continue

        return dates

    def _calculate_experience_from_dates(self, dates: List[datetime]) -> Optional[str]:
        """从项目日期计算经验年数"""
        print(f"\n📋 计算经验年数:")

        # 去重并排序
        unique_dates = list(set(dates))
        sorted_dates = sorted(unique_dates)

        print(f"   去重后的项目日期: {[d.strftime('%Y/%m') for d in sorted_dates]}")

        if not sorted_dates:
            return None

        earliest_date = sorted_dates[0]
        latest_date = sorted_dates[-1]

        print(f"   最早项目日期: {earliest_date.strftime('%Y/%m')}")
        print(f"   最晚项目日期: {latest_date.strftime('%Y/%m')}")

        # 计算到当前时间的经验年数
        current_date = datetime.now()

        # 从最早项目开始计算
        total_months = (current_date.year - earliest_date.year) * 12 + (
            current_date.month - earliest_date.month
        )
        experience_years = total_months / 12

        print(f"   从最早项目到现在: {experience_years:.1f} 年")

        # 验证合理性
        if experience_years <= 0:
            return None
        elif experience_years > 30:
            # 如果超过30年，可能有错误，使用保守估计
            experience_years = min(20, experience_years)
            print(f"   调整后的经验年数: {experience_years:.1f} 年")

        # 格式化输出
        years = int(experience_years)
        months = round((experience_years - years) * 12)

        if months == 0:
            result = f"{years}年"
        elif months >= 12:
            result = f"{years + 1}年"
        else:
            result = f"{years}年{months}ヶ月"

        print(f"   最终经验年数: {result}")
        return result
