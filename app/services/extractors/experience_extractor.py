# -*- coding: utf-8 -*-
"""经验提取器 - 修复重复提取问题"""

from typing import List, Dict, Any, Optional
from datetime import datetime, date
import pandas as pd
import re

from app.base.base_extractor import BaseExtractor


class ExperienceExtractor(BaseExtractor):
    """经验信息提取器 - 修复重复提取问题"""

    def extract(self, all_data: List[Dict[str, Any]]) -> str:
        """提取经验年数

        Args:
            all_data: 包含所有sheet数据的列表

        Returns:
            经验年数字符串，如果未找到返回空字符串
        """
        print("\n" + "=" * 60)
        print("🔍 开始修复重复提取问题的经验年数计算")
        print("=" * 60)

        all_project_dates = []

        for sheet_idx, data in enumerate(all_data):
            df = data["df"]
            sheet_name = data.get("sheet_name", f"Sheet_{sheet_idx}")

            print(f"\n📊 处理数据表 {sheet_idx+1}/{len(all_data)}: '{sheet_name}'")
            print(f"   表格大小: {len(df)} 行 x {len(df.columns)} 列")

            # 步骤1：从下向上搜索项目关键词
            project_keyword_rows = self._find_all_project_keyword_rows(df)

            if project_keyword_rows:
                print(f"   ✅ 找到项目关键词在行: {project_keyword_rows}")

                # 步骤2：从最早的关键词行向后提取所有日期
                start_row = min(project_keyword_rows)
                project_dates = self._extract_all_dates_after_row_fixed(df, start_row)

                if project_dates:
                    print(
                        f"   ✅ 从行{start_row}向后提取到 {len(project_dates)} 个项目日期"
                    )
                    all_project_dates.extend(project_dates)
                else:
                    print(f"   ❌ 未找到项目日期")
            else:
                print(f"   ❌ 未找到项目关键词")

        # 步骤3：计算经验年数
        if all_project_dates:
            experience_years = self._calculate_experience_from_project_dates(
                all_project_dates
            )
            if experience_years:
                print(f"\n🎯 计算结果: {experience_years}")
                return experience_years

        print(f"\n❌ 无法计算经验年数")
        return ""

    def _find_all_project_keyword_rows(self, df: pd.DataFrame) -> List[int]:
        """找到所有包含项目关键词的行号"""
        print(f"     🔍 搜索所有项目关键词行...")

        project_keywords = [
            "基本設計",
            "詳細設計",
            "要件定義",
            "実装",
            "開発",
            "システム",
            "プロジェクト",
            "案件",
            "API",
            "アプリ",
            "Web",
            "バッチ",
        ]

        keyword_rows = []

        for idx in range(len(df)):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if pd.notna(cell):
                    cell_str = str(cell)
                    for keyword in project_keywords:
                        if keyword in cell_str:
                            if idx not in keyword_rows:
                                keyword_rows.append(idx)
                                print(
                                    f"       找到 '{keyword}' 在行 {idx}: '{cell_str[:50]}...'"
                                )
                            break

        return sorted(keyword_rows)

    def _extract_all_dates_after_row_fixed(
        self, df: pd.DataFrame, start_row: int
    ) -> List[datetime]:
        """从指定行向后提取所有日期 - 修复重复问题"""
        print(f"     🔍 从行{start_row}向后提取所有日期...")

        dates = []
        current_date = datetime.now()

        # 先检查哪些列包含"現在"关键字
        current_keyword_columns = self._find_current_keyword_columns(df)
        print(f"       包含'現在'的列: {current_keyword_columns}")

        # 从start_row开始到表格结束
        for row_idx in range(start_row, len(df)):
            for col_idx in range(len(df.columns)):
                cell = df.iloc[row_idx, col_idx]

                if pd.notna(cell):
                    cell_str = str(cell)

                    # 检查"現在"关键字
                    current_keywords = [
                        "現在",
                        "现在",
                        "至今",
                        "到现在",
                        "present",
                        "current",
                    ]
                    is_current = False

                    if col_idx in current_keyword_columns:
                        for current_keyword in current_keywords:
                            if current_keyword in cell_str:
                                dates.append(
                                    datetime(current_date.year, current_date.month, 1)
                                )
                                print(
                                    f"       行{row_idx}, 列{col_idx} '現在'转换为: {current_date.strftime('%Y/%m')}"
                                )
                                is_current = True
                                break

                    if not is_current:
                        # 修复：避免重复提取，每个单元格只提取一次
                        extracted_date = self._extract_single_date_from_cell(cell)
                        if extracted_date:
                            dates.append(extracted_date)
                            print(
                                f"       行{row_idx}, 列{col_idx} 提取日期: {extracted_date.strftime('%Y/%m')} ('{cell_str}')"
                            )

        # 去重并排序
        unique_dates = sorted(list(set(dates)))
        print(f"     去重后的项目日期: {[d.strftime('%Y/%m') for d in unique_dates]}")

        return unique_dates

    def _find_current_keyword_columns(self, df: pd.DataFrame) -> set:
        """找到包含"現在"关键字的列"""
        current_keyword_columns = set()
        current_keywords = ["現在", "现在", "至今", "到现在", "present", "current"]

        for row_idx in range(len(df)):
            for col_idx in range(len(df.columns)):
                cell = df.iloc[row_idx, col_idx]
                if pd.notna(cell):
                    cell_str = str(cell)
                    for current_keyword in current_keywords:
                        if current_keyword in cell_str:
                            current_keyword_columns.add(col_idx)
                            break

        return current_keyword_columns

    def _extract_single_date_from_cell(self, cell) -> Optional[datetime]:
        """从单元格提取单个日期 - 修复重复问题"""

        # 优先处理datetime对象，避免字符串解析的重复问题
        if isinstance(cell, (datetime, date)):
            if 1980 <= cell.year <= 2030:
                if hasattr(cell, "month"):
                    return datetime(cell.year, cell.month, 1)
                else:
                    return datetime(cell.year, 1, 1)

        # 只有当不是datetime对象时，才进行字符串解析
        elif pd.notna(cell):
            cell_str = str(cell)

            # 修复：避免处理datetime对象的字符串表示
            if "GMT" in cell_str or "日本标准时间" in cell_str:
                # 这是datetime对象的字符串表示，跳过
                return None

            # 进行字符串日期解析
            return self._parse_single_date_from_text(cell_str)

        return None

    def _parse_single_date_from_text(self, text: str) -> Optional[datetime]:
        """从文本解析单个日期 - 修复重复匹配问题"""

        # 转换全角数字
        text = text.translate(self.trans_table)

        # 修复：使用优先级顺序，找到第一个匹配就返回，避免重复
        date_patterns = [
            # 1. 最具体的：年月日格式
            (
                r"(\d{4})[年/\-.](\d{1,2})[月/\-.](\d{1,2})日?",
                lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))),
            ),
            # 2. 年月格式
            (
                r"(\d{4})[年/\-.](\d{1,2})月?",
                lambda m: datetime(int(m.group(1)), int(m.group(2)), 1),
            ),
            (
                r"(\d{4})/(\d{1,2})(?:/\d{1,2})?",
                lambda m: datetime(int(m.group(1)), int(m.group(2)), 1),
            ),
            (
                r"(\d{4})\.(\d{1,2})(?:\.\d{1,2})?",
                lambda m: datetime(int(m.group(1)), int(m.group(2)), 1),
            ),
            (
                r"(\d{4})-(\d{1,2})(?:-\d{1,2})?",
                lambda m: datetime(int(m.group(1)), int(m.group(2)), 1),
            ),
            # 3. 期间格式 - 返回开始日期
            (
                r"(\d{4})[/\-.](\d{1,2})\s*[～〜~\-]\s*(\d{4})[/\-.](\d{1,2})",
                lambda m: datetime(int(m.group(1)), int(m.group(2)), 1),
            ),
            # 4. 年份格式 - 最后考虑，避免误匹配时区等
            (
                r"\b(\d{4})\b",
                lambda m: (
                    datetime(int(m.group(1)), 1, 1)
                    if 1980 <= int(m.group(1)) <= 2030
                    else None
                ),
            ),
        ]

        # 按优先级顺序尝试，找到第一个匹配就返回
        for pattern, converter in date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    result = converter(match)
                    if result and 1980 <= result.year <= 2030:
                        return result
                except (ValueError, TypeError):
                    continue

        return None

    def _calculate_experience_from_project_dates(
        self, project_dates: List[datetime]
    ) -> Optional[str]:
        """从项目日期计算经验年数"""
        print(f"\n📋 从项目日期计算经验年数:")
        print(f"   所有项目日期: {[d.strftime('%Y/%m') for d in project_dates]}")

        if not project_dates:
            return None

        # 排序日期
        sorted_dates = sorted(project_dates)
        earliest_date = sorted_dates[0]
        latest_date = sorted_dates[-1]

        print(f"   最早项目日期: {earliest_date.strftime('%Y/%m')}")
        print(f"   最晚项目日期: {latest_date.strftime('%Y/%m')}")

        # 使用最早项目日期作为工作开始时间
        current_date = datetime.now()

        # 计算总月数
        total_months = (current_date.year - earliest_date.year) * 12 + (
            current_date.month - earliest_date.month
        )

        # 如果当前日期的日数小于开始日期的日数，减去一个月
        if current_date.day < earliest_date.day:
            total_months -= 1

        experience_years = total_months / 12

        print(f"   从最早项目到现在: {total_months} 个月")
        print(f"   计算经验年数: {experience_years:.1f} 年")

        # 合理性检查
        if total_months <= 0:
            print(f"   ❌ 经验月数不合理: {total_months}")
            return None
        elif experience_years > 40:
            print(f"   ⚠️  经验年数过长: {experience_years:.1f} 年，限制为20年")
            total_months = min(total_months, 20 * 12)
            experience_years = total_months / 12

        # 格式化输出
        years = int(experience_years)
        months = total_months % 12

        if months == 0:
            result = f"{years}年"
        else:
            result = f"{years}年{months}ヶ月"

        print(f"   最终经验年数: {result}")
        return result
