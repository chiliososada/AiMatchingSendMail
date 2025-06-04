# app/config.py
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Optional, Any, Dict, Union
import os
import re
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
    DATABASE_URL: str = "sqlite:///./email_api.db"
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10

    # 安全配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ENCRYPTION_KEY: Optional[str] = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8

    # CORS配置
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:3001",
        "https://localhost:3000",
        "https://localhost:8080",
    ]

    # Redis配置
    REDIS_URL: Optional[str] = None
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_ENABLED: bool = False

    # 文件上传配置
    UPLOAD_DIR: str = "uploads"
    ATTACHMENT_DIR: str = "uploads/attachments"
    TEMP_DIR: str = "uploads/temp"
    MAX_FILE_SIZE: int = 26214400
    MAX_FILES_PER_REQUEST: int = 10
    MAX_TOTAL_REQUEST_SIZE: int = 104857600

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

    # 禁止的文件类型
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
    LOG_MAX_SIZE: int = 10485760
    LOG_BACKUP_COUNT: int = 5

    # 监控和性能配置
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    REQUEST_TIMEOUT: int = 300

    # 速率限制配置
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60

    # SMTP默认配置
    DEFAULT_SMTP_TIMEOUT: int = 30
    DEFAULT_RETRY_DELAY: int = 60

    # 环境配置
    ENVIRONMENT: str = "development"

    # 第三方服务配置
    SENTRY_DSN: Optional[str] = None

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
    CACHE_TTL_SECONDS: int = 300
    CACHE_MAX_SIZE: int = 1000

    # 并发配置
    MAX_CONCURRENT_SENDS: int = 10
    BATCH_SIZE: int = 50

    # 健康检查配置
    HEALTH_CHECK_INTERVAL: int = 30
    HEALTH_CHECK_TIMEOUT: int = 10

    # 存储配置
    STORAGE_TYPE: str = "local"

    # 项目信息
    LICENSE: str = "MIT"
    COPYRIGHT: str = "2024 Your Company Name"
    CONTACT_EMAIL: str = "admin@yourdomain.com"

    # 功能开关
    FEATURE_EMAIL_TRACKING: bool = True
    FEATURE_CLICK_TRACKING: bool = True
    FEATURE_BULK_SEND: bool = True
    FEATURE_TEMPLATES: bool = True
    FEATURE_WEBHOOKS: bool = False

    # API限制
    API_RATE_LIMIT_PER_MINUTE: int = 60
    API_BURST_LIMIT: int = 100

    # 维护模式
    MAINTENANCE_MODE: bool = False
    MAINTENANCE_MESSAGE: str = "系统维护中，请稍后再试"

    # 启动验证
    VALIDATE_CONFIG_ON_STARTUP: bool = True

    # 安全头配置
    SECURITY_HEADERS: Dict[str, str] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }

    # 字段验证器 - 清理带注释的数值
    @field_validator(
        "MAX_FILE_SIZE", "MAX_TOTAL_REQUEST_SIZE", "LOG_MAX_SIZE", mode="before"
    )
    @classmethod
    def clean_integer_values(cls, v):
        """清理包含注释的整数值"""
        if isinstance(v, str):
            # 移除注释部分（# 之后的内容）
            cleaned = re.sub(r"\s*#.*$", "", v.strip())
            try:
                return int(cleaned)
            except ValueError:
                # 如果无法转换，尝试提取数字
                numbers = re.findall(r"\d+", v)
                if numbers:
                    return int(numbers[0])
                # 返回默认值
                if "MAX_FILE_SIZE" in str(v):
                    return 26214400
                elif "MAX_TOTAL_REQUEST_SIZE" in str(v):
                    return 104857600
                elif "LOG_MAX_SIZE" in str(v):
                    return 10485760
        return v

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

    def get_file_size_mb(self, size_bytes: int) -> float:
        """将字节转换为MB"""
        return size_bytes / (1024 * 1024)

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
        if self.MAX_FILE_SIZE > 100 * 1024 * 1024:
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

        url = self.DATABASE_URL
        if "://" in url and "@" in url:
            protocol, rest = url.split("://", 1)
            if "@" in rest:
                credentials, host_part = rest.rsplit("@", 1)
                if ":" in credentials:
                    username, _ = credentials.split(":", 1)
                    return f"{protocol}://{username}:***@{host_part}"
        return url

    def get_size_info(self) -> Dict[str, str]:
        """获取文件大小信息（便于查看）"""
        return {
            "max_file_size": f"{self.get_file_size_mb(self.MAX_FILE_SIZE):.1f}MB",
            "max_total_request_size": f"{self.get_file_size_mb(self.MAX_TOTAL_REQUEST_SIZE):.1f}MB",
            "log_max_size": f"{self.get_file_size_mb(self.LOG_MAX_SIZE):.1f}MB",
        }

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"
        env_prefix = ""


# 创建全局设置实例
try:
    settings = Settings()
    print("✅ 配置加载成功")
except Exception as e:
    print(f"❌ 配置加载失败: {str(e)}")
    print("使用默认配置启动...")
    settings = Settings(
        DATABASE_URL="sqlite:///./email_api.db",
        SECRET_KEY="development-secret-key",
        ENCRYPTION_KEY=None,
    )

# 配置验证
if settings.VALIDATE_CONFIG_ON_STARTUP:
    validation_errors = settings.validate_settings()
    if validation_errors:
        import sys

        print("⚠️  配置验证警告:")
        for error in validation_errors:
            print(f"  - {error}")
        if settings.is_production():
            print("🚫 生产环境中检测到配置错误，退出...")
            sys.exit(1)

# 创建必要的目录
try:
    settings.create_directories()
    print(f"📁 目录创建成功: {settings.attachment_path}")
except Exception as e:
    print(f"❌ 创建目录失败: {str(e)}")

# 环境特定配置
if settings.is_development():
    settings.DATABASE_ECHO = True
    settings.DEBUG = True
    print("🔧 开发环境配置已应用")

if settings.is_production():
    settings.DATABASE_ECHO = False
    settings.DEBUG = False
    print("🔒 生产环境配置已应用")

# 导出
__all__ = ["settings", "Settings"]
