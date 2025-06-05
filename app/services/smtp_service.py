# app/services/smtp_service.py - 移除SQLAlchemy引用
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
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
import logging
import asyncio
from datetime import datetime

from ..utils.security import decrypt_password, smtp_password_manager
from ..schemas.email_schemas import AttachmentInfo

logger = logging.getLogger(__name__)


class SMTPService:
    """增强版SMTP服务 - 支持完整的密码解密和连接管理"""

    def __init__(self, smtp_settings: Any):
        """
        初始化SMTP服务

        Args:
            smtp_settings: SMTP配置设置对象或字典
        """
        self.settings = smtp_settings
        self._smtp_password = None
        self._connection_verified = False

        # 解密SMTP密码
        try:
            self._smtp_password = self._decrypt_smtp_password()
            logger.info(f"SMTP密码解密成功: {self.settings.smtp_username}")
        except Exception as e:
            logger.error(f"SMTP密码解密失败: {str(e)}")
            raise Exception(f"SMTP密码解密失败: {str(e)}")

    def _decrypt_smtp_password(self) -> str:
        """
        解密SMTP密码 - 修复版，与aimachingmail项目兼容

        Returns:
            str: 解密后的明文密码
        """
        try:
            # 修复：使用属性访问而不是字典访问
            encrypted_password = self.settings.smtp_password_encrypted

            if not encrypted_password:
                raise Exception("SMTP密码为空")

            logger.info(f"开始解密SMTP密码，数据类型: {type(encrypted_password)}")

            # 处理不同类型的加密密码数据
            if isinstance(encrypted_password, str):
                # 字符串类型，可能是hex格式或base64格式
                logger.info(
                    f"处理字符串格式的加密密码，长度: {len(encrypted_password)}"
                )

                # 处理hex格式（如 \x开头的字符串）
                if encrypted_password.startswith("\\x"):
                    hex_str = encrypted_password[2:]
                    logger.info(f"检测到\\x格式，转换hex: {hex_str[:20]}...")
                    try:
                        password_bytes = bytes.fromhex(hex_str)
                        return smtp_password_manager.decrypt(password_bytes)
                    except ValueError as ve:
                        logger.error(f"hex转换失败: {ve}")
                        raise Exception(f"hex格式密码转换失败: {ve}")
                else:
                    # 普通字符串，尝试直接解密
                    logger.info("尝试直接解密字符串格式")
                    return smtp_password_manager.decrypt(encrypted_password)

            elif isinstance(encrypted_password, bytes):
                # bytes类型，直接解密
                logger.info(f"处理bytes格式的加密密码，长度: {len(encrypted_password)}")
                return smtp_password_manager.decrypt(encrypted_password)
            else:
                # 其他类型，尝试转换
                logger.warning(f"未知的密码数据类型: {type(encrypted_password)}")
                return smtp_password_manager.decrypt(str(encrypted_password))

        except Exception as e:
            logger.error(f"解密SMTP密码失败，原始错误: {str(e)}")

            # 尝试回退到传统解密方法
            try:
                logger.info("尝试使用传统解密方法")
                return decrypt_password(str(self.settings.smtp_password_encrypted))
            except Exception as fallback_error:
                logger.error(f"传统解密方法也失败: {str(fallback_error)}")

            # 所有方法都失败
            error_msg = f"SMTP密码解密失败，请检查加密密钥配置。原始错误: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

    @property
    def smtp_password(self) -> str:
        """获取解密后的SMTP密码"""
        return self._smtp_password

    def _create_attachment(
        self, attachment_info: AttachmentInfo, file_path: str
    ) -> MIMEBase:
        """
        创建邮件附件

        Args:
            attachment_info: 附件信息
            file_path: 文件路径

        Returns:
            MIMEBase: 邮件附件对象
        """
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

            logger.debug(f"附件创建成功: {attachment_info.filename}")
            return attachment

        except Exception as e:
            logger.error(f"创建附件失败: {attachment_info.filename}, 错误: {str(e)}")
            raise Exception(f"创建附件失败: {attachment_info.filename}")

    def _validate_attachments(
        self, attachments: List[AttachmentInfo]
    ) -> Dict[str, Any]:
        """
        验证附件

        Args:
            attachments: 附件列表

        Returns:
            Dict: 验证结果
        """
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

    def _get_connection_config(self) -> Dict[str, Any]:
        """
        获取连接配置

        Returns:
            Dict: 连接配置参数
        """
        # 配置SSL/TLS
        if self.settings.security_protocol.upper() == "SSL":
            use_tls = True
            start_tls = False
        elif self.settings.security_protocol.upper() == "TLS":
            use_tls = False
            start_tls = True
        else:
            use_tls = False
            start_tls = False

        return {
            "hostname": self.settings.smtp_host,
            "port": self.settings.smtp_port,
            "use_tls": use_tls,
            "start_tls": start_tls,
            "username": self.settings.smtp_username,
            "password": self.smtp_password,
            "timeout": 60,  # 增加超时时间以支持大附件
        }

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
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
    ) -> dict:
        """
        发送邮件（支持附件和抄送）

        Args:
            to_emails: 收件人列表
            subject: 邮件主题
            body_text: 纯文本内容
            body_html: HTML内容
            attachments: 附件信息列表
            attachment_paths: 附件路径映射
            cc_emails: 抄送列表
            bcc_emails: 密送列表

        Returns:
            Dict: 发送结果
        """
        send_start_time = datetime.utcnow()

        try:
            # 验证附件
            if attachments:
                validation = self._validate_attachments(attachments)
                if not validation["valid"]:
                    return {
                        "status": "failed",
                        "message": validation["error"],
                        "error": validation["error"],
                        "error_type": "attachment_validation_error",
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
                if getattr(self.settings, "from_name", None)
                else self.settings.from_email
            )
            msg["To"] = ", ".join(to_emails)
            msg["Subject"] = subject

            # 设置抄送和密送
            if cc_emails:
                msg["Cc"] = ", ".join(cc_emails)
            if bcc_emails:
                msg["Bcc"] = ", ".join(bcc_emails)

            if getattr(self.settings, "reply_to_email", None):
                msg["Reply-To"] = self.settings.reply_to_email

            # 添加附件
            attachment_count = 0
            if attachments and attachment_paths:
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

            # 获取连接配置
            conn_config = self._get_connection_config()

            # 发送邮件
            all_recipients = to_emails + (cc_emails or []) + (bcc_emails or [])

            smtp_response = await aiosmtplib.send(
                msg, recipients=all_recipients, **conn_config
            )

            # 计算发送时间
            send_end_time = datetime.utcnow()
            send_duration = (send_end_time - send_start_time).total_seconds()

            # 获取消息ID
            message_id = msg.get("Message-ID", "")

            return {
                "status": "success",
                "message": "邮件发送成功",
                "message_id": message_id,
                "smtp_response": str(smtp_response),
                "attachment_count": attachment_count,
                "total_size": (
                    sum(att.file_size for att in attachments) if attachments else 0
                ),
                "send_duration_seconds": send_duration,
                "recipients": {
                    "to": to_emails,
                    "cc": cc_emails or [],
                    "bcc": bcc_emails or [],
                    "total": len(all_recipients),
                },
            }

        except aiosmtplib.SMTPAuthenticationError as e:
            error_msg = f"SMTP认证失败: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "failed",
                "message": error_msg,
                "error": str(e),
                "error_type": "smtp_authentication_error",
                "suggestion": "请检查用户名和密码是否正确",
            }
        except aiosmtplib.SMTPConnectError as e:
            error_msg = f"SMTP连接失败: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "failed",
                "message": error_msg,
                "error": str(e),
                "error_type": "smtp_connection_error",
                "suggestion": "请检查服务器地址和端口是否正确",
            }
        except FileNotFoundError as e:
            error_msg = f"附件文件不存在: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "failed",
                "message": error_msg,
                "error": str(e),
                "error_type": "file_not_found",
                "suggestion": "请确认附件文件存在",
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

    async def test_connection(self) -> dict:
        """
        测试SMTP连接

        Returns:
            Dict: 测试结果
        """
        try:
            conn_config = self._get_connection_config()

            # 创建SMTP连接
            smtp = aiosmtplib.SMTP(
                hostname=conn_config["hostname"],
                port=conn_config["port"],
                use_tls=conn_config["use_tls"],
                timeout=30,
            )

            # 连接到服务器
            await smtp.connect()

            # 如果需要，启动TLS
            if conn_config["start_tls"]:
                await smtp.starttls()

            # 登录
            await smtp.login(conn_config["username"], conn_config["password"])

            # 获取服务器信息
            server_info = await smtp.noop()

            # 断开连接
            await smtp.quit()

            self._connection_verified = True

            return {
                "status": "success",
                "message": "SMTP连接测试成功",
                "server_info": str(server_info),
                "connection_config": {
                    "host": conn_config["hostname"],
                    "port": conn_config["port"],
                    "security": self.settings.security_protocol,
                    "username": conn_config["username"],
                },
                "test_time": datetime.utcnow().isoformat(),
            }

        except aiosmtplib.SMTPAuthenticationError as e:
            return {
                "status": "failed",
                "message": f"SMTP认证失败: {str(e)}",
                "error": str(e),
                "error_type": "authentication_error",
                "suggestion": "请检查用户名和密码",
                "test_time": datetime.utcnow().isoformat(),
            }
        except aiosmtplib.SMTPConnectError as e:
            return {
                "status": "failed",
                "message": f"SMTP连接失败: {str(e)}",
                "error": str(e),
                "error_type": "connection_error",
                "suggestion": "请检查服务器地址和端口",
                "test_time": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            return {
                "status": "failed",
                "message": f"SMTP连接测试失败: {str(e)}",
                "error": str(e),
                "error_type": "general_error",
                "test_time": datetime.utcnow().isoformat(),
            }

    async def send_test_email(
        self, test_email: str, custom_subject: str = None
    ) -> Dict[str, Any]:
        """
        发送测试邮件

        Args:
            test_email: 测试邮箱
            custom_subject: 自定义主题

        Returns:
            Dict: 发送结果
        """
        subject = custom_subject or "邮件系统连接测试"
        body_text = f"""
这是一封来自邮件系统的测试邮件。

如果您收到此邮件，说明以下配置正常工作：
- SMTP服务器: {self.settings.smtp_host}:{self.settings.smtp_port}
- 发送账户: {self.settings.smtp_username}
- 安全协议: {self.settings.security_protocol}

测试时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

请不要回复此邮件。
"""

        body_html = f"""
<html>
<body>
    <h2>邮件系统连接测试</h2>
    <p>这是一封来自邮件系统的测试邮件。</p>
    
    <p>如果您收到此邮件，说明以下配置正常工作：</p>
    <ul>
        <li><strong>SMTP服务器:</strong> {self.settings.smtp_host}:{self.settings.smtp_port}</li>
        <li><strong>发送账户:</strong> {self.settings.smtp_username}</li>
        <li><strong>安全协议:</strong> {self.settings.security_protocol}</li>
    </ul>
    
    <p><strong>测试时间:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
    
    <hr>
    <p style="color: #666; font-size: 12px;">请不要回复此邮件。</p>
</body>
</html>
"""

        return await self.send_email(
            to_emails=[test_email],
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )
