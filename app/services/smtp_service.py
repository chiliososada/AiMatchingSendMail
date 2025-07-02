# app/services/smtp_service.py - 修复From头部问题的完整版本
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.audio import MIMEAudio
from email.mime.application import MIMEApplication
from email.utils import formataddr, formatdate, make_msgid
from email import encoders
import ssl
import os
import mimetypes
import re
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
import logging
import asyncio
from datetime import datetime

from ..utils.security import decrypt_password, smtp_password_manager
from ..schemas.email_schemas import AttachmentInfo

logger = logging.getLogger(__name__)


class SMTPService:
    """增强版SMTP服务 - 修复From头部问题的完整版本"""

    def __init__(self, smtp_settings: Any):
        """
        初始化SMTP服务

        Args:
            smtp_settings: SMTP配置设置对象或字典
        """
        self.settings = smtp_settings
        self._smtp_password = None
        self._connection_verified = False

        # 验证SMTP设置
        self._validate_smtp_settings()

        # 解密SMTP密码
        try:
            self._smtp_password = self._decrypt_smtp_password()
            logger.info(f"SMTP密码解密成功: {self.settings.smtp_username}")
        except Exception as e:
            logger.error(f"SMTP密码解密失败: {str(e)}")
            raise Exception(f"SMTP密码解密失败: {str(e)}")

    def _validate_smtp_settings(self):
        """验证SMTP设置，特别是From相关字段"""
        errors = []

        # 检查必需字段
        required_fields = {
            "smtp_host": "服务器地址",
            "smtp_port": "端口号",
            "smtp_username": "用户名",
            "smtp_password_encrypted": "密码",
            "from_email": "发件人邮箱",
        }

        for field, description in required_fields.items():
            value = getattr(self.settings, field, None)
            if not value:
                errors.append(f"缺少必需字段: {description} ({field})")

        # 验证from_email格式
        from_email = getattr(self.settings, "from_email", "")
        if from_email:
            if not self._is_valid_email(from_email):
                errors.append(f"发件人邮箱格式无效: {from_email}")

        # 检查smtp_username与from_email的关系
        smtp_username = getattr(self.settings, "smtp_username", "")
        if smtp_username and from_email and smtp_username != from_email:
            logger.warning(
                f"SMTP用户名 ({smtp_username}) 与发件人邮箱 ({from_email}) 不一致，可能导致认证问题"
            )

        # 验证端口号
        smtp_port = getattr(self.settings, "smtp_port", 0)
        if not isinstance(smtp_port, int) or not (1 <= smtp_port <= 65535):
            errors.append(f"无效的端口号: {smtp_port}")

        if errors:
            error_msg = "; ".join(errors)
            logger.error(f"SMTP设置验证失败: {error_msg}")
            raise ValueError(f"SMTP配置错误: {error_msg}")

        logger.info("SMTP设置验证通过")

    def _is_valid_email(self, email: str) -> bool:
        """验证邮箱格式是否符合RFC 5322"""
        if not email or not isinstance(email, str):
            return False

        # RFC 5322 兼容的邮箱正则表达式
        pattern = r"^[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~-]+)*@(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?$"

        try:
            if not re.match(pattern, email):
                return False

            # 额外检查
            local, domain = email.split("@", 1)

            # 本地部分不能超过64字符
            if len(local) > 64:
                return False

            # 域名部分不能超过253字符
            if len(domain) > 253:
                return False

            # 不能以点号开头或结尾
            if local.startswith(".") or local.endswith("."):
                return False

            # 不能包含连续的点号
            if ".." in email:
                return False

            return True
        except:
            return False

    def _clean_display_name(self, name: str) -> str:
        """清理显示名称中的特殊字符"""
        if not name:
            return ""

        # 移除可能导致问题的字符
        forbidden_chars = '<>@"\\()'
        cleaned = "".join(char for char in str(name) if char not in forbidden_chars)

        # 去除首尾空格和控制字符
        cleaned = re.sub(r"[\x00-\x1f\x7f]", "", cleaned).strip()

        # 如果清理后为空，返回默认名称
        if not cleaned:
            return "Email System"

        # 限制长度（RFC建议显示名称不要过长）
        if len(cleaned) > 50:
            cleaned = cleaned[:47] + "..."

        return cleaned

    def _create_from_header(self) -> str:
        """创建符合RFC 5322规范的From头部"""
        from_email = self.settings.from_email
        from_name = getattr(self.settings, "from_name", None)

        # 确保from_email有效
        if not from_email or not self._is_valid_email(from_email):
            raise ValueError(f"无效的发件人邮箱: {from_email}")

        # 如果有from_name，使用formataddr确保格式正确
        if from_name and str(from_name).strip():
            cleaned_name = self._clean_display_name(from_name)
            try:
                from_header = formataddr((cleaned_name, from_email))
                logger.debug(f"创建From头部: {from_header}")
                return from_header
            except Exception as e:
                logger.warning(f"formataddr失败，使用简单格式: {e}")
                return from_email
        else:
            # 只使用邮箱地址
            logger.debug(f"创建简单From头部: {from_email}")
            return from_email

    def _decrypt_smtp_password(self) -> str:
        """
        解密SMTP密码 - 修复版，与aimachingmail项目兼容

        Returns:
            str: 解密后的明文密码
        """
        try:
            encrypted_password = self.settings.smtp_password_encrypted

            if not encrypted_password:
                raise Exception("SMTP密码为空")

            logger.debug(f"开始解密SMTP密码，数据类型: {type(encrypted_password)}")

            # 处理不同类型的加密密码数据
            if isinstance(encrypted_password, str):
                # 字符串类型，可能是hex格式或base64格式
                logger.debug(
                    f"处理字符串格式的加密密码，长度: {len(encrypted_password)}"
                )

                # 处理hex格式（如 \x开头的字符串）
                if encrypted_password.startswith("\\x"):
                    hex_str = encrypted_password[2:]
                    logger.debug(f"检测到\\x格式，转换hex: {hex_str[:20]}...")
                    try:
                        password_bytes = bytes.fromhex(hex_str)
                        return smtp_password_manager.decrypt(password_bytes)
                    except ValueError as ve:
                        logger.error(f"hex转换失败: {ve}")
                        raise Exception(f"hex格式密码转换失败: {ve}")
                else:
                    # 普通字符串，尝试直接解密
                    logger.debug("尝试直接解密字符串格式")
                    return smtp_password_manager.decrypt(encrypted_password)

            elif isinstance(encrypted_password, bytes):
                # bytes类型，直接解密
                logger.debug(
                    f"处理bytes格式的加密密码，长度: {len(encrypted_password)}"
                )
                return smtp_password_manager.decrypt(encrypted_password)
            else:
                # 其他类型，尝试转换
                logger.warning(f"未知的密码数据类型: {type(encrypted_password)}")
                return smtp_password_manager.decrypt(str(encrypted_password))

        except Exception as e:
            logger.error(f"解密SMTP密码失败，原始错误: {str(e)}")

            # 尝试回退到传统解密方法
            try:
                logger.debug("尝试使用传统解密方法")
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

            # 设置附件头信息 - 正确处理非ASCII文件名
            filename = attachment_info.filename
            
            # 处理非ASCII文件名 - 使用多种兼容方法
            logger.info(f"处理附件文件名: {filename} (类型: {type(filename)})")
            
            # 确保filename是字符串
            if not isinstance(filename, str):
                filename = str(filename)
            
            # 检查是否为ASCII
            is_ascii = True
            try:
                filename.encode('ascii')
            except UnicodeEncodeError:
                is_ascii = False
                
            logger.info(f"文件名是否为ASCII: {is_ascii}")
            
            if is_ascii:
                # ASCII文件名，直接使用
                attachment.add_header("Content-Disposition", "attachment", filename=filename)
                logger.info(f"使用ASCII文件名: {filename}")
            else:
                # 非ASCII文件名，使用多种编码方法确保最大兼容性
                import urllib.parse
                import base64
                from email.header import Header
                
                # 方法1: 使用RFC 2047 Base64编码 (对日文字符更友好)
                try:
                    # 对于日文字符，有些邮件客户端更喜欢这种方式
                    encoded_b64 = base64.b64encode(filename.encode('utf-8')).decode('ascii')
                    disposition_b64 = f'attachment; filename="=?UTF-8?B?{encoded_b64}?="'
                    
                    attachment["Content-Disposition"] = disposition_b64
                    
                    logger.info(f"使用Base64编码: {filename}")
                    logger.info(f"Base64编码结果: {encoded_b64}")
                    logger.info(f"Content-Disposition (Base64): {disposition_b64}")
                    
                except Exception as e:
                    logger.warning(f"Base64编码失败，使用RFC 2231: {e}")
                    
                    # 方法2: RFC 2231编码 (现代标准)
                    url_encoded = urllib.parse.quote(filename.encode('utf-8'))
                    
                    # 创建ASCII fallback (保留扩展名)
                    name_part, ext_part = os.path.splitext(filename)
                    ascii_fallback = f"document{ext_part}" if ext_part else "document"
                    
                    # 构建Content-Disposition头
                    disposition_value = f'attachment; filename="{ascii_fallback}"; filename*=utf-8\'\'{url_encoded}'
                    
                    attachment["Content-Disposition"] = disposition_value
                    
                    logger.info(f"使用RFC 2231编码: {filename}")
                    logger.info(f"Content-Disposition头: {disposition_value}")
                    logger.info(f"URL编码文件名: {url_encoded}")
                    logger.info(f"ASCII回退文件名: {ascii_fallback}")
                
                # 验证当前设置的头部
                current_disposition = attachment.get("Content-Disposition", "未设置")
                logger.info(f"最终Content-Disposition: {current_disposition}")

            # 添加文件大小信息（可选）
            attachment.add_header("Content-Length", str(attachment_info.file_size))

            logger.info(f"附件创建成功: {attachment_info.filename}")
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
        security_protocol = getattr(self.settings, "security_protocol", "TLS").upper()

        if security_protocol == "SSL":
            use_tls = True
            start_tls = False
        elif security_protocol == "TLS":
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

    def _create_message_headers(
        self,
        to_emails: List[str],
        subject: str,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """创建符合RFC 5322的邮件头部"""
        headers = {}

        # 1. From头部（最重要）- 修复From头部问题的关键
        try:
            headers["From"] = self._create_from_header()
            logger.debug(f"From头部创建成功: {headers['From']}")
        except Exception as e:
            logger.error(f"创建From头部失败: {str(e)}")
            raise ValueError(f"创建From头部失败: {str(e)}")

        # 2. To头部
        if isinstance(to_emails, list):
            headers["To"] = ", ".join(to_emails)
        else:
            headers["To"] = str(to_emails)

        # 3. Subject头部
        headers["Subject"] = str(subject) if subject else "No Subject"

        # 4. 可选头部
        if cc_emails:
            if isinstance(cc_emails, list):
                headers["Cc"] = ", ".join(cc_emails)
            else:
                headers["Cc"] = str(cc_emails)

        # 注意：Bcc头部通常不应该出现在最终邮件中

        # 5. Reply-To头部
        reply_to = getattr(self.settings, "reply_to_email", None)
        if reply_to and self._is_valid_email(reply_to):
            headers["Reply-To"] = reply_to

        # 6. 其他标准头部
        headers["Date"] = formatdate(localtime=True)
        headers["Message-ID"] = self._generate_message_id()

        # 7. 邮件客户端识别
        headers["X-Mailer"] = "Email API System v2.0"

        return headers

    def _generate_message_id(self) -> str:
        """生成唯一的Message-ID"""
        try:
            from_email = self.settings.from_email
            domain = from_email.split("@")[1] if "@" in from_email else "localhost"
            return make_msgid(domain=domain)
        except Exception as e:
            logger.warning(f"生成Message-ID失败，使用默认: {e}")
            import time
            import random

            timestamp = str(int(time.time()))
            random_part = str(random.randint(10000, 99999))
            return f"<{timestamp}.{random_part}@localhost>"

    async def send_email(
        self,
        to_emails: List[str],
        subject: str,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        attachments: Optional[List[AttachmentInfo]] = None,
        attachment_paths: Optional[Dict[str, str]] = None,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
    ) -> dict:
        """
        发送邮件（支持附件和抄送）- 修复From头部问题的版本

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
            # 输入验证
            if not to_emails:
                raise ValueError("收件人列表不能为空")

            if not subject:
                subject = "No Subject"

            if not body_text and not body_html:
                raise ValueError("邮件内容不能为空")

            logger.info(f"开始发送邮件: {subject} -> {to_emails}")

            # 验证所有邮箱地址
            all_emails = to_emails + (cc_emails or []) + (bcc_emails or [])
            for email in all_emails:
                if not self._is_valid_email(email):
                    raise ValueError(f"无效的邮箱地址: {email}")

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
                if body_text and body_html:
                    content_container = MIMEMultipart("alternative")
                    content_container.attach(MIMEText(body_text, "plain", "utf-8"))
                    content_container.attach(MIMEText(body_html, "html", "utf-8"))
                    msg.attach(content_container)
                elif body_html:
                    msg.attach(MIMEText(body_html, "html", "utf-8"))
                elif body_text:
                    msg.attach(MIMEText(body_text, "plain", "utf-8"))

            else:
                # 简单消息（无附件）
                if body_html:
                    msg = MIMEText(body_html, "html", "utf-8")
                else:
                    msg = MIMEText(body_text or "", "plain", "utf-8")

            # 设置邮件头部（关键修复点）
            try:
                headers = self._create_message_headers(
                    to_emails, subject, cc_emails, bcc_emails
                )

                for header_name, header_value in headers.items():
                    msg[header_name] = header_value
                    logger.debug(f"设置头部: {header_name}: {header_value}")

                # 验证关键头部
                if not msg.get("From"):
                    raise ValueError("From头部未设置")

                if not msg.get("To"):
                    raise ValueError("To头部未设置")

                logger.info(
                    f"邮件头部设置完成 - From: {msg.get('From')}, To: {msg.get('To')}"
                )

            except Exception as e:
                logger.error(f"设置邮件头部失败: {str(e)}")
                return {
                    "status": "failed",
                    "message": f"设置邮件头部失败: {str(e)}",
                    "error": str(e),
                    "error_type": "header_creation_error",
                }

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
            logger.debug(
                f"SMTP连接配置: {conn_config['hostname']}:{conn_config['port']}"
            )

            # 发送邮件
            all_recipients = to_emails + (cc_emails or []) + (bcc_emails or [])

            logger.info(f"通过SMTP发送邮件，收件人总数: {len(all_recipients)}")
            smtp_response = await aiosmtplib.send(
                msg, recipients=all_recipients, **conn_config
            )

            # 计算发送时间
            send_end_time = datetime.utcnow()
            send_duration = (send_end_time - send_start_time).total_seconds()

            # 获取消息ID
            message_id = msg.get("Message-ID", "")

            logger.info(f"邮件发送成功: {message_id}, 耗时: {send_duration:.2f}秒")

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
                "headers": {
                    "from": msg.get("From"),
                    "to": msg.get("To"),
                    "subject": msg.get("Subject"),
                    "message_id": message_id,
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
                "suggestion": "请检查用户名和密码是否正确，Gmail需要使用应用专用密码",
            }
        except aiosmtplib.SMTPConnectError as e:
            error_msg = f"SMTP连接失败: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "failed",
                "message": error_msg,
                "error": str(e),
                "error_type": "smtp_connection_error",
                "suggestion": "请检查服务器地址和端口是否正确，确认网络连接正常",
            }
        except aiosmtplib.SMTPDataError as e:
            error_msg = f"SMTP数据错误: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "failed",
                "message": error_msg,
                "error": str(e),
                "error_type": "smtp_data_error",
                "suggestion": "邮件内容或格式有问题，请检查邮件头部和内容",
            }
        except ValueError as e:
            error_msg = f"参数验证失败: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "failed",
                "message": error_msg,
                "error": str(e),
                "error_type": "validation_error",
                "suggestion": "请检查邮件参数是否正确",
            }
        except FileNotFoundError as e:
            error_msg = f"附件文件不存在: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "failed",
                "message": error_msg,
                "error": str(e),
                "error_type": "file_not_found",
                "suggestion": "请确认附件文件存在且路径正确",
            }
        except Exception as e:
            error_msg = f"邮件发送失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "status": "failed",
                "message": error_msg,
                "error": str(e),
                "error_type": "general_error",
                "suggestion": "请查看详细日志获取更多信息",
            }

    async def test_connection(self) -> dict:
        """
        测试SMTP连接

        Returns:
            Dict: 测试结果
        """
        try:
            logger.info("开始测试SMTP连接...")
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
            logger.debug("SMTP服务器连接成功")

            # 如果需要，启动TLS
            if conn_config["start_tls"]:
                await smtp.starttls()
                logger.debug("TLS启动成功")

            # 登录
            await smtp.login(conn_config["username"], conn_config["password"])
            logger.debug("SMTP认证成功")

            # 获取服务器信息
            server_info = await smtp.noop()

            # 断开连接
            await smtp.quit()
            logger.debug("SMTP连接已关闭")

            self._connection_verified = True

            logger.info("SMTP连接测试成功")
            return {
                "status": "success",
                "message": "SMTP连接测试成功",
                "server_info": str(server_info),
                "connection_config": {
                    "host": conn_config["hostname"],
                    "port": conn_config["port"],
                    "security": getattr(self.settings, "security_protocol", "TLS"),
                    "username": conn_config["username"],
                    "from_email": self.settings.from_email,
                },
                "test_time": datetime.utcnow().isoformat(),
            }

        except aiosmtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP认证失败: {str(e)}")
            return {
                "status": "failed",
                "message": f"SMTP认证失败: {str(e)}",
                "error": str(e),
                "error_type": "authentication_error",
                "suggestion": "请检查用户名和密码，Gmail需要使用应用专用密码",
                "test_time": datetime.utcnow().isoformat(),
            }
        except aiosmtplib.SMTPConnectError as e:
            logger.error(f"SMTP连接失败: {str(e)}")
            return {
                "status": "failed",
                "message": f"SMTP连接失败: {str(e)}",
                "error": str(e),
                "error_type": "connection_error",
                "suggestion": "请检查服务器地址、端口和网络连接",
                "test_time": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"SMTP连接测试失败: {str(e)}", exc_info=True)
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
        if not self._is_valid_email(test_email):
            return {
                "status": "failed",
                "message": f"测试邮箱格式无效: {test_email}",
                "error": "invalid_email_format",
                "error_type": "validation_error",
            }

        subject = custom_subject or "邮件系统连接测试 - From头部修复版"

        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        body_text = f"""
这是一封来自邮件系统的测试邮件（From头部修复版）。

如果您收到此邮件，说明以下配置正常工作：
- SMTP服务器: {self.settings.smtp_host}:{self.settings.smtp_port}
- 发送账户: {self.settings.smtp_username}
- 安全协议: {getattr(self.settings, 'security_protocol', 'TLS')}
- 发件人邮箱: {self.settings.from_email}
- From头部格式: 符合RFC 5322规范

✅ From头部问题已修复！

测试时间: {current_time} UTC

此邮件验证了系统能够正确发送邮件，不会出现550-5.7.1错误。

请不要回复此邮件。
"""

        body_html = f"""
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 30px; border-radius: 15px; text-align: center; margin-bottom: 20px;">
        <h1 style="margin: 0; font-size: 28px;">✅ From头部修复成功！</h1>
        <p style="margin: 15px 0 0 0; opacity: 0.9; font-size: 16px;">邮件系统连接测试</p>
    </div>
    
    <div style="background: #f8f9fa; padding: 25px; border-radius: 10px; margin: 20px 0;">
        <h3 style="color: #495057; margin-top: 0; border-bottom: 2px solid #dee2e6; padding-bottom: 10px;">📊 配置信息</h3>
        <table style="width: 100%; border-collapse: collapse;">
            <tr><td style="padding: 8px 0; color: #6c757d; width: 40%;"><strong>SMTP服务器:</strong></td><td style="padding: 8px 0;">{self.settings.smtp_host}:{self.settings.smtp_port}</td></tr>
            <tr><td style="padding: 8px 0; color: #6c757d;"><strong>发送账户:</strong></td><td style="padding: 8px 0;">{self.settings.smtp_username}</td></tr>
            <tr><td style="padding: 8px 0; color: #6c757d;"><strong>安全协议:</strong></td><td style="padding: 8px 0;">{getattr(self.settings, 'security_protocol', 'TLS')}</td></tr>
            <tr><td style="padding: 8px 0; color: #6c757d;"><strong>发件人邮箱:</strong></td><td style="padding: 8px 0;">{self.settings.from_email}</td></tr>
            <tr><td style="padding: 8px 0; color: #6c757d;"><strong>From头部格式:</strong></td><td style="padding: 8px 0; color: #28a745;"><strong>符合RFC 5322规范</strong></td></tr>
        </table>
    </div>
    
    <div style="background: #d1ecf1; border-left: 4px solid #17a2b8; padding: 20px; margin: 20px 0;">
        <h4 style="color: #0c5460; margin-top: 0;">🎯 如果您收到此邮件，说明From头部问题已修复！</h4>
        <p style="color: #0c5460; margin: 10px 0 0 0;">系统不会再出现550-5.7.1错误，可以正常发送邮件。</p>
    </div>
    
    <div style="background: #d4edda; border-left: 4px solid #28a745; padding: 20px; margin: 20px 0;">
        <h4 style="color: #155724; margin-top: 0;">✅ 修复验证</h4>
        <ul style="color: #155724; line-height: 1.6; margin: 0; padding-left: 20px;">
            <li>From头部正确设置</li>
            <li>邮箱格式验证通过</li>
            <li>SMTP认证成功</li>
            <li>邮件成功投递</li>
        </ul>
    </div>
    
    <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 2px solid #dee2e6;">
        <p style="color: #6c757d; font-size: 14px; margin: 0;">
            测试时间: {current_time} UTC<br>
            <span style="color: #28a745; font-weight: bold;">🚀 邮件系统正常运行</span><br>
            请不要回复此邮件
        </p>
    </div>
</body>
</html>"""

        return await self.send_email(
            to_emails=[test_email],
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )

    def get_debug_info(self) -> Dict[str, Any]:
        """获取调试信息"""
        return {
            "smtp_settings": {
                "host": self.settings.smtp_host,
                "port": self.settings.smtp_port,
                "username": self.settings.smtp_username,
                "from_email": self.settings.from_email,
                "from_name": getattr(self.settings, "from_name", None),
                "reply_to_email": getattr(self.settings, "reply_to_email", None),
                "security_protocol": getattr(self.settings, "security_protocol", "TLS"),
            },
            "validation": {
                "from_email_valid": self._is_valid_email(self.settings.from_email),
                "connection_verified": self._connection_verified,
            },
            "capabilities": {
                "supports_attachments": True,
                "supports_html": True,
                "supports_cc_bcc": True,
                "rfc_5322_compliant": True,
            },
        }
