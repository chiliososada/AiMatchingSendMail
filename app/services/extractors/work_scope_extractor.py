# -*- coding: utf-8 -*-
"""作业范围提取器"""

from typing import List, Dict, Any, Set
import pandas as pd
import re

from base.base_extractor import BaseExtractor


class WorkScopeExtractor(BaseExtractor):
    """作业范围信息提取器"""

    def __init__(self):
        super().__init__()
        # 工程阶段关键词
        self.design_keywords = [
            "基本設計",
            "詳細設計",
            "製造",
            "単体テスト",
            "結合テスト",
            "総合テスト",
            "運用保守",
            "要件定義",
            "基本设计",
            "详细设计",
            "単体試験",
            "結合試験",
            "総合試験",
            "運用",
            "保守",
            "要件",
            "定義",
        ]

        # 作业标记符号
        self.work_marks = ["●", "◯", "○", "◎"]

        # 标准化映射
        self.scope_mapping = {
            "基本设计": "基本設計",
            "详细设计": "詳細設計",
            "単体試験": "単体テスト",
            "結合試験": "結合テスト",
            "総合試験": "総合テスト",
            "運用": "運用保守",
            "保守": "運用保守",
            "要件": "要件定義",
            "定義": "要件定義",
        }

    def extract(self, all_data: List[Dict[str, Any]]) -> List[str]:
        """提取作业范围

        Args:
            all_data: 包含所有sheet数据的列表

        Returns:
            作业范围列表
        """
        all_scopes = set()

        for data in all_data:
            df = data["df"]
            sheet_name = data.get("sheet_name", "Unknown")

            print(f"\n🔍 开始作业范围提取 - Sheet: {sheet_name}")
            print(f"    表格大小: {df.shape[0]}行 x {df.shape[1]}列")

            # 查找包含工程阶段关键词的位置
            design_positions = self._find_design_positions(df)

            if design_positions:
                print(f"    找到 {len(design_positions)} 个工程阶段位置")

                # 对每个位置检查是否有作业标记
                for pos in design_positions:
                    scope = self._check_work_mark_in_column(df, pos)
                    if scope:
                        normalized_scope = self._normalize_scope(scope)
                        all_scopes.add(normalized_scope)
                        print(f"    ✓ 发现作业范围: {normalized_scope}")
            else:
                print("    未找到工程阶段列")

        # 转换为列表并排序（按照预定义的顺序）
        final_scopes = self._sort_scopes(list(all_scopes))

        print(f"\n✅ 最终提取的作业范围: {final_scopes}")
        return final_scopes

    def _find_design_positions(self, df: pd.DataFrame) -> List[Dict]:
        """查找包含工程阶段关键词的位置"""
        positions = []

        # 遍历整个表格查找关键词
        for row in range(len(df)):
            for col in range(len(df.columns)):
                cell = df.iloc[row, col]
                if pd.notna(cell):
                    cell_str = str(cell).strip()

                    # 检查是否包含工程阶段关键词
                    for keyword in self.design_keywords:
                        if keyword in cell_str:
                            # 记录位置和具体的关键词
                            positions.append(
                                {
                                    "row": row,
                                    "col": col,
                                    "value": cell_str,
                                    "keyword": keyword,
                                }
                            )
                            break

        return positions

    def _check_work_mark_in_column(self, df: pd.DataFrame, position: Dict) -> str:
        """检查该列下方是否有作业标记"""
        row = position["row"]
        col = position["col"]
        keyword = position["keyword"]

        # 搜索该列下方的内容（最多搜索999行）
        search_limit = min(row + 999, len(df))

        for check_row in range(row + 1, search_limit):
            cell = df.iloc[check_row, col]
            if pd.notna(cell):
                cell_str = str(cell).strip()

                # 检查是否包含作业标记
                if any(mark in cell_str for mark in self.work_marks):
                    # 返回原始的工程阶段关键词
                    return keyword

                # 如果遇到其他工程阶段关键词，停止搜索
                if any(k in cell_str for k in self.design_keywords if k != keyword):
                    break

                # 如果遇到明显的项目分隔（日期格式等），停止搜索
                if re.match(r"^\d{4}[年/]\d{1,2}[月/]", cell_str):
                    break

        return ""

    def _normalize_scope(self, scope: str) -> str:
        """标准化作业范围名称"""
        # 首先检查是否需要映射
        if scope in self.scope_mapping:
            return self.scope_mapping[scope]

        # 检查是否已经是标准格式
        standard_scopes = [
            "要件定義",
            "基本設計",
            "詳細設計",
            "製造",
            "単体テスト",
            "結合テスト",
            "総合テスト",
            "運用保守",
        ]

        if scope in standard_scopes:
            return scope

        # 如果包含标准格式的一部分，返回对应的标准格式
        for standard in standard_scopes:
            if standard in scope:
                return standard

        return scope

    def _sort_scopes(self, scopes: List[str]) -> List[str]:
        """按照开发流程顺序排序作业范围"""
        # 定义标准顺序
        order = [
            "要件定義",
            "基本設計",
            "詳細設計",
            "製造",
            "単体テスト",
            "結合テスト",
            "総合テスト",
            "運用保守",
        ]

        # 按照预定义顺序排序
        sorted_scopes = []
        for item in order:
            if item in scopes:
                sorted_scopes.append(item)

        # 添加不在预定义顺序中的项目（如果有）
        for scope in scopes:
            if scope not in sorted_scopes:
                sorted_scopes.append(scope)

        return sorted_scopes
