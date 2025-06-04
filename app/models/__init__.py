# app/models/__init__.py
"""
数据模型模块

包含系统中所有的SQLAlchemy数据模型定义。

模型列表：
- EmailSMTPSettings: SMTP配置设置
- EmailSendingQueue: 邮件发送队列
- EmailSendingLogs: 邮件发送日志
"""

from .email_models import (
    EmailSMTPSettings,
    EmailSendingQueue,
    EmailSendingLogs,
)

# 导出所有模型
__all__ = [
    "EmailSMTPSettings",
    "EmailSendingQueue",
    "EmailSendingLogs",
]

# 模型注册表（用于自动化处理）
MODEL_REGISTRY = {
    "smtp_settings": EmailSMTPSettings,
    "sending_queue": EmailSendingQueue,
    "sending_logs": EmailSendingLogs,
}

# 主要表名映射
TABLE_NAMES = {
    EmailSMTPSettings: "email_smtp_settings",
    EmailSendingQueue: "email_sending_queue",
    EmailSendingLogs: "email_sending_logs",
}
