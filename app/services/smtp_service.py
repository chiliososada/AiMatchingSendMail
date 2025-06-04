# app/services/smtp_service.py
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.audio import MIMEAudio
from email.mime.application import MIMEApplication
from email import encoders
import ssl
import os
import mimetypes
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging

from ..utils.security import decrypt_password
from ..models.email_models import EmailSMTPSettings
from ..schemas.email_schemas import AttachmentInfo

logger = logging.getLogger(__name__)


class SMTPService:
    def __init__(self, smtp_settings: EmailSMTPSettings):
        self.settings = smtp_settings
        self.smtp_password = decrypt_password(smtp_settings.smtp_password_encrypted)

    def _create_attachment(
        self, attachment_info: AttachmentInfo, file_path: str
    ) -> MIMEBase:
        """创建邮件附件"""
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"附件文件不存在: {file_path}")

            # 读取文件内容
            with open(file_path, "rb") as file:
                file_data = file.read()

            # 根据MIME类型创建对应的附件对象
            main_type, sub_type = attachment_info.content_type.split("/", 1)

            if main_type == "text":
                attachment = MIMEText(file_data.decode("utf-8"), sub_type)
            elif main_type == "image":
                attachment = MIMEImage(file_data, sub_type)
            elif main_type == "audio":
                attachment = MIMEAudio(file_data, sub_type)
            elif main_type == "application":
                attachment = MIMEApplication(file_data, sub_type)
            else:
                # 默认使用MIMEBase
                attachment = MIMEBase(main_type, sub_type)
                attachment.set_payload(file_data)
                encoders.encode_base64(attachment)

            # 设置附件头信息
            attachment.add_header(
                "Content-Disposition", "attachment", filename=attachment_info.filename
            )

            # 添加文件大小信息（可选）
            attachment.add_header("Content-Length", str(attachment_info.file_size))

            return attachment

        except Exception as e:
            logger.error(f"创建附件失败: {attachment_info.filename}, 错误: {str(e)}")
            raise Exception(f"创建附件失败: {attachment_info.filename}")

    def _validate_attachments(
        self, attachments: List[AttachmentInfo]
    ) -> Dict[str, Any]:
        """验证附件"""
        if not attachments:
            return {"valid": True, "total_size": 0, "count": 0}

        total_size = sum(att.file_size for att in attachments)
        max_total_size = 25 * 1024 * 1024  # 25MB总限制

        if total_size > max_total_size:
            return {
                "valid": False,
                "error": f"附件总大小超过限制，最大25MB，当前: {total_size/1024/1024:.2f}MB",
                "total_size": total_size,
                "count": len(attachments),
            }

        if len(attachments) > 10:
            return {
                "valid": False,
                "error": f"附件数量超过限制，最大10个，当前: {len(attachments)}",
                "total_size": total_size,
                "count": len(attachments),
            }

        return {"valid": True, "total_size": total_size, "count": len(attachments)}

    async def send_email(
        self,
        to_emails: List[str],
        subject: str,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        attachments: Optional[List[AttachmentInfo]] = None,
        attachment_paths: Optional[
            Dict[str, str]
        ] = None,  # attachment_id -> file_path映射
    ) -> dict:
        """发送邮件（支持附件）"""
        try:
            # 验证附件
            if attachments:
                validation = self._validate_attachments(attachments)
                if not validation["valid"]:
                    return {
                        "status": "failed",
                        "message": validation["error"],
                        "error": validation["error"],
                    }

            # 创建邮件消息
            if attachments or (body_text and body_html):
                msg = MIMEMultipart("mixed")

                # 创建内容容器
                content_container = MIMEMultipart("alternative")

                # 添加文本内容
                if body_text:
                    text_part = MIMEText(body_text, "plain", "utf-8")
                    content_container.attach(text_part)

                if body_html:
                    html_part = MIMEText(body_html, "html", "utf-8")
                    content_container.attach(html_part)

                # 将内容容器添加到主消息
                msg.attach(content_container)

            else:
                # 简单消息（无附件）
                if body_html:
                    msg = MIMEText(body_html, "html", "utf-8")
                else:
                    msg = MIMEText(body_text or "", "plain", "utf-8")

            # 设置邮件头
            msg["From"] = (
                f"{self.settings.from_name} <{self.settings.from_email}>"
                if self.settings.from_name
                else self.settings.from_email
            )
            msg["To"] = ", ".join(to_emails)
            msg["Subject"] = subject

            if self.settings.reply_to_email:
                msg["Reply-To"] = self.settings.reply_to_email

            # 添加附件
            if attachments and attachment_paths:
                attachment_count = 0
                for attachment_info in attachments:
                    try:
                        # 获取附件文件路径
                        file_path = attachment_paths.get(str(attachment_info.filename))
                        if not file_path and hasattr(attachment_info, "file_path"):
                            file_path = attachment_info.file_path

                        if not file_path:
                            logger.warning(
                                f"找不到附件文件路径: {attachment_info.filename}"
                            )
                            continue

                        # 创建并添加附件
                        attachment_mime = self._create_attachment(
                            attachment_info, file_path
                        )
                        msg.attach(attachment_mime)
                        attachment_count += 1

                    except Exception as e:
                        logger.error(
                            f"添加附件失败: {attachment_info.filename}, 错误: {str(e)}"
                        )
                        # 继续处理其他附件，不中断发送
                        continue

                logger.info(f"成功添加 {attachment_count}/{len(attachments)} 个附件")

            # 配置SSL/TLS
            if self.settings.security_protocol.upper() == "SSL":
                use_tls = False
                start_tls = False
            elif self.settings.security_protocol.upper() == "TLS":
                use_tls = True
                start_tls = True
            else:
                use_tls = False
                start_tls = False

            # 发送邮件
            smtp_response = await aiosmtplib.send(
                msg,
                hostname=self.settings.smtp_host,
                port=self.settings.smtp_port,
                username=self.settings.smtp_username,
                password=self.smtp_password,
                use_tls=use_tls,
                start_tls=start_tls,
                timeout=60,  # 增加超时时间以支持大附件
            )

            # 获取消息ID
            message_id = msg.get("Message-ID", "")

            return {
                "status": "success",
                "message": "邮件发送成功",
                "message_id": message_id,
                "smtp_response": str(smtp_response),
                "attachment_count": len(attachments) if attachments else 0,
                "total_size": (
                    sum(att.file_size for att in attachments) if attachments else 0
                ),
            }

        except aiosmtplib.SMTPException as e:
            error_msg = f"SMTP错误: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "failed",
                "message": error_msg,
                "error": str(e),
                "error_type": "smtp_error",
            }
        except FileNotFoundError as e:
            error_msg = f"附件文件不存在: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "failed",
                "message": error_msg,
                "error": str(e),
                "error_type": "file_not_found",
            }
        except Exception as e:
            error_msg = f"邮件发送失败: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "failed",
                "message": error_msg,
                "error": str(e),
                "error_type": "general_error",
            }

    async def send_bulk_emails(
        self,
        email_list: List[Dict[str, Any]],
        common_attachments: Optional[List[AttachmentInfo]] = None,
        attachment_paths: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """批量发送邮件"""
        results = {"total": len(email_list), "success": 0, "failed": 0, "errors": []}

        for i, email_data in enumerate(email_list):
            try:
                # 合并公共附件和个人附件
                email_attachments = (
                    list(common_attachments) if common_attachments else []
                )
                if "attachments" in email_data:
                    email_attachments.extend(email_data["attachments"])

                result = await self.send_email(
                    to_emails=[email_data["to_email"]],
                    subject=email_data.get("subject", ""),
                    body_text=email_data.get("body_text"),
                    body_html=email_data.get("body_html"),
                    attachments=email_attachments if email_attachments else None,
                    attachment_paths=attachment_paths,
                )

                if result["status"] == "success":
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append(
                        {
                            "index": i,
                            "email": email_data["to_email"],
                            "error": result.get("error", "Unknown error"),
                        }
                    )

            except Exception as e:
                results["failed"] += 1
                results["errors"].append(
                    {
                        "index": i,
                        "email": email_data.get("to_email", "Unknown"),
                        "error": str(e),
                    }
                )

        return results

    async def test_connection(self) -> dict:
        """测试SMTP连接"""
        try:
            if self.settings.security_protocol.upper() == "SSL":
                use_tls = True
                start_tls = False
            elif self.settings.security_protocol.upper() == "TLS":
                use_tls = False
                start_tls = True
            else:
                use_tls = False
                start_tls = False

            # 创建SMTP连接
            smtp = aiosmtplib.SMTP(
                hostname=self.settings.smtp_host,
                port=self.settings.smtp_port,
                use_tls=use_tls,
                timeout=30,
            )

            # 连接到服务器
            await smtp.connect()

            # 如果需要，启动TLS
            if start_tls:
                await smtp.starttls()

            # 登录
            await smtp.login(self.settings.smtp_username, self.smtp_password)

            # 获取服务器信息
            server_info = await smtp.noop()

            # 断开连接
            await smtp.quit()

            return {
                "status": "success",
                "message": "SMTP连接测试成功",
                "server_info": str(server_info),
            }

        except aiosmtplib.SMTPAuthenticationError as e:
            return {
                "status": "failed",
                "message": f"SMTP认证失败: {str(e)}",
                "error": str(e),
                "error_type": "authentication_error",
            }
        except aiosmtplib.SMTPConnectError as e:
            return {
                "status": "failed",
                "message": f"SMTP连接失败: {str(e)}",
                "error": str(e),
                "error_type": "connection_error",
            }
        except Exception as e:
            return {
                "status": "failed",
                "message": f"SMTP连接测试失败: {str(e)}",
                "error": str(e),
                "error_type": "general_error",
            }

    def get_supported_file_types(self) -> Dict[str, List[str]]:
        """获取支持的文件类型"""
        return {
            "documents": [
                ".pdf",
                ".doc",
                ".docx",
                ".xls",
                ".xlsx",
                ".ppt",
                ".pptx",
                ".txt",
                ".rtf",
            ],
            "images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".svg"],
            "archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
            "others": [".csv", ".json", ".xml", ".log"],
        }

    def validate_file_type(self, filename: str) -> bool:
        """验证文件类型是否支持"""
        supported_types = self.get_supported_file_types()
        file_ext = Path(filename).suffix.lower()

        for category, extensions in supported_types.items():
            if file_ext in extensions:
                return True

        return False
