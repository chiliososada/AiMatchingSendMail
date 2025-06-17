# -*- coding: utf-8 -*-
"""经验提取器 - 修复重复提取问题并支持研修时间减法"""

from typing import List, Dict, Any, Optional
from datetime import datetime, date
import pandas as pd
import re

from app.base.base_extractor import BaseExtractor


class ExperienceExtractor(BaseExtractor):
    """经验信息提取器 - 修复重复提取问题并支持研修时间减法"""

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

        # 步骤3：计算经验年数（包含研修时间减法）
        if all_project_dates:
            experience_years = self._calculate_experience_from_project_dates(
                all_project_dates, all_data
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
        for idx in range(start_row, len(df)):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if pd.notna(cell):
                    cell_str = str(cell)

                    # 检查是否是"現在"关键字
                    if "現在" in cell_str and col in current_keyword_columns:
                        if current_date not in dates:
                            dates.append(current_date)
                            print(f"       找到現在日期: 行{idx} 列{col}")
                        continue

                    # 提取普通日期
                    parsed_date = self._parse_single_date(cell_str)
                    if parsed_date and parsed_date not in dates:
                        dates.append(parsed_date)
                        print(
                            f"       找到日期: 行{idx} 列{col} - {parsed_date.strftime('%Y/%m')}"
                        )

        return sorted(list(set(dates)))

    def _find_current_keyword_columns(self, df: pd.DataFrame) -> List[int]:
        """找到包含'現在'关键字的列"""
        current_columns = []
        for col in range(len(df.columns)):
            for idx in range(len(df)):
                cell = df.iloc[idx, col]
                if pd.notna(cell) and "現在" in str(cell):
                    if col not in current_columns:
                        current_columns.append(col)
                    break
        return current_columns

    def _parse_single_date(self, text: str) -> Optional[datetime]:
        """解析单个日期字符串"""
        text = str(text).strip()

        # 日期解析模式，按优先级排序
        date_patterns = [
            # 1. 标准日期格式
            (
                r"(\d{4})[年/\-.](\d{1,2})[月/\-.](\d{1,2})",
                lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))),
            ),
            # 2. 年月格式
            (
                r"(\d{4})[年/\-.](\d{1,2})[月]?",
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
        self, project_dates: List[datetime], all_data: List[Dict[str, Any]]
    ) -> Optional[str]:
        """从项目日期计算经验年数（包含研修时间减法）"""
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
        print(f"   初步计算经验年数: {experience_years:.1f} 年")

        # 合理性检查
        if total_months <= 0:
            print(f"   ❌ 经验月数不合理: {total_months}")
            return None
        elif experience_years > 40:
            print(f"   ⚠️  经验年数过长: {experience_years:.1f} 年，限制为20年")
            total_months = min(total_months, 20 * 12)
            experience_years = total_months / 12

        # 🆕 新增：减去研修时间
        print(f"\n📚 检查并减去研修时间...")
        adjusted_months = self._subtract_training_periods(all_data, total_months)
        if adjusted_months != total_months:
            print(f"   ✂️  减去研修时间后: {total_months} → {adjusted_months} 个月")
            total_months = adjusted_months
        else:
            print(f"   ℹ️  未发现需要减去的研修时间")

        # 重新计算
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

    def _subtract_training_periods(
        self, all_data: List[Dict[str, Any]], total_months: int
    ) -> int:
        """从总项目时间中减去研修时间"""

        training_months = 0

        # 1. 搜索研修相关内容的关键词
        training_keywords = [
            "日本語学校",
            "日本語の学習",
            "来日準備",
            "研究生",
            "修士を履修",
            "大学で",
            "学習",
            "研修",
            "勉強",
            "準備期間",
            "国士舘大学",
            "西安工程大学",
            "大学",
            "学校",
            "院卒",
            "履修",
            "卒業",
        ]

        print(f"   搜索研修关键词: {training_keywords}")

        for sheet_idx, data in enumerate(all_data):
            df = data["df"]
            sheet_name = data.get("sheet_name", f"Sheet_{sheet_idx}")

            print(f"   检查表格 '{sheet_name}' 中的研修时间...")

            # 2. 扫描所有单元格，查找研修相关内容
            for idx in range(len(df)):
                for col in range(len(df.columns)):
                    cell = df.iloc[idx, col]
                    if pd.notna(cell):
                        cell_str = str(cell)

                        # 检查是否包含研修关键词
                        if any(keyword in cell_str for keyword in training_keywords):

                            # 3. 提取这个研修时间段
                            training_period = self._extract_training_duration(cell_str)
                            if training_period:
                                training_months += training_period
                                print(
                                    f"     📚 检测到研修时间: {cell_str[:50]}... ({training_period}个月)"
                                )

        print(f"   总研修时间: {training_months} 个月")
        return max(0, total_months - training_months)

    def _extract_training_duration(self, text: str) -> int:
        """提取研修时间长度（月数）"""

        print(f"       正在解析研修时间: '{text[:100]}...'")

        # 模式1: "24ヶ月" 直接月数
        month_pattern = r"(\d+)\s*[ヶか]月"
        month_match = re.search(month_pattern, text)
        if month_match:
            months = int(month_match.group(1))
            print(f"       找到直接月数: {months}个月")
            return months

        # 模式2: "2017/04～2019/3" 或 "2017/04～2020/03" 时间段
        period_pattern = r"(\d{4})[/.](\d{1,2})\s*[～〜~]\s*(\d{4})[/.](\d{1,2})"
        total_months = 0

        # 找到所有时间段并累加
        for match in re.finditer(period_pattern, text):
            start_year, start_month = int(match.group(1)), int(match.group(2))
            end_year, end_month = int(match.group(3)), int(match.group(4))

            try:
                start_date = datetime(start_year, start_month, 1)
                end_date = datetime(end_year, end_month, 1)

                # 计算月数差
                months = (end_date.year - start_date.year) * 12 + (
                    end_date.month - start_date.month
                )
                if months > 0:
                    total_months += months
                    print(
                        f"       找到时间段: {start_year}/{start_month}～{end_year}/{end_month} = {months}个月"
                    )
            except ValueError:
                print(
                    f"       日期解析错误: {start_year}/{start_month}～{end_year}/{end_month}"
                )

        if total_months > 0:
            print(f"       累计研修时间: {total_months}个月")
            return total_months

        # 模式3: 单个年份范围，如 "2017年～2020年"
        year_range_pattern = r"(\d{4})\s*[年～〜~]\s*(\d{4})"
        year_match = re.search(year_range_pattern, text)
        if year_match:
            start_year = int(year_match.group(1))
            end_year = int(year_match.group(2))
            months = (end_year - start_year) * 12
            if months > 0:
                print(
                    f"       找到年份范围: {start_year}年～{end_year}年 = {months}个月"
                )
                return months

        print(f"       未找到有效的研修时间")
        return 0
