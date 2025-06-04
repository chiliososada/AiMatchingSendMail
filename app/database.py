# app/database.py
from sqlalchemy import create_engine, event, pool, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import logging
import time
from typing import Generator, Optional
from .config import settings

# 配置日志
logger = logging.getLogger(__name__)

# 创建数据库引擎
engine = create_engine(
    settings.DATABASE_URL,
    # 连接池配置
    poolclass=QueuePool,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,  # 连接前检查连接有效性
    pool_recycle=3600,  # 1小时后回收连接
    # 调试配置
    echo=settings.DATABASE_ECHO,
    echo_pool=settings.is_development(),
    # 连接参数
    connect_args=(
        {
            "connect_timeout": 30,
            "application_name": settings.PROJECT_NAME,
            "options": "-c timezone=Asia/Tokyo",
        }
        if "postgresql" in settings.DATABASE_URL
        else {}
    ),
    # 性能优化
    execution_options={"isolation_level": "READ_COMMITTED"},
)

# 创建会话工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,  # 避免对象在commit后过期
)

# 创建基础模型类
Base = declarative_base()

# 数据库事件监听器


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """SQLite数据库优化设置"""
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=1000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()


@event.listens_for(engine, "connect")
def set_postgresql_settings(dbapi_connection, connection_record):
    """PostgreSQL数据库优化设置"""
    if "postgresql" in settings.DATABASE_URL:
        with dbapi_connection.cursor() as cursor:
            # 设置时区
            cursor.execute("SET timezone = 'Asia/Tokyo'")
            # 设置语句超时
            cursor.execute("SET statement_timeout = '300s'")
            # 设置搜索路径
            cursor.execute("SET search_path = public")


@event.listens_for(engine, "before_cursor_execute")
def receive_before_cursor_execute(
    conn, cursor, statement, parameters, context, executemany
):
    """记录SQL执行开始时间"""
    if settings.is_development():
        context._query_start_time = time.time()


@event.listens_for(engine, "after_cursor_execute")
def receive_after_cursor_execute(
    conn, cursor, statement, parameters, context, executemany
):
    """记录SQL执行时间"""
    if settings.is_development() and hasattr(context, "_query_start_time"):
        total = time.time() - context._query_start_time
        if total > 0.1:  # 记录执行时间超过100ms的查询
            logger.warning(f"Slow query ({total:.3f}s): {statement[:100]}...")


# 依赖注入函数


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话（依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """获取数据库会话（上下文管理器）"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database context error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


# 数据库工具函数


def create_tables():
    """创建所有数据库表"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表创建成功")
    except Exception as e:
        logger.error(f"创建数据库表失败: {str(e)}")
        raise


def drop_tables():
    """删除所有数据库表（谨慎使用）"""
    if not settings.is_development():
        raise RuntimeError("只能在开发环境中删除表")

    try:
        Base.metadata.drop_all(bind=engine)
        logger.warning("数据库表已删除")
    except Exception as e:
        logger.error(f"删除数据库表失败: {str(e)}")
        raise


def check_database_connection() -> bool:
    """检查数据库连接"""
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            return result.fetchone()[0] == 1
    except Exception as e:
        logger.error(f"数据库连接检查失败: {str(e)}")
        return False


def get_database_info() -> dict:
    """获取数据库信息"""
    try:
        with engine.connect() as connection:
            # PostgreSQL
            if "postgresql" in settings.DATABASE_URL:
                result = connection.execute(text("SELECT version()"))
                version = result.fetchone()[0]

                # 获取数据库大小
                db_name = connection.execute(
                    text("SELECT current_database()")
                ).fetchone()[0]
                size_result = connection.execute(
                    text("SELECT pg_size_pretty(pg_database_size(current_database()))")
                )
                db_size = size_result.fetchone()[0]

                return {
                    "type": "PostgreSQL",
                    "version": version,
                    "database": db_name,
                    "size": db_size,
                    "encoding": connection.execute(
                        text("SHOW server_encoding")
                    ).fetchone()[0],
                }

            # SQLite
            elif "sqlite" in settings.DATABASE_URL:
                result = connection.execute(text("SELECT sqlite_version()"))
                version = result.fetchone()[0]

                return {
                    "type": "SQLite",
                    "version": version,
                    "file": settings.DATABASE_URL.replace("sqlite:///", ""),
                }

            else:
                return {"type": "Unknown"}

    except Exception as e:
        logger.error(f"获取数据库信息失败: {str(e)}")
        return {"error": str(e)}


def execute_sql_file(file_path: str) -> bool:
    """执行SQL文件"""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            sql_content = file.read()

        with engine.connect() as connection:
            # 分割SQL语句（简单实现）
            statements = [
                stmt.strip() for stmt in sql_content.split(";") if stmt.strip()
            ]

            for statement in statements:
                if statement:
                    connection.execute(text(statement))
                    connection.commit()

        logger.info(f"SQL文件执行成功: {file_path}")
        return True

    except Exception as e:
        logger.error(f"执行SQL文件失败: {file_path}, 错误: {str(e)}")
        return False


def backup_database(backup_path: str) -> bool:
    """备份数据库（简单实现）"""
    try:
        if "postgresql" in settings.DATABASE_URL:
            import subprocess
            import os
            from urllib.parse import urlparse

            parsed = urlparse(settings.DATABASE_URL)

            env = os.environ.copy()
            env["PGPASSWORD"] = parsed.password

            cmd = [
                "pg_dump",
                "-h",
                parsed.hostname,
                "-p",
                str(parsed.port or 5432),
                "-U",
                parsed.username,
                "-d",
                parsed.path[1:],  # 去掉开头的 /
                "-f",
                backup_path,
                "--verbose",
            ]

            result = subprocess.run(cmd, env=env, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info(f"数据库备份成功: {backup_path}")
                return True
            else:
                logger.error(f"数据库备份失败: {result.stderr}")
                return False

        elif "sqlite" in settings.DATABASE_URL:
            import shutil

            db_file = settings.DATABASE_URL.replace("sqlite:///", "")
            shutil.copy2(db_file, backup_path)
            logger.info(f"SQLite数据库备份成功: {backup_path}")
            return True

        else:
            logger.error("不支持的数据库类型备份")
            return False

    except Exception as e:
        logger.error(f"数据库备份失败: {str(e)}")
        return False


def get_table_stats() -> dict:
    """获取表统计信息"""
    try:
        with engine.connect() as connection:
            stats = {}

            if "postgresql" in settings.DATABASE_URL:
                # PostgreSQL表统计
                result = connection.execute(
                    text(
                        """
                    SELECT 
                        schemaname,
                        tablename,
                        n_tup_ins as inserts,
                        n_tup_upd as updates,
                        n_tup_del as deletes,
                        n_live_tup as live_tuples,
                        n_dead_tup as dead_tuples
                    FROM pg_stat_user_tables
                    ORDER BY schemaname, tablename
                """
                    )
                )

                for row in result:
                    table_name = f"{row[0]}.{row[1]}"
                    stats[table_name] = {
                        "inserts": row[2],
                        "updates": row[3],
                        "deletes": row[4],
                        "live_tuples": row[5],
                        "dead_tuples": row[6],
                    }

            return stats

    except Exception as e:
        logger.error(f"获取表统计信息失败: {str(e)}")
        return {}


def optimize_database():
    """优化数据库"""
    try:
        with engine.connect() as connection:
            if "postgresql" in settings.DATABASE_URL:
                # PostgreSQL优化
                connection.execute(text("VACUUM ANALYZE"))
                logger.info("PostgreSQL数据库优化完成")

            elif "sqlite" in settings.DATABASE_URL:
                # SQLite优化
                connection.execute(text("VACUUM"))
                connection.execute(text("ANALYZE"))
                logger.info("SQLite数据库优化完成")

            connection.commit()

    except Exception as e:
        logger.error(f"数据库优化失败: {str(e)}")


# 数据库监控类


class DatabaseMonitor:
    """数据库监控"""

    def __init__(self):
        self.connection_count = 0
        self.slow_queries = []
        self.errors = []

    def log_connection(self):
        """记录连接"""
        self.connection_count += 1

    def log_slow_query(self, query: str, duration: float):
        """记录慢查询"""
        self.slow_queries.append(
            {"query": query, "duration": duration, "timestamp": time.time()}
        )

        # 只保留最近100个慢查询
        if len(self.slow_queries) > 100:
            self.slow_queries = self.slow_queries[-100:]

    def log_error(self, error: str):
        """记录错误"""
        self.errors.append({"error": error, "timestamp": time.time()})

        # 只保留最近50个错误
        if len(self.errors) > 50:
            self.errors = self.errors[-50:]

    def get_stats(self) -> dict:
        """获取监控统计"""
        return {
            "total_connections": self.connection_count,
            "slow_queries_count": len(self.slow_queries),
            "errors_count": len(self.errors),
            "recent_slow_queries": self.slow_queries[-10:],
            "recent_errors": self.errors[-10:],
        }


# 创建监控实例
db_monitor = DatabaseMonitor()

# 健康检查函数


async def health_check() -> dict:
    """数据库健康检查"""
    try:
        start_time = time.time()
        is_connected = check_database_connection()
        response_time = time.time() - start_time

        if is_connected:
            db_info = get_database_info()
            return {
                "status": "healthy",
                "response_time": f"{response_time:.3f}s",
                "database_info": db_info,
                "connection_pool": {
                    "size": engine.pool.size(),
                    "checked_in": engine.pool.checkedin(),
                    "checked_out": engine.pool.checkedout(),
                    "overflow": engine.pool.overflow(),
                    "invalid": engine.pool.invalid(),
                },
            }
        else:
            return {"status": "unhealthy", "error": "无法连接到数据库"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


# 导出
__all__ = [
    "engine",
    "SessionLocal",
    "Base",
    "get_db",
    "get_db_context",
    "create_tables",
    "check_database_connection",
    "get_database_info",
    "db_monitor",
    "health_check",
]
