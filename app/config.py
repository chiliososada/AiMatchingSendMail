# app/config.py
from pydantic_settings import BaseSettings
from typing import List, Optional, Any, Dict, Union
import os
from pathlib import Path


class Settings(BaseSettings):
    # 应用基本配置
    PROJECT_NAME: str = "Email API"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1

    # 数据库配置
    DATABASE_URL: str
    DATABASE_ECHO: bool = False  # 是否打印SQL语句
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10

    # 安全配置
    SECRET_KEY: str
    ENCRYPTION_KEY: Optional[str] = None  # Fernet加密密钥
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8天

    # CORS配置
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:3001",
        "https://localhost:3000",
        "https://localhost:8080",
    ]

    # Redis配置（可选，当前未使用）
    REDIS_URL: Optional[str] = None
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_ENABLED: bool = False

    # 文件上传配置
    UPLOAD_DIR: str = "uploads"
    ATTACHMENT_DIR: str = "uploads/attachments"
    TEMP_DIR: str = "uploads/temp"
    MAX_FILE_SIZE: int = 25 * 1024 * 1024  # 25MB
    MAX_FILES_PER_REQUEST: int = 10
    MAX_TOTAL_REQUEST_SIZE: int = 100 * 1024 * 1024  # 100MB

    # 支持的文件类型
    ALLOWED_EXTENSIONS: List[str] = [
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".svg",
        ".tiff",
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
        ".txt",
        ".csv",
        ".json",
        ".xml",
        ".log",
        ".rtf",
    ]

    # 禁止的文件类型（安全考虑）
    FORBIDDEN_EXTENSIONS: List[str] = [
        ".exe",
        ".bat",
        ".cmd",
        ".scr",
        ".pif",
        ".com",
        ".vbs",
        ".js",
        ".jar",
        ".msi",
        ".deb",
        ".rpm",
        ".dmg",
    ]

    # 邮件配置限制
    MAX_RECIPIENTS_PER_EMAIL: int = 100
    MAX_BULK_EMAILS: int = 1000
    MAX_RETRY_ATTEMPTS: int = 3
    EMAIL_TIMEOUT_SECONDS: int = 60

    # 附件清理配置
    ATTACHMENT_RETENTION_HOURS: int = 24
    AUTO_CLEANUP_ENABLED: bool = True
    CLEANUP_INTERVAL_HOURS: int = 6

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "app.log"
    LOG_MAX_SIZE: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 5

    # 监控和性能配置
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    REQUEST_TIMEOUT: int = 300  # 5分钟

    # 速率限制配置
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # 60秒窗口

    # SMTP默认配置
    DEFAULT_SMTP_TIMEOUT: int = 30
    DEFAULT_RETRY_DELAY: int = 60  # 重试延迟（秒）

    # 环境配置
    ENVIRONMENT: str = "development"  # development, testing, production

    # 第三方服务配置
    SENTRY_DSN: Optional[str] = None  # Sentry错误监控

    # 数据库备份配置
    BACKUP_ENABLED: bool = False
    BACKUP_INTERVAL_HOURS: int = 24
    BACKUP_RETENTION_DAYS: int = 7

    # 邮件模板配置
    TEMPLATE_DIR: str = "templates"
    DEFAULT_TEMPLATE_LANGUAGE: str = "ja"

    # 统计分析配置
    ANALYTICS_ENABLED: bool = True
    ANALYTICS_RETENTION_DAYS: int = 90

    # 缓存配置
    CACHE_TTL_SECONDS: int = 300  # 5分钟
    CACHE_MAX_SIZE: int = 1000

    # 并发配置
    MAX_CONCURRENT_SENDS: int = 10
    BATCH_SIZE: int = 50

    # 安全头配置
    SECURITY_HEADERS: Dict[str, str] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }

    @property
    def upload_path(self) -> Path:
        """获取上传目录路径"""
        return Path(self.UPLOAD_DIR)

    @property
    def attachment_path(self) -> Path:
        """获取附件目录路径"""
        return Path(self.ATTACHMENT_DIR)

    @property
    def temp_path(self) -> Path:
        """获取临时目录路径"""
        return Path(self.TEMP_DIR)

    def is_production(self) -> bool:
        """判断是否为生产环境"""
        return self.ENVIRONMENT.lower() == "production"

    def is_development(self) -> bool:
        """判断是否为开发环境"""
        return self.ENVIRONMENT.lower() == "development"

    def is_testing(self) -> bool:
        """判断是否为测试环境"""
        return self.ENVIRONMENT.lower() == "testing"

    def get_log_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
                "detailed": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": self.LOG_LEVEL,
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": self.LOG_LEVEL,
                    "formatter": "detailed",
                    "filename": self.LOG_FILE,
                    "maxBytes": self.LOG_MAX_SIZE,
                    "backupCount": self.LOG_BACKUP_COUNT,
                    "encoding": "utf-8",
                },
            },
            "loggers": {
                "": {
                    "level": self.LOG_LEVEL,
                    "handlers": ["console", "file"],
                },
                "uvicorn": {
                    "level": "INFO",
                    "handlers": ["console"],
                    "propagate": False,
                },
                "sqlalchemy.engine": {
                    "level": "INFO" if self.DATABASE_ECHO else "WARNING",
                    "handlers": ["file"],
                    "propagate": False,
                },
            },
        }

    def create_directories(self) -> None:
        """创建必要的目录"""
        directories = [
            self.upload_path,
            self.attachment_path,
            self.temp_path,
            Path(self.TEMPLATE_DIR),
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def validate_settings(self) -> List[str]:
        """验证配置设置"""
        errors = []

        # 验证必需的配置
        required_settings = ["DATABASE_URL", "SECRET_KEY"]
        for setting in required_settings:
            if not getattr(self, setting):
                errors.append(f"缺少必需的配置: {setting}")

        # 验证文件大小限制
        if self.MAX_FILE_SIZE > 100 * 1024 * 1024:  # 100MB
            errors.append("MAX_FILE_SIZE 不能超过100MB")

        if self.MAX_TOTAL_REQUEST_SIZE < self.MAX_FILE_SIZE:
            errors.append("MAX_TOTAL_REQUEST_SIZE 必须大于等于 MAX_FILE_SIZE")

        # 验证端口号
        if not (1 <= self.PORT <= 65535):
            errors.append("PORT 必须在1-65535范围内")

        # 验证工作进程数
        if self.WORKERS < 1:
            errors.append("WORKERS 必须大于0")

        # 验证数据库连接池设置
        if self.DATABASE_POOL_SIZE < 1:
            errors.append("DATABASE_POOL_SIZE 必须大于0")

        if self.DATABASE_MAX_OVERFLOW < 0:
            errors.append("DATABASE_MAX_OVERFLOW 不能为负数")

        return errors

    def get_database_url(self, hide_password: bool = False) -> str:
        """获取数据库URL，可选择隐藏密码"""
        if not hide_password:
            return self.DATABASE_URL

        # 隐藏密码用于日志记录
        url = self.DATABASE_URL
        if "://" in url and "@" in url:
            protocol, rest = url.split("://", 1)
            if "@" in rest:
                credentials, host_part = rest.rsplit("@", 1)
                if ":" in credentials:
                    username, _ = credentials.split(":", 1)
                    return f"{protocol}://{username}:***@{host_part}"
        return url

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

        # 环境变量前缀
        env_prefix = ""

        # 字段别名
        fields = {
            "DATABASE_URL": {"env": ["DATABASE_URL", "DB_URL", "POSTGRES_URL"]},
            "SECRET_KEY": {"env": ["SECRET_KEY", "APP_SECRET_KEY"]},
            "REDIS_URL": {"env": ["REDIS_URL", "REDIS_CONNECTION_STRING"]},
        }


# 创建全局设置实例
settings = Settings()

# 验证配置
validation_errors = settings.validate_settings()
if validation_errors:
    import sys

    print("配置验证失败:")
    for error in validation_errors:
        print(f"  - {error}")
    sys.exit(1)

# 创建必要的目录
settings.create_directories()

# 开发环境下的额外配置
if settings.is_development():
    settings.DATABASE_ECHO = True
    settings.DEBUG = True

# 生产环境下的安全配置
if settings.is_production():
    settings.DATABASE_ECHO = False
    settings.DEBUG = False

    # 生产环境必须使用HTTPS
    if not any(
        origin.startswith("https://") for origin in settings.BACKEND_CORS_ORIGINS
    ):
        print("警告: 生产环境建议使用HTTPS")

# 导出常用配置
__all__ = ["settings", "Settings"]
