# -*- coding: utf-8 -*-
"""技能提取器"""

from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
import re

from base.base_extractor import BaseExtractor
from base.constants import VALID_SKILLS, SKILL_MARKS, EXCLUDE_PATTERNS


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
            # "No.",  # 添加 No. 作为工程阶段标题
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
        """提取技能列表

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

            # 主要方法：基于工程阶段列定位技术列
            skills, design_positions = self._extract_skills_by_design_column(df)
            if skills:
                print(f"    ✓ 从技术列提取到 {len(skills)} 个技能")
                all_skills.extend(skills)

            # 备用方法：如果主方法失败或提取太少
            if len(all_skills) < 5:
                print(f"    使用备用方法补充提取")
                # 方法2：查找合并单元格（限制在设计行下方）
                merged_skills = self._find_skills_in_merged_cells(df, design_positions)
                all_skills.extend(merged_skills)

                # 方法3：全文搜索（限制在设计行下方）
                if len(all_skills) < 5:
                    fallback_skills = self._extract_skills_fallback(
                        df, design_positions
                    )
                    all_skills.extend(fallback_skills)

        # 去重和标准化
        final_skills = self._process_and_deduplicate_skills(all_skills)
        return final_skills

    def _extract_skills_by_design_column(
        self, df: pd.DataFrame
    ) -> Tuple[List[str], List[Dict]]:
        """基于工程阶段列定位并提取技术列"""
        skills = []

        # Step 1: 找到包含"基本設計"等关键词的列位置
        design_positions = self._find_design_column_positions(df)
        if not design_positions:
            print("    未找到工程阶段列")
            return skills, design_positions

        print(f"    找到 {len(design_positions)} 个工程阶段列位置")

        # Step 2: 对每个找到的设计列位置，向左查找所有技术列
        for design_pos in design_positions:
            # 找到所有技术列（不是只找一个）
            tech_columns = self._find_all_tech_columns_left(df, design_pos)

            if tech_columns:
                print(
                    f"    从设计列 {design_pos['col']} (行{design_pos['row']}: {design_pos['value']}) 向左找到 {len(tech_columns)} 个技术列"
                )

                # Step 3: 提取每个技术列的内容
                for tech_column in tech_columns:
                    print(
                        f"      提取列 {tech_column['col']} (类型: {tech_column.get('type', '未知')})"
                    )
                    column_skills = self._extract_entire_column_skills(df, tech_column)
                    skills.extend(column_skills)

        return skills, design_positions

    def _find_design_column_positions(self, df: pd.DataFrame) -> List[Dict]:
        """查找包含工程阶段关键词的列位置"""
        positions = []

        # 从右向左扫描（优先查找右侧的列）
        for col in range(len(df.columns) - 1, -1, -1):
            for row in range(len(df)):  # 搜索整个列
                cell = df.iloc[row, col]
                if pd.notna(cell):
                    cell_str = str(cell).strip()
                    # 检查是否包含工程阶段关键词
                    if any(keyword in cell_str for keyword in self.design_keywords):
                        positions.append({"row": row, "col": col, "value": cell_str})
                        break  # 该列已找到，继续下一列

        return positions

    def _find_all_tech_columns_left(
        self, df: pd.DataFrame, design_pos: Dict
    ) -> List[Dict]:
        """从设计列位置向左查找所有技术列"""
        design_row = design_pos["row"]
        design_col = design_pos["col"]
        tech_columns = []

        # 定义搜索范围：只在设计行的下方搜索
        search_start_row = design_row  # 从设计行开始
        search_end_row = len(df)  # 搜索到表格末尾

        # 从设计列向左逐列搜索
        for col in range(design_col - 1, max(-1, design_col - 20), -1):
            # 检查该列是否包含技术内容
            tech_info = self._analyze_column_for_tech(
                df, col, search_start_row, search_end_row
            )

            if tech_info and tech_info["score"] >= 2:
                tech_columns.append(tech_info)

        return tech_columns

    def _analyze_column_for_tech(
        self, df: pd.DataFrame, col: int, start_row: int, end_row: int
    ) -> Optional[Dict]:
        """分析某一列是否为技术列"""
        tech_score = 0
        tech_row_start = None
        column_type = None
        sample_skills = []

        for row in range(start_row, end_row):
            if row >= len(df):
                break

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
                "start_row": tech_row_start or start_row,
                "score": tech_score,
                "type": column_type or "general",
                "sample_skills": sample_skills[:5],  # 保留前5个作为样本
            }

        return None

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

    def _extract_entire_column_skills(
        self, df: pd.DataFrame, tech_column: Dict
    ) -> List[str]:
        """提取整个技术列的所有技能"""
        skills = []
        col = tech_column["col"]
        start_row = tech_column["start_row"]

        print(f"        从行 {start_row} 开始提取")

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

    def _find_skills_in_merged_cells(
        self, df: pd.DataFrame, design_positions: List[Dict]
    ) -> List[str]:
        """查找合并单元格中的技能（备用方法）"""
        skills = []

        # 获取最早的设计行位置（如果有的话）
        min_design_row = 0
        if design_positions:
            min_design_row = min(pos["row"] for pos in design_positions)

        for row in range(min_design_row, len(df)):  # 只搜索设计行下方
            for col in range(len(df.columns)):
                cell = df.iloc[row, col]
                if pd.notna(cell) and "\n" in str(cell):
                    cell_str = str(cell)
                    lines = cell_str.split("\n")

                    # 计算包含技能的行数
                    skill_count = 0
                    for line in lines:
                        if self._cell_contains_tech_content(line):
                            skill_count += 1

                    # 如果多行包含技能，提取所有
                    if skill_count >= 3:
                        for line in lines:
                            line_skills = self._extract_skills_from_text(line)
                            skills.extend(line_skills)

        return skills

    def _extract_skills_fallback(
        self, df: pd.DataFrame, design_positions: List[Dict]
    ) -> List[str]:
        """全文搜索技能（最后的备用方法）"""
        skills = []

        # 只搜索设计行下方的文本
        min_design_row = 0
        if design_positions:
            min_design_row = min(pos["row"] for pos in design_positions)

        # 只将设计行下方的内容转换为文本
        text_parts = []
        for idx in range(min_design_row, len(df)):
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

    def _is_valid_skill(self, skill: str) -> bool:
        """验证是否为有效技能"""
        if not skill or len(skill) < 1 or len(skill) > 50:
            return False

        skill = skill.strip()

        # 新增：排除包含 "os" 或 "db" 关键字的技能（不区分大小写）
        skill_lower = skill.lower()
        if "os" in skill_lower or "db" in skill_lower:
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

        # 排除模式
        for pattern in EXCLUDE_PATTERNS:
            if re.match(pattern, skill, re.IGNORECASE):
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
        """标准化技能名称"""
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

        # 技能名称映射
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
            # 数据库
            "MySql": "MySQL",
            "mysql": "MySQL",
            "mybatis": "MyBatis",
            "Mybatis": "MyBatis",
            "MYBATIS": "MyBatis",
            "PostgreSQL": "PostgreSQL",
            "Postgre SQL": "PostgreSQL",
            "SqlServer": "SQL Server",
            "SQLServer": "SQL Server",
            "sqlserver": "SQL Server",
            "SQL SERVER": "SQL Server",
            # 框架
            "spring": "Spring",
            "springboot": "SpringBoot",
            "SpringBoot": "SpringBoot",
            "node.js": "Node.js",
            "Node.JS": "Node.js",
            "nodejs": "Node.js",
            "vue.js": "Vue",
            "react.js": "React",
            "thymeleaf": "Thymeleaf",
            # IDE和工具
            "eclipse": "Eclipse",
            "eclipes": "Eclipse",  # 常见拼写错误
            "ECLIPSE": "Eclipse",
            "vscode": "VS Code",
            "Vscode": "VS Code",
            "VSCode": "VS Code",
            "VScode": "VS Code",
            "VS Code": "VS Code",
            "VS code": "VS Code",
            "vs code": "VS Code",
            "Visual Studio Code": "VS Code",
            "junit": "JUnit",
            "Junit": "JUnit",
            "JUNIT": "JUnit",
            "github": "GitHub",
            "GITHUB": "GitHub",
            "svn": "SVN",
            "Svn": "SVN",
            "TortoiseSVN": "TortoiseSVN",
            "Tortoise SVN": "TortoiseSVN",
            "winmerge": "WinMerge",
            "WINMERGE": "WinMerge",
            "teraterm": "TeraTerm",
            "TERATERM": "TeraTerm",
            "Tera Term": "TeraTerm",
            # 协作工具
            "slack": "Slack",
            "SLACK": "Slack",
            "teams": "Teams",
            "TEAMS": "Teams",
            "ovice": "oVice",
            "Ovice": "oVice",
            # 云服务
            "aws": "AWS",
            "Aws": "AWS",
            "azure": "Azure",
            "AZURE": "Azure",
            "Azure SQL DB": "Azure SQL Database",
            # AWS服务标准化
            "glue": "AWS Glue",
            "S3": "AWS S3",
            "Lambda": "AWS Lambda",
            "EC2": "AWS EC2",
            "IAM": "AWS IAM",
            "codecommit": "AWS CodeCommit",
            # 其他
            "dynamics365": "Dynamics 365",
            "Dynamics365": "Dynamics 365",
            "FO": "Finance and Operations",
            "JP1": "JP1",
            "jp1": "JP1",
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
