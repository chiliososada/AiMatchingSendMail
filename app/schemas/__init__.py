# app/schemas/__init__.py
"""
数据验证和序列化模块

包含所有的Pydantic模型定义，用于API请求/响应的数据验证和序列化。

主要功能：
- 请求数据验证
- 响应数据序列化
- 类型检查
- 自动文档生成
"""

from .email_schemas import (
    # SMTP配置相关
    SMTPSettingsCreate,
    SMTPSettingsResponse,
    # 邮件发送相关
    EmailSendRequest,
    EmailWithAttachmentsRequest,
    EmailSendResponse,
    EmailTestRequest,
    EmailStatusResponse,
    # 附件相关
    AttachmentInfo,
    AttachmentUploadResponse,
    AttachmentDeleteRequest,
    AttachmentListResponse,
    # 批量发送相关
    BulkEmailRequest,
    # 模板相关
    EmailTemplate,
    EmailTemplateRenderRequest,
    # 统计相关
    EmailStatistics,
)

# 导出所有schema
__all__ = [
    # SMTP配置
    "SMTPSettingsCreate",
    "SMTPSettingsResponse",
    # 邮件发送
    "EmailSendRequest",
    "EmailWithAttachmentsRequest",
    "EmailSendResponse",
    "EmailTestRequest",
    "EmailStatusResponse",
    # 附件管理
    "AttachmentInfo",
    "AttachmentUploadResponse",
    "AttachmentDeleteRequest",
    "AttachmentListResponse",
    # 批量发送
    "BulkEmailRequest",
    # 模板
    "EmailTemplate",
    "EmailTemplateRenderRequest",
    # 统计
    "EmailStatistics",
]

# Schema分类
SMTP_SCHEMAS = [SMTPSettingsCreate, SMTPSettingsResponse]

EMAIL_SCHEMAS = [
    EmailSendRequest,
    EmailWithAttachmentsRequest,
    EmailSendResponse,
    EmailTestRequest,
    EmailStatusResponse,
]

ATTACHMENT_SCHEMAS = [
    AttachmentInfo,
    AttachmentUploadResponse,
    AttachmentDeleteRequest,
    AttachmentListResponse,
]

TEMPLATE_SCHEMAS = [EmailTemplate, EmailTemplateRenderRequest]

STATISTICS_SCHEMAS = [EmailStatistics]

# Schema注册表
SCHEMA_REGISTRY = {
    "smtp": SMTP_SCHEMAS,
    "email": EMAIL_SCHEMAS,
    "attachment": ATTACHMENT_SCHEMAS,
    "template": TEMPLATE_SCHEMAS,
    "statistics": STATISTICS_SCHEMAS,
}
