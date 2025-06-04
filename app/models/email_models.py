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

    # 元数据和统计 - 修改字段名避免与SQLAlchemy保留字冲突
    email_metadata = Column(JSONB, default={})  # 原来的 metadata 改为 email_metadata
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


# 为了兼容性，保持原有的导入
__all__ = [
    "EmailSMTPSettings",
    "EmailSendingQueue",
    "EmailSendingLogs",
]
