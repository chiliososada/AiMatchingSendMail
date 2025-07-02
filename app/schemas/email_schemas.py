# app/schemas/email_schemas.py
from pydantic import BaseModel, EmailStr, validator, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID


class SMTPSettingsCreate(BaseModel):
    tenant_id: UUID
    setting_name: str
    smtp_host: str
    smtp_port: int = 587
    smtp_username: str
    smtp_password: str  # 未加密，服务端会加密
    security_protocol: str = "TLS"
    from_email: EmailStr
    from_name: Optional[str] = None
    reply_to_email: Optional[EmailStr] = None
    daily_send_limit: int = 1000
    hourly_send_limit: int = 100
    is_default: bool = False


class SMTPSettingsResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    setting_name: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    security_protocol: str
    from_email: str
    from_name: Optional[str]
    reply_to_email: Optional[str]
    connection_status: str
    is_default: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AttachmentInfo(BaseModel):
    """附件信息"""

    filename: str
    content_type: str
    file_size: int
    file_path: Optional[str] = None  # 服务器存储路径
    file_url: Optional[str] = None  # 可访问的URL

    @validator("file_size")
    def validate_file_size(cls, v):
        # 限制单个附件最大25MB
        max_size = 25 * 1024 * 1024  # 25MB
        if v > max_size:
            raise ValueError(f"附件大小不能超过25MB，当前大小: {v/1024/1024:.2f}MB")
        return v

    @validator("filename")
    def validate_filename(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("文件名不能为空")

        # 禁止的文件扩展名（安全考虑）
        forbidden_extensions = [
            ".exe",
            ".bat",
            ".cmd",
            ".scr",
            ".pif",
            ".com",
            ".vbs",
            ".js",
        ]
        filename_lower = v.lower()

        for ext in forbidden_extensions:
            if filename_lower.endswith(ext):
                raise ValueError(f"不允许上传 {ext} 类型的文件")

        return v


class EmailSendRequest(BaseModel):
    tenant_id: UUID
    to_emails: List[EmailStr]
    subject: str
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    smtp_setting_id: Optional[UUID] = None  # 如果不指定，使用默认配置
    priority: int = 5
    scheduled_at: Optional[datetime] = None
    related_project_id: Optional[UUID] = None
    related_engineer_id: Optional[UUID] = None
    metadata: Optional[Dict[str, Any]] = {}

    @validator("to_emails")
    def validate_to_emails(cls, v):
        if not v:
            raise ValueError("至少需要一个收件人")
        if len(v) > 100:  # 限制群发数量
            raise ValueError("收件人数量不能超过100个")
        return v

    @validator("priority")
    def validate_priority(cls, v):
        if not 1 <= v <= 10:
            raise ValueError("优先级必须在1-10之间")
        return v


class EmailWithAttachmentsRequest(EmailSendRequest):
    """带附件的邮件发送请求"""

    attachment_ids: Optional[List[UUID]] = Field(
        default_factory=list, description="已上传的附件ID列表"
    )
    attachment_filenames: Optional[List[str]] = Field(
        default_factory=list, description="附件的原始文件名列表，与attachment_ids对应"
    )

    @validator("attachment_ids")
    def validate_attachments(cls, v):
        if v and len(v) > 10:  # 限制附件数量
            raise ValueError("附件数量不能超过10个")
        return v
    
    @validator("attachment_filenames")
    def validate_attachment_filenames(cls, v, values):
        attachment_ids = values.get("attachment_ids", [])
        if v and attachment_ids and len(v) != len(attachment_ids):
            raise ValueError("attachment_filenames的数量必须与attachment_ids的数量一致")
        return v


class EmailSendResponse(BaseModel):
    queue_id: UUID
    status: str
    message: str
    to_emails: List[str]
    scheduled_at: Optional[datetime]
    attachments_count: Optional[int] = 0


class EmailTestRequest(BaseModel):
    tenant_id: UUID
    smtp_setting_id: UUID
    test_email: EmailStr


class EmailStatusResponse(BaseModel):
    id: UUID
    to_emails: List[str]
    subject: str
    status: str
    created_at: datetime
    sent_at: Optional[datetime]
    error_message: Optional[str]
    attachments_info: Optional[List[AttachmentInfo]] = Field(default_factory=list)

    class Config:
        from_attributes = True


class AttachmentUploadResponse(BaseModel):
    """附件上传响应"""

    attachment_id: UUID
    filename: str
    content_type: str
    file_size: int
    upload_url: Optional[str] = None  # 如果需要分步上传
    status: str = "uploaded"
    message: str = "附件上传成功"


class AttachmentDeleteRequest(BaseModel):
    """删除附件请求"""

    tenant_id: UUID
    attachment_id: UUID


class BulkEmailRequest(BaseModel):
    """批量邮件发送请求（带个性化内容）"""

    tenant_id: UUID
    emails: List[Dict[str, Any]]  # 每个邮件的个性化内容
    common_subject: Optional[str] = None  # 公共主题
    common_body_text: Optional[str] = None  # 公共文本内容
    common_body_html: Optional[str] = None  # 公共HTML内容
    common_attachment_ids: Optional[List[UUID]] = Field(
        default_factory=list
    )  # 公共附件
    smtp_setting_id: Optional[UUID] = None
    priority: int = 5

    @validator("emails")
    def validate_emails(cls, v):
        if not v:
            raise ValueError("邮件列表不能为空")
        if len(v) > 1000:  # 限制批量发送数量
            raise ValueError("批量发送数量不能超过1000封")

        for email in v:
            if "to_email" not in email:
                raise ValueError("每封邮件必须包含to_email字段")

        return v


class AttachmentListResponse(BaseModel):
    """附件列表响应"""

    attachments: List[AttachmentInfo]
    total_count: int
    total_size: int  # 总大小（字节）


class EmailStatistics(BaseModel):
    """邮件统计信息"""

    total_sent: int
    total_failed: int
    total_pending: int
    success_rate: float
    total_attachments: int
    total_attachment_size: int  # 总附件大小（字节）
    avg_send_time: Optional[float] = None  # 平均发送时间（秒）
