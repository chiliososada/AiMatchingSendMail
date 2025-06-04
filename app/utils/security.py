# app/utils/security.py
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from passlib.context import CryptContext
from passlib.hash import bcrypt
import base64
import os
import secrets
import hashlib
import hmac
import time
from typing import Optional, Dict, Any, Union
import logging
import re
from pathlib import Path

from ..config import settings

logger = logging.getLogger(__name__)

# 密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 文件类型验证
MIME_TYPE_MAPPING = {
    # 文档类型
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    # 图片类型
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    ".tiff": "image/tiff",
    # 压缩文件
    ".zip": "application/zip",
    ".rar": "application/x-rar-compressed",
    ".7z": "application/x-7z-compressed",
    ".tar": "application/x-tar",
    ".gz": "application/gzip",
    # 文本文件
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".json": "application/json",
    ".xml": "application/xml",
    ".log": "text/plain",
    ".rtf": "application/rtf",
}


def _derive_key(key: str) -> bytes:
    """
    派生Fernet兼容的密钥 - 与aimachingmail项目完全一致
    使用简单的SHA256哈希，而不是PBKDF2
    """
    return base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())


def get_encryption_key() -> bytes:
    """获取或生成加密密钥 - 与aimachingmail项目完全一致"""
    if settings.ENCRYPTION_KEY:
        try:
            # 如果是base64编码的密钥（44字符且以=结尾）
            if len(settings.ENCRYPTION_KEY) == 44 and settings.ENCRYPTION_KEY.endswith(
                "="
            ):
                return base64.urlsafe_b64decode(settings.ENCRYPTION_KEY.encode())
            else:
                # 如果是普通字符串，使用与aimachingmail一致的简单SHA256派生
                return _derive_key(settings.ENCRYPTION_KEY)
        except Exception as e:
            logger.error(f"解析加密密钥失败: {str(e)}")
            raise Exception("加密密钥格式错误")

    # 生成新密钥
    key = Fernet.generate_key()
    logger.warning(f"生成新的加密密钥: {key.decode()}")
    logger.warning("请将此密钥保存到环境变量 ENCRYPTION_KEY 中")
    return key


def encrypt_password(password: str) -> str:
    """
    加密SMTP密码 - 与aimachingmail项目完全一致

    Args:
        password: 明文密码

    Returns:
        str: base64编码的加密密码
    """
    try:
        f = Fernet(get_encryption_key())
        encrypted = f.encrypt(password.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    except Exception as e:
        logger.error(f"密码加密失败: {str(e)}")
        raise Exception("密码加密失败")


def decrypt_password(encrypted_password: str) -> str:
    """
    解密SMTP密码 - 与aimachingmail项目完全一致

    Args:
        encrypted_password: base64编码的加密密码或原始bytes

    Returns:
        str: 明文密码
    """
    try:
        f = Fernet(get_encryption_key())

        # 处理不同格式的输入
        if isinstance(encrypted_password, str):
            # 如果是字符串，尝试base64解码
            try:
                encrypted_bytes = base64.urlsafe_b64decode(encrypted_password.encode())
            except:
                # 如果解码失败，可能是hex格式或其他格式
                if encrypted_password.startswith("\\x"):
                    hex_str = encrypted_password[2:]
                else:
                    hex_str = encrypted_password
                try:
                    encrypted_bytes = bytes.fromhex(hex_str)
                except:
                    # 直接当作bytes处理
                    encrypted_bytes = encrypted_password.encode()
        else:
            encrypted_bytes = encrypted_password

        decrypted = f.decrypt(encrypted_bytes)
        return decrypted.decode()
    except InvalidToken:
        logger.error("密码解密失败: Invalid token or incorrect key.")
        raise Exception("密码解密失败: Invalid token or incorrect key.")
    except Exception as e:
        logger.error(f"密码解密失败: {str(e)}")
        raise Exception(f"密码解密失败: {str(e)}")


def hash_password(password: str) -> str:
    """哈希密码（用于用户密码存储）"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def generate_secure_token(length: int = 32) -> str:
    """生成安全令牌"""
    return secrets.token_urlsafe(length)


def generate_api_key() -> str:
    """生成API密钥"""
    return f"eak_{secrets.token_urlsafe(32)}"  # eak = email api key


def calculate_file_hash(file_content: bytes, algorithm: str = "sha256") -> str:
    """计算文件哈希值"""
    if algorithm == "md5":
        hasher = hashlib.md5()
    elif algorithm == "sha1":
        hasher = hashlib.sha1()
    elif algorithm == "sha256":
        hasher = hashlib.sha256()
    else:
        raise ValueError(f"不支持的哈希算法: {algorithm}")

    hasher.update(file_content)
    return hasher.hexdigest()


def verify_file_integrity(
    file_content: bytes, expected_hash: str, algorithm: str = "sha256"
) -> bool:
    """验证文件完整性"""
    actual_hash = calculate_file_hash(file_content, algorithm)
    return hmac.compare_digest(actual_hash, expected_hash)


# ========== SMTP密码处理类 - 修复版 ==========
class SMTPPasswordManager:
    """SMTP密码管理器 - 与aimachingmail项目完全兼容"""

    def __init__(self, encryption_key: Optional[str] = None):
        """
        初始化密码管理器

        Args:
            encryption_key: 可选的加密密钥，如果不提供则使用系统默认
        """
        self.encryption_key = encryption_key or settings.ENCRYPTION_KEY
        self._fernet_key = self._get_fernet_key()

    def _get_fernet_key(self) -> bytes:
        """获取Fernet密钥 - 与aimachingmail项目完全一致"""
        if not self.encryption_key:
            raise ValueError("未设置加密密钥")

        try:
            # 如果是base64编码的密钥
            if len(self.encryption_key) == 44 and self.encryption_key.endswith("="):
                return base64.urlsafe_b64decode(self.encryption_key.encode())
            else:
                # 使用与aimachingmail一致的简单SHA256派生
                return _derive_key(self.encryption_key)
        except Exception as e:
            logger.error(f"获取Fernet密钥失败: {str(e)}")
            raise Exception("加密密钥配置错误")

    def encrypt(self, password: str) -> str:
        """加密密码"""
        try:
            f = Fernet(self._fernet_key)
            encrypted = f.encrypt(password.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"密码加密失败: {str(e)}")
            raise Exception("密码加密失败")

    def decrypt(self, encrypted_password: Union[str, bytes]) -> str:
        """
        解密密码 - 增强版，支持多种输入格式

        Args:
            encrypted_password: 加密的密码，支持多种格式

        Returns:
            str: 解密后的明文密码
        """
        try:
            f = Fernet(self._fernet_key)

            # 处理不同类型的输入
            if isinstance(encrypted_password, bytes):
                encrypted_bytes = encrypted_password
            elif isinstance(encrypted_password, str):
                # 处理文本字符串
                if encrypted_password.startswith("\\x"):
                    # 处理 \x 开头的hex字符串
                    hex_str = encrypted_password[2:]
                    try:
                        encrypted_bytes = bytes.fromhex(hex_str)
                    except ValueError as ve:
                        logger.error(f"Failed to convert hex string to bytes: {ve}")
                        raise Exception(f"无效的hex格式: {encrypted_password}")
                else:
                    # 尝试base64解码
                    try:
                        encrypted_bytes = base64.urlsafe_b64decode(
                            encrypted_password.encode()
                        )
                    except Exception:
                        # 如果base64解码失败，尝试当作hex处理
                        try:
                            encrypted_bytes = bytes.fromhex(encrypted_password)
                        except:
                            # 最后尝试直接当作bytes
                            encrypted_bytes = encrypted_password.encode()
            else:
                raise ValueError(f"不支持的加密密码类型: {type(encrypted_password)}")

            # 解密
            decrypted = f.decrypt(encrypted_bytes)
            return decrypted.decode()

        except InvalidToken:
            logger.error("解密失败: Invalid token or incorrect key")
            raise Exception("密码解密失败: Invalid token or incorrect key")
        except Exception as e:
            logger.error(f"密码解密失败: {str(e)}")
            raise Exception(f"密码解密失败: {str(e)}")

    def test_encryption(self, test_password: str = "test_password_123") -> bool:
        """测试加密解密功能"""
        try:
            encrypted = self.encrypt(test_password)
            decrypted = self.decrypt(encrypted)
            result = decrypted == test_password
            logger.info(f"加密测试结果: {result}")
            return result
        except Exception as e:
            logger.error(f"加密测试失败: {str(e)}")
            return False

    def get_key_info(self) -> Dict[str, Any]:
        """获取密钥信息（用于调试，不包含实际密钥）"""
        return {
            "key_length": len(self.encryption_key) if self.encryption_key else 0,
            "key_type": (
                "base64"
                if (
                    self.encryption_key
                    and len(self.encryption_key) == 44
                    and self.encryption_key.endswith("=")
                )
                else "string"
            ),
            "key_prefix": (
                self.encryption_key[:8] + "..." if self.encryption_key else "None"
            ),
            "fernet_key_length": len(self._fernet_key),
            "test_result": self.test_encryption(),
        }


# ========== 兼容性函数 ==========
def test_smtp_password_encryption():
    """测试SMTP密码加密解密功能"""
    try:
        manager = SMTPPasswordManager()
        test_passwords = [
            "simple_password",
            "复杂密码!@#$%^&*()",
            "password_with_123_numbers",
            "Gmail应用密码16位字符",
        ]

        results = []
        for password in test_passwords:
            try:
                encrypted = manager.encrypt(password)
                decrypted = manager.decrypt(encrypted)
                success = decrypted == password

                results.append(
                    {
                        "password_length": len(password),
                        "encrypted_length": len(encrypted),
                        "success": success,
                        "error": None if success else "解密结果不匹配",
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "password_length": len(password),
                        "encrypted_length": 0,
                        "success": False,
                        "error": str(e),
                    }
                )

        return {
            "overall_success": all(r["success"] for r in results),
            "test_count": len(results),
            "success_count": sum(1 for r in results if r["success"]),
            "results": results,
            "key_info": manager.get_key_info(),
        }

    except Exception as e:
        return {
            "overall_success": False,
            "error": str(e),
            "test_count": 0,
            "success_count": 0,
        }


class FileValidator:
    """文件验证器"""

    def __init__(self):
        self.max_file_size = settings.MAX_FILE_SIZE
        self.allowed_extensions = set(settings.ALLOWED_EXTENSIONS)
        self.forbidden_extensions = set(settings.FORBIDDEN_EXTENSIONS)

    def validate_filename(self, filename: str) -> Dict[str, Any]:
        """验证文件名"""
        result = {"valid": True, "errors": []}

        if not filename or not filename.strip():
            result["valid"] = False
            result["errors"].append("文件名不能为空")
            return result

        # 检查文件名长度
        if len(filename) > 255:
            result["valid"] = False
            result["errors"].append("文件名过长（最大255字符）")

        # 检查特殊字符
        invalid_chars = r'[<>:"/\\|?*]'
        if re.search(invalid_chars, filename):
            result["valid"] = False
            result["errors"].append("文件名包含非法字符")

        # 检查扩展名
        file_ext = Path(filename).suffix.lower()

        if file_ext in self.forbidden_extensions:
            result["valid"] = False
            result["errors"].append(f"不允许的文件类型: {file_ext}")

        if self.allowed_extensions and file_ext not in self.allowed_extensions:
            result["valid"] = False
            result["errors"].append(f"不支持的文件类型: {file_ext}")

        return result

    def validate_file_size(self, file_size: int) -> Dict[str, Any]:
        """验证文件大小"""
        result = {"valid": True, "errors": []}

        if file_size <= 0:
            result["valid"] = False
            result["errors"].append("文件大小无效")
        elif file_size > self.max_file_size:
            max_mb = self.max_file_size / (1024 * 1024)
            current_mb = file_size / (1024 * 1024)
            result["valid"] = False
            result["errors"].append(
                f"文件过大（最大{max_mb:.1f}MB，当前{current_mb:.1f}MB）"
            )

        return result

    def validate_mime_type(self, filename: str, content_type: str) -> Dict[str, Any]:
        """验证MIME类型"""
        result = {"valid": True, "errors": []}

        file_ext = Path(filename).suffix.lower()
        expected_mime = MIME_TYPE_MAPPING.get(file_ext)

        if expected_mime and content_type:
            # 允许一些常见的变体
            mime_variants = {
                "application/pdf": ["application/pdf"],
                "image/jpeg": ["image/jpeg", "image/jpg"],
                "image/png": ["image/png"],
                "text/plain": ["text/plain", "text/csv"],
                "application/zip": ["application/zip", "application/x-zip-compressed"],
            }

            allowed_types = mime_variants.get(expected_mime, [expected_mime])

            if content_type not in allowed_types:
                result["valid"] = False
                result["errors"].append(
                    f"MIME类型不匹配（期望: {expected_mime}，实际: {content_type}）"
                )

        return result

    def scan_file_content(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """扫描文件内容（基本恶意内容检测）"""
        result = {"valid": True, "errors": [], "warnings": []}

        # 检查文件头（魔数）
        file_ext = Path(filename).suffix.lower()

        # 常见文件格式的魔数
        magic_numbers = {
            ".pdf": [b"%PDF"],
            ".zip": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
            ".jpg": [b"\xff\xd8\xff"],
            ".jpeg": [b"\xff\xd8\xff"],
            ".png": [b"\x89PNG\r\n\x1a\n"],
            ".gif": [b"GIF87a", b"GIF89a"],
            ".doc": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
            ".docx": [b"PK\x03\x04"],
        }

        if file_ext in magic_numbers:
            expected_headers = magic_numbers[file_ext]
            header_found = any(
                file_content.startswith(header) for header in expected_headers
            )

            if not header_found:
                result["warnings"].append(f"文件头不匹配预期格式 {file_ext}")

        # 检查可疑内容（简单实现）
        suspicious_patterns = [
            b"<script",
            b"javascript:",
            b"vbscript:",
            b"onload=",
            b"onerror=",
            b"eval(",
            b"base64,",
        ]

        for pattern in suspicious_patterns:
            if pattern in file_content.lower():
                result["warnings"].append(
                    f"发现可疑内容模式: {pattern.decode('utf-8', errors='ignore')}"
                )

        # 检查嵌入的可执行文件
        executable_signatures = [
            b"MZ",  # PE executable
            b"\x7fELF",  # ELF executable
            b"\xca\xfe\xba\xbe",  # Mach-O binary
        ]

        for sig in executable_signatures:
            if sig in file_content:
                result["valid"] = False
                result["errors"].append("文件包含可执行代码")
                break

        return result

    def validate_file(
        self, file_content: bytes, filename: str, content_type: str = None
    ) -> Dict[str, Any]:
        """完整文件验证"""
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "file_info": {
                "filename": filename,
                "size": len(file_content),
                "hash": calculate_file_hash(file_content),
                "content_type": content_type,
            },
        }

        # 验证文件名
        filename_result = self.validate_filename(filename)
        if not filename_result["valid"]:
            result["valid"] = False
            result["errors"].extend(filename_result["errors"])

        # 验证文件大小
        size_result = self.validate_file_size(len(file_content))
        if not size_result["valid"]:
            result["valid"] = False
            result["errors"].extend(size_result["errors"])

        # 验证MIME类型
        if content_type:
            mime_result = self.validate_mime_type(filename, content_type)
            if not mime_result["valid"]:
                result["warnings"].extend(
                    mime_result["errors"]
                )  # MIME类型不匹配作为警告

        # 扫描文件内容
        content_result = self.scan_file_content(file_content, filename)
        if not content_result["valid"]:
            result["valid"] = False
            result["errors"].extend(content_result["errors"])
        result["warnings"].extend(content_result["warnings"])

        return result


def sanitize_filename(filename: str) -> str:
    """清理文件名"""
    # 移除危险字符
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)

    # 移除控制字符
    filename = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", filename)

    # 限制长度
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        max_name_length = 255 - len(ext)
        filename = name[:max_name_length] + ext

    # 确保不是保留名称（Windows）
    reserved_names = [
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    ]

    name_without_ext = Path(filename).stem.upper()
    if name_without_ext in reserved_names:
        filename = f"file_{filename}"

    return filename


def generate_secure_filename(original_filename: str, prefix: str = "") -> str:
    """生成安全的文件名"""
    # 清理原始文件名
    clean_filename = sanitize_filename(original_filename)

    # 获取扩展名
    ext = Path(clean_filename).suffix

    # 生成唯一前缀
    timestamp = int(time.time())
    random_part = secrets.token_hex(8)

    # 构建新文件名
    if prefix:
        new_filename = f"{prefix}_{timestamp}_{random_part}{ext}"
    else:
        new_filename = f"{timestamp}_{random_part}{ext}"

    return new_filename


def create_signed_url(url: str, secret_key: str, expires_in: int = 3600) -> str:
    """创建签名URL"""
    timestamp = int(time.time()) + expires_in
    message = f"{url}:{timestamp}"
    signature = hmac.new(
        secret_key.encode(), message.encode(), hashlib.sha256
    ).hexdigest()

    return f"{url}?expires={timestamp}&signature={signature}"


def verify_signed_url(signed_url: str, secret_key: str) -> bool:
    """验证签名URL"""
    try:
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(signed_url)
        query_params = parse_qs(parsed.query)

        expires = int(query_params.get("expires", [0])[0])
        signature = query_params.get("signature", [""])[0]

        # 检查是否过期
        if expires < int(time.time()):
            return False

        # 重构原始URL
        base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        message = f"{base_url}:{expires}"

        # 验证签名
        expected_signature = hmac.new(
            secret_key.encode(), message.encode(), hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected_signature)

    except Exception:
        return False


# 安全头部中间件
def get_security_headers() -> Dict[str, str]:
    """获取安全头部"""
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';",
    }


# 创建全局实例
file_validator = FileValidator()
smtp_password_manager = SMTPPasswordManager()

# 导出
__all__ = [
    "encrypt_password",
    "decrypt_password",
    "hash_password",
    "verify_password",
    "generate_secure_token",
    "generate_api_key",
    "calculate_file_hash",
    "verify_file_integrity",
    "FileValidator",
    "file_validator",
    "sanitize_filename",
    "generate_secure_filename",
    "create_signed_url",
    "verify_signed_url",
    "get_security_headers",
    "SMTPPasswordManager",
    "smtp_password_manager",
    "test_smtp_password_encryption",
]
