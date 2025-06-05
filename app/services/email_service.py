# app/services/email_service.py - 纯 asyncpg 版本
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timedelta
import os
import shutil
from pathlib import Path
import mimetypes
import logging
import json

# 移除 SQLAlchemy 模型导入，直接使用 asyncpg
from ..database import (
    fetch_one,
    fetch_all,
    execute_query,
    get_db_connection,
    get_db_transaction,
)
from ..schemas.email_schemas import (
    EmailSendRequest,
    SMTPSettingsCreate,
    AttachmentInfo,
    EmailWithAttachmentsRequest,
    BulkEmailRequest,
    AttachmentUploadResponse,
)
from ..utils.security import encrypt_password, smtp_password_manager
from .smtp_service import SMTPService
from ..config import settings

logger = logging.getLogger(__name__)


class AttachmentManager:
    """纯 asyncpg 版本的附件管理器"""

    def __init__(self, base_path: str = "uploads/attachments"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.cleanup_threshold = timedelta(hours=24)

    def save_attachment(
        self,
        file_content: bytes,
        filename: str,
        tenant_id: UUID,
        content_type: Optional[str] = None,
    ) -> Tuple[AttachmentInfo, UUID]:
        """保存附件文件"""
        try:
            attachment_id = uuid4()
            tenant_dir = self.base_path / str(tenant_id)
            tenant_dir.mkdir(parents=True, exist_ok=True)

            file_extension = Path(filename).suffix
            safe_filename = f"{attachment_id}{file_extension}"
            file_path = tenant_dir / safe_filename

            with open(file_path, "wb") as f:
                f.write(file_content)

            if not content_type:
                content_type, _ = mimetypes.guess_type(filename)
                if not content_type:
                    content_type = "application/octet-stream"

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

    def get_attachment_info(
        self, tenant_id: UUID, attachment_id: UUID, filename: str
    ) -> Optional[AttachmentInfo]:
        """获取附件信息"""
        file_path = self.get_attachment_path(tenant_id, attachment_id, filename)
        if not file_path or not os.path.exists(file_path):
            return None

        try:
            stat = os.stat(file_path)
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
    """纯 asyncpg 版本的邮件服务"""

    def __init__(self):
        self.attachment_manager = AttachmentManager()

    async def create_smtp_settings(
        self, settings_data: SMTPSettingsCreate
    ) -> Dict[str, Any]:
        """创建SMTP设置 - 使用纯 asyncpg"""
        try:
            encrypted_password = smtp_password_manager.encrypt(
                settings_data.smtp_password
            )

            # 如果设置为默认，先取消其他默认设置
            if settings_data.is_default:
                await execute_query(
                    """
                    UPDATE email_smtp_settings 
                    SET is_default = FALSE 
                    WHERE tenant_id = $1 AND is_default = TRUE
                    """,
                    settings_data.tenant_id,
                )

            # 插入新的SMTP设置
            query = """
                INSERT INTO email_smtp_settings (
                    tenant_id, setting_name, smtp_host, smtp_port, smtp_username,
                    smtp_password_encrypted, security_protocol, from_email, from_name,
                    reply_to_email, daily_send_limit, hourly_send_limit, is_default
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                RETURNING id, created_at
            """

            result = await fetch_one(
                query,
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

            smtp_settings_dict = {
                "id": result["id"],
                "tenant_id": settings_data.tenant_id,
                "setting_name": settings_data.setting_name,
                "smtp_host": settings_data.smtp_host,
                "smtp_port": settings_data.smtp_port,
                "smtp_username": settings_data.smtp_username,
                "security_protocol": settings_data.security_protocol,
                "from_email": settings_data.from_email,
                "from_name": settings_data.from_name,
                "reply_to_email": settings_data.reply_to_email,
                "connection_status": "untested",
                "is_default": settings_data.is_default,
                "is_active": True,
                "created_at": result["created_at"],
            }

            logger.info(
                f"SMTP设置创建成功: {settings_data.setting_name} (ID: {result['id']})"
            )
            return smtp_settings_dict

        except Exception as e:
            logger.error(f"创建SMTP设置失败: {str(e)}")
            raise Exception(f"创建SMTP设置失败: {str(e)}")

    async def get_smtp_settings(
        self, tenant_id: UUID, setting_id: Optional[UUID] = None
    ) -> Optional[Dict[str, Any]]:
        """获取SMTP设置 - 使用纯 asyncpg"""
        try:
            if setting_id:
                query = """
                    SELECT * FROM email_smtp_settings 
                    WHERE tenant_id = $1 AND id = $2 AND is_active = TRUE
                """
                result = await fetch_one(query, tenant_id, setting_id)
            else:
                # 获取默认设置
                query = """
                    SELECT * FROM email_smtp_settings 
                    WHERE tenant_id = $1 AND is_active = TRUE AND is_default = TRUE
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                result = await fetch_one(query, tenant_id)

                if not result:
                    # 如果没有默认设置，返回第一个
                    query = """
                        SELECT * FROM email_smtp_settings 
                        WHERE tenant_id = $1 AND is_active = TRUE
                        ORDER BY created_at DESC
                        LIMIT 1
                    """
                    result = await fetch_one(query, tenant_id)

            return result
        except Exception as e:
            logger.error(f"获取SMTP设置失败: {str(e)}")
            return None

    async def get_smtp_settings_list(self, tenant_id: UUID) -> List[Dict[str, Any]]:
        """获取SMTP设置列表 - 使用纯 asyncpg"""
        try:
            query = """
                SELECT * FROM email_smtp_settings 
                WHERE tenant_id = $1 AND is_active = TRUE
                ORDER BY is_default DESC, created_at DESC
            """
            results = await fetch_all(query, tenant_id)
            return results
        except Exception as e:
            logger.error(f"获取SMTP设置列表失败: {str(e)}")
            return []

    # 其他方法继续使用相同的模式...
    # (这里省略其他方法的实现，但都遵循相同的 asyncpg 模式)

    async def get_smtp_config_info(
        self, tenant_id: UUID, setting_id: Optional[UUID] = None
    ) -> Optional[Dict[str, Any]]:
        """获取SMTP配置信息（包含解密后的密码）- 纯 asyncpg 版本"""
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

            # 解密密码
            try:
                decrypted_password = smtp_password_manager.decrypt(encrypted_password)
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
