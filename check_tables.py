#!/usr/bin/env python3
# simple_db_check.py - 简化的数据库连接检查

import os
from dotenv import load_dotenv

load_dotenv()


def check_database():
    """简单的数据库连接检查"""
    DATABASE_URL = os.getenv("DATABASE_URL")

    if not DATABASE_URL:
        print("❌ 未找到 DATABASE_URL 环境变量")
        print("请检查 .env 文件配置")
        return False

    print("=" * 50)
    print("         数据库连接检查")
    print("=" * 50)
    print(f"数据库URL: {DATABASE_URL[:50]}...")

    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(DATABASE_URL)

        # 测试连接
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            if result.fetchone()[0] == 1:
                print("✅ 数据库连接成功")

                # 查看现有表
                if "postgresql" in DATABASE_URL:
                    tables_result = connection.execute(
                        text(
                            """
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public'
                        ORDER BY table_name
                    """
                        )
                    )
                    tables = [row[0] for row in tables_result]

                    if tables:
                        print(f"📋 发现 {len(tables)} 个表:")
                        for table in tables:
                            print(f"   - {table}")
                    else:
                        print("📭 数据库中暂无表")

                return True

    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install sqlalchemy psycopg2-binary")
        return False

    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False


def check_env_file():
    """检查.env文件"""
    if not os.path.exists(".env"):
        print("❌ 未找到 .env 文件")
        return False

    required_vars = ["DATABASE_URL", "SECRET_KEY", "ENCRYPTION_KEY"]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"❌ 缺少环境变量: {', '.join(missing_vars)}")
        return False

    print("✅ 环境变量配置正常")
    return True


if __name__ == "__main__":
    print("正在检查项目配置...")
    print()

    # 检查环境变量
    if not check_env_file():
        print("\n请先配置 .env 文件")
        exit(1)

    print()

    # 检查数据库连接
    if check_database():
        print("\n🚀 可以开始启动项目:")
        print("   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    else:
        print("\n❌ 请先解决数据库连接问题")
