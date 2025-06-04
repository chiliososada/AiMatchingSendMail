# app/models/__init__.py
"""
数据模型模块

包含系统中所有的SQLAlchemy数据模型定义。

模型列表：
- EmailSMTPSettings: SMTP配置设置
- EmailSendingQueue: 邮件发送队列
- EmailSendingLogs: 邮件发送日志
- EmailTemplate: 邮件模板
- AttachmentMetadata: 附件元数据
- EmailBulkSend: 批量发送记录
- EmailTrackingPixel: 邮件跟踪像素
- EmailClickTracking: 邮件点击跟踪
"""

from .email_models import (
    EmailSMTPSettings,
    EmailSendingQueue,
    EmailSendingLogs,
    EmailTemplate,
    AttachmentMetadata,
    EmailBulkSend,
    EmailTrackingPixel,
    EmailClickTracking,
)

# 导出所有模型
__all__ = [
    "EmailSMTPSettings",
    "EmailSendingQueue",
    "EmailSendingLogs",
    "EmailTemplate",
    "AttachmentMetadata",
    "EmailBulkSend",
    "EmailTrackingPixel",
    "EmailClickTracking",
]

# 模型注册表（用于自动化处理）
MODEL_REGISTRY = {
    "smtp_settings": EmailSMTPSettings,
    "sending_queue": EmailSendingQueue,
    "sending_logs": EmailSendingLogs,
    "templates": EmailTemplate,
    "attachments": AttachmentMetadata,
    "bulk_send": EmailBulkSend,
    "tracking_pixel": EmailTrackingPixel,
    "click_tracking": EmailClickTracking,
}

# 主要表名映射
TABLE_NAMES = {
    EmailSMTPSettings: "email_smtp_settings",
    EmailSendingQueue: "email_sending_queue",
    EmailSendingLogs: "email_sending_logs",
    EmailTemplate: "email_templates",
    AttachmentMetadata: "attachment_metadata",
    EmailBulkSend: "email_bulk_send",
    EmailTrackingPixel: "email_tracking_pixel",
    EmailClickTracking: "email_click_tracking",
}
