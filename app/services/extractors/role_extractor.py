# -*- coding: utf-8 -*-
"""角色（役割）提取器 - 改进版"""

from typing import List, Dict, Any, Set, Optional, Tuple
import pandas as pd
import re

from base.base_extractor import BaseExtractor


class RoleExtractor(BaseExtractor):
    """角色信息提取器"""

    def __init__(self):
        super().__init__()
        # 工程阶段关键词（用于定位作业范围）
        self.design_keywords = [
            "基本設計",
            "詳細設計",
            "製造",
            "単体テスト",
            "結合テスト",
            "総合テスト",
            "運用保守",
            "要件定義",
            "作業範囲",
        ]

        # 角色关键词
        self.role_keywords = ["PM", "PL", "SL", "TL", "BSE", "SE", "PG"]

        # 角色级别映射（数字越大，级别越高）
        self.role_levels = {
            "PM": 6,  # Project Manager - 最高级别
            "PL": 5,  # Project Leader
            "SL": 4,  # Sub Leader
            "TL": 3,  # Team Leader
            "BSE": 2.5,  # Bridge System Engineer
            "SE": 2,  # System Engineer
            "PG": 1,  # Programmer - 最低级别
        }

        # 角色的全称映射
        self.role_full_names = {
            "PM": ["Project Manager", "プロジェクトマネージャー", "プロマネ"],
            "PL": ["Project Leader", "プロジェクトリーダー"],
            "SL": ["Sub Leader", "サブリーダー", "副リーダー"],
            "TL": ["Team Leader", "チームリーダー"],
            "BSE": ["Bridge System Engineer", "ブリッジSE", "Bridge SE"],
            "SE": ["System Engineer", "システムエンジニア"],
            "PG": ["Programmer", "プログラマー", "プログラマ"],
        }

        # 角色列标题关键词
        self.role_column_keywords = [
            "役割",
            "役　割",
            "担当",
            "ポジション",
            "Position",
            "Role",
            "職種",
            "職位",
        ]

    def extract(self, all_data: List[Dict[str, Any]]) -> List[str]:
        """提取角色

        Args:
            all_data: 包含所有sheet数据的列表

        Returns:
            角色列表（按级别排序）
        """
        all_roles = set()
        debug_info = []  # 收集调试信息

        for data in all_data:
            df = data["df"]
            sheet_name = data.get("sheet_name", "Unknown")

            print(f"\n🔍 开始角色提取 - Sheet: {sheet_name}")
            print(f"    表格大小: {df.shape[0]}行 x {df.shape[1]}列")

            # 方法1：查找标记为"役割"的列
            role_columns = self._find_role_columns_by_header(df)
            if role_columns:
                print(f"    找到 {len(role_columns)} 个角色列（通过标题）")
                for col_info in role_columns:
                    roles = self._extract_roles_from_column_range(
                        df, col_info["col"], col_info["row"] + 1, len(df)
                    )
                    if roles:
                        all_roles.update(roles)
                        print(f"    ✓ 从列{col_info['col']}发现角色: {roles}")
                        debug_info.append(
                            f"方法1: 从役割列{col_info['col']}提取到{roles}"
                        )

            # 方法2：查找作业范围附近的角色
            design_positions = self._find_design_positions(df)
            if design_positions:
                print(f"    找到 {len(design_positions)} 个作业范围位置")
                for design_pos in design_positions:
                    # 在作业范围同行查找角色
                    roles = self._extract_roles_from_design_row(df, design_pos)
                    if roles:
                        all_roles.update(roles)
                        print(f"    ✓ 从作业范围行发现角色: {roles}")
                        debug_info.append(
                            f"方法2: 从作业范围行{design_pos['row']}提取到{roles}"
                        )

            # 方法3：查找包含多个角色的列
            if len(all_roles) < 2:  # 如果找到的角色太少，使用更激进的方法
                print("    使用方法3：查找包含角色的列")
                role_rich_columns = self._find_columns_with_roles(df)
                for col in role_rich_columns:
                    roles = self._extract_all_roles_from_column(df, col)
                    if roles:
                        all_roles.update(roles)
                        print(f"    ✓ 从列{col}发现角色: {roles}")
                        debug_info.append(f"方法3: 从列{col}提取到{roles}")

            # 方法4：全文搜索（最后的备用方法）
            if not all_roles:
                print("    使用备用方法：全文搜索")
                fallback_roles = self._extract_roles_fallback(df)
                all_roles.update(fallback_roles)
                if fallback_roles:
                    debug_info.append(f"方法4: 全文搜索提取到{fallback_roles}")

        # 打印调试信息汇总
        if debug_info:
            print("\n📋 角色提取详情:")
            for info in debug_info:
                print(f"    - {info}")

        # 按照职位级别排序
        sorted_roles = self._sort_roles_by_level(list(all_roles))

        print(f"\n✅ 最终提取的角色: {sorted_roles}")
        return sorted_roles

    def _find_role_columns_by_header(self, df: pd.DataFrame) -> List[Dict]:
        """通过列标题查找角色列"""
        role_columns = []

        # 扫描前30行查找列标题（增加搜索范围）
        for row in range(min(30, len(df))):
            for col in range(len(df.columns)):
                cell = df.iloc[row, col]
                if pd.notna(cell):
                    cell_str = str(cell).strip()
                    # 检查是否包含角色列标题关键词
                    if any(
                        keyword in cell_str for keyword in self.role_column_keywords
                    ):
                        # 额外检查：确保不是说明文字
                        if len(cell_str) < 20:  # 避免长文本误判
                            role_columns.append(
                                {"row": row, "col": col, "header": cell_str}
                            )
                            print(
                                f"      发现角色列标题 '{cell_str}' 在: 行{row}, 列{col}"
                            )

        return role_columns

    def _find_design_positions(self, df: pd.DataFrame) -> List[Dict]:
        """查找包含作业范围的位置"""
        positions = []

        for row in range(len(df)):
            design_count = 0
            design_cols = []

            for col in range(len(df.columns)):
                cell = df.iloc[row, col]
                if pd.notna(cell):
                    cell_str = str(cell).strip()
                    # 检查是否包含工程阶段关键词
                    for keyword in self.design_keywords:
                        if keyword in cell_str:
                            design_count += 1
                            design_cols.append(col)
                            break

            # 如果该行包含多个工程阶段关键词，记录该行
            if design_count >= 3:
                positions.append(
                    {"row": row, "design_cols": design_cols, "count": design_count}
                )

        return positions

    def _extract_roles_from_design_row(
        self, df: pd.DataFrame, design_pos: Dict
    ) -> Set[str]:
        """从作业范围行提取角色"""
        roles = set()
        row = design_pos["row"]

        # 在同一行查找角色（左侧）
        first_design_col = (
            min(design_pos["design_cols"]) if design_pos["design_cols"] else 0
        )

        # 检查左侧的列
        for col in range(0, first_design_col):
            cell = df.iloc[row, col]
            if pd.notna(cell):
                cell_str = str(cell).strip()
                extracted_role = self._extract_role_from_text(cell_str)
                if extracted_role:
                    roles.add(extracted_role)

        # 检查下方几行的左侧列
        for row_offset in range(1, min(10, len(df) - row)):
            for col in range(0, min(5, first_design_col)):  # 只检查最左边的几列
                cell = df.iloc[row + row_offset, col]
                if pd.notna(cell):
                    cell_str = str(cell).strip()
                    extracted_role = self._extract_role_from_text(cell_str)
                    if extracted_role:
                        roles.add(extracted_role)

        return roles

    def _find_columns_with_roles(self, df: pd.DataFrame) -> List[int]:
        """查找包含角色的列"""
        column_role_counts = {}

        # 统计每列包含的角色数量
        for col in range(len(df.columns)):
            role_count = 0
            for row in range(len(df)):
                cell = df.iloc[row, col]
                if pd.notna(cell):
                    cell_str = str(cell).strip()
                    if self._extract_role_from_text(cell_str):
                        role_count += 1

            if role_count > 0:
                column_role_counts[col] = role_count

        # 返回包含角色的列（按角色数量排序）
        sorted_columns = sorted(
            column_role_counts.items(), key=lambda x: x[1], reverse=True
        )
        return [col for col, count in sorted_columns if count >= 1]

    def _extract_roles_from_column_range(
        self, df: pd.DataFrame, col: int, start_row: int, end_row: int
    ) -> Set[str]:
        """从指定列的指定行范围提取角色"""
        roles = set()

        for row in range(start_row, min(end_row, len(df))):
            cell = df.iloc[row, col]
            if pd.notna(cell):
                cell_str = str(cell).strip()
                extracted_role = self._extract_role_from_text(cell_str)
                if extracted_role:
                    roles.add(extracted_role)

        return roles

    def _extract_all_roles_from_column(self, df: pd.DataFrame, col: int) -> Set[str]:
        """从整列提取所有角色"""
        return self._extract_roles_from_column_range(df, col, 0, len(df))

    def _extract_role_from_text(self, text: str) -> Optional[str]:
        """从文本中提取角色"""
        # 移除可能的标记符号
        text = re.sub(r"^[●○◎△×・\-\s]+", "", text).strip()

        # 排除说明性文字（图例/legend）
        # 如果文本包含多个角色的说明，则不提取
        if self._is_role_legend(text):
            return None

        # 排除包含技术术语的情况
        # PL/SQL 是数据库语言，不是角色
        if "PL/SQL" in text.upper() or "PL／SQL" in text:
            return None

        # 排除其他可能的技术术语组合
        tech_combinations = [
            r"SQL[・\s]*PL",  # SQL・PL
            r"PL[・\s]*SQL",  # PL・SQL
            r"\bPL/",  # PL/开头的技术术语
            r"/PL\b",  # /PL结尾的技术术语
        ]

        for tech_pattern in tech_combinations:
            if re.search(tech_pattern, text, re.IGNORECASE):
                return None

        # 特殊检查：如果包含"角色名：说明"格式，不提取
        # 例如 "PL：ﾌﾟﾛｼﾞｪｸﾄﾘｰﾀﾞｰ"
        if re.search(r"(PM|PL|SL|TL|BSE|SE|PG)[：:]", text):
            return None

        # 首先检查精确匹配
        for role in self.role_keywords:
            patterns = [
                rf"^{role}$",  # 完全匹配
                rf"^{role}(?:[^A-Za-z]|$)",  # 以角色开头
                rf"(?:^|[^A-Za-z]){role}$",  # 以角色结尾
                rf"(?:^|[^A-Za-z]){role}(?:[^A-Za-z]|$)",  # 独立的角色词
            ]

            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return role.upper()

        # 检查全称匹配
        for role, full_names in self.role_full_names.items():
            for full_name in full_names:
                if full_name.lower() in text.lower():
                    return role.upper()

        return None

    def _is_role_legend(self, text: str) -> bool:
        """判断是否是角色说明/图例文字

        Args:
            text: 要检查的文本

        Returns:
            如果是说明文字返回True
        """
        # 检查是否包含多个角色和说明符号
        role_count = 0
        for role in self.role_keywords:
            if role in text:
                role_count += 1

        # 如果包含2个或以上角色，可能是说明文字
        if role_count >= 2:
            # 检查是否包含说明性符号
            legend_indicators = [
                "：",  # 全角冒号
                ":",  # 半角冒号
                "／",  # 全角斜杠
                "ﾌﾟﾛｼﾞｪｸﾄ",  # 项目
                "ﾌﾟﾛｸﾞﾗﾏｰ",  # 程序员
                "ﾘｰﾀﾞｰ",  # 领导
                "経験有り",  # 有经验
                "○：",  # 圆圈说明
            ]

            for indicator in legend_indicators:
                if indicator in text:
                    return True

        # 检查是否是长文本（超过30个字符的可能是说明）
        if len(text) > 30 and any(role in text for role in self.role_keywords):
            # 如果是长文本且包含角色，检查是否有说明性词汇
            explanation_words = ["説明", "凡例", "記号", "マーク", "表記"]
            for word in explanation_words:
                if word in text:
                    return True

        return False

    def _extract_roles_fallback(self, df: pd.DataFrame) -> Set[str]:
        """备用方法：全文搜索角色（更严格的验证）"""
        roles = set()

        # 收集可疑的单元格，用于调试
        suspicious_cells = []

        # 将整个DataFrame转换为文本进行搜索
        for idx in range(len(df)):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if pd.notna(cell):
                    cell_str = str(cell).strip()

                    # 跳过过长的单元格（可能是说明文字）
                    if len(cell_str) > 50:
                        continue

                    # 尝试提取角色
                    extracted_role = self._extract_role_from_text(cell_str)
                    if extracted_role:
                        # 额外验证：检查是否在合理的上下文中
                        if self._is_valid_role_context(df, idx, col):
                            roles.add(extracted_role)
                        else:
                            suspicious_cells.append(
                                {
                                    "row": idx,
                                    "col": col,
                                    "value": cell_str,
                                    "role": extracted_role,
                                }
                            )

        # 如果有可疑的提取，打印警告
        if suspicious_cells:
            print("    ⚠️ 发现可疑的角色提取（已排除）:")
            for cell in suspicious_cells[:3]:  # 只显示前3个
                print(
                    f"      行{cell['row']}, 列{cell['col']}: '{cell['value']}' -> {cell['role']}"
                )

        return roles

    def _is_valid_role_context(self, df: pd.DataFrame, row: int, col: int) -> bool:
        """检查角色所在的上下文是否合理

        Args:
            df: DataFrame
            row: 行索引
            col: 列索引

        Returns:
            如果上下文合理返回True
        """
        # 检查同列是否有其他角色或项目相关内容
        role_count_in_column = 0
        project_related_count = 0

        for check_row in range(max(0, row - 10), min(len(df), row + 10)):
            if check_row != row:
                cell = df.iloc[check_row, col]
                if pd.notna(cell):
                    cell_str = str(cell).strip()

                    # 检查是否有其他角色
                    if self._extract_role_from_text(cell_str):
                        role_count_in_column += 1

                    # 检查是否有项目相关内容
                    project_keywords = [
                        "プロジェクト",
                        "開発",
                        "システム",
                        "業務",
                        "担当",
                        "作業",
                    ]
                    if any(keyword in cell_str for keyword in project_keywords):
                        project_related_count += 1

        # 如果同列有其他角色或项目相关内容，认为上下文合理
        return role_count_in_column > 0 or project_related_count >= 2

    def _sort_roles_by_level(self, roles: List[str]) -> List[str]:
        """按照职位级别排序（从高到低）"""
        # 确保所有角色都是大写
        roles = [role.upper() for role in roles]

        # 去重
        roles = list(set(roles))

        # 按照级别排序
        sorted_roles = sorted(
            roles,
            key=lambda x: self.role_levels.get(x, 0),
            reverse=True,  # 降序，级别高的在前
        )

        return sorted_roles
