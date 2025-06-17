# app/services/__init__.py
"""
业务服务模块

包含系统的核心业务逻辑实现。

服务列表：
- EmailService: 邮件管理业务逻辑
- SMTPService: SMTP发送服务
- AttachmentManager: 附件管理服务
- AIMatchingService: AI匹配服务（简化版）
- AIMatchingDatabase: AI匹配数据库操作层
"""

from .email_service import EmailService, AttachmentManager
from .smtp_service import SMTPService
from .ai_matching_service import AIMatchingService
from .ai_matching_database import AIMatchingDatabase
from .resume_parser_service import ResumeParserService

# 导出所有服务
__all__ = [
    "EmailService",
    "SMTPService",
    "AttachmentManager",
    "AIMatchingService",
    "AIMatchingDatabase",
    "ResumeParserService",
]


# 服务工厂函数
def create_email_service(db_session):
    """创建邮件服务实例"""
    return EmailService(db_session)


def create_smtp_service(smtp_settings):
    """创建SMTP服务实例"""
    return SMTPService(smtp_settings)


def create_attachment_manager(base_path: str = "uploads/attachments"):
    """创建附件管理器实例"""
    return AttachmentManager(base_path)


def create_ai_matching_service():
    """创建AI匹配服务实例"""
    return AIMatchingService()


def create_ai_matching_database():
    """创建AI匹配数据库实例"""
    return AIMatchingDatabase()


# 服务注册表
SERVICE_REGISTRY = {
    "email": EmailService,
    "smtp": SMTPService,
    "attachment": AttachmentManager,
    "ai_matching": AIMatchingService,
    "ai_matching_db": AIMatchingDatabase,
    "resume_parser": ResumeParserService,
}

# 服务配置
DEFAULT_SERVICE_CONFIG = {
    "email": {"max_retry_attempts": 3, "retry_delay_seconds": 60, "batch_size": 50},
    "smtp": {"timeout_seconds": 30, "connection_pool_size": 10},
    "attachment": {
        "base_path": "uploads/attachments",
        "cleanup_threshold_hours": 24,
        "max_file_size": 25 * 1024 * 1024,  # 25MB
    },
    "ai_matching": {
        "model_version": "pgvector_database_similarity",
        "use_custom_weights": False,  # 简化版不使用自定义权重
        "default_min_score": 0.1,
        "default_max_matches": 50,
    },
}
