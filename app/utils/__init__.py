# app/utils/__init__.py
"""
工具模块

包含系统的各种工具函数和类。

工具列表：
- security: 安全相关工具（加密、解密、文件验证等）
"""

from .date_utils import convert_excel_serial_to_date, calculate_age_from_birthdate
from .text_utils import dataframe_to_text
from .validation_utils import is_valid_name

from .security import (
    # 密码加密解密
    encrypt_password,
    decrypt_password,
    hash_password,
    verify_password,
    # 令牌生成
    generate_secure_token,
    generate_api_key,
    # 文件安全
    calculate_file_hash,
    verify_file_integrity,
    FileValidator,
    file_validator,
    sanitize_filename,
    generate_secure_filename,
    # URL签名
    create_signed_url,
    verify_signed_url,
    # 安全头部
    get_security_headers,
)

# 导出所有工具
__all__ = [
    # 密码处理
    "encrypt_password",
    "decrypt_password",
    "hash_password",
    "verify_password",
    # 令牌生成
    "generate_secure_token",
    "generate_api_key",
    # 文件处理
    "calculate_file_hash",
    "verify_file_integrity",
    "FileValidator",
    "file_validator",
    "sanitize_filename",
    "generate_secure_filename",
    # URL安全
    "create_signed_url",
    "verify_signed_url",
    # 安全头部
    "get_security_headers",
    "convert_excel_serial_to_date",
    "calculate_age_from_birthdate",
    "dataframe_to_text",
    "is_valid_name",
]

# 工具分类
SECURITY_TOOLS = [
    "encrypt_password",
    "decrypt_password",
    "hash_password",
    "verify_password",
    "generate_secure_token",
    "generate_api_key",
]

FILE_TOOLS = [
    "calculate_file_hash",
    "verify_file_integrity",
    "FileValidator",
    "sanitize_filename",
    "generate_secure_filename",
]

URL_TOOLS = ["create_signed_url", "verify_signed_url"]

HTTP_TOOLS = ["get_security_headers"]

# 工具注册表
TOOL_REGISTRY = {
    "security": SECURITY_TOOLS,
    "file": FILE_TOOLS,
    "url": URL_TOOLS,
    "http": HTTP_TOOLS,
}


# 常用工具快捷方式
def quick_encrypt(text: str) -> str:
    """快速加密文本"""
    return encrypt_password(text)


def quick_decrypt(encrypted_text: str) -> str:
    """快速解密文本"""
    return decrypt_password(encrypted_text)


def quick_hash(text: str) -> str:
    """快速哈希文本"""
    return hash_password(text)


def quick_token(length: int = 32) -> str:
    """快速生成令牌"""
    return generate_secure_token(length)


def quick_validate_file(
    content: bytes, filename: str, content_type: str = None
) -> dict:
    """快速验证文件"""
    return file_validator.validate_file(content, filename, content_type)


# 快捷工具映射
QUICK_TOOLS = {
    "encrypt": quick_encrypt,
    "decrypt": quick_decrypt,
    "hash": quick_hash,
    "token": quick_token,
    "validate_file": quick_validate_file,
}
