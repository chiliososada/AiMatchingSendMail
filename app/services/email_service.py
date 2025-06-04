# app/services/email_service.py
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timedelta
import os
import shutil
from pathlib import Path
import mimetypes
import logging

from ..models.email_models import EmailSMTPSettings, EmailSendingQueue, EmailSendingLogs
from ..schemas.email_schemas import (
    EmailSendRequest,
    SMTPSettingsCreate,
    AttachmentInfo,
    EmailWithAttachmentsRequest,
    BulkEmailRequest,
    AttachmentUploadResponse,
)
from ..utils.security import encrypt_password
from .smtp_service import SMTPService
from ..config import settings

logger = logging.getLogger(__name__)


class AttachmentManager:
    """附件管理器"""

    def __init__(self, base_path: str = "uploads/attachments"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # 临时文件清理阈值（24小时）
        self.cleanup_threshold = timedelta(hours=24)

    def save_attachment(
        self,
        file_content: bytes,
        filename: str,
        tenant_id: UUID,
        content_type: Optional[str] = None,
    ) -> AttachmentInfo:
        """保存附件文件"""
        try:
            # 生成唯一的文件ID
            attachment_id = uuid4()

            # 创建租户专属目录
            tenant_dir = self.base_path / str(tenant_id)
            tenant_dir.mkdir(parents=True, exist_ok=True)

            # 生成文件路径
            file_extension = Path(filename).suffix
            safe_filename = f"{attachment_id}{file_extension}"
            file_path = tenant_dir / safe_filename

            # 保存文件
            with open(file_path, "wb") as f:
                f.write(file_content)

            # 自动检测MIME类型
            if not content_type:
                content_type, _ = mimetypes.guess_type(filename)
                if not content_type:
                    content_type = "application/octet-stream"

            # 创建附件信息
            attachment_info = AttachmentInfo(
                filename=filename,
                content_type=content_type,
                file_size=len(file_content),
                file_path=str(file_path),
            )

            logger.info(f"附件保存成功: {filename}, 大小: {len(file_content)} bytes")
            return attachment_info, attachment_id

        except Exception as e:
            logger.error(f"保存附件失败: {filename}, 错误: {str(e)}")
            raise Exception(f"保存附件失败: {str(e)}")

    def get_attachment_path(
        self, tenant_id: UUID, attachment_id: UUID, filename: str
    ) -> Optional[str]:
        """获取附件文件路径"""
        file_extension = Path(filename).suffix
        safe_filename = f"{attachment_id}{file_extension}"
        file_path = self.base_path / str(tenant_id) / safe_filename

        if file_path.exists():
            return str(file_path)
        return None

    def delete_attachment(
        self, tenant_id: UUID, attachment_id: UUID, filename: str
    ) -> bool:
        """删除附件文件"""
        try:
            file_path = self.get_attachment_path(tenant_id, attachment_id, filename)
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"附件删除成功: {filename}")
                return True
            return False
        except Exception as e:
            logger.error(f"删除附件失败: {filename}, 错误: {str(e)}")
            return False

    def cleanup_old_files(self, tenant_id: Optional[UUID] = None):
        """清理过期的临时文件"""
        try:
            threshold_time = datetime.now() - self.cleanup_threshold
            cleanup_count = 0

            search_path = (
                self.base_path / str(tenant_id) if tenant_id else self.base_path
            )

            for file_path in search_path.rglob("*"):
                if file_path.is_file():
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_mtime < threshold_time:
                        try:
                            file_path.unlink()
                            cleanup_count += 1
                        except Exception as e:
                            logger.warning(
                                f"删除过期文件失败: {file_path}, 错误: {str(e)}"
                            )

            logger.info(f"清理完成，删除了 {cleanup_count} 个过期文件")
            return cleanup_count

        except Exception as e:
            logger.error(f"清理过期文件失败: {str(e)}")
            return 0

    def get_tenant_storage_usage(self, tenant_id: UUID) -> Dict[str, Any]:
        """获取租户存储使用情况"""
        try:
            tenant_dir = self.base_path / str(tenant_id)
            if not tenant_dir.exists():
                return {"total_size": 0, "file_count": 0, "files": []}

            total_size = 0
            file_count = 0
            files = []

            for file_path in tenant_dir.rglob("*"):
                if file_path.is_file():
                    file_size = file_path.stat().st_size
                    total_size += file_size
                    file_count += 1

                    files.append(
                        {
                            "name": file_path.name,
                            "size": file_size,
                            "modified": datetime.fromtimestamp(
                                file_path.stat().st_mtime
                            ),
                        }
                    )

            return {"total_size": total_size, "file_count": file_count, "files": files}

        except Exception as e:
            logger.error(f"获取存储使用情况失败: {str(e)}")
            return {"total_size": 0, "file_count": 0, "files": [], "error": str(e)}


class EmailService:
    def __init__(self, db: Session):
        self.db = db
        self.attachment_manager = AttachmentManager()

    def create_smtp_settings(
        self, settings_data: SMTPSettingsCreate
    ) -> EmailSMTPSettings:
        """创建SMTP设置"""
        # 加密密码
        encrypted_password = encrypt_password(settings_data.smtp_password)

        # 如果设置为默认，先取消其他默认设置
        if settings_data.is_default:
            self.db.query(EmailSMTPSettings).filter(
                and_(
                    EmailSMTPSettings.tenant_id == settings_data.tenant_id,
                    EmailSMTPSettings.is_default == True,
                )
            ).update({"is_default": False})

        smtp_settings = EmailSMTPSettings(
            tenant_id=settings_data.tenant_id,
            setting_name=settings_data.setting_name,
            smtp_host=settings_data.smtp_host,
            smtp_port=settings_data.smtp_port,
            smtp_username=settings_data.smtp_username,
            smtp_password_encrypted=encrypted_password,
            security_protocol=settings_data.security_protocol,
            from_email=settings_data.from_email,
            from_name=settings_data.from_name,
            reply_to_email=settings_data.reply_to_email,
            daily_send_limit=settings_data.daily_send_limit,
            hourly_send_limit=settings_data.hourly_send_limit,
            is_default=settings_data.is_default,
        )

        self.db.add(smtp_settings)
        self.db.commit()
        self.db.refresh(smtp_settings)

        return smtp_settings

    def get_smtp_settings(
        self, tenant_id: UUID, setting_id: Optional[UUID] = None
    ) -> Optional[EmailSMTPSettings]:
        """获取SMTP设置"""
        query = self.db.query(EmailSMTPSettings).filter(
            and_(
                EmailSMTPSettings.tenant_id == tenant_id,
                EmailSMTPSettings.is_active == True,
            )
        )

        if setting_id:
            return query.filter(EmailSMTPSettings.id == setting_id).first()
        else:
            # 获取默认设置
            default = query.filter(EmailSMTPSettings.is_default == True).first()
            if default:
                return default
            # 如果没有默认设置，返回第一个
            return query.first()

    def get_smtp_settings_list(self, tenant_id: UUID) -> List[EmailSMTPSettings]:
        """获取SMTP设置列表"""
        return (
            self.db.query(EmailSMTPSettings)
            .filter(
                and_(
                    EmailSMTPSettings.tenant_id == tenant_id,
                    EmailSMTPSettings.is_active == True,
                )
            )
            .all()
        )

    def save_attachment(
        self,
        file_content: bytes,
        filename: str,
        tenant_id: UUID,
        content_type: Optional[str] = None,
    ) -> tuple[AttachmentInfo, UUID]:
        """保存附件并返回附件信息"""
        return self.attachment_manager.save_attachment(
            file_content, filename, tenant_id, content_type
        )

    def get_attachment_info(
        self, tenant_id: UUID, attachment_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """获取附件信息（从数据库或缓存）"""
        # 这里可以实现数据库存储的附件元数据
        # 暂时返回None，表示需要从文件系统获取
        return None

    def delete_attachment(
        self, tenant_id: UUID, attachment_id: UUID, filename: str
    ) -> bool:
        """删除附件"""
        return self.attachment_manager.delete_attachment(
            tenant_id, attachment_id, filename
        )

    async def test_smtp_connection(self, tenant_id: UUID, setting_id: UUID) -> dict:
        """测试SMTP连接"""
        smtp_settings = self.get_smtp_settings(tenant_id, setting_id)
        if not smtp_settings:
            return {"status": "failed", "message": "SMTP设置不存在"}

        smtp_service = SMTPService(smtp_settings)
        result = await smtp_service.test_connection()

        # 更新连接状态
        smtp_settings.connection_status = result["status"]
        smtp_settings.last_test_at = datetime.utcnow()
        if result["status"] == "failed":
            smtp_settings.last_test_error = result.get("error", "")
        else:
            smtp_settings.last_test_error = None

        self.db.commit()

        return result

    def create_email_queue(
        self,
        email_request: EmailWithAttachmentsRequest,
        attachments_info: Optional[List[AttachmentInfo]] = None,
        created_by: Optional[UUID] = None,
    ) -> EmailSendingQueue:
        """创建邮件发送队列（支持附件）"""
        # 获取SMTP设置
        smtp_settings = self.get_smtp_settings(
            email_request.tenant_id, email_request.smtp_setting_id
        )
        if not smtp_settings:
            raise ValueError("未找到可用的SMTP设置")

        # 准备附件信息
        attachments_data = {}
        if attachments_info:
            attachments_data = {
                "attachments": [
                    {
                        "filename": att.filename,
                        "content_type": att.content_type,
                        "file_size": att.file_size,
                        "file_path": att.file_path,
                    }
                    for att in attachments_info
                ],
                "total_attachment_size": sum(att.file_size for att in attachments_info),
                "attachment_count": len(attachments_info),
            }

        queue_item = EmailSendingQueue(
            tenant_id=email_request.tenant_id,
            to_emails=email_request.to_emails,
            subject=email_request.subject,
            body_text=email_request.body_text,
            body_html=email_request.body_html,
            smtp_setting_id=smtp_settings.id,
            priority=email_request.priority,
            scheduled_at=email_request.scheduled_at or datetime.utcnow(),
            related_project_id=email_request.related_project_id,
            related_engineer_id=email_request.related_engineer_id,
            metadata={**(email_request.metadata or {}), **attachments_data},
            attachments=attachments_data,
            created_by=created_by,
        )

        self.db.add(queue_item)
        self.db.commit()
        self.db.refresh(queue_item)

        return queue_item

    async def send_email_with_attachments(
        self,
        email_request: EmailWithAttachmentsRequest,
        created_by: Optional[UUID] = None,
    ) -> dict:
        """发送带附件的邮件"""
        try:
            # 获取附件信息和文件路径
            attachments_info = []
            attachment_paths = {}

            if email_request.attachment_ids:
                for attachment_id in email_request.attachment_ids:
                    # 这里需要从数据库或缓存获取附件信息
                    # 暂时使用文件系统查找
                    # 在实际实现中，应该有一个附件元数据表
                    pass

            # 创建队列记录
            queue_item = self.create_email_queue(
                email_request, attachments_info, created_by
            )

            # 获取SMTP设置
            smtp_settings = self.get_smtp_settings(
                email_request.tenant_id, email_request.smtp_setting_id
            )
            smtp_service = SMTPService(smtp_settings)

            # 发送邮件
            result = await smtp_service.send_email(
                to_emails=email_request.to_emails,
                subject=email_request.subject,
                body_text=email_request.body_text,
                body_html=email_request.body_html,
                attachments=attachments_info,
                attachment_paths=attachment_paths,
            )

            # 更新队列状态
            if result["status"] == "success":
                queue_item.status = "sent"
                queue_item.sent_at = datetime.utcnow()
            else:
                queue_item.status = "failed"
                queue_item.error_message = result.get("error", "")

            queue_item.last_attempt_at = datetime.utcnow()
            self.db.commit()

            # 创建日志记录
            log_entry = EmailSendingLogs(
                queue_id=queue_item.id,
                tenant_id=email_request.tenant_id,
                message_id=result.get("message_id", ""),
                smtp_response=result.get("smtp_response", ""),
                delivery_status=result["status"],
            )
            self.db.add(log_entry)
            self.db.commit()

            return {
                "queue_id": queue_item.id,
                "status": result["status"],
                "message": result["message"],
                "to_emails": email_request.to_emails,
                "attachment_count": len(attachments_info),
                "scheduled_at": email_request.scheduled_at,
            }

        except Exception as e:
            logger.error(f"发送带附件邮件失败: {str(e)}")
            raise Exception(f"发送邮件失败: {str(e)}")

    async def send_email_immediately(
        self, email_request: EmailSendRequest, created_by: Optional[UUID] = None
    ) -> dict:
        """立即发送邮件（兼容旧接口）"""
        # 转换为带附件的请求格式
        enhanced_request = EmailWithAttachmentsRequest(
            **email_request.dict(), attachment_ids=[]
        )
        return await self.send_email_with_attachments(enhanced_request, created_by)

    async def send_bulk_emails(
        self, bulk_request: BulkEmailRequest, created_by: Optional[UUID] = None
    ) -> dict:
        """批量发送邮件"""
        try:
            # 获取SMTP设置
            smtp_settings = self.get_smtp_settings(
                bulk_request.tenant_id, bulk_request.smtp_setting_id
            )
            if not smtp_settings:
                raise ValueError("未找到可用的SMTP设置")

            smtp_service = SMTPService(smtp_settings)

            # 准备公共附件信息
            common_attachments = []
            attachment_paths = {}

            if bulk_request.common_attachment_ids:
                # 获取公共附件信息
                # 这里需要实现附件ID到附件信息的转换
                pass

            # 准备邮件列表
            email_list = []
            for email_data in bulk_request.emails:
                email_item = {
                    "to_email": email_data["to_email"],
                    "subject": email_data.get("subject", bulk_request.common_subject),
                    "body_text": email_data.get(
                        "body_text", bulk_request.common_body_text
                    ),
                    "body_html": email_data.get(
                        "body_html", bulk_request.common_body_html
                    ),
                }
                email_list.append(email_item)

            # 批量发送
            results = await smtp_service.send_bulk_emails(
                email_list=email_list,
                common_attachments=common_attachments,
                attachment_paths=attachment_paths,
            )

            # 记录批量发送结果
            for i, email_data in enumerate(bulk_request.emails):
                queue_item = EmailSendingQueue(
                    tenant_id=bulk_request.tenant_id,
                    to_emails=[email_data["to_email"]],
                    subject=email_data.get("subject", bulk_request.common_subject),
                    body_text=email_data.get(
                        "body_text", bulk_request.common_body_text
                    ),
                    body_html=email_data.get(
                        "body_html", bulk_request.common_body_html
                    ),
                    smtp_setting_id=smtp_settings.id,
                    priority=bulk_request.priority,
                    status="sent" if i < results["success"] else "failed",
                    sent_at=datetime.utcnow() if i < results["success"] else None,
                    created_by=created_by,
                    metadata={"bulk_send": True, "batch_index": i},
                )
                self.db.add(queue_item)

            self.db.commit()

            return {
                "status": "completed",
                "total_emails": results["total"],
                "successful_sends": results["success"],
                "failed_sends": results["failed"],
                "errors": results["errors"],
            }

        except Exception as e:
            logger.error(f"批量发送邮件失败: {str(e)}")
            raise Exception(f"批量发送失败: {str(e)}")

    async def send_test_email(
        self, tenant_id: UUID, smtp_setting_id: UUID, test_email: str
    ) -> dict:
        """发送测试邮件"""
        email_request = EmailWithAttachmentsRequest(
            tenant_id=tenant_id,
            to_emails=[test_email],
            subject="邮件系统测试",
            body_text="这是一封测试邮件，如果您收到此邮件，说明邮件系统配置正确。",
            body_html="<p>这是一封测试邮件，如果您收到此邮件，说明邮件系统配置正确。</p>",
            smtp_setting_id=smtp_setting_id,
            attachment_ids=[],
            metadata={"test_email": True},
        )

        return await self.send_email_with_attachments(email_request)

    def get_email_queue_status(
        self, tenant_id: UUID, queue_id: UUID
    ) -> Optional[EmailSendingQueue]:
        """获取邮件队列状态"""
        return (
            self.db.query(EmailSendingQueue)
            .filter(
                and_(
                    EmailSendingQueue.id == queue_id,
                    EmailSendingQueue.tenant_id == tenant_id,
                )
            )
            .first()
        )

    def get_email_queue_list(
        self, tenant_id: UUID, limit: int = 50, offset: int = 0
    ) -> List[EmailSendingQueue]:
        """获取邮件队列列表"""
        return (
            self.db.query(EmailSendingQueue)
            .filter(EmailSendingQueue.tenant_id == tenant_id)
            .order_by(EmailSendingQueue.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_email_statistics(self, tenant_id: UUID, days: int = 30) -> Dict[str, Any]:
        """获取邮件发送统计"""
        from sqlalchemy import func

        # 计算日期范围
        start_date = datetime.utcnow() - timedelta(days=days)

        # 基础统计查询
        stats_query = (
            self.db.query(
                func.count(EmailSendingQueue.id).label("total"),
                func.sum(
                    func.case([(EmailSendingQueue.status == "sent", 1)], else_=0)
                ).label("sent"),
                func.sum(
                    func.case([(EmailSendingQueue.status == "failed", 1)], else_=0)
                ).label("failed"),
                func.sum(
                    func.case(
                        [(EmailSendingQueue.status.in_(["queued", "sending"]), 1)],
                        else_=0,
                    )
                ).label("pending"),
            )
            .filter(
                and_(
                    EmailSendingQueue.tenant_id == tenant_id,
                    EmailSendingQueue.created_at >= start_date,
                )
            )
            .first()
        )

        total = stats_query.total or 0
        sent = stats_query.sent or 0
        failed = stats_query.failed or 0
        pending = stats_query.pending or 0

        # 计算成功率
        success_rate = (sent / total * 100) if total > 0 else 0

        # 获取附件统计
        attachment_stats = self.attachment_manager.get_tenant_storage_usage(tenant_id)

        return {
            "total_sent": sent,
            "total_failed": failed,
            "total_pending": pending,
            "success_rate": round(success_rate, 2),
            "total_attachments": attachment_stats["file_count"],
            "total_attachment_size": attachment_stats["total_size"],
            "period_days": days,
        }

    def cleanup_old_attachments(
        self, tenant_id: Optional[UUID] = None, days: int = 7
    ) -> int:
        """清理过期附件"""
        return self.attachment_manager.cleanup_old_files(tenant_id)
