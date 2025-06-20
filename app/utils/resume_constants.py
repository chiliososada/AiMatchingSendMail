# app/utils/resume_constants.py
"""简历解析相关常量定义"""

# 从 base/constants.py 迁移
VALID_SKILLS = [
    # 编程语言
    "Java",
    "Python",
    "JavaScript",
    "C#",
    "C++",
    "C",
    "Go",
    "Ruby",
    "PHP",
    "TypeScript",
    "Swift",
    "Kotlin",
    "Rust",
    "Scala",
    "R",
    "MATLAB",
    "VB.NET",
    "VB",
    "VBA",
    "COBOL",
    "Fortran",
    "Pascal",
    "Delphi",
    "Perl",
    "Shell",
    "Bash",
    "PowerShell",
    # 前端技术
    "HTML",
    "CSS",
    "React",
    "Vue",
    "Angular",
    "jQuery",
    "Bootstrap",
    "Sass",
    "Less",
    "Webpack",
    "Next.js",
    "Nuxt.js",
    "Gatsby",
    "React Native",
    "Flutter",
    "Ionic",
    # 后端框架
    "Spring",
    "Spring Boot",
    "Spring MVC",
    "Django",
    "Flask",
    "FastAPI",
    "Express",
    "Node.js",
    "Rails",
    "Laravel",
    "Symfony",
    ".NET",
    "ASP.NET",
    "Struts",
    "Hibernate",
    "MyBatis",
    # 数据库
    "MySQL",
    "PostgreSQL",
    "Oracle",
    "SQL Server",
    "MongoDB",
    "Redis",
    "Elasticsearch",
    "Cassandra",
    "DynamoDB",
    "SQLite",
    "MariaDB",
    "DB2",
    "Sybase",
    "Access",
    "Firebase",
    # 云服务
    "AWS",
    "Azure",
    "GCP",
    "Alibaba Cloud",
    "Docker",
    "Kubernetes",
    "Jenkins",
    "GitLab CI",
    "GitHub Actions",
    "CircleCI",
    "Travis CI",
    # 其他工具
    "Git",
    "SVN",
    "Mercurial",
    "TortoiseSVN",
    "SourceTree",
    "Jira",
    "Confluence",
    "Slack",
    "Teams",
    "Zoom",
    "Eclipse",
    "IntelliJ IDEA",
    "Visual Studio",
    "VS Code",
    "Xcode",
    "Android Studio",
    "NetBeans",
    "Sublime Text",
    "Atom",
    # 操作系统
    "Windows",
    "Linux",
    "Unix",
    "macOS",
    "Ubuntu",
    "CentOS",
    "Debian",
    "Red Hat",
    "SUSE",
    "AIX",
    "Solaris",
    # 其他技术
    "REST",
    "GraphQL",
    "SOAP",
    "gRPC",
    "WebSocket",
    "OAuth",
    "JWT",
    "SSL/TLS",
    "HTTP/HTTPS",
    "TCP/IP",
    "DNS",
    "Nginx",
    "Apache",
    "IIS",
    "Tomcat",
    "WebLogic",
    "WebSphere",
    "RabbitMQ",
    "Kafka",
    "ActiveMQ",
    "ZeroMQ",
    "Hadoop",
    "Spark",
    "Hive",
    "HBase",
    "Flink",
    "TensorFlow",
    "PyTorch",
    "Keras",
    "scikit-learn",
    "Unity",
    "Unreal Engine",
    "Cocos2d",
    "Photoshop",
    "Illustrator",
    "Sketch",
    "Figma",
    "Adobe XD",
    # 日本相关
    "TeraTerm",
    "Tera Term",
    "JP1",
    "Hulft",
    "A5:SQL",
    "秀丸",
    "サクラエディタ",
    "WinSCP",
    "FFFTP",
]

# 技能标记
SKILL_MARKS = ["◎", "○", "△", "×", "★", "●", "◯", "▲", "※"]

# 排除模式
EXCLUDE_PATTERNS = [
    r"^\d+$",  # 纯数字
    r"^[A-Z]$",  # 单个大写字母
    r"^(and|or|the|of|in|on|at|to|for)$",  # 常见介词
    r"^(年|月|日|時|分|秒)$",  # 时间单位
    r"^第\d+",  # 第N个
    r"^その他",  # 其他
]

# 工作范围选项
WORK_SCOPE_OPTIONS = [
    "要件定義",
    "基本設計",
    "詳細設計",
    "製造",
    "開発",
    "単体テスト",
    "結合テスト",
    "総合テスト",
    "システムテスト",
    "運用保守",
    "運用",
    "保守",
    "サポート",
    "導入",
    "移行",
    "プロジェクト管理",
    "品質管理",
    "構成管理",
]

# 角色选项
ROLE_OPTIONS = [
    "PM",
    "PL",
    "SL",
    "TL",
    "BSE",
    "SE",
    "PG",
    "PE",
    "アーキテクト",
    "コンサルタント",
    "サポート",
]
