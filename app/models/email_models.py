# app/models/email_models.py
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Text,
    DECIMAL,
    ForeignKey,
    ARRAY,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from ..database import Base


class EmailSMTPSettings(Base):
    __tablename__ = "email_smtp_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # 基本设置
    setting_name = Column(String, nullable=False)
    smtp_host = Column(String, nullable=False)
    smtp_port = Column(Integer, nullable=False, default=587)
    smtp_username = Column(String, nullable=False)
    smtp_password_encrypted = Column(String, nullable=False)

    # 安全设置
    security_protocol = Column(String, default="TLS")

    # 发送方信息
    from_email = Column(String, nullable=False)
    from_name = Column(String)
    reply_to_email = Column(String)

    # 限制设置
    daily_send_limit = Column(Integer, default=1000)
    hourly_send_limit = Column(Integer, default=100)

    # 连接测试状态
    connection_status = Column(String, default="untested")
    last_test_at = Column(DateTime(timezone=True))
    last_test_error = Column(Text)

    # 状态字段
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class EmailSendingQueue(Base):
    __tablename__ = "email_sending_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # 收件人信息
    to_emails = Column(ARRAY(String), nullable=False)
    cc_emails = Column(ARRAY(String), default=[])  # 添加CC支持
    bcc_emails = Column(ARRAY(String), default=[])  # 添加BCC支持

    # 邮件内容
    subject = Column(String, nullable=False)
    body_text = Column(Text)
    body_html = Column(Text)

    # 附件信息 - 新增字段
    attachments = Column(JSONB, default={})  # 存储附件元数据

    # SMTP设置
    smtp_setting_id = Column(UUID(as_uuid=True), ForeignKey("email_smtp_settings.id"))
    template_id = Column(UUID(as_uuid=True))  # 如果使用模板

    # 调度设置
    priority = Column(Integer, default=5)
    scheduled_at = Column(DateTime(timezone=True), server_default=func.now())
    max_retry_count = Column(Integer, default=3)
    current_retry_count = Column(Integer, default=0)

    # 发送状态
    status = Column(
        String, default="queued"
    )  # queued, sending, sent, failed, cancelled, retry_scheduled
    sent_at = Column(DateTime(timezone=True))
    last_attempt_at = Column(DateTime(timezone=True))
    error_message = Column(Text)

    # 关联信息
    related_project_id = Column(UUID(as_uuid=True))
    related_engineer_id = Column(UUID(as_uuid=True))

    # 元数据和统计
    metadata = Column(JSONB, default={})
    send_duration_ms = Column(Integer)  # 发送耗时（毫秒）

    # 系统字段
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    smtp_setting = relationship("EmailSMTPSettings", backref="queue_items")


class EmailSendingLogs(Base):
    __tablename__ = "email_sending_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    queue_id = Column(UUID(as_uuid=True), ForeignKey("email_sending_queue.id"))
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # 发送详细信息
    message_id = Column(String)  # SMTP服务器返回的消息ID
    smtp_response = Column(Text)  # SMTP服务器响应
    delivery_status = Column(
        String
    )  # sending, delivered, bounced, complained, delivery_delayed, failed

    # 性能指标
    send_start_time = Column(DateTime(timezone=True))
    send_end_time = Column(DateTime(timezone=True))
    response_time_ms = Column(Integer)

    # 接收方反应
    opened_at = Column(DateTime(timezone=True))
    clicked_at = Column(DateTime(timezone=True))
    replied_at = Column(DateTime(timezone=True))
    unsubscribed_at = Column(DateTime(timezone=True))

    # 错误信息
    bounce_type = Column(String)  # hard, soft, transient
    bounce_reason = Column(Text)
    complaint_type = Column(String)  # spam, virus, unsubscribe
    complaint_reason = Column(Text)

    # 附件传输日志
    attachment_transfer_log = Column(JSONB, default={})  # 附件传输详情

    # 日志时间
    logged_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    queue_item = relationship("EmailSendingQueue", backref="logs")


class EmailTemplate(Base):
    """邮件模板表"""

    __tablename__ = "email_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # 模板基本信息
    name = Column(String, nullable=False)
    description = Column(Text)
    category = Column(String)  # project_introduction, engineer_introduction, etc.

    # 模板内容
    subject_template = Column(String, nullable=False)
    body_template_text = Column(Text, nullable=False)
    body_template_html = Column(Text)

    # 模板变量
    available_placeholders = Column(ARRAY(String), default=[])
    required_placeholders = Column(ARRAY(String), default=[])

    # 默认附件设置
    default_attachment_ids = Column(ARRAY(UUID), default=[])

    # 使用统计
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True))

    # AI相关设置
    ai_summary_enabled = Column(Boolean, default=False)
    ai_personalization_enabled = Column(Boolean, default=False)

    # 状态字段
    is_active = Column(Boolean, default=True)
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class AttachmentMetadata(Base):
    """附件元数据表"""

    __tablename__ = "attachment_metadata"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # 文件基本信息
    original_filename = Column(String, nullable=False)
    stored_filename = Column(String, nullable=False)  # 服务器存储的文件名
    content_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    file_hash = Column(String)  # 文件hash，用于去重

    # 存储信息
    storage_path = Column(String, nullable=False)
    storage_type = Column(String, default="local")  # local, s3, etc.

    # 安全信息
    is_scanned = Column(Boolean, default=False)  # 是否已扫描病毒
    scan_result = Column(String)  # clean, infected, unknown
    scan_date = Column(DateTime(timezone=True))

    # 使用统计
    download_count = Column(Integer, default=0)
    last_accessed = Column(DateTime(timezone=True))

    # 过期设置
    expires_at = Column(DateTime(timezone=True))  # 过期时间
    auto_delete = Column(Boolean, default=True)  # 是否自动删除

    # 关联信息
    related_emails = Column(ARRAY(UUID), default=[])  # 关联的邮件ID
    tags = Column(ARRAY(String), default=[])  # 标签

    # 状态字段
    is_active = Column(Boolean, default=True)
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class EmailBulkSend(Base):
    """批量发送记录表"""

    __tablename__ = "email_bulk_send"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # 批量发送信息
    batch_name = Column(String)
    total_emails = Column(Integer, nullable=False)
    successful_sends = Column(Integer, default=0)
    failed_sends = Column(Integer, default=0)

    # 发送设置
    smtp_setting_id = Column(UUID(as_uuid=True), ForeignKey("email_smtp_settings.id"))
    template_id = Column(UUID(as_uuid=True), ForeignKey("email_templates.id"))

    # 公共内容
    common_subject = Column(String)
    common_body_text = Column(Text)
    common_body_html = Column(Text)
    common_attachments = Column(JSONB, default={})

    # 执行状态
    status = Column(
        String, default="pending"
    )  # pending, running, completed, failed, cancelled
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    # 错误信息
    error_summary = Column(JSONB, default={})

    # 设置信息
    send_rate_limit = Column(Integer)  # 每分钟发送限制
    batch_size = Column(Integer, default=10)  # 批次大小

    # 系统字段
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    smtp_setting = relationship("EmailSMTPSettings")
    template = relationship("EmailTemplate")


class EmailTrackingPixel(Base):
    """邮件跟踪像素表"""

    __tablename__ = "email_tracking_pixel"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    queue_id = Column(UUID(as_uuid=True), ForeignKey("email_sending_queue.id"))
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # 跟踪信息
    recipient_email = Column(String, nullable=False)
    tracking_token = Column(String, unique=True, nullable=False)

    # 访问记录
    first_opened_at = Column(DateTime(timezone=True))
    last_opened_at = Column(DateTime(timezone=True))
    open_count = Column(Integer, default=0)

    # 设备信息
    user_agent = Column(Text)
    ip_address = Column(String)
    device_type = Column(String)  # desktop, mobile, tablet

    # 地理位置
    country = Column(String)
    city = Column(String)

    # 状态
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    queue_item = relationship("EmailSendingQueue")


class EmailClickTracking(Base):
    """邮件点击跟踪表"""

    __tablename__ = "email_click_tracking"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    queue_id = Column(UUID(as_uuid=True), ForeignKey("email_sending_queue.id"))
    tenant_id = Column(UUID(as_uuid=True), nullable=False)

    # 链接信息
    original_url = Column(Text, nullable=False)
    tracking_token = Column(String, unique=True, nullable=False)
    link_text = Column(String)

    # 点击记录
    first_clicked_at = Column(DateTime(timezone=True))
    last_clicked_at = Column(DateTime(timezone=True))
    click_count = Column(Integer, default=0)

    # 设备信息
    user_agent = Column(Text)
    ip_address = Column(String)

    # 状态
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    queue_item = relationship("EmailSendingQueue")


# 为了兼容性，保持原有的导入
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
