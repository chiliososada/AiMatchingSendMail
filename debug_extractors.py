# -*- coding: utf-8 -*-
"""
AiMatchingSendMail 简历提取器调试脚本
用于诊断 arrival_year_japan 和 experience 字段返回 null 的问题
"""

import asyncio
import sys
import traceback
import pandas as pd
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

try:
    from app.services.resume_parser_service import ResumeParserService
except ImportError as e:
    print(f"❌ 无法导入ResumeParserService: {e}")
    sys.exit(1)


async def debug_extraction():
    """调试提取器问题"""

    print("=== AiMatchingSendMail 简历提取器调试 ===\n")

    # 初始化服务
    try:
        parser = ResumeParserService()
        print("✅ 提取器服务初始化成功")
    except Exception as e:
        print(f"❌ 提取器服务初始化失败: {e}")
        traceback.print_exc()
        return

    # 测试导入状态
    print("\n=== 检查导入状态 ===")

    try:
        # 检查各个提取器的状态
        extractors = [
            ("姓名", parser.name_extractor),
            ("来日年份", parser.arrival_year_extractor),
            ("经验", parser.experience_extractor),
            ("年龄", parser.age_extractor),
            ("技能", parser.skills_extractor),
        ]

        for name, extractor in extractors:
            if hasattr(extractor, "__class__"):
                print(f"✅ {name}提取器: {extractor.__class__.__name__}")

                # 检查是否有特定方法
                methods_to_check = [
                    "_extract_from_arrival_labels",
                    "_extract_from_experience_labels",
                    "_extract_from_years_expression",
                    "_search_experience_value",
                ]

                for method in methods_to_check:
                    if hasattr(extractor, method):
                        print(f"   - 有 {method} 方法")

            else:
                print(f"❌ {name}提取器: 未正确初始化")

    except Exception as e:
        print(f"❌ 检查提取器状态时出错: {e}")
        traceback.print_exc()

    # 测试关键词导入
    print("\n=== 检查关键词导入 ===")

    try:
        # 尝试各种导入路径
        import_paths = [
            "base.constants",
            "app.base.constants",
            "app.utils.resume_constants",
            "extractors.constants",
        ]

        keywords_found = False

        for path in import_paths:
            try:
                if path == "base.constants":
                    from base.constants import KEYWORDS
                elif path == "app.base.constants":
                    from app.base.constants import KEYWORDS
                elif path == "app.utils.resume_constants":
                    from app.utils.resume_constants import VALID_SKILLS as KEYWORDS
                elif path == "extractors.constants":
                    from extractors.constants import KEYWORDS

                print(f"✅ 成功从 {path} 导入关键词")

                if isinstance(KEYWORDS, dict):
                    arrival_keys = KEYWORDS.get("arrival", [])
                    experience_keys = KEYWORDS.get("experience", [])

                    print(
                        f"   - arrival 关键词 ({len(arrival_keys)}个): {arrival_keys[:3]}..."
                    )
                    print(
                        f"   - experience 关键词 ({len(experience_keys)}个): {experience_keys[:3]}..."
                    )
                else:
                    print(f"   - 导入的不是字典类型: {type(KEYWORDS)}")

                keywords_found = True
                break

            except ImportError:
                print(f"❌ 无法从 {path} 导入关键词")
            except Exception as e:
                print(f"❌ 从 {path} 导入时出错: {e}")

        if not keywords_found:
            print("❌ 所有导入路径都失败了！这是主要问题原因。")

    except Exception as e:
        print(f"❌ 检查关键词导入时出错: {e}")

    # 测试基类导入
    print("\n=== 检查基类导入 ===")

    base_import_paths = [
        "base.base_extractor",
        "app.base.base_extractor",
        "extractors.base_extractor",
    ]

    for path in base_import_paths:
        try:
            if path == "base.base_extractor":
                from base.base_extractor import BaseExtractor
            elif path == "app.base.base_extractor":
                from app.base.base_extractor import BaseExtractor
            elif path == "extractors.base_extractor":
                from extractors.base_extractor import BaseExtractor

            print(f"✅ 成功从 {path} 导入 BaseExtractor")
            print(
                f"   - 基类方法: {[m for m in dir(BaseExtractor) if not m.startswith('_')]}"
            )
            break

        except ImportError:
            print(f"❌ 无法从 {path} 导入 BaseExtractor")
        except Exception as e:
            print(f"❌ 从 {path} 导入时出错: {e}")

    # 如果有测试文件，进行实际提取测试
    print("\n=== 文件提取测试 ===")
    test_file = input("请输入测试文件路径（留空跳过测试）: ").strip()

    if test_file and Path(test_file).exists():
        print(f"\n测试文件提取: {test_file}")

        try:
            result = await parser.parse_resume(test_file)

            print(f"✅ 解析完成，成功: {result.get('success', False)}")
            print(f"解析耗时: {result.get('parse_time', 0):.3f}秒")

            if result.get("success"):
                data = result.get("data", {})

                # 重点检查问题字段
                problem_fields = ["arrival_year_japan", "experience"]

                print("\n🔍 重点字段检查:")
                for field in problem_fields:
                    value = data.get(field)
                    value_type = type(value).__name__
                    value_str = f"'{value}'" if isinstance(value, str) else str(value)

                    if value is None:
                        print(
                            f"  ❌ {field}: {value_str} (类型: {value_type}) - 问题！应该有值"
                        )
                    else:
                        print(f"  ✅ {field}: {value_str} (类型: {value_type}) - 正常")

                print(f"\n📋 完整提取结果:")
                for key, value in data.items():
                    indicator = (
                        "❌" if value is None and key in problem_fields else "✅"
                    )
                    print(f"  {indicator} {key}: {value}")

            else:
                error_msg = result.get("error", "Unknown error")
                print(f"❌ 解析失败: {error_msg}")

        except Exception as e:
            print(f"❌ 解析过程中出错: {e}")
            traceback.print_exc()

    elif test_file:
        print(f"❌ 文件不存在: {test_file}")

    print("\n=== 调试完成 ===")


def create_test_data():
    """创建测试数据进行简单验证"""

    print("\n=== 创建测试数据验证 ===")

    # 创建模拟的Excel数据
    test_data = [
        {
            "df": pd.DataFrame(
                {
                    "A": ["氏名", "来日年", "実務経験", "年齢", "性別"],
                    "B": ["エン", "2016", "4年", "27", "男性"],
                    "C": [None, None, None, None, None],
                }
            ),
            "sheet_name": "test_sheet",
        }
    ]

    print("📋 测试数据:")
    print(test_data[0]["df"])

    # 测试各个提取器
    try:
        parser = ResumeParserService()

        # 测试来日年份提取
        print("\n🔍 测试来日年份提取:")
        try:
            arrival_result = parser.arrival_year_extractor.extract(test_data, None)
            print(f"结果: {arrival_result}")
            if arrival_result == "2016":
                print("✅ 来日年份提取正常")
            else:
                print("❌ 来日年份提取异常")
        except Exception as e:
            print(f"❌ 来日年份提取失败: {e}")
            traceback.print_exc()

        # 测试经验提取
        print("\n🔍 测试经验提取:")
        try:
            experience_result = parser.experience_extractor.extract(test_data)
            print(f"结果: {experience_result}")
            if experience_result == "4年":
                print("✅ 经验提取正常")
            else:
                print("❌ 经验提取异常")
        except Exception as e:
            print(f"❌ 经验提取失败: {e}")
            traceback.print_exc()

    except Exception as e:
        print(f"❌ 创建解析器失败: {e}")


def create_fix_constants_file():
    """创建修复用的常量文件"""

    print("\n=== 创建修复文件 ===")

    constants_content = '''# -*- coding: utf-8 -*-
"""常量定义 - 修复版本"""

# 关键词定义
KEYWORDS = {
    "name": ["氏名", "氏 名", "名前", "フリガナ", "Name", "名　前", "姓名"],
    "age": ["年齢", "年龄", "年令", "歳", "才", "Age", "年　齢", "生年月", "満"],
    "gender": ["性別", "性别", "Gender", "性　別"],
    "nationality": ["国籍", "出身国", "出身地", "Nationality", "国　籍"],
    "experience": [
        "経験年数",
        "実務経験",
        "開発経験", 
        "ソフト関連業務経験年数",
        "IT経験",
        "業務経験",
        "経験",
        "実務年数",
        "Experience",
        "エンジニア経験",
        "経験年月",
        "職歴",
        "IT経験年数",
        "コンピュータソフトウエア関連業務",
    ],
    "arrival": [
        "来日",
        "渡日",
        "入国", 
        "日本滞在年数",
        "滞在年数",
        "在日年数",
        "来日年",
        "来日時期",
        "来日年月",
        "来日年度",
    ],
    "japanese": [
        "日本語",
        "日語",
        "JLPT", 
        "日本語能力",
        "語学力",
        "言語能力",
        "日本語レベル",
        "Japanese",
    ],
    "education": ["学歴", "学校", "大学", "卒業", "専門学校", "高校", "最終学歴"],
    "skills": [
        "技術",
        "スキル",
        "言語",
        "DB",
        "OS", 
        "フレームワーク",
        "ツール",
        "Skills",
        "开发语言",
        "プログラミング言語",
        "データベース",
        "開発環境",
        "技術経験",
    ],
}

# 有效的国籍列表
VALID_NATIONALITIES = [
    "中国", "日本", "韓国", "ベトナム", "フィリピン", "インド", "ネパール",
    "アメリカ", "ブラジル", "台湾", "タイ", "インドネシア", "バングラデシュ",
    "スリランカ", "ミャンマー", "カンボジア", "ラオス", "モンゴル",
]

# 有效技能列表
VALID_SKILLS = [
    # 编程语言
    "Java", "Python", "JavaScript", "C#", "C++", "C", "Go", "Ruby", "PHP",
    "TypeScript", "Swift", "Kotlin", "Rust", "Scala", "R", "VB.NET", "VB",
    "VBA", "COBOL", "Perl", "Shell", "Bash", "PowerShell",
    # 前端技术
    "HTML", "CSS", "React", "Vue", "Angular", "jQuery", "Bootstrap", 
    "Sass", "Less", "Webpack", "Next.js", "React Native", "Flutter",
    # 后端框架
    "Spring", "SpringBoot", "Spring Boot", "Django", "Flask", "FastAPI",
    "Express", "Node.js", "Rails", "Laravel", ".NET", "ASP.NET", "Struts",
    "Hibernate", "MyBatis", "Mybatis", "JSP", "Servlet",
    # 数据库
    "MySQL", "PostgreSQL", "Oracle", "SQL Server", "MongoDB", "Redis",
    "Elasticsearch", "SQLite", "DB2", "Access", "Firebase",
    # 云服务和工具
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Git", "SVN", "Jenkins",
    "Eclipse", "IntelliJ IDEA", "Visual Studio", "VS Code",
    # 操作系统
    "Windows", "Linux", "Unix", "macOS", "Ubuntu", "CentOS", "Red Hat",
    # 其他技术
    "REST", "GraphQL", "SOAP", "WebSocket", "Nginx", "Apache", "Tomcat",
]
'''

    try:
        # 创建目录结构
        base_dir = Path("app/base")
        base_dir.mkdir(parents=True, exist_ok=True)

        # 写入常量文件
        constants_file = base_dir / "constants.py"
        with open(constants_file, "w", encoding="utf-8") as f:
            f.write(constants_content)

        # 创建__init__.py
        init_content = """from .constants import KEYWORDS, VALID_SKILLS, VALID_NATIONALITIES

__all__ = ["KEYWORDS", "VALID_SKILLS", "VALID_NATIONALITIES"]
"""

        init_file = base_dir / "__init__.py"
        with open(init_file, "w", encoding="utf-8") as f:
            f.write(init_content)

        print(f"✅ 已创建修复文件:")
        print(f"   - {constants_file}")
        print(f"   - {init_file}")

        # 创建基类文件
        base_extractor_content = '''# -*- coding: utf-8 -*-
"""基础提取器类"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import pandas as pd


class BaseExtractor(ABC):
    """所有提取器的基类"""

    def __init__(self):
        """初始化基础提取器"""
        # 全角转半角的转换表
        self.trans_table = str.maketrans("０１２３４５６７８９", "0123456789")

    @abstractmethod
    def extract(self, all_data: List[Dict[str, Any]]) -> Any:
        """提取信息的抽象方法"""
        pass

    def has_nearby_keyword(
        self, df: pd.DataFrame, row: int, col: int, keywords: List[str], radius: int = 5
    ) -> bool:
        """检查附近是否有关键词"""
        for r in range(max(0, row - radius), min(len(df), row + radius + 1)):
            for c in range(max(0, col - radius), min(len(df.columns), col + radius + 1)):
                cell = df.iloc[r, c]
                if pd.notna(cell) and any(k in str(cell) for k in keywords):
                    return True
        return False

    def get_context_score(
        self, df: pd.DataFrame, row: int, col: int, context_keywords: List[str]
    ) -> float:
        """计算上下文评分"""
        score = 0.0
        for r in range(max(0, row - 3), min(len(df), row + 4)):
            for c in range(max(0, col - 5), min(len(df.columns), col + 6)):
                cell = df.iloc[r, c]
                if pd.notna(cell):
                    cell_str = str(cell)
                    for keyword in context_keywords:
                        if keyword in cell_str:
                            score += 1.0
        return score
'''

        base_extractor_file = base_dir / "base_extractor.py"
        with open(base_extractor_file, "w", encoding="utf-8") as f:
            f.write(base_extractor_content)

        print(f"   - {base_extractor_file}")

        print("\n💡 创建完成后，请修改提取器文件中的导入语句:")
        print("   将 'from base.constants import KEYWORDS'")
        print("   改为 'from app.base.constants import KEYWORDS'")

    except Exception as e:
        print(f"❌ 创建修复文件失败: {e}")
        traceback.print_exc()


def show_import_fix_guide():
    """显示导入修复指南"""

    print("\n=== 导入问题修复指南 ===")

    print("\n📋 需要修改的文件和导入语句:")

    files_to_fix = [
        "app/services/extractors/arrival_year_extractor.py",
        "app/services/extractors/experience_extractor.py",
        "app/services/extractors/age_extractor.py",
        "app/services/extractors/birthdate_extractor.py",
        "app/services/extractors/name_extractor.py",
        "app/services/extractors/skills_extractor.py",
        # 添加其他提取器文件
    ]

    print("\n🔧 修改步骤:")
    for i, file_path in enumerate(files_to_fix, 1):
        print(f"\n{i}. 编辑 {file_path}")
        print("   找到:")
        print("     from base.constants import KEYWORDS")
        print("     from base.base_extractor import BaseExtractor")
        print("   替换为:")
        print("     from app.base.constants import KEYWORDS")
        print("     from app.base.base_extractor import BaseExtractor")

    print("\n📝 批量替换命令 (Linux/Mac):")
    print(
        "find app/services/extractors/ -name '*.py' -exec sed -i 's/from base\\.constants/from app.base.constants/g' {} \\;"
    )
    print(
        "find app/services/extractors/ -name '*.py' -exec sed -i 's/from base\\.base_extractor/from app.base.base_extractor/g' {} \\;"
    )

    print("\n📝 批量替换命令 (Windows PowerShell):")
    print(
        "Get-ChildItem app/services/extractors/*.py | ForEach-Object { (Get-Content $_) -replace 'from base\\.constants', 'from app.base.constants' | Set-Content $_ }"
    )
    print(
        "Get-ChildItem app/services/extractors/*.py | ForEach-Object { (Get-Content $_) -replace 'from base\\.base_extractor', 'from app.base.base_extractor' | Set-Content $_ }"
    )


def main():
    """主函数"""
    print("🔧 AiMatchingSendMail 提取器调试工具")
    print("=" * 50)
    print("1. 运行完整调试检查")
    print("2. 创建测试数据验证")
    print("3. 创建修复用常量文件")
    print("4. 显示导入修复指南")
    print("5. 退出")

    while True:
        choice = input("\n请选择操作 (1-5): ").strip()

        if choice == "1":
            asyncio.run(debug_extraction())
        elif choice == "2":
            create_test_data()
        elif choice == "3":
            create_fix_constants_file()
        elif choice == "4":
            show_import_fix_guide()
        elif choice == "5":
            print("👋 退出调试工具")
            break
        else:
            print("❌ 无效选择，请输入 1-5")


if __name__ == "__main__":
    main()
