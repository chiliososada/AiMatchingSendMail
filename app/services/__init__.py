# app/services/__init__.py
"""
业务服务模块

包含系统的核心业务逻辑实现。

服务列表：
- EmailService: 邮件管理业务逻辑
- SMTPService: SMTP发送服务
- AttachmentManager: 附件管理服务
"""

from .email_service import EmailService, AttachmentManager
from .smtp_service import SMTPService

# 导出所有服务
__all__ = ["EmailService", "SMTPService", "AttachmentManager"]


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


# 服务注册表
SERVICE_REGISTRY = {
    "email": EmailService,
    "smtp": SMTPService,
    "attachment": AttachmentManager,
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
}
