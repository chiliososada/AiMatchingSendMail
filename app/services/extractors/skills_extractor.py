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
        """使用 design_keywords 从下往上查找项目表头行"""
        print(f"    🔍 使用design_keywords查找项目表头行...")

        # 从下往上扫描，找到包含>=3个工程阶段关键词的行
        for row in range(len(df) - 1, -1, -1):
            design_count = 0
            found_keywords = []

            for col in range(len(df.columns)):
                cell = df.iloc[row, col]
                if pd.notna(cell):
                    cell_str = str(cell).strip()

                    # 使用 design_keywords 而不是 project_header_keywords
                    for keyword in self.design_keywords:
                        if keyword in cell_str:
                            design_count += 1
                            found_keywords.append(keyword)
                            break

            # 如果该行包含3个或以上的工程阶段关键词，认为是项目表头
            if design_count >= 3:
                print(f"    ✅ 找到项目表头行: 第{row + 1}行")
                print(f"    📍 包含工程阶段关键词: {found_keywords}")
                return row

        print(f"    ❌ 未找到包含足够工程阶段关键词的项目表头行")
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
                                            normalized = self._extract_skills_from_text(
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
        """判断是否可能是技术技能 - 修复版本"""
        if (
            not text or len(text) < 2 or len(text) > 100
        ):  # 🔥 增加长度限制，支持复杂技能
            return False

        # 排除明显非技能的内容
        if text in ["●", "○", "◎", "△", "×"]:
            return False
        if text.isdigit():
            return False
        if text.upper() in ["PM", "PL", "SL", "TL", "BSE", "SE", "PG"]:
            return False

        # 🔥 修复：特殊检查包含AWS的复杂格式
        if "AWS" in text.upper():
            print(f"        检测到AWS相关内容: {text}")
            return True

        # 🔥 修复：检查是否包含已知的技术关键词
        known_tech_keywords = [
            "Python",
            "Java",
            "JavaScript",
            "C#",
            "C++",
            "PHP",
            "Ruby",
            "Go",
            "Spring",
            "React",
            "Vue",
            "Angular",
            "Node.js",
            "jQuery",
            "MySQL",
            "PostgreSQL",
            "Oracle",
            "MongoDB",
            "Redis",
            "Windows",
            "Linux",
            "Unix",
            "macOS",
            "Git",
            "SVN",
            "GitHub",
            "Docker",
            "Kubernetes",
            "Eclipse",
            "IntelliJ",
            "VS Code",
            "Visual Studio",
            "TeraTerm",
            "JP1",
            "HTML",
            "CSS",
            "Bootstrap",
        ]

        text_upper = text.upper()
        for keyword in known_tech_keywords:
            if keyword.upper() in text_upper:
                print(f"        包含已知技术关键词 '{keyword}': {text}")
                return True

        # 🔥 修复：更完善的技能模式匹配，支持全角括号和复杂格式
        tech_patterns = [
            r"^[A-Za-z#][A-Za-z0-9#\s\.\+\-\(\)（）/／]*$",  # 🔥 支持全角括号和斜杠
            r"^[A-Za-z][A-Za-z0-9]*\.[A-Za-z][A-Za-z0-9]*$",  # 如 Node.js
            r"^[A-Za-z]+[0-9]*$",  # 如 HTML5
            r"^AWS\s+\w+$",  # AWS服务如 "AWS S3"
            r".*AWS.*（.*）.*",  # AWS括号格式：AWS（service1/service2）
            r".*[A-Za-z]+.*[（(].*[）)].*",  # 任何包含字母和括号的组合
        ]

        for pattern in tech_patterns:
            if re.match(pattern, text):
                print(f"        匹配技能模式: {text}")
                return True

        return False

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
                                    print(f"            处理技能行: '{line}'")

                                    # 🔥 关键修复：使用 _extract_skills_from_text 处理复杂技能
                                    line_skills = self._extract_skills_from_text(line)
                                    skills.extend(line_skills)
                                    print(f"            提取结果: {line_skills}")

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
        """从文本中提取技能 - 完整修复版本"""
        skills = []
        text = text.strip()

        if not text:
            return skills

        # 移除标记符号
        text = re.sub(r"^[◎○△×★●◯▲※・\-\s]+", "", text)

        print(f"        处理文本: '{text}'")

        # 处理括号内的内容
        bracket_patterns = [
            r"([^（(]+)\s*（([^）]+)）",  # 全角括号（优先匹配）
            r"([^（(]+)\s*\(([^)]+)\)",  # 半角括号
        ]

        bracket_match = None
        # 循环匹配每个正则表达式
        for pattern in bracket_patterns:
            bracket_match = re.match(pattern, text)
            if bracket_match:
                print(f"        ✅ 匹配到括号模式: {pattern}")
                break

        if bracket_match:
            # 括号前的内容
            main_part = bracket_match.group(1).strip()
            # 括号内的内容
            bracket_content = bracket_match.group(2).strip()

            print(f"        主要部分: '{main_part}'")
            print(f"        括号内容: '{bracket_content}'")

            # 提取主要部分的技能
            main_skills = self._split_and_validate_skills(main_part)
            skills.extend(main_skills)
            print(f"        主要部分提取的技能: {main_skills}")

            # 🔥 关键修复：检查主要部分是否包含AWS
            main_part_upper = main_part.upper()
            if "AWS" in main_part_upper:
                print(f"        检测到AWS，处理括号内的服务...")
                # 括号内是AWS服务列表，使用专门的AWS服务提取方法
                aws_services = self._extract_aws_services(bracket_content)
                skills.extend(aws_services)
                print(f"        AWS服务: {aws_services}")

                # 🔥 处理括号后可能的其他技能
                remaining_text = text[bracket_match.end() :].strip()
                print(f"        括号后剩余文本: '{remaining_text}'")

                if remaining_text.startswith("/") or remaining_text.startswith("／"):
                    remaining_text = remaining_text[1:].strip()

                if remaining_text:
                    remaining_skills = self._split_and_validate_skills(remaining_text)
                    skills.extend(remaining_skills)
                    print(f"        括号后的技能: {remaining_skills}")
            else:
                # 普通的括号内容处理
                bracket_skills = self._split_and_validate_skills(bracket_content)
                skills.extend(bracket_skills)
                print(f"        普通括号内容技能: {bracket_skills}")
        else:
            # 没有括号，直接提取
            print(f"        无括号模式，直接分割")
            skills.extend(self._split_and_validate_skills(text))

        print(f"        _extract_skills_from_text 最终结果: {skills}")
        return skills

    def _extract_aws_services(self, services_text: str) -> List[str]:
        """专门提取AWS服务的方法"""
        aws_skills = ["AWS"]  # 总是包含AWS主技能

        # 分割AWS服务，支持 / 和 ／
        services = re.split(r"[/／]+", services_text)

        for service in services:
            service = service.strip()
            if service:
                normalized_service = self._normalize_aws_service(service)
                if normalized_service:
                    aws_skills.append(f"AWS {normalized_service}")

        return aws_skills

    def _normalize_aws_service(self, service: str) -> str:
        """规范化AWS服务名称"""
        aws_service_mapping = {
            "glue": "Glue",
            "s3": "S3",
            "lambda": "Lambda",
            "ec2": "EC2",
            "iam": "IAM",
            "codecommit": "CodeCommit",
        }

        service_lower = service.lower()
        return aws_service_mapping.get(service_lower, service)

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

    def _normalize_skill_name(self, skill) -> str:
        """标准化技能名称 - 修复版本，处理各种数据类型"""
        # 🔥 关键修复：处理各种可能的数据类型
        if skill is None:
            return ""

        # 如果是列表类型，尝试处理
        if isinstance(skill, list):
            if not skill:  # 空列表
                return ""
            # 取第一个非空元素
            for item in skill:
                if item and str(item).strip():
                    skill = str(item).strip()
                    break
            else:
                return ""  # 列表中没有有效数据

        # 如果是其他非字符串类型，转换为字符串
        if not isinstance(skill, str):
            skill = str(skill)

        # 现在可以安全地调用字符串方法
        skill = skill.strip()

        if not skill:
            return ""

        # 移除多余的空格
        skill = re.sub(r"\s+", " ", skill)

        # 移除引号
        skill = skill.strip('"\'""' "")

        # 标准化常见技能名称
        skill_mappings = {
            "javascript": "JavaScript",
            "js": "JavaScript",
            "typescript": "TypeScript",
            "ts": "TypeScript",
            "nodejs": "Node.js",
            "node.js": "Node.js",
            "node": "Node.js",
            "reactjs": "React",
            "react.js": "React",
            "vuejs": "Vue.js",
            "vue.js": "Vue.js",
            "vue": "Vue.js",
            "angularjs": "Angular",
            "angular.js": "Angular",
            "c++": "C++",
            "cpp": "C++",
            "c#": "C#",
            "csharp": "C#",
            "visualstudio": "Visual Studio",
            "vs": "Visual Studio",
            "vscode": "VS Code",
            "sqlserver": "SQL Server",
            "sql server": "SQL Server",
            "mysql": "MySQL",
            "postgresql": "PostgreSQL",
            "postgres": "PostgreSQL",
            "mongodb": "MongoDB",
            "mongo": "MongoDB",
            "redis": "Redis",
            "elasticsearch": "Elasticsearch",
            "aws": "AWS",
            "azure": "Azure",
            "gcp": "GCP",
            "docker": "Docker",
            "kubernetes": "Kubernetes",
            "k8s": "Kubernetes",
            "git": "Git",
            "github": "GitHub",
            "gitlab": "GitLab",
            "jenkins": "Jenkins",
            "maven": "Maven",
            "gradle": "Gradle",
            "spring": "Spring",
            "springboot": "Spring Boot",
            "spring boot": "Spring Boot",
            "hibernate": "Hibernate",
            "django": "Django",
            "flask": "Flask",
            "rails": "Ruby on Rails",
            "ruby on rails": "Ruby on Rails",
            "laravel": "Laravel",
            "symfony": "Symfony",
            "codeigniter": "CodeIgniter",
            "express": "Express.js",
            "express.js": "Express.js",
            "fastapi": "FastAPI",
            "tornado": "Tornado",
            "pandas": "Pandas",
            "numpy": "NumPy",
            "scikit-learn": "Scikit-learn",
            "sklearn": "Scikit-learn",
            "tensorflow": "TensorFlow",
            "pytorch": "PyTorch",
            "keras": "Keras",
            "opencv": "OpenCV",
            "matplotlib": "Matplotlib",
            "seaborn": "Seaborn",
            "plotly": "Plotly",
            "jupyter": "Jupyter",
            "anaconda": "Anaconda",
            "conda": "Conda",
            "pip": "pip",
            "npm": "npm",
            "yarn": "Yarn",
            "webpack": "Webpack",
            "babel": "Babel",
            "eslint": "ESLint",
            "prettier": "Prettier",
            "jest": "Jest",
            "mocha": "Mocha",
            "chai": "Chai",
            "cypress": "Cypress",
            "selenium": "Selenium",
            "junit": "JUnit",
            "testng": "TestNG",
            "mockito": "Mockito",
            "postman": "Postman",
            "swagger": "Swagger",
            "rest": "REST",
            "restful": "RESTful",
            "graphql": "GraphQL",
            "soap": "SOAP",
            "json": "JSON",
            "xml": "XML",
            "yaml": "YAML",
            "yml": "YAML",
            "html": "HTML",
            "html5": "HTML5",
            "css": "CSS",
            "css3": "CSS3",
            "sass": "Sass",
            "scss": "SCSS",
            "less": "Less",
            "bootstrap": "Bootstrap",
            "tailwind": "Tailwind CSS",
            "tailwindcss": "Tailwind CSS",
            "materialui": "Material-UI",
            "material-ui": "Material-UI",
            "mui": "Material-UI",
            "antd": "Ant Design",
            "ant design": "Ant Design",
            "redux": "Redux",
            "mobx": "MobX",
            "vuex": "Vuex",
            "pinia": "Pinia",
            "nginx": "Nginx",
            "apache": "Apache",
            "tomcat": "Tomcat",
            "jetty": "Jetty",
            "iis": "IIS",
            "linux": "Linux",
            "ubuntu": "Ubuntu",
            "centos": "CentOS",
            "redhat": "Red Hat",
            "debian": "Debian",
            "windows": "Windows",
            "macos": "macOS",
            "ios": "iOS",
            "android": "Android",
            "flutter": "Flutter",
            "react native": "React Native",
            "xamarin": "Xamarin",
            "unity": "Unity",
            "unreal": "Unreal Engine",
            "blender": "Blender",
            "photoshop": "Photoshop",
            "illustrator": "Illustrator",
            "sketch": "Sketch",
            "figma": "Figma",
            "xd": "Adobe XD",
            "adobe xd": "Adobe XD",
            "zeplin": "Zeplin",
            "invision": "InVision",
            "jira": "Jira",
            "confluence": "Confluence",
            "trello": "Trello",
            "asana": "Asana",
            "slack": "Slack",
            "teams": "Microsoft Teams",
            "zoom": "Zoom",
            "office": "Microsoft Office",
            "excel": "Excel",
            "word": "Word",
            "powerpoint": "PowerPoint",
            "outlook": "Outlook",
            "google workspace": "Google Workspace",
            "gsuite": "Google Workspace",
            "gmail": "Gmail",
            "gdrive": "Google Drive",
            "sheets": "Google Sheets",
            "docs": "Google Docs",
            "slides": "Google Slides",
        }

        skill_lower = skill.lower()
        if skill_lower in skill_mappings:
            return skill_mappings[skill_lower]

        # 保持原有格式，但首字母大写（除非已经有特定格式）
        if skill.islower() and len(skill) > 1:
            return skill.capitalize()

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
