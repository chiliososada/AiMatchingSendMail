# app/services/email_service.py - asyncpg版本
import asyncio
from uuid import UUID, uuid4
from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime, timedelta
import os
import shutil
from pathlib import Path
import mimetypes
import logging
import json


from ..database import (
    get_db_connection,
    get_db_transaction,
    execute_query,
    fetch_one,
    fetch_all,
    fetch_val,
)
from ..schemas.email_schemas import (
    EmailSendRequest,
    SMTPSettingsCreate,
    AttachmentInfo,
    EmailWithAttachmentsRequest,
    BulkEmailRequest,
    AttachmentUploadResponse,
)
from ..utils.security import encrypt_password, SMTPPasswordManager

# 创建全局SMTP密码管理器实例
smtp_password_manager = SMTPPasswordManager()
from .smtp_service import SMTPService
from ..config import settings


logger = logging.getLogger(__name__)


class AttachmentManager:
    """增强版附件管理器"""

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
    ) -> Tuple[AttachmentInfo, UUID]:
        """
        保存附件文件

        Args:
            file_content: 文件内容
            filename: 文件名
            tenant_id: 租户ID
            content_type: MIME类型

        Returns:
            Tuple[AttachmentInfo, UUID]: 附件信息和附件ID
        """
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

            logger.info(
                f"附件保存成功: {filename}, 大小: {len(file_content)} bytes, ID: {attachment_id}"
            )
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

    def get_attachment_info_by_id(
        self, tenant_id: UUID, attachment_id: UUID
    ) -> Optional[AttachmentInfo]:
        """
        根据attachment_id获取附件信息
        
        Args:
            tenant_id: 租户ID
            attachment_id: 附件ID
            
        Returns:
            Optional[AttachmentInfo]: 附件信息
        """
        # 构建租户目录路径
        tenant_dir = os.path.join(self.base_path, str(tenant_id))
        if not os.path.exists(tenant_dir):
            return None
            
        # 查找以attachment_id为前缀的文件
        for filename in os.listdir(tenant_dir):
            if filename.startswith(str(attachment_id)):
                file_path = os.path.join(tenant_dir, filename)
                if os.path.isfile(file_path):
                    try:
                        # 获取文件统计信息
                        stat = os.stat(file_path)
                        
                        # 检测MIME类型
                        content_type, _ = mimetypes.guess_type(filename)
                        if not content_type:
                            content_type = "application/octet-stream"
                            
                        return AttachmentInfo(
                            filename=filename,
                            content_type=content_type,
                            file_size=stat.st_size,
                            file_path=file_path,
                        )
                    except Exception as e:
                        logger.error(f"获取附件信息失败: {filename}, 错误: {str(e)}")
                        return None
        return None

    def get_attachment_info(
        self, tenant_id: UUID, attachment_id: UUID, filename: str
    ) -> Optional[AttachmentInfo]:
        """
        获取附件信息

        Args:
            tenant_id: 租户ID
            attachment_id: 附件ID
            filename: 文件名

        Returns:
            Optional[AttachmentInfo]: 附件信息
        """
        file_path = self.get_attachment_path(tenant_id, attachment_id, filename)
        if not file_path or not os.path.exists(file_path):
            return None

        try:
            # 获取文件统计信息
            stat = os.stat(file_path)

            # 检测MIME类型
            content_type, _ = mimetypes.guess_type(filename)
            if not content_type:
                content_type = "application/octet-stream"

            return AttachmentInfo(
                filename=filename,
                content_type=content_type,
                file_size=stat.st_size,
                file_path=file_path,
            )
        except Exception as e:
            logger.error(f"获取附件信息失败: {filename}, 错误: {str(e)}")
            return None

    def delete_attachment(
        self, tenant_id: UUID, attachment_id: UUID, filename: str
    ) -> bool:
        """删除附件文件"""
        try:
            file_path = self.get_attachment_path(tenant_id, attachment_id, filename)
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"附件删除成功: {filename} (ID: {attachment_id})")
                return True
            return False
        except Exception as e:
            logger.error(f"删除附件失败: {filename}, 错误: {str(e)}")
            return False

    def cleanup_old_files(self, tenant_id: Optional[UUID] = None) -> int:
        """清理过期的临时文件"""
        try:
            threshold_time = datetime.now() - self.cleanup_threshold
            cleanup_count = 0

            search_path = (
                self.base_path / str(tenant_id) if tenant_id else self.base_path
            )

            if not search_path.exists():
                return 0

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
                            ).isoformat(),
                        }
                    )

            return {
                "total_size": total_size,
                "file_count": file_count,
                "files": files,
                "tenant_id": str(tenant_id),
                "storage_path": str(tenant_dir),
            }

        except Exception as e:
            logger.error(f"获取存储使用情况失败: {str(e)}")
            return {"total_size": 0, "file_count": 0, "files": [], "error": str(e)}


class EmailService:
    """增强版邮件服务 - asyncpg版本"""

    def __init__(self):
        self.attachment_manager = AttachmentManager()

    async def create_smtp_settings(
        self, settings_data: SMTPSettingsCreate
    ) -> Dict[str, Any]:
        """
        创建SMTP设置

        Args:
            settings_data: SMTP设置数据

        Returns:
            Dict: 创建的SMTP设置信息
        """
        try:
            # 使用增强的密码管理器加密密码
            encrypted_password = smtp_password_manager.encrypt(
                settings_data.smtp_password
            )

            async with get_db_transaction() as conn:
                # 如果设置为默认，先取消其他默认设置
                if settings_data.is_default:
                    await conn.execute(
                        """
                        UPDATE email_smtp_settings 
                        SET is_default = FALSE 
                        WHERE tenant_id = $1 AND is_default = TRUE
                        """,
                        settings_data.tenant_id,
                    )

                # 插入新的SMTP设置
                smtp_id = await conn.fetchval(
                    """
                    INSERT INTO email_smtp_settings (
                        tenant_id, setting_name, smtp_host, smtp_port, 
                        smtp_username, smtp_password_encrypted, security_protocol,
                        from_email, from_name, reply_to_email, 
                        daily_send_limit, hourly_send_limit, is_default
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    RETURNING id
                    """,
                    settings_data.tenant_id,
                    settings_data.setting_name,
                    settings_data.smtp_host,
                    settings_data.smtp_port,
                    settings_data.smtp_username,
                    encrypted_password,
                    settings_data.security_protocol,
                    settings_data.from_email,
                    settings_data.from_name,
                    settings_data.reply_to_email,
                    settings_data.daily_send_limit,
                    settings_data.hourly_send_limit,
                    settings_data.is_default,
                )

                # 获取创建的记录
                smtp_settings = await conn.fetchrow(
                    "SELECT * FROM email_smtp_settings WHERE id = $1", smtp_id
                )

            logger.info(
                f"SMTP设置创建成功: {settings_data.setting_name} (ID: {smtp_id})"
            )
            return dict(smtp_settings)

        except Exception as e:
            logger.error(f"创建SMTP设置失败: {str(e)}")
            raise Exception(f"创建SMTP设置失败: {str(e)}")

    async def get_smtp_settings(
        self, tenant_id: UUID, setting_id: Optional[UUID] = None
    ) -> Optional[Dict[str, Any]]:
        """获取SMTP设置"""
        try:
            if setting_id:
                query = """
                SELECT * FROM email_smtp_settings 
                WHERE tenant_id = $1 AND id = $2 AND is_active = TRUE
                """
                smtp_settings = await fetch_one(query, tenant_id, setting_id)
            else:
                # 获取默认设置
                query = """
                SELECT * FROM email_smtp_settings 
                WHERE tenant_id = $1 AND is_active = TRUE 
                ORDER BY is_default DESC, created_at DESC 
                LIMIT 1
                """
                smtp_settings = await fetch_one(query, tenant_id)

            return smtp_settings

        except Exception as e:
            logger.error(f"获取SMTP设置失败: {str(e)}")
            return None

    async def get_smtp_settings_list(self, tenant_id: UUID) -> List[Dict[str, Any]]:
        """获取SMTP设置列表"""
        try:
            query = """
            SELECT * FROM email_smtp_settings 
            WHERE tenant_id = $1 AND is_active = TRUE
            ORDER BY is_default DESC, created_at DESC
            """
            return await fetch_all(query, tenant_id)

        except Exception as e:
            logger.error(f"获取SMTP设置列表失败: {str(e)}")
            return []

    def save_attachment(
        self,
        file_content: bytes,
        filename: str,
        tenant_id: UUID,
        content_type: Optional[str] = None,
    ) -> Tuple[AttachmentInfo, UUID]:
        """保存附件并返回附件信息"""
        return self.attachment_manager.save_attachment(
            file_content, filename, tenant_id, content_type
        )

    def get_attachment_info(
        self, tenant_id: UUID, attachment_id: UUID, filename: str
    ) -> Optional[AttachmentInfo]:
        """获取附件信息"""
        return self.attachment_manager.get_attachment_info(
            tenant_id, attachment_id, filename
        )

    def delete_attachment(
        self, tenant_id: UUID, attachment_id: UUID, filename: str
    ) -> bool:
        """删除附件"""
        return self.attachment_manager.delete_attachment(
            tenant_id, attachment_id, filename
        )

    async def test_smtp_connection(self, tenant_id: UUID, setting_id: UUID) -> dict:
        """测试SMTP连接 - 修复版"""
        try:
            smtp_settings = await self.get_smtp_settings(tenant_id, setting_id)
            if not smtp_settings:
                return {"status": "failed", "message": "SMTP设置不存在"}

            logger.info(f"开始测试SMTP连接: {smtp_settings['setting_name']}")

            # 创建SMTP服务实例（需要模拟EmailSMTPSettings对象）
            class SMTPSettingsObj:
                def __init__(self, data):
                    for key, value in data.items():
                        setattr(self, key, value)

            smtp_settings_obj = SMTPSettingsObj(smtp_settings)

            try:
                smtp_service = SMTPService(smtp_settings_obj)
                result = await smtp_service.test_connection()
            except Exception as service_error:
                logger.error(f"创建SMTP服务失败: {str(service_error)}")
                return {
                    "status": "failed",
                    "message": f"SMTP服务初始化失败: {str(service_error)}",
                    "error": str(service_error),
                    "error_type": "service_initialization_error",
                }

            # 更新连接状态
            async with get_db_connection() as conn:
                await conn.execute(
                    """
                    UPDATE email_smtp_settings 
                    SET connection_status = $1, last_test_at = $2, last_test_error = $3
                    WHERE id = $4
                    """,
                    result["status"],
                    datetime.utcnow(),
                    result.get("error") if result["status"] == "failed" else None,
                    setting_id,
                )

            return result

        except Exception as e:
            logger.error(f"SMTP连接测试失败: {str(e)}")
            import traceback

            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return {
                "status": "failed",
                "message": f"测试过程中发生错误: {str(e)}",
                "error": str(e),
                "error_type": "service_error",
            }

    async def create_email_queue(
        self,
        email_request: EmailWithAttachmentsRequest,
        attachments_info: Optional[List[AttachmentInfo]] = None,
        created_by: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """创建邮件发送队列（支持附件）"""
        try:
            # 获取SMTP设置
            smtp_settings = await self.get_smtp_settings(
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
                            "attachment_id": str(att.filename),  # 使用文件名作为ID
                            "filename": att.filename,
                            "content_type": att.content_type,
                            "file_size": att.file_size,
                            "file_path": att.file_path,
                        }
                        for att in attachments_info
                    ],
                    "total_attachment_size": sum(
                        att.file_size for att in attachments_info
                    ),
                    "attachment_count": len(attachments_info),
                }

            # 创建队列项
            async with get_db_connection() as conn:
                queue_id = await conn.fetchval(
                    """
                    INSERT INTO email_sending_queue (
                        tenant_id, to_emails, subject, body_text, body_html,
                        smtp_setting_id, priority, scheduled_at, 
                        related_project_id, related_engineer_id,
                        email_metadata, attachments, created_by
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    RETURNING id
                    """,
                    email_request.tenant_id,
                    email_request.to_emails,
                    email_request.subject,
                    email_request.body_text,
                    email_request.body_html,
                    smtp_settings["id"],
                    email_request.priority,
                    email_request.scheduled_at or datetime.utcnow(),
                    email_request.related_project_id,
                    email_request.related_engineer_id,
                    json.dumps({**(email_request.metadata or {}), **attachments_data}),
                    json.dumps(attachments_data),
                    created_by,
                )

                # 获取创建的记录
                queue_item = await conn.fetchrow(
                    "SELECT * FROM email_sending_queue WHERE id = $1", queue_id
                )

            logger.info(f"邮件队列创建成功: {queue_id}")
            return dict(queue_item)

        except Exception as e:
            logger.error(f"创建邮件队列失败: {str(e)}")
            raise Exception(f"创建邮件队列失败: {str(e)}")

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
                attachment_manager = AttachmentManager()
                attachment_filenames = email_request.attachment_filenames or []
                
                for i, attachment_id in enumerate(email_request.attachment_ids):
                    try:
                        # 获取附件信息
                        attachment_info = attachment_manager.get_attachment_info_by_id(
                            email_request.tenant_id, attachment_id
                        )
                        if attachment_info:
                            # 如果提供了原始文件名，则使用传递的文件名
                            if i < len(attachment_filenames) and attachment_filenames[i]:
                                original_filename = attachment_filenames[i]
                                # 创建新的AttachmentInfo使用原始文件名
                                attachment_info = AttachmentInfo(
                                    filename=original_filename,
                                    content_type=attachment_info.content_type,
                                    file_size=attachment_info.file_size,
                                    file_path=attachment_info.file_path,
                                )
                            
                            attachments_info.append(attachment_info)
                            # 构建文件路径映射
                            attachment_paths[attachment_info.filename] = attachment_info.file_path
                            logger.info(f"已加载附件: {attachment_info.filename}")
                        else:
                            logger.warning(f"附件不存在: {attachment_id}")
                    except Exception as e:
                        logger.error(f"获取附件信息失败: {attachment_id} - {str(e)}")

            # 创建队列记录
            queue_item = await self.create_email_queue(
                email_request, attachments_info, created_by
            )

            # 获取SMTP设置并创建服务
            smtp_settings = await self.get_smtp_settings(
                email_request.tenant_id, email_request.smtp_setting_id
            )

            # 创建SMTP服务实例
            class SMTPSettingsObj:
                def __init__(self, data):
                    for key, value in data.items():
                        setattr(self, key, value)

            smtp_settings_obj = SMTPSettingsObj(smtp_settings)
            smtp_service = SMTPService(smtp_settings_obj)

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
            async with get_db_connection() as conn:
                if result["status"] == "success":
                    await conn.execute(
                        """
                        UPDATE email_sending_queue 
                        SET status = 'sent', sent_at = $1, send_duration_ms = $2, last_attempt_at = $3
                        WHERE id = $4
                        """,
                        datetime.utcnow(),
                        int(result.get("send_duration_seconds", 0) * 1000),
                        datetime.utcnow(),
                        queue_item["id"],
                    )
                    
                    # 邮件发送成功后立即清理附件文件
                    if attachments_info and attachment_paths:
                        await self._cleanup_sent_attachments(
                            email_request.tenant_id, 
                            attachments_info, 
                            attachment_paths
                        )
                else:
                    await conn.execute(
                        """
                        UPDATE email_sending_queue 
                        SET status = 'failed', error_message = $1, last_attempt_at = $2
                        WHERE id = $3
                        """,
                        result.get("error", ""),
                        datetime.utcnow(),
                        queue_item["id"],
                    )

                # 创建详细日志记录
                await conn.execute(
                    """
                    INSERT INTO email_sending_logs (
                        queue_id, tenant_id, message_id, smtp_response, delivery_status,
                        send_start_time, send_end_time, response_time_ms, attachment_transfer_log
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    queue_item["id"],
                    email_request.tenant_id,
                    result.get("message_id", ""),
                    result.get("smtp_response", ""),
                    result["status"],
                    datetime.utcnow(),
                    datetime.utcnow(),
                    int(result.get("send_duration_seconds", 0) * 1000),
                    json.dumps(
                        {"attachment_count": len(attachments_info)}
                        if attachments_info
                        else {}
                    ),
                )

            return {
                "queue_id": queue_item["id"],
                "status": result["status"],
                "message": result["message"],
                "to_emails": email_request.to_emails,
                "attachment_count": len(attachments_info),
                "scheduled_at": email_request.scheduled_at,
                "message_id": result.get("message_id"),
                "send_duration_ms": int(result.get("send_duration_seconds", 0) * 1000),
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

    async def send_test_email(
        self, tenant_id: UUID, smtp_setting_id: UUID, test_email: str
    ) -> dict:
        """发送测试邮件"""
        try:
            smtp_settings = await self.get_smtp_settings(tenant_id, smtp_setting_id)
            if not smtp_settings:
                return {"status": "failed", "message": "SMTP设置不存在"}

            # 创建SMTP服务实例
            class SMTPSettingsObj:
                def __init__(self, data):
                    for key, value in data.items():
                        setattr(self, key, value)

            smtp_settings_obj = SMTPSettingsObj(smtp_settings)
            smtp_service = SMTPService(smtp_settings_obj)
            result = await smtp_service.send_test_email(test_email)

            # 记录测试邮件到队列
            if result["status"] == "success":
                async with get_db_connection() as conn:
                    await conn.execute(
                        """
                        INSERT INTO email_sending_queue (
                            tenant_id, to_emails, subject, body_text, 
                            smtp_setting_id, status, sent_at, email_metadata
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """,
                        tenant_id,
                        [test_email],
                        "邮件系统测试",
                        "这是一封测试邮件",
                        smtp_setting_id,
                        "sent",  # 修复：使用 "sent" 而不是 "success"
                        datetime.utcnow(),
                        json.dumps({"test_email": True}),
                    )

            return result

        except Exception as e:
            logger.error(f"发送测试邮件失败: {str(e)}")
            return {
                "status": "failed",
                "message": f"发送测试邮件失败: {str(e)}",
                "error": str(e),
            }

    async def get_email_queue_status(
        self, tenant_id: UUID, queue_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """获取邮件队列状态"""
        try:
            query = """
            SELECT * FROM email_sending_queue 
            WHERE id = $1 AND tenant_id = $2
            """
            return await fetch_one(query, queue_id, tenant_id)

        except Exception as e:
            logger.error(f"获取邮件队列状态失败: {str(e)}")
            return None

    async def get_email_queue_list(
        self, tenant_id: UUID, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """获取邮件队列列表"""
        try:
            query = """
            SELECT * FROM email_sending_queue 
            WHERE tenant_id = $1
            ORDER BY created_at DESC 
            LIMIT $2 OFFSET $3
            """
            return await fetch_all(query, tenant_id, limit, offset)

        except Exception as e:
            logger.error(f"获取邮件队列列表失败: {str(e)}")
            return []

    async def get_email_statistics(
        self, tenant_id: UUID, days: int = 30
    ) -> Dict[str, Any]:
        """获取邮件发送统计"""
        try:
            # 计算日期范围
            start_date = datetime.utcnow() - timedelta(days=days)

            # 基础统计查询
            stats_query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status IN ('queued', 'sending') THEN 1 ELSE 0 END) as pending,
                AVG(send_duration_ms) as avg_duration_ms
            FROM email_sending_queue 
            WHERE tenant_id = $1 AND created_at >= $2
            """

            stats = await fetch_one(stats_query, tenant_id, start_date)

            total = stats["total"] or 0
            sent = stats["sent"] or 0
            failed = stats["failed"] or 0
            pending = stats["pending"] or 0
            avg_duration_ms = stats["avg_duration_ms"] or 0

            # 计算成功率
            success_rate = (sent / total * 100) if total > 0 else 0

            # 获取附件统计
            attachment_stats = self.attachment_manager.get_tenant_storage_usage(
                tenant_id
            )

            return {
                "total_sent": sent,
                "total_failed": failed,
                "total_pending": pending,
                "success_rate": round(success_rate, 2),
                "avg_send_time_ms": round(avg_duration_ms, 2) if avg_duration_ms else 0,
                "total_attachments": attachment_stats["file_count"],
                "total_attachment_size": attachment_stats["total_size"],
                "period_days": days,
                "start_date": start_date.isoformat(),
                "end_date": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"获取邮件统计失败: {str(e)}")
            return {
                "total_sent": 0,
                "total_failed": 0,
                "total_pending": 0,
                "success_rate": 0,
                "avg_send_time_ms": 0,
                "total_attachments": 0,
                "total_attachment_size": 0,
                "period_days": days,
                "error": str(e),
            }

    def cleanup_old_attachments(
        self, tenant_id: Optional[UUID] = None, days: int = 7
    ) -> int:
        """清理过期附件"""
        return self.attachment_manager.cleanup_old_files(tenant_id)

    async def get_smtp_config_info(
        self, tenant_id: UUID, setting_id: Optional[UUID] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取SMTP配置信息（包含解密后的密码，仅供内部使用）
        修复版 - 与aimachingmail项目兼容

        Args:
            tenant_id: 租户ID
            setting_id: 设置ID，如果为None则获取默认设置

        Returns:
            Optional[Dict]: SMTP配置信息
        """
        try:
            smtp_settings = await self.get_smtp_settings(tenant_id, setting_id)
            if not smtp_settings:
                logger.warning(
                    f"未找到SMTP设置: tenant_id={tenant_id}, setting_id={setting_id}"
                )
                return None

            logger.info(f"开始解密SMTP配置: {smtp_settings['setting_name']}")

            # 获取加密的密码字段
            encrypted_password = smtp_settings["smtp_password_encrypted"]
            if not encrypted_password:
                logger.error("SMTP密码字段为空")
                return None

            logger.info(f"加密密码数据类型: {type(encrypted_password)}")

            # 解密密码 - 处理不同格式的数据库字段
            try:
                if isinstance(encrypted_password, str):
                    # 处理字符串格式（可能是hex格式）
                    if encrypted_password.startswith("\\x"):
                        # 处理 \x 开头的hex字符串
                        hex_str = encrypted_password[2:]
                        logger.info(f"检测到\\x格式，hex长度: {len(hex_str)}")
                        try:
                            password_bytes = bytes.fromhex(hex_str)
                            decrypted_password = smtp_password_manager.decrypt(
                                password_bytes
                            )
                        except ValueError as ve:
                            logger.error(f"hex转换失败: {ve}")
                            return None
                    else:
                        # 普通字符串格式
                        logger.info("尝试直接解密字符串格式")
                        decrypted_password = smtp_password_manager.decrypt(
                            encrypted_password
                        )
                elif isinstance(encrypted_password, bytes):
                    # bytes格式
                    logger.info("处理bytes格式的加密密码")
                    decrypted_password = smtp_password_manager.decrypt(
                        encrypted_password
                    )
                else:
                    # 其他格式，转换为字符串
                    logger.info(f"未知格式，转换为字符串: {type(encrypted_password)}")
                    decrypted_password = smtp_password_manager.decrypt(
                        str(encrypted_password)
                    )

                logger.info("SMTP密码解密成功")

            except Exception as decrypt_error:
                logger.error(f"解密失败: {str(decrypt_error)}")
                return None

            return {
                "id": str(smtp_settings["id"]),
                "tenant_id": str(smtp_settings["tenant_id"]),
                "setting_name": smtp_settings["setting_name"],
                "smtp_host": smtp_settings["smtp_host"],
                "smtp_port": smtp_settings["smtp_port"],
                "smtp_username": smtp_settings["smtp_username"],
                "smtp_password": decrypted_password,  # 明文密码
                "security_protocol": smtp_settings["security_protocol"],
                "from_email": smtp_settings["from_email"],
                "from_name": smtp_settings["from_name"],
                "reply_to_email": smtp_settings["reply_to_email"],
                "daily_send_limit": smtp_settings["daily_send_limit"],
                "hourly_send_limit": smtp_settings["hourly_send_limit"],
                "is_default": smtp_settings["is_default"],
                "is_active": smtp_settings["is_active"],
                "connection_status": smtp_settings["connection_status"],
                "last_test_at": (
                    smtp_settings["last_test_at"].isoformat()
                    if smtp_settings["last_test_at"]
                    else None
                ),
                "created_at": (
                    smtp_settings["created_at"].isoformat()
                    if smtp_settings["created_at"]
                    else None
                ),
            }

        except Exception as e:
            logger.error(f"获取SMTP配置信息失败: {str(e)}")
            import traceback

            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return None

    async def send_email_individual(
        self,
        email_request: EmailSendRequest,
        created_by: Optional[UUID] = None,
        delay_between_sends: float = 0.5,
    ) -> dict:
        """
        单独发送邮件（每个收件人收到独立的邮件）

        Args:
            email_request: 邮件发送请求
            created_by: 创建者ID
            delay_between_sends: 发送间隔（秒）

        Returns:
            Dict: 发送结果汇总
        """
        try:
            to_emails = email_request.to_emails
            total_recipients = len(to_emails)

            logger.info(f"开始单独发送邮件给 {total_recipients} 个收件人")

            # 获取SMTP设置
            smtp_settings = await self.get_smtp_settings(
                email_request.tenant_id, email_request.smtp_setting_id
            )
            if not smtp_settings:
                raise ValueError("未找到可用的SMTP设置")

            # 为整个批次创建一个主队列ID用于跟踪
            batch_queue_id = uuid4()

            # 存储所有单独发送的结果
            individual_results = []
            successful_sends = []
            failed_sends = []

            # 创建SMTP服务实例
            class SMTPSettingsObj:
                def __init__(self, data):
                    for key, value in data.items():
                        setattr(self, key, value)

            smtp_settings_obj = SMTPSettingsObj(smtp_settings)
            smtp_service = SMTPService(smtp_settings_obj)

            # 循环单独发送每封邮件
            for index, recipient_email in enumerate(to_emails):
                try:
                    logger.info(
                        f"发送第 {index + 1}/{total_recipients} 封邮件到: {recipient_email}"
                    )

                    # 创建单独的队列记录
                    queue_item = await self._create_individual_queue_item(
                        email_request,
                        recipient_email,
                        batch_queue_id,
                        created_by,
                        index + 1,
                    )

                    # 发送单独邮件
                    result = await smtp_service.send_email(
                        to_emails=[recipient_email],  # 只发给一个收件人
                        subject=email_request.subject,
                        body_text=email_request.body_text,
                        body_html=email_request.body_html,
                        attachments=None,  # 基础版本不包含附件
                        attachment_paths=None,
                    )

                    # 更新队列状态
                    await self._update_individual_queue_status(
                        queue_item["id"], result, email_request.tenant_id
                    )

                    individual_results.append(
                        {
                            "recipient": recipient_email,
                            "queue_id": str(queue_item["id"]),  # 转换为字符串
                            "status": result["status"],
                            "message": result.get("message", ""),
                            "index": index + 1,
                        }
                    )

                    if result["status"] == "success":
                        successful_sends.append(recipient_email)
                        logger.info(
                            f"✅ 第 {index + 1} 封邮件发送成功: {recipient_email}"
                        )
                    else:
                        failed_sends.append(
                            {
                                "email": recipient_email,
                                "error": result.get("error", "Unknown error"),
                            }
                        )
                        logger.error(
                            f"❌ 第 {index + 1} 封邮件发送失败: {recipient_email} - {result.get('error', '')}"
                        )

                    # 发送间隔
                    if index < total_recipients - 1:
                        await asyncio.sleep(delay_between_sends)

                except Exception as e:
                    logger.error(f"发送给 {recipient_email} 的邮件异常: {str(e)}")
                    failed_sends.append({"email": recipient_email, "error": str(e)})
                    individual_results.append(
                        {
                            "recipient": recipient_email,
                            "queue_id": None,
                            "status": "error",
                            "message": str(e),
                            "index": index + 1,
                        }
                    )

            # 创建批次汇总记录
            await self._create_batch_summary_record(
                batch_queue_id, email_request, individual_results, created_by
            )

            # 生成汇总结果
            success_count = len(successful_sends)
            failed_count = len(failed_sends)
            success_rate = (
                (success_count / total_recipients * 100) if total_recipients > 0 else 0
            )

            overall_status = (
                "success"
                if failed_count == 0
                else "partial" if success_count > 0 else "failed"
            )

            return {
                "queue_id": str(batch_queue_id),  # 转换为字符串
                "status": overall_status,
                "message": f"单独发送完成: {success_count} 成功, {failed_count} 失败",
                "to_emails": to_emails,
                "scheduled_at": email_request.scheduled_at,
                "attachment_count": 0,
                "individual_results": individual_results,
                "summary": {
                    "total_recipients": total_recipients,
                    "successful_sends": success_count,
                    "failed_sends": failed_count,
                    "success_rate": round(success_rate, 2),
                    "successful_emails": successful_sends,
                    "failed_emails": failed_sends,
                },
            }

        except Exception as e:
            logger.error(f"单独发送邮件失败: {str(e)}")
            raise Exception(f"单独发送邮件失败: {str(e)}")

    async def send_email_individual_with_attachments(
        self,
        email_request: EmailWithAttachmentsRequest,
        created_by: Optional[UUID] = None,
        delay_between_sends: float = 0.5,
    ) -> dict:
        """
        单独发送带附件的邮件（每个收件人收到独立的邮件）

        Args:
            email_request: 带附件的邮件发送请求
            created_by: 创建者ID
            delay_between_sends: 发送间隔（秒）

        Returns:
            Dict: 发送结果汇总
        """
        try:
            to_emails = email_request.to_emails
            total_recipients = len(to_emails)

            logger.info(f"开始单独发送带附件邮件给 {total_recipients} 个收件人")

            # 获取附件信息和文件路径
            attachments_info = []
            attachment_paths = {}

            if email_request.attachment_ids:
                attachment_manager = AttachmentManager()
                attachment_filenames = email_request.attachment_filenames or []
                
                for i, attachment_id in enumerate(email_request.attachment_ids):
                    try:
                        # 获取附件信息
                        attachment_info = attachment_manager.get_attachment_info_by_id(
                            email_request.tenant_id, attachment_id
                        )
                        if attachment_info:
                            # 如果提供了原始文件名，则使用传递的文件名
                            if i < len(attachment_filenames) and attachment_filenames[i]:
                                original_filename = attachment_filenames[i]
                                # 创建新的AttachmentInfo使用原始文件名
                                attachment_info = AttachmentInfo(
                                    filename=original_filename,
                                    content_type=attachment_info.content_type,
                                    file_size=attachment_info.file_size,
                                    file_path=attachment_info.file_path,
                                )
                            
                            attachments_info.append(attachment_info)
                            # 构建文件路径映射
                            attachment_paths[attachment_info.filename] = attachment_info.file_path
                            logger.info(f"已加载附件: {attachment_info.filename}")
                        else:
                            logger.warning(f"附件不存在: {attachment_id}")
                    except Exception as e:
                        logger.error(f"获取附件信息失败: {attachment_id} - {str(e)}")

            # 获取SMTP设置
            smtp_settings = await self.get_smtp_settings(
                email_request.tenant_id, email_request.smtp_setting_id
            )
            if not smtp_settings:
                raise ValueError("未找到可用的SMTP设置")

            # 为整个批次创建一个主队列ID用于跟踪
            batch_queue_id = uuid4()

            # 存储所有单独发送的结果
            individual_results = []
            successful_sends = []
            failed_sends = []

            # 创建SMTP服务实例
            class SMTPSettingsObj:
                def __init__(self, data):
                    for key, value in data.items():
                        setattr(self, key, value)

            smtp_settings_obj = SMTPSettingsObj(smtp_settings)
            smtp_service = SMTPService(smtp_settings_obj)

            # 循环单独发送每封邮件
            for index, recipient_email in enumerate(to_emails):
                try:
                    logger.info(
                        f"发送第 {index + 1}/{total_recipients} 封带附件邮件到: {recipient_email}"
                    )

                    # 创建单独的队列记录
                    queue_item = await self._create_individual_queue_item(
                        email_request,
                        recipient_email,
                        batch_queue_id,
                        created_by,
                        index + 1,
                    )

                    # 发送单独邮件（带附件）
                    result = await smtp_service.send_email(
                        to_emails=[recipient_email],  # 只发给一个收件人
                        subject=email_request.subject,
                        body_text=email_request.body_text,
                        body_html=email_request.body_html,
                        attachments=attachments_info,
                        attachment_paths=attachment_paths,
                    )

                    # 更新队列状态
                    await self._update_individual_queue_status(
                        queue_item["id"], result, email_request.tenant_id
                    )

                    individual_results.append(
                        {
                            "recipient": recipient_email,
                            "queue_id": str(queue_item["id"]),  # 转换为字符串
                            "status": result["status"],
                            "message": result.get("message", ""),
                            "attachment_count": len(attachments_info),
                            "index": index + 1,
                        }
                    )

                    if result["status"] == "success":
                        successful_sends.append(recipient_email)
                        logger.info(
                            f"✅ 第 {index + 1} 封带附件邮件发送成功: {recipient_email}"
                        )
                    else:
                        failed_sends.append(
                            {
                                "email": recipient_email,
                                "error": result.get("error", "Unknown error"),
                            }
                        )
                        logger.error(
                            f"❌ 第 {index + 1} 封带附件邮件发送失败: {recipient_email} - {result.get('error', '')}"
                        )

                    # 发送间隔
                    if index < total_recipients - 1:
                        await asyncio.sleep(delay_between_sends)

                except Exception as e:
                    logger.error(f"发送带附件邮件给 {recipient_email} 异常: {str(e)}")
                    failed_sends.append({"email": recipient_email, "error": str(e)})
                    individual_results.append(
                        {
                            "recipient": recipient_email,
                            "queue_id": None,
                            "status": "error",
                            "message": str(e),
                            "attachment_count": len(attachments_info),
                            "index": index + 1,
                        }
                    )

            # 创建批次汇总记录
            await self._create_batch_summary_record(
                batch_queue_id, email_request, individual_results, created_by
            )

            # 生成汇总结果
            success_count = len(successful_sends)
            failed_count = len(failed_sends)
            success_rate = (
                (success_count / total_recipients * 100) if total_recipients > 0 else 0
            )

            # 所有邮件发送完成后清理附件文件（只要有成功发送的就清理）
            if attachments_info and attachment_paths and success_count > 0:
                await self._cleanup_sent_attachments(
                    email_request.tenant_id, 
                    attachments_info, 
                    attachment_paths
                )

            overall_status = (
                "success"
                if failed_count == 0
                else "partial" if success_count > 0 else "failed"
            )

            return {
                "queue_id": str(batch_queue_id),  # 转换为字符串
                "status": overall_status,
                "message": f"单独发送带附件邮件完成: {success_count} 成功, {failed_count} 失败",
                "to_emails": to_emails,
                "scheduled_at": email_request.scheduled_at,
                "attachment_count": len(attachments_info),
                "individual_results": individual_results,
                "summary": {
                    "total_recipients": total_recipients,
                    "successful_sends": success_count,
                    "failed_sends": failed_count,
                    "success_rate": round(success_rate, 2),
                    "successful_emails": successful_sends,
                    "failed_emails": failed_sends,
                },
            }

        except Exception as e:
            logger.error(f"单独发送带附件邮件失败: {str(e)}")
            raise Exception(f"单独发送邮件失败: {str(e)}")

    async def _create_individual_queue_item(
        self,
        email_request: Union[EmailSendRequest, EmailWithAttachmentsRequest],
        recipient_email: str,
        batch_queue_id: UUID,
        created_by: Optional[UUID],
        sequence_number: int,
    ) -> Dict[str, Any]:
        """为单独发送创建队列项"""

        # 准备附件信息
        attachments_data = {}
        if hasattr(email_request, "attachment_ids") and email_request.attachment_ids:
            attachments_data = {
                "attachment_ids": [
                    str(aid) for aid in email_request.attachment_ids
                ],  # 转换为字符串
                "attachment_count": len(email_request.attachment_ids),
            }

        # 创建队列项
        async with get_db_connection() as conn:
            queue_id = await conn.fetchval(
                """
                INSERT INTO email_sending_queue (
                    tenant_id, to_emails, subject, body_text, body_html,
                    smtp_setting_id, priority, scheduled_at, 
                    related_project_id, related_engineer_id,
                    email_metadata, attachments, created_by
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                RETURNING id
                """,
                email_request.tenant_id,
                [recipient_email],  # 只有一个收件人
                email_request.subject,
                email_request.body_text,
                email_request.body_html,
                email_request.smtp_setting_id,
                email_request.priority,
                email_request.scheduled_at or datetime.utcnow(),
                email_request.related_project_id,
                email_request.related_engineer_id,
                json.dumps(
                    {
                        **(email_request.metadata or {}),
                        "batch_queue_id": str(batch_queue_id),
                        "sequence_number": sequence_number,
                        "send_type": "individual",
                        **attachments_data,
                    }
                ),
                json.dumps(attachments_data),
                created_by,
            )

            # 获取创建的记录
            queue_item = await conn.fetchrow(
                "SELECT * FROM email_sending_queue WHERE id = $1", queue_id
            )

        return dict(queue_item)

    async def _update_individual_queue_status(
        self, queue_id: UUID, send_result: Dict[str, Any], tenant_id: UUID
    ) -> None:
        """更新单独发送的队列状态"""

        async with get_db_connection() as conn:
            if send_result["status"] == "success":
                await conn.execute(
                    """
                    UPDATE email_sending_queue 
                    SET status = 'sent', sent_at = $1, send_duration_ms = $2, last_attempt_at = $3
                    WHERE id = $4
                    """,
                    datetime.utcnow(),
                    int(send_result.get("send_duration_seconds", 0) * 1000),
                    datetime.utcnow(),
                    queue_id,
                )
            else:
                await conn.execute(
                    """
                    UPDATE email_sending_queue 
                    SET status = 'failed', error_message = $1, last_attempt_at = $2
                    WHERE id = $3
                    """,
                    send_result.get("error", ""),
                    datetime.utcnow(),
                    queue_id,
                )

            # 创建详细日志记录
            await conn.execute(
                """
                INSERT INTO email_sending_logs (
                    queue_id, tenant_id, message_id, smtp_response, delivery_status,
                    send_start_time, send_end_time, response_time_ms
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                queue_id,
                tenant_id,
                send_result.get("message_id", ""),
                send_result.get("smtp_response", ""),
                send_result["status"],
                datetime.utcnow(),
                datetime.utcnow(),
                int(send_result.get("send_duration_seconds", 0) * 1000),
            )

    async def _create_batch_summary_record(
        self,
        batch_queue_id: UUID,
        email_request: Union[EmailSendRequest, EmailWithAttachmentsRequest],
        individual_results: List[Dict[str, Any]],
        created_by: Optional[UUID],
    ) -> None:
        """创建批次汇总记录"""

        # 统计信息
        total_count = len(individual_results)
        success_count = sum(1 for r in individual_results if r["status"] == "success")
        failed_count = total_count - success_count

        # 汇总状态
        if failed_count == 0:
            batch_status = "sent"
        elif success_count == 0:
            batch_status = "failed"
        else:
            batch_status = "partial"

        # 确保 metadata 中的所有 UUID 都转换为字符串
        clean_metadata = {
            "send_type": "individual_batch",
            "total_recipients": total_count,
            "successful_sends": success_count,
            "failed_sends": failed_count,
            "individual_results": individual_results,  # 这里的 queue_id 已经是字符串了
        }

        # 合并原始metadata，确保UUID转换
        if email_request.metadata:
            for k, v in email_request.metadata.items():
                if isinstance(v, UUID):
                    clean_metadata[k] = str(v)
                else:
                    clean_metadata[k] = v

        # 创建汇总记录
        async with get_db_connection() as conn:
            await conn.execute(
                """
                INSERT INTO email_sending_queue (
                    id, tenant_id, to_emails, subject, body_text, body_html,
                    smtp_setting_id, priority, scheduled_at, 
                    status, sent_at, email_metadata, created_by
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                batch_queue_id,
                email_request.tenant_id,
                email_request.to_emails,  # 原始收件人列表
                f"[批量单独发送] {email_request.subject}",
                email_request.body_text,
                email_request.body_html,
                email_request.smtp_setting_id,
                email_request.priority,
                email_request.scheduled_at or datetime.utcnow(),
                batch_status,
                datetime.utcnow() if success_count > 0 else None,
                json.dumps(clean_metadata),  # 使用清理后的metadata
                created_by,
            )

    async def _cleanup_sent_attachments(
        self, 
        tenant_id: str, 
        attachments_info: List[AttachmentInfo], 
        attachment_paths: Dict[str, str]
    ) -> None:
        """
        邮件发送成功后清理附件文件
        
        Args:
            tenant_id: 租户ID
            attachments_info: 附件信息列表
            attachment_paths: 附件路径映射
        """
        cleanup_count = 0
        failed_count = 0
        
        try:
            import os
            
            for attachment_info in attachments_info:
                try:
                    file_path = attachment_paths.get(attachment_info.filename)
                    if not file_path:
                        file_path = attachment_info.file_path
                    
                    if file_path and os.path.exists(file_path):
                        # 删除文件
                        os.remove(file_path)
                        cleanup_count += 1
                        logger.info(f"✅ 已清理附件文件: {attachment_info.filename}")
                    else:
                        logger.warning(f"⚠️  附件文件不存在，跳过清理: {attachment_info.filename}")
                        
                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ 清理附件文件失败: {attachment_info.filename} - {str(e)}")
            
            if cleanup_count > 0:
                logger.info(f"🧹 附件清理完成: 成功删除 {cleanup_count} 个文件，失败 {failed_count} 个")
            
        except Exception as e:
            logger.error(f"附件清理过程出错: {str(e)}")
