# -*- coding: utf-8 -*-
"""技能提取器 - 最终完整版"""

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
        """提取技能列表 - 只提取项目经验部分的技能"""
        all_skills = []

        for data in all_data:
            df = data["df"]
            sheet_name = data.get("sheet_name", "Unknown")

            print(f"\n🔍 开始技术关键字提取 - Sheet: {sheet_name}")
            print(f"    表格大小: {df.shape[0]}行 x {df.shape[1]}列")

            # 从下往上找项目表头行
            project_start_row = self._find_project_start_row(df)

            if project_start_row is not None:
                print(f"    ✅ 找到项目表头行: 第{project_start_row + 1}行")
                print(f"    📍 只提取第{project_start_row + 1}行之下的项目经验技能")

                # 方法1：项目经验行技能提取（主要方法）
                project_skills = self._extract_project_row_skills(df, project_start_row)
                print(
                    f"    📊 项目经验行提取到: {len(project_skills)} 个技能: {project_skills}"
                )
                all_skills.extend(project_skills)

                # 方法2：项目经验区域的横向技能提取（补充方法）
                horizontal_skills = self._extract_skills_from_horizontal_table_limited(
                    df, project_start_row
                )
                print(
                    f"    📊 项目经验横向提取到: {len(horizontal_skills)} 个技能: {horizontal_skills}"
                )
                all_skills.extend(horizontal_skills)

                # 如果技能还是太少，使用备用方法（仅限项目经验区域）
                if len(all_skills) < 15:
                    print(f"    技能数量不足，使用备用方法补充（仅限项目经验区域）")
                    fallback_skills = self._extract_skills_fallback_limited(
                        df, project_start_row
                    )
                    print(
                        f"    📊 备用方法提取到: {len(fallback_skills)} 个技能: {fallback_skills}"
                    )
                    all_skills.extend(fallback_skills)

                print(f"    📊 所有方法共提取到: {len(all_skills)} 个原始技能")
            else:
                print("    ❌ 未找到项目表头关键词，无法确定提取范围")
                print("    🚫 跳过该表格，不进行任何技能提取")

        # 去重和标准化
        print(f"\n🔄 开始去重和标准化...")
        print(f"    输入技能数量: {len(all_skills)}")
        final_skills = self._process_and_deduplicate_skills(all_skills)

        final_skills = [
            re.sub(r"\s+", " ", skill.strip())
            for skill in final_skills
            if skill and isinstance(skill, str)
        ]

        final_skills = self._split_valid_skills(final_skills)
        print(f"    输出技能数量: {len(final_skills)}")

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

    def _extract_project_row_skills(
        self, df: pd.DataFrame, project_start_row: int
    ) -> List[str]:
        """提取项目经验行中的技能（专门处理项目数据行）- 修复版本"""
        skills = []

        print(f"    使用项目经验行提取方法（从第{project_start_row + 1}行之下）...")

        # **关键修复：从project_start_row+1开始查找项目数据行**
        for row in range(project_start_row + 1, len(df)):
            row_data = df.iloc[row]

            # **修复：检查是否是项目数据行（第一列通常是项目编号）**
            first_cell = row_data.iloc[0] if len(row_data) > 0 else None
            if pd.notna(first_cell):
                first_cell_str = str(first_cell).strip()
                # 检查是否是数字项目编号
                if first_cell_str.isdigit():
                    print(
                        f"        发现项目数据行: 第{row + 1}行，项目编号: {first_cell_str}"
                    )

                    # **关键修复：查找包含技能的列**
                    for col_idx in range(len(row_data)):
                        cell = row_data.iloc[col_idx]
                        if pd.notna(cell):
                            cell_str = str(cell).strip()

                            # **修复：检查是否包含换行符分隔的多个技能**
                            if "\r\n" in cell_str or "\n" in cell_str:
                                lines = re.split(r"\r?\n", cell_str)
                                tech_lines = []
                                for line in lines:
                                    line = line.strip()
                                    if line and self._is_likely_tech_skill(line):
                                        tech_lines.append(line)

                                if len(tech_lines) >= 2:  # 至少2个技能才认为是技能列
                                    print(
                                        f"            第{col_idx + 1}列包含{len(tech_lines)}个技能:"
                                    )
                                    for line in tech_lines:
                                        if self._is_valid_skill(line):
                                            normalized = self._normalize_skill_name(
                                                line
                                            )
                                            skills.append(normalized)
                                            print(
                                                f"              - {line} -> {normalized}"
                                            )

                            # **修复：检查单个技能（数据库名等）**
                            elif self._is_likely_single_tech_skill(cell_str):
                                if self._is_valid_skill(cell_str):
                                    normalized = self._normalize_skill_name(cell_str)
                                    skills.append(normalized)
                                    print(
                                        f"            第{col_idx + 1}列单个技能: {cell_str} -> {normalized}"
                                    )

        print(f"    项目经验行提取完成，共找到 {len(skills)} 个技能")
        return skills

    def _is_likely_tech_skill(self, text: str) -> bool:
        """判断是否可能是技术技能"""
        if not text or len(text) < 2 or len(text) > 30:
            return False

        # 排除明显非技能的内容
        if text in ["●", "○", "◎", "△", "×"]:
            return False
        if text.isdigit():
            return False
        if text.upper() in ["PM", "PL", "SL", "TL", "BSE", "SE", "PG"]:
            return False

        # 🔥 修复：添加对括号的支持
        # 常见技能模式
        tech_patterns = [
            r"^[A-Za-z#][A-Za-z0-9#\s\.\+\-\(\)]*$",  # 🔥 添加了 # 和 \(\) 支持 C# ASP.NET(MVC 5)
            r"^[A-Za-z][A-Za-z0-9]*\.[A-Za-z][A-Za-z0-9]*$",  # 如 Node.js
            r"^[A-Za-z]+[0-9]*$",  # 如 HTML5
        ]

        return any(re.match(pattern, text) for pattern in tech_patterns)

    def _is_likely_single_tech_skill(self, text: str) -> bool:
        """判断是否可能是单个技术技能"""
        # 常见的单个技能（数据库、操作系统等）
        common_single_skills = [
            "PostgreSQL",
            "MySQL",
            "Oracle",
            "Windows",
            "Linux",
            "macOS",
            "MongoDB",
            "Redis",
            "SQLite",
            "DB2",
            "Access",
        ]

        return text in common_single_skills or self._is_likely_tech_skill(text)

    def _extract_skills_from_horizontal_table_limited(
        self, df: pd.DataFrame, project_start_row: int
    ) -> List[str]:
        """
        处理横向多列技能表格（限制在project_start_row之下）- 修复版本
        **只处理项目经验部分，不处理简历上半部分的技能表格**
        """
        skills = []

        print(
            f"    使用横向表格提取方法（只处理第{project_start_row + 1}行之下的项目经验）..."
        )

        # **修复：只查找project_start_row之下的项目经验区域**
        for row in range(project_start_row + 1, len(df)):
            row_data = df.iloc[row]

            # 检查该行是否包含项目相关的技能信息
            # 跳过项目数据行，查找项目说明行或其他包含技能的行
            first_cell = row_data.iloc[0] if len(row_data) > 0 else None

            # 跳过项目编号行（由方法1处理）
            if pd.notna(first_cell) and str(first_cell).strip().isdigit():
                continue

            # 查找包含技能的行
            for col_idx, cell in enumerate(row_data):
                if pd.notna(cell):
                    cell_str = str(cell).strip()

                    # 检查是否包含多个技能（用换行符分隔）
                    if "\r\n" in cell_str or "\n" in cell_str:
                        lines = re.split(r"\r?\n", cell_str)
                        tech_count = 0
                        for line in lines:
                            line = line.strip()
                            if line and self._is_likely_tech_skill(line):
                                tech_count += 1

                        # 如果包含多个技能，提取它们
                        if tech_count >= 2:
                            print(
                                f"        第{row + 1}行第{col_idx + 1}列包含{tech_count}个技能:"
                            )
                            for line in lines:
                                line = line.strip()
                                if line and self._is_likely_tech_skill(line):
                                    if self._is_valid_skill(line):
                                        normalized = self._normalize_skill_name(line)
                                        skills.append(normalized)
                                        print(f"            - {line} -> {normalized}")

        print(f"    横向表格提取完成，共找到 {len(skills)} 个技能")
        return skills

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
        # if any(bracket in skill for bracket in ["(", ")", "（", "）"]):
        #     return False

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
            "eclipes": "Eclipse",  # **修复拼写错误**
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
            # 协作工具
            "slack": "Slack",
            "Slack": "Slack",
            "SLACK": "Slack",
            "teams": "Teams",
            "Teams": "Teams",
            "TEAMS": "Teams",
            "ovice": "oVice",
            "Ovice": "oVice",
            "oVice": "oVice",
            # 其他工具
            "teraterm": "TeraTerm",
            "TeraTerm": "TeraTerm",
            "TERATERM": "TeraTerm",
            "Tera Term": "TeraTerm",
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

    # 保持兼容性的方法（避免其他地方调用出错）
    def _find_min_design_row(self, df: pd.DataFrame) -> Optional[int]:
        """兼容性方法：重定向到新的项目表头查找方法"""
        return self._find_project_start_row(df)

    def _extract_skills_by_design_column(
        self, df: pd.DataFrame
    ) -> Tuple[List[str], List[Dict]]:
        """基于工程阶段列定位并提取技术列（保持兼容性）"""
        return [], []

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

    def _split_valid_skills(self, final_skills):
        """
        智能拆分技能列表中的复合技能
        这个方法可以直接添加到 SkillsExtractor 类中
        """
        # 导入有效技能列表
        try:
            from app.base.constants import VALID_SKILLS
        except ImportError:
            try:
                from app.utils.resume_constants import VALID_SKILLS
            except ImportError:
                # 使用内置的核心技能列表
                VALID_SKILLS = {
                    "Java",
                    "Python",
                    "JavaScript",
                    "TypeScript",
                    "C",
                    "C++",
                    "C#",
                    "PHP",
                    "Ruby",
                    "Go",
                    "Eclipse",
                    "IntelliJ",
                    "VS Code",
                    "React",
                    "Vue",
                    "Angular",
                    "Spring",
                    "SpringBoot",
                    "Node.js",
                    "MySQL",
                    "PostgreSQL",
                    "Oracle",
                    "MongoDB",
                    "Git",
                    "GitHub",
                    "SVN",
                    "Docker",
                    "AWS",
                    "Azure",
                    "HTML",
                    "CSS",
                    "Bootstrap",
                    "jQuery",
                }

        if not final_skills:
            return final_skills

        # 处理 VALID_SKILLS 的不同格式
        if isinstance(VALID_SKILLS, (list, tuple)):
            valid_skills_set = set(VALID_SKILLS)
        else:
            valid_skills_set = VALID_SKILLS

        # 创建不区分大小写的映射
        skill_mapping = {}
        for skill in valid_skills_set:
            if isinstance(skill, str):
                skill_mapping[skill.lower()] = skill

        result_skills = []

        for skill in final_skills:
            if not skill or not isinstance(skill, str):
                continue

            skill = skill.strip()
            if not skill:
                continue

            # 按空格拆分
            parts = skill.split()

            if len(parts) <= 1:
                # 单个词，直接添加
                result_skills.append(skill)
            else:
                # 多个词，检查拆分
                valid_parts = []

                for part in parts:
                    part_clean = part.strip()
                    if part_clean.lower() in skill_mapping:
                        # 使用标准格式的技能名称
                        valid_parts.append(skill_mapping[part_clean.lower()])
                    else:
                        # 检查常见变体
                        variants = {
                            "eclipse": "Eclipse",
                            "eclipes": "Eclipse",
                            "intellij": "IntelliJ",
                            "vscode": "VS Code",
                            "github": "GitHub",
                            "springboot": "SpringBoot",
                            "nodejs": "Node.js",
                            "mysql": "MySQL",
                        }

                        if part_clean.lower() in variants:
                            valid_parts.append(variants[part_clean.lower()])

                if len(valid_parts) >= 2:
                    # 成功拆分为多个有效技能
                    print(f"🔧 拆分技能: '{skill}' -> {valid_parts}")
                    result_skills.extend(valid_parts)
                else:
                    # 无法有效拆分，保持原样
                    result_skills.append(skill)

        # 去重
        seen = set()
        final_result = []

        for skill in result_skills:
            if skill and skill.lower() not in seen:
                seen.add(skill.lower())
                final_result.append(skill)

        return final_result
