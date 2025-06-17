# -*- coding: utf-8 -*-
"""技能提取器 - 修复提取范围版本"""

from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
import re

from app.base.base_extractor import BaseExtractor
from app.base.constants import VALID_SKILLS, SKILL_MARKS, EXCLUDE_PATTERNS


class SkillsExtractor(BaseExtractor):
    """技能信息提取器"""

    def __init__(self):
        super().__init__()
        # 工程阶段关键词（用于定位右侧列）
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
        ]

        # 技术列标题关键词（用于识别技术列）
        self.tech_column_keywords = [
            "言語",
            "ツール",
            "技術",
            "スキル",
            "DB",
            "OS",
            "フレームワーク",
            "開発環境",
            "プログラミング",
            "機種",
            "Git",
            "SVN",
            "バージョン管理",
        ]

        # 不应该被空格分割的技能（保持完整性）
        self.no_split_skills = {
            "Spring Boot",
            "VS Code",
            "Visual Studio",
            "Android Studio",
            "IntelliJ IDEA",
            "SQL Server",
            "Azure SQL Database",
            "Azure SQL DB",
            "React Native",
            "Node.js",
            "Vue.js",
            "React.js",
            "TeraTerm",
            "Tera Term",
            "Win95/98",
            "Finance and Operations",
            "Dynamics 365",
            "AWS Glue",
            "AWS S3",
            "AWS Lambda",
            "AWS EC2",
            "AWS IAM",
            "AWS CodeCommit",
        }

    def extract(self, all_data: List[Dict[str, Any]]) -> List[str]:
        """提取技能列表 - 限制在工程阶段关键词之下

        Args:
            all_data: 包含所有sheet数据的列表

        Returns:
            技能列表
        """
        all_skills = []

        for data in all_data:
            df = data["df"]
            sheet_name = data.get("sheet_name", "Unknown")

            print(f"\n🔍 开始技术关键字提取 - Sheet: {sheet_name}")
            print(f"    表格大小: {df.shape[0]}行 x {df.shape[1]}列")

            # **关键修复：先确定工程阶段的最小行位置，只在该行之下提取技能**
            min_design_row = self._find_min_design_row(df)

            if min_design_row is not None:
                print(f"    ✓ 找到工程阶段起始行: {min_design_row + 1}")
                print(f"    📍 只提取第{min_design_row + 1}行之下的技能")

                # 方法1：基于工程阶段列定位技术列（限制在项目表头之下）
                skills, design_positions = (
                    self._extract_skills_by_design_column_limited(df, project_start_row)
                )
                if skills:
                    print(f"    ✓ 从技术列提取到 {len(skills)} 个技能")
                    all_skills.extend(skills)

                # **新增方法：横向技能表格处理（限制在项目表头之下）**
                horizontal_skills = self._extract_skills_from_horizontal_table_limited(
                    df, project_start_row
                )
                if horizontal_skills:
                    print(f"    ✓ 从横向表格提取到 {len(horizontal_skills)} 个技能")
                    all_skills.extend(horizontal_skills)

                # 备用方法：如果主方法失败或提取太少（限制在项目表头之下）
                if len(all_skills) < 10:
                    print(
                        f"    使用备用方法补充提取（限制在第{project_start_row + 1}行之下）"
                    )
                    fallback_skills = self._extract_skills_fallback_limited(
                        df, project_start_row
                    )
                    all_skills.extend(fallback_skills)
            else:
                print("    ❌ 未找到项目表头关键词，无法确定提取范围")
                print("    🚫 跳过该表格，不进行全表格提取")
                # 不进行任何提取，直接跳过

        # 去重和标准化
        final_skills = self._process_and_deduplicate_skills(all_skills)
        return final_skills

    def _find_project_start_row(self, df: pd.DataFrame) -> Optional[int]:
        """从下往上找到项目表头行（包含項番、作業期間等的行）

        Returns:
            项目表头行号，如果没找到则返回None
        """
        project_header_keywords = [
            "項番",
            "作業期間",
            "開発場所",
            "言語",
            "ツール",
            "DB",
        ]

        # **关键修复：从下往上查找，找到第一个就停止**
        for row in range(len(df) - 1, -1, -1):  # 从最后一行往上找
            for col in range(len(df.columns)):
                cell = df.iloc[row, col]
                if pd.notna(cell):
                    cell_str = str(cell).strip()
                    # 检查是否包含项目表头关键词
                    if any(keyword in cell_str for keyword in project_header_keywords):
                        print(
                            f"    发现项目表头: 第{row + 1}行,第{col + 1}列 = '{cell_str}'"
                        )
                        return row  # **找到第一个就立即返回，不再继续查找**

        return None

    def _extract_skills_by_design_column_limited(
        self, df: pd.DataFrame, min_design_row: int
    ) -> Tuple[List[str], List[Dict]]:
        """基于工程阶段列定位并提取技术列（限制在工程阶段之下）"""
        skills = []

        # Step 1: 找到包含"基本設計"等关键词的列位置（只在min_design_row之下搜索）
        design_positions = self._find_design_column_positions_limited(
            df, min_design_row
        )
        if not design_positions:
            print("    未找到工程阶段列")
            return skills, design_positions

        print(f"    找到 {len(design_positions)} 个工程阶段列位置")

        # Step 2: 对每个找到的设计列位置，向左查找所有技术列
        for design_pos in design_positions:
            # 找到所有技术列（不是只找一个）
            tech_columns = self._find_all_tech_columns_left_limited(
                df, design_pos, min_design_row
            )

            if tech_columns:
                print(
                    f"    从设计列 {design_pos['col']} (行{design_pos['row']}: {design_pos['value']}) 向左找到 {len(tech_columns)} 个技术列"
                )

                # Step 3: 提取每个技术列的内容
                for tech_column in tech_columns:
                    print(
                        f"      提取列 {tech_column['col']} (类型: {tech_column.get('type', '未知')})"
                    )
                    column_skills = self._extract_entire_column_skills_limited(
                        df, tech_column, min_design_row
                    )
                    skills.extend(column_skills)

        return skills, design_positions

    def _find_design_column_positions_limited(
        self, df: pd.DataFrame, project_start_row: int
    ) -> List[Dict]:
        """查找包含工程阶段关键词的列位置（限制在project_start_row之下）"""
        positions = []

        # 从右向左扫描（优先查找右侧的列）
        for col in range(len(df.columns) - 1, -1, -1):
            for row in range(
                project_start_row, len(df)
            ):  # **关键修复：只搜索project_start_row之下**
                cell = df.iloc[row, col]
                if pd.notna(cell):
                    cell_str = str(cell).strip()
                    # 检查是否包含工程阶段关键词
                    if any(keyword in cell_str for keyword in self.design_keywords):
                        positions.append({"row": row, "col": col, "value": cell_str})
                        break  # 该列已找到，继续下一列

        return positions

    def _find_all_tech_columns_left_limited(
        self, df: pd.DataFrame, design_pos: Dict, project_start_row: int
    ) -> List[Dict]:
        """从设计列位置向左查找所有技术列（限制在project_start_row之下）"""
        design_row = design_pos["row"]
        design_col = design_pos["col"]
        tech_columns = []

        # **关键修复：确保搜索范围不超过project_start_row之上**
        search_start_row = max(design_row, project_start_row)  # 取较大值
        search_end_row = len(df)  # 搜索到表格末尾

        print(f"      技能搜索范围: 第{search_start_row + 1}行 到 第{search_end_row}行")

        # 从设计列向左逐列搜索
        for col in range(design_col - 1, max(-1, design_col - 20), -1):
            # 检查该列是否包含技术内容
            tech_info = self._analyze_column_for_tech_limited(
                df, col, search_start_row, search_end_row, project_start_row
            )

            if tech_info and tech_info["score"] >= 2:
                tech_columns.append(tech_info)

        return tech_columns

    def _analyze_column_for_tech_limited(
        self,
        df: pd.DataFrame,
        col: int,
        start_row: int,
        end_row: int,
        project_start_row: int,
    ) -> Optional[Dict]:
        """分析某一列是否为技术列（限制在project_start_row之下）"""
        tech_score = 0
        tech_row_start = None
        column_type = None
        sample_skills = []

        for row in range(start_row, end_row):
            if (
                row >= len(df) or row < project_start_row
            ):  # **关键修复：确保不超过project_start_row之上**
                continue

            cell = df.iloc[row, col]
            if pd.notna(cell):
                cell_str = str(cell).strip()

                # 检查列标题
                if any(keyword in cell_str for keyword in self.tech_column_keywords):
                    tech_score += 10

                    # 识别列类型
                    if any(k in cell_str for k in ["言語", "ツール", "プログラミング"]):
                        column_type = "programming"
                    elif "DB" in cell_str or "データベース" in cell_str:
                        column_type = "database"
                    elif "OS" in cell_str or "機種" in cell_str:
                        column_type = "os"
                    elif any(k in cell_str for k in ["Git", "SVN", "バージョン"]):
                        column_type = "version_control"

                    if tech_row_start is None:
                        tech_row_start = row

                # 检查是否包含技术内容
                if self._cell_contains_tech_content(cell_str):
                    tech_score += 1
                    if tech_row_start is None:
                        tech_row_start = row

                    # 收集样本技能
                    if len(sample_skills) < 5:
                        extracted = self._extract_skills_from_text(cell_str)
                        sample_skills.extend(extracted[:2])  # 只取前2个避免太多

        # 如果该列技术分数足够高，返回信息
        if tech_score >= 2:
            return {
                "col": col,
                "start_row": max(
                    tech_row_start or start_row, project_start_row
                ),  # **确保起始行不超过project_start_row之上**
                "score": tech_score,
                "type": column_type or "general",
                "sample_skills": sample_skills[:5],  # 保留前5个作为样本
            }

        return None

    def _extract_entire_column_skills_limited(
        self, df: pd.DataFrame, tech_column: Dict, project_start_row: int
    ) -> List[str]:
        """提取整个技术列的所有技能（限制在project_start_row之下）"""
        skills = []
        col = tech_column["col"]
        start_row = max(
            tech_column["start_row"], project_start_row
        )  # **确保起始行不超过project_start_row之上**

        print(f"        从行 {start_row + 1} 开始提取（限制在项目表头之下）")

        # 提取该列从start_row开始的所有内容
        consecutive_empty = 0
        for row in range(start_row, len(df)):
            cell = df.iloc[row, col]
            if pd.notna(cell):
                cell_str = str(cell).strip()
                consecutive_empty = 0

                # 检查是否到达技能区域结束
                if self._is_column_end(cell_str):
                    break

                # 跳过职位标记
                if cell_str.upper() in ["PM", "PL", "SL", "TL", "BSE", "SE", "PG"]:
                    continue

                # 处理多行内容（换行符分隔）
                if "\n" in cell_str:
                    lines = cell_str.split("\n")
                    for line in lines:
                        line_skills = self._extract_skills_from_text(line)
                        skills.extend(line_skills)
                else:
                    # 单行内容
                    cell_skills = self._extract_skills_from_text(cell_str)
                    skills.extend(cell_skills)
            else:
                consecutive_empty += 1
                # 如果连续5个空单元格，可能技能区域已结束
                if consecutive_empty >= 5:
                    break

        return skills

    def _extract_skills_from_horizontal_table_limited(
        self, df: pd.DataFrame, project_start_row: int
    ) -> List[str]:
        """
        处理横向多列技能表格（限制在project_start_row之下）
        针对每行包含多个技能的布局
        """
        skills = []

        # 技能分类关键词
        skill_category_keywords = ["言語", "DB", "FW", "ツール", "OS", "機種"]

        print(f"    使用横向表格提取方法（限制在第{project_start_row + 1}行之下）...")

        # **关键修复：只查找project_start_row之下的技能相关行**
        for row in range(project_start_row, len(df)):
            row_data = df.iloc[row]

            # 检查该行是否包含技能分类标识
            has_skill_category = False
            category_found = ""

            for cell in row_data:
                if pd.notna(cell):
                    cell_str = str(cell).strip()
                    for keyword in skill_category_keywords:
                        if keyword in cell_str:
                            has_skill_category = True
                            category_found = keyword
                            break
                    if has_skill_category:
                        break

            if has_skill_category:
                print(f"        处理技能行 {row + 1} ({category_found})")

                # 提取该行的所有技能
                row_skills = []
                for col_idx, cell in enumerate(row_data):
                    if pd.notna(cell):
                        cell_str = str(cell).strip()

                        # 跳过分类标题和评价符号
                        if not any(
                            keyword in cell_str for keyword in skill_category_keywords
                        ) and cell_str not in ["◎", "○", "△", "×", ""]:

                            # 处理复合技能（如"Git,GitHub"）
                            if "," in cell_str:
                                sub_skills = [s.strip() for s in cell_str.split(",")]
                                for sub_skill in sub_skills:
                                    if sub_skill and self._is_valid_skill(sub_skill):
                                        normalized = self._normalize_skill_name(
                                            sub_skill
                                        )
                                        row_skills.append(normalized)
                            else:
                                if self._is_valid_skill(cell_str):
                                    normalized = self._normalize_skill_name(cell_str)
                                    row_skills.append(normalized)

                skills.extend(row_skills)
                print(f"            提取技能: {row_skills}")

        return skills

    # 移除不需要的方法，因为永远不进行全表格提取
    # def _extract_skills_from_horizontal_table(self, df: pd.DataFrame) -> List[str]:

    def _extract_skills_fallback_limited(
        self, df: pd.DataFrame, project_start_row: int
    ) -> List[str]:
        """全文搜索技能（最后的备用方法，限制在project_start_row之下）"""
        skills = []

        print(f"    使用备用全文搜索（限制在第{project_start_row + 1}行之下）")

        # **关键修复：只将project_start_row之下的内容转换为文本**
        text_parts = []
        for idx in range(project_start_row, len(df)):
            row = df.iloc[idx]
            row_text = " ".join([str(cell) for cell in row if pd.notna(cell)])
            if row_text.strip():
                text_parts.append(row_text)

        text = "\n".join(text_parts)

        for skill in VALID_SKILLS:
            patterns = [
                rf"\b{re.escape(skill)}\b",
                rf"(?:^|\s|[、,，/]){re.escape(skill)}(?:$|\s|[、,，/])",
            ]

            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    skills.append(skill)
                    break

        return skills

    # 以下方法保持不变，但添加必要的修复...

    def _cell_contains_tech_content(self, cell_str: str) -> bool:
        """检查单元格是否包含技术内容"""
        # 快速检查常见技术关键词
        tech_patterns = [
            r"\b(Java|Python|JavaScript|PHP|Ruby|C\+\+|C#|Go|VB|COBOL)\b",
            r"\b(Spring|React|Vue|Angular|Django|Rails|Node\.js|\.NET)\b",
            r"\b(MySQL|PostgreSQL|Oracle|MongoDB|Redis|SQL\s*Server|DB2)\b",
            r"\b(AWS|Azure|GCP|Docker|Kubernetes)\b",
            r"\b(Git|SVN|Jenkins|Maven|TortoiseSVN|GitHub)\b",
            r"\b(Windows|Linux|Unix|Ubuntu|CentOS|win\d+)\b",
            r"\b(Eclipse|IntelliJ|VS\s*Code|Visual\s*Studio|NetBeans)\b",
            r"(HTML|CSS|SQL|XML|JSON|TeraTerm)",
        ]

        cell_upper = cell_str.upper()
        for pattern in tech_patterns:
            if re.search(pattern, cell_str, re.IGNORECASE):
                return True

        # 检查是否包含预定义的有效技能
        for skill in VALID_SKILLS:
            if skill.upper() in cell_upper:
                return True

        # 特殊情况：单独的"SE"或"PG"不算技能，但在技术列中可能出现
        if cell_str in ["SE", "PG", "PL", "PM"]:
            return False

        return False

    def _is_column_end(self, cell_str: str) -> bool:
        """判断是否到达技术列结束"""
        # 如果遇到这些内容，说明技能区域结束
        end_markers = [
            "プロジェクト",
            "案件",
            "経歴",
            "実績",
            "期間",
            "業務内容",
            "担当",
            "概要",
            "備考",
            "その他",
            "職歴",
            "経験",
            "資格",
        ]

        # 日期格式也表示新的项目开始
        if re.match(r"^\d{4}[年/]\d{1,2}[月/]", cell_str):
            return True

        return any(marker in cell_str for marker in end_markers)

    def _extract_skills_from_text(self, text: str) -> List[str]:
        """从文本中提取技能"""
        skills = []
        text = text.strip()

        if not text:
            return skills

        # 移除标记符号
        text = re.sub(r"^[◎○△×★●◯▲※・\-\s]+", "", text)

        # 处理括号内的内容
        # 例如: "Python AWS (glue/S3/Lambda/EC2/IAM/codecommit)"
        bracket_pattern = r"([^(]+)\s*\(([^)]+)\)"
        bracket_match = re.match(bracket_pattern, text)

        if bracket_match:
            # 括号前的内容
            main_part = bracket_match.group(1)
            # 括号内的内容
            bracket_content = bracket_match.group(2)

            # 提取主要部分的技能
            main_skills = self._split_and_validate_skills(main_part)
            skills.extend(main_skills)

            # 提取括号内的技能（通常是具体的服务/模块）
            bracket_skills = self._split_and_validate_skills(bracket_content)
            skills.extend(bracket_skills)
        else:
            # 没有括号，直接提取
            skills.extend(self._split_and_validate_skills(text))

        return skills

    def _split_and_validate_skills(self, text: str) -> List[str]:
        """分割文本并验证技能"""
        skills = []

        # 首先检查是否是不应该被分割的技能
        text_stripped = text.strip()

        # 检查完整文本是否匹配不可分割技能（不区分大小写）
        for no_split_skill in self.no_split_skills:
            if text_stripped.lower() == no_split_skill.lower():
                if self._is_valid_skill(text_stripped):
                    normalized = self._normalize_skill_name(text_stripped)
                    skills.append(normalized)
                    return skills

        # 保护不可分割的技能：将它们临时替换为占位符
        protected_skills = {}
        protected_text = text
        placeholder_index = 0

        for no_split_skill in self.no_split_skills:
            # 使用正则表达式进行不区分大小写的匹配
            pattern = re.compile(re.escape(no_split_skill), re.IGNORECASE)
            if pattern.search(protected_text):
                placeholder = f"__SKILL_PLACEHOLDER_{placeholder_index}__"
                protected_skills[placeholder] = no_split_skill
                protected_text = pattern.sub(placeholder, protected_text)
                placeholder_index += 1

        # 使用多种分隔符分割（但不包括被保护的技能）
        items = re.split(r"[、,，/／\s\|｜]+", protected_text)

        for item in items:
            item = item.strip()
            if not item:
                continue

            # 检查是否是占位符
            if item in protected_skills:
                # 恢复原始技能
                original_skill = protected_skills[item]
                if self._is_valid_skill(original_skill):
                    normalized = self._normalize_skill_name(original_skill)
                    skills.append(normalized)
            else:
                # 普通技能验证
                if self._is_valid_skill(item):
                    normalized = self._normalize_skill_name(item)
                    skills.append(normalized)

        # 如果分割后没有找到技能，尝试将整个文本作为技能
        if not skills and text and self._is_valid_skill(text):
            normalized = self._normalize_skill_name(text)
            skills.append(normalized)

        return skills

    def _is_valid_skill(self, skill: str) -> bool:
        """验证是否为有效技能 - 修复版本"""
        if not skill or len(skill) < 1 or len(skill) > 50:
            return False

        skill = skill.strip()

        # **修复：排除占位符**
        if "__SKILL_PLACEHOLDER_" in skill:
            return False

        # **修复：不再直接排除包含"os"或"db"的技能**
        # 而是更精确地排除
        skill_lower = skill.lower()

        # 只排除明确的非技能内容，而不是包含os/db的所有内容
        if skill_lower in ["os", "db"]:  # 只排除单独的"os"和"db"
            return False

        # 排除包含"数据库"、"操作系统"等完整词汇的描述性文本
        if any(word in skill for word in ["数据库", "操作系统", "データベース"]):
            return False

        # 排除包含括号的技能（半角和全角）
        if any(bracket in skill for bracket in ["(", ")", "（", "）"]):
            return False

        # 排除包含日文关键词的非技能内容
        exclude_japanese_keywords = [
            "自己PR",
            "自己紹介",
            "志望動機",
            "アピール",
            "ポイント",
            "経歴書",
            "履歴書",
            "スキルシート",
            "職務経歴",
            "氏名",
            "性別",
            "生年月日",
            "年齢",
            "住所",
            "電話",
            "学歴",
            "職歴",
            "資格",
            "趣味",
            "特技",
            "備考",
        ]
        if any(keyword in skill for keyword in exclude_japanese_keywords):
            return False

        # 排除评价符号
        if skill in ["◎", "○", "△", "×", ""]:
            return False

        # 排除模式
        exclude_patterns = [
            r"^[0-9\s\.\-]+$",  # 纯数字
            r"^[◎○△×\s]+$",  # 评价符号
        ]

        for pattern in exclude_patterns:
            if re.match(pattern, skill):
                return False

        # 特殊情况
        if skill.upper() == "C":
            return True

        # 特殊排除：职位标记
        if skill.upper() in ["PM", "PL", "SL", "TL", "BSE", "SE", "PG"]:
            return False

        # 检查预定义技能列表
        skill_upper = skill.upper()
        for valid_skill in VALID_SKILLS:
            if valid_skill.upper() == skill_upper:
                return True

        # 操作系统模式
        if re.match(r"^win\d+$", skill_lower) or re.match(
            r"^Windows\s*\d+$", skill, re.IGNORECASE
        ):
            return True

        # 包含技术关键词
        if re.search(r"[a-zA-Z]", skill) and len(skill) >= 2:
            exclude_words = [
                "設計",
                "製造",
                "試験",
                "テスト",
                "管理",
                "経験",
                "担当",
                "役割",
                "フェーズ",
            ]
            if not any(word in skill for word in exclude_words):
                return True

        return False

    def _normalize_skill_name(self, skill: str) -> str:
        """标准化技能名称 - 增强版本"""
        skill = skill.strip()

        # 处理冒号分隔的情况（支持全角和半角冒号）
        # 例如: "言語:Java" -> "Java", "DB：PostgreSQL" -> "PostgreSQL"
        if ":" in skill or "：" in skill:
            # 替换全角冒号为半角，然后分割
            skill_parts = skill.replace("：", ":").split(":", 1)
            if len(skill_parts) == 2:
                # 取冒号后面的部分
                skill = skill_parts[1].strip()
                # 如果冒号后面为空，返回原始值
                if not skill:
                    skill = skill_parts[0].strip()

        # 特殊处理：操作系统标准化
        # 如果包含 Windows（无论大小写），统一返回 Windows
        if "windows" in skill.lower():
            return "Windows"

        # 如果包含 Linux（无论大小写），统一返回 Linux
        if "linux" in skill.lower():
            return "Linux"

        # **增强的技能名称映射**
        skill_mapping = {
            # 编程语言
            "JAVA": "Java",
            "java": "Java",
            "Javascript": "JavaScript",
            "javascript": "JavaScript",
            "JAVASCRIPT": "JavaScript",
            "typescript": "TypeScript",
            "TYPESCRIPT": "TypeScript",
            "python": "Python",
            "PYTHON": "Python",
            "C#": "C#",
            "c#": "C#",
            "C++": "C++",
            "c++": "C++",
            "C": "C",
            "c": "C",
            "PHP": "PHP",
            "php": "PHP",
            "Ruby": "Ruby",
            "ruby": "Ruby",
            "GO": "Go",
            "go": "Go",
            "VB．NET": "VB.NET",
            "VB.NET": "VB.NET",
            "ASP．NET": "ASP.NET",
            "ASP.NET": "ASP.NET",
            "COBOL": "COBOL",
            "cobol": "COBOL",
            "Groovy": "Groovy",
            "groovy": "Groovy",
            "Objective-C": "Objective-C",
            "objective-c": "Objective-C",
            "Swift": "Swift",
            "swift": "Swift",
            "Kotlin": "Kotlin",
            "kotlin": "Kotlin",
            "HTML5": "HTML5",
            "html5": "HTML5",
            "HTML": "HTML",
            "html": "HTML",
            "CSS": "CSS",
            "css": "CSS",
            # 数据库
            "MySql": "MySQL",
            "mysql": "MySQL",
            "MYSQL": "MySQL",
            "mybatis": "MyBatis",
            "Mybatis": "MyBatis",
            "MYBATIS": "MyBatis",
            "PostgreSQL": "PostgreSQL",
            "Postgre SQL": "PostgreSQL",
            "postgresql": "PostgreSQL",
            "SqlServer": "SQL Server",
            "SQLServer": "SQL Server",
            "sqlserver": "SQL Server",
            "SQL SERVER": "SQL Server",
            "ORACLE": "Oracle",
            "oracle": "Oracle",
            "Oracle": "Oracle",
            "DB2": "DB2",
            "db2": "DB2",
            "ACCESS": "Access",
            "access": "Access",
            "Access": "Access",
            "ADABAS": "ADABAS",
            "adabas": "ADABAS",
            "HIRDB": "HiRDB",
            "hirdb": "HiRDB",
            # 框架
            "spring": "Spring",
            "Spring": "Spring",
            "SPRING": "Spring",
            "spring boot": "Spring Boot",
            "springboot": "Spring Boot",
            "spring-boot": "Spring Boot",
            "SPRING BOOT": "Spring Boot",
            "SpringBoot": "Spring Boot",  # **重要：处理这个变体**
            "SpringMVC": "Spring MVC",
            "springmvc": "Spring MVC",
            "Struts1.0": "Struts 1.0",
            "struts1.0": "Struts 1.0",
            "Struts2.0": "Struts 2.0",
            "struts2.0": "Struts 2.0",
            "thymeleaf": "Thymeleaf",
            "Thymeleaf": "Thymeleaf",
            "THYMELEAF": "Thymeleaf",
            "Angular": "Angular",
            "angular": "Angular",
            "ANGULAR": "Angular",
            "AngularJS": "AngularJS",
            "angularjs": "AngularJS",
            "ANGULARJS": "AngularJS",
            "jQuery": "jQuery",
            "jquery": "jQuery",
            "JQUERY": "jQuery",
            "node.js": "Node.js",
            "Node.JS": "Node.js",
            "nodejs": "Node.js",
            "NODE.JS": "Node.js",
            "vue.js": "Vue.js",
            "Vue.js": "Vue.js",
            "vuejs": "Vue.js",
            "VUE.JS": "Vue.js",
            "react.js": "React",
            "React.js": "React",
            "reactjs": "React",
            "REACT.JS": "React",
            "JSF": "JSF",
            "jsf": "JSF",
            "BackBone.js": "Backbone.js",
            "backbone.js": "Backbone.js",
            # 测试和构建工具
            "junit": "JUnit",
            "Junit": "JUnit",
            "JUNIT": "JUnit",
            "Spock": "Spock",
            "spock": "Spock",
            "Jmeter": "JMeter",
            "jmeter": "JMeter",
            "JMETER": "JMeter",
            "A5M2": "A5:SQL Mk-2",
            "a5m2": "A5:SQL Mk-2",
            # IDE和工具
            "eclipse": "Eclipse",
            "Eclipse": "Eclipse",
            "ECLIPSE": "Eclipse",
            "vscode": "VS Code",
            "Vscode": "VS Code",
            "VSCode": "VS Code",
            "VS Code": "VS Code",
            "vs code": "VS Code",
            "VS code": "VS Code",
            "Visual Studio Code": "VS Code",
            "Visual Studio": "Visual Studio",
            "visual studio": "Visual Studio",
            "Intellij": "IntelliJ IDEA",
            "intellij": "IntelliJ IDEA",
            "IntelliJ": "IntelliJ IDEA",
            "postman": "Postman",
            "Postman": "Postman",
            "POSTMAN": "Postman",
            "WinMerge": "WinMerge",
            "winmerge": "WinMerge",
            "WINMERGE": "WinMerge",
            # 版本控制
            "git": "Git",
            "Git": "Git",
            "GIT": "Git",
            "github": "GitHub",
            "Github": "GitHub",
            "GITHUB": "GitHub",
            "svn": "SVN",
            "Svn": "SVN",
            "SVN": "SVN",
            "TortoiseSVN": "TortoiseSVN",
            "tortoisesvn": "TortoiseSVN",
            # 云服务
            "aws": "AWS",
            "Aws": "AWS",
            "AWS": "AWS",
            "azure": "Azure",
            "Azure": "Azure",
            "AZURE": "Azure",
            "SalseForce": "Salesforce",
            "salesforce": "Salesforce",
            "Salesforce": "Salesforce",
            "OutSystems": "OutSystems",
            "outsystems": "OutSystems",
            # 操作系统
            "Solris": "Solaris",
            "solaris": "Solaris",
            "Solaris": "Solaris",
            "UNIX": "Unix",
            "unix": "Unix",
            "Unix": "Unix",
            "Linux": "Linux",
            "linux": "Linux",
            "LINUX": "Linux",
            "DOS": "DOS",
            "dos": "DOS",
            "Mac": "macOS",
            "mac": "macOS",
            "macOS": "macOS",
            "MacOS": "macOS",
            "iOS": "iOS",
            "ios": "iOS",
            "Android": "Android",
            "android": "Android",
            "ANDROID": "Android",
        }

        # 检查映射
        if skill in skill_mapping:
            return skill_mapping[skill]

        # 大小写不敏感查找
        skill_lower = skill.lower()
        for k, v in skill_mapping.items():
            if k.lower() == skill_lower:
                return v

        # 检查有效技能列表
        for valid_skill in VALID_SKILLS:
            if valid_skill.lower() == skill_lower:
                return valid_skill

        # 如果在no_split_skills中有对应的技能，使用标准形式
        for no_split_skill in self.no_split_skills:
            if skill.lower() == no_split_skill.lower():
                return no_split_skill

        return skill

    def _process_and_deduplicate_skills(self, skills: List[str]) -> List[str]:
        """处理和去重技能列表"""
        final_skills = []
        seen_lower = set()

        for skill in skills:
            if not skill:
                continue

            normalized = self._normalize_skill_name(skill)
            normalized_lower = normalized.lower()

            # 去重（大小写不敏感）
            if normalized_lower not in seen_lower:
                seen_lower.add(normalized_lower)
                final_skills.append(normalized)

        # 保持原始顺序，不进行排序
        print(f"    最终提取技能数量: {len(final_skills)}")
        if final_skills:
            print(f"    前10个技能: {', '.join(final_skills[:10])}")

        return final_skills

    def _dataframe_to_text(self, df: pd.DataFrame) -> str:
        """将DataFrame转换为文本"""
        text_parts = []
        for idx, row in df.iterrows():
            row_text = " ".join([str(cell) for cell in row if pd.notna(cell)])
            if row_text.strip():
                text_parts.append(row_text)
        return "\n".join(text_parts)
