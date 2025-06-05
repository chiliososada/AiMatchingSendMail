# app/database.py - asyncpg版本
import asyncpg
import logging
import time
from typing import Optional, Dict, Any, AsyncGenerator
from contextlib import asynccontextmanager
import asyncio
from .config import settings

logger = logging.getLogger(__name__)

# 全局连接池
_pool: Optional[asyncpg.Pool] = None


async def create_database_pool() -> asyncpg.Pool:
    """创建数据库连接池"""
    global _pool

    if _pool is not None:
        return _pool

    try:
        # 解析数据库URL database_url = settings.DATABASE_URL
        database_url = settings.DATABASE_URL
        # logger.info(settings.DATABASE_URL)
        # database_url = "postgresql://postgres.utkxuvldiveojhnzfsca:1994Lzy.@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres"
        # if database_url.startswith("postgresql://"):
        #     database_url = database_url.replace("postgresql://", "postgres://", 1)

        logger.info(f"正在创建数据库连接池...")

        _pool = await asyncpg.create_pool(
            database_url,
            min_size=settings.DATABASE_POOL_SIZE,
            max_size=settings.DATABASE_POOL_SIZE + settings.DATABASE_MAX_OVERFLOW,
            command_timeout=60,
            server_settings={
                "application_name": settings.PROJECT_NAME,
                "timezone": "Asia/Tokyo",
            },
        )

        logger.info("数据库连接池创建成功")
        return _pool

    except Exception as e:
        logger.error(f"创建数据库连接池失败: {str(e)}")
        raise


async def get_database_pool() -> asyncpg.Pool:
    """获取数据库连接池"""
    global _pool
    if _pool is None:
        _pool = await create_database_pool()
    return _pool


async def close_database_pool():
    """关闭数据库连接池"""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("数据库连接池已关闭")


@asynccontextmanager
async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """获取数据库连接（上下文管理器）"""
    pool = await get_database_pool()
    async with pool.acquire() as connection:
        try:
            yield connection
        except Exception as e:
            logger.error(f"数据库连接错误: {str(e)}")
            raise


@asynccontextmanager
async def get_db_transaction() -> AsyncGenerator[asyncpg.Connection, None]:
    """获取数据库事务连接"""
    pool = await get_database_pool()
    async with pool.acquire() as connection:
        async with connection.transaction():
            try:
                yield connection
            except Exception as e:
                logger.error(f"数据库事务错误: {str(e)}")
                raise


async def execute_query(query: str, *args) -> str:
    """执行查询（INSERT/UPDATE/DELETE）"""
    async with get_db_connection() as conn:
        result = await conn.execute(query, *args)
        return result


async def fetch_one(query: str, *args) -> Optional[Dict[str, Any]]:
    """获取单行数据"""
    async with get_db_connection() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None


async def fetch_all(query: str, *args) -> list[Dict[str, Any]]:
    """获取多行数据"""
    async with get_db_connection() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(row) for row in rows]


async def fetch_val(query: str, *args) -> Any:
    """获取单个值"""
    async with get_db_connection() as conn:
        return await conn.fetchval(query, *args)


class DatabaseManager:
    """数据库管理器"""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """初始化数据库连接池"""
        self.pool = await create_database_pool()
        await self.create_tables()

    async def close(self):
        """关闭连接池"""
        await close_database_pool()

    async def create_tables(self):
        """创建数据库表"""
        create_tables_sql = """
        -- 创建SMTP设置表
        CREATE TABLE IF NOT EXISTS email_smtp_settings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            setting_name VARCHAR NOT NULL,
            smtp_host VARCHAR NOT NULL,
            smtp_port INTEGER NOT NULL DEFAULT 587,
            smtp_username VARCHAR NOT NULL,
            smtp_password_encrypted TEXT NOT NULL,
            security_protocol VARCHAR DEFAULT 'TLS',
            from_email VARCHAR NOT NULL,
            from_name VARCHAR,
            reply_to_email VARCHAR,
            daily_send_limit INTEGER DEFAULT 1000,
            hourly_send_limit INTEGER DEFAULT 100,
            connection_status VARCHAR DEFAULT 'untested',
            last_test_at TIMESTAMP WITH TIME ZONE,
            last_test_error TEXT,
            is_default BOOLEAN DEFAULT FALSE,
            is_active BOOLEAN DEFAULT TRUE,
            created_by UUID,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            deleted_at TIMESTAMP WITH TIME ZONE
        );

        -- 创建邮件发送队列表
        CREATE TABLE IF NOT EXISTS email_sending_queue (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            to_emails TEXT[] NOT NULL,
            cc_emails TEXT[] DEFAULT '{}',
            bcc_emails TEXT[] DEFAULT '{}',
            subject VARCHAR NOT NULL,
            body_text TEXT,
            body_html TEXT,
            attachments JSONB DEFAULT '{}',
            smtp_setting_id UUID REFERENCES email_smtp_settings(id),
            template_id UUID,
            priority INTEGER DEFAULT 5,
            scheduled_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            max_retry_count INTEGER DEFAULT 3,
            current_retry_count INTEGER DEFAULT 0,
            status VARCHAR DEFAULT 'queued',
            sent_at TIMESTAMP WITH TIME ZONE,
            last_attempt_at TIMESTAMP WITH TIME ZONE,
            error_message TEXT,
            related_project_id UUID,
            related_engineer_id UUID,
            email_metadata JSONB DEFAULT '{}',
            send_duration_ms INTEGER,
            created_by UUID,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        -- 创建邮件发送日志表
        CREATE TABLE IF NOT EXISTS email_sending_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            queue_id UUID REFERENCES email_sending_queue(id),
            tenant_id UUID NOT NULL,
            message_id VARCHAR,
            smtp_response TEXT,
            delivery_status VARCHAR,
            send_start_time TIMESTAMP WITH TIME ZONE,
            send_end_time TIMESTAMP WITH TIME ZONE,
            response_time_ms INTEGER,
            opened_at TIMESTAMP WITH TIME ZONE,
            clicked_at TIMESTAMP WITH TIME ZONE,
            replied_at TIMESTAMP WITH TIME ZONE,
            unsubscribed_at TIMESTAMP WITH TIME ZONE,
            bounce_type VARCHAR,
            bounce_reason TEXT,
            complaint_type VARCHAR,
            complaint_reason TEXT,
            attachment_transfer_log JSONB DEFAULT '{}',
            logged_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        -- 创建索引
        CREATE INDEX IF NOT EXISTS idx_smtp_settings_tenant_id ON email_smtp_settings(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_smtp_settings_is_default ON email_smtp_settings(tenant_id, is_default);
        CREATE INDEX IF NOT EXISTS idx_queue_tenant_id ON email_sending_queue(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_queue_status ON email_sending_queue(status);
        CREATE INDEX IF NOT EXISTS idx_queue_created_at ON email_sending_queue(created_at);
        CREATE INDEX IF NOT EXISTS idx_logs_tenant_id ON email_sending_logs(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_logs_queue_id ON email_sending_logs(queue_id);
        """

        try:
            async with get_db_connection() as conn:
                await conn.execute(create_tables_sql)
            logger.info("数据库表创建/更新成功")
        except Exception as e:
            logger.error(f"创建数据库表失败: {str(e)}")
            raise


async def check_database_connection() -> bool:
    """检查数据库连接"""
    try:
        result = await fetch_val("SELECT 1")
        return result == 1
    except Exception as e:
        logger.error(f"数据库连接检查失败: {str(e)}")
        return False


async def get_database_info() -> Dict[str, Any]:
    """获取数据库信息"""
    try:
        version = await fetch_val("SELECT version()")
        db_name = await fetch_val("SELECT current_database()")
        db_size = await fetch_val(
            "SELECT pg_size_pretty(pg_database_size(current_database()))"
        )
        encoding = await fetch_val("SHOW server_encoding")

        return {
            "type": "PostgreSQL",
            "version": version,
            "database": db_name,
            "size": db_size,
            "encoding": encoding,
        }
    except Exception as e:
        logger.error(f"获取数据库信息失败: {str(e)}")
        return {"error": str(e)}


async def get_table_stats() -> Dict[str, Any]:
    """获取表统计信息"""
    try:
        query = """
        SELECT 
            schemaname,
            tablename,
            n_tup_ins as inserts,
            n_tup_upd as updates,
            n_tup_del as deletes,
            n_live_tup as live_tuples,
            n_dead_tup as dead_tuples
        FROM pg_stat_user_tables
        WHERE tablename IN ('email_smtp_settings', 'email_sending_queue', 'email_sending_logs')
        ORDER BY schemaname, tablename
        """

        rows = await fetch_all(query)
        stats = {}

        for row in rows:
            table_name = f"{row['schemaname']}.{row['tablename']}"
            stats[table_name] = {
                "inserts": row["inserts"],
                "updates": row["updates"],
                "deletes": row["deletes"],
                "live_tuples": row["live_tuples"],
                "dead_tuples": row["dead_tuples"],
            }

        return stats
    except Exception as e:
        logger.error(f"获取表统计信息失败: {str(e)}")
        return {}


async def optimize_database():
    """优化数据库"""
    try:
        await execute_query("VACUUM ANALYZE")
        logger.info("数据库优化完成")
    except Exception as e:
        logger.error(f"数据库优化失败: {str(e)}")


async def health_check() -> Dict[str, Any]:
    """数据库健康检查"""
    try:
        start_time = time.time()
        is_connected = await check_database_connection()
        response_time = time.time() - start_time

        if is_connected:
            db_info = await get_database_info()
            pool = await get_database_pool()

            return {
                "status": "healthy",
                "response_time": f"{response_time:.3f}s",
                "database_info": db_info,
                "connection_pool": {
                    "size": pool.get_size(),
                    "max_size": pool.get_max_size(),
                    "min_size": pool.get_min_size(),
                },
            }
        else:
            return {"status": "unhealthy", "error": "无法连接到数据库"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# 创建全局数据库管理器实例
db_manager = DatabaseManager()

# 导出
__all__ = [
    "create_database_pool",
    "get_database_pool",
    "close_database_pool",
    "get_db_connection",
    "get_db_transaction",
    "execute_query",
    "fetch_one",
    "fetch_all",
    "fetch_val",
    "check_database_connection",
    "get_database_info",
    "db_manager",
    "health_check",
    "DatabaseManager",
]
