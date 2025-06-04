# app/utils/security.py
from cryptography.fernet import Fernet
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


def get_encryption_key() -> bytes:
    """获取或生成加密密钥"""
    if settings.ENCRYPTION_KEY:
        try:
            # 如果是base64编码的密钥
            if len(settings.ENCRYPTION_KEY) == 44 and settings.ENCRYPTION_KEY.endswith(
                "="
            ):
                return base64.urlsafe_b64decode(settings.ENCRYPTION_KEY.encode())
            else:
                # 如果是普通字符串，生成密钥
                return derive_key_from_password(
                    settings.ENCRYPTION_KEY, b"email_api_salt"
                )
        except Exception as e:
            logger.error(f"解析加密密钥失败: {str(e)}")

    # 生成新密钥
    key = Fernet.generate_key()
    logger.warning(f"生成新的加密密钥: {key.decode()}")
    logger.warning("请将此密钥保存到环境变量 ENCRYPTION_KEY 中")
    return key


def derive_key_from_password(password: str, salt: bytes) -> bytes:
    """从密码派生加密密钥"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def encrypt_password(password: str) -> str:
    """加密密码"""
    try:
        f = Fernet(get_encryption_key())
        encrypted = f.encrypt(password.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    except Exception as e:
        logger.error(f"密码加密失败: {str(e)}")
        raise Exception("密码加密失败")


def decrypt_password(encrypted_password: str) -> str:
    """解密密码"""
    try:
        f = Fernet(get_encryption_key())
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_password.encode())
        decrypted = f.decrypt(encrypted_bytes)
        return decrypted.decode()
    except Exception as e:
        logger.error(f"密码解密失败: {str(e)}")
        raise Exception("密码解密失败")


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


# 创建全局文件验证器实例
file_validator = FileValidator()

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
]
