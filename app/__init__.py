# Initialize application
# app/__init__.py
"""
邮件发送API系统

一个功能强大的多租户邮件发送系统，支持附件上传、SMTP配置管理、
邮件队列、发送状态跟踪等完整功能。

主要功能：
- 多租户支持
- SMTP配置管理
- 单发/群发邮件
- 附件支持
- 邮件队列管理
- 发送状态跟踪
- 安全文件验证
- 统计分析

版本: 2.0.0
作者: Your Name
许可证: MIT
"""

__version__ = "2.0.0"
__author__ = "Your Name"
__email__ = "your.email@domain.com"
__license__ = "MIT"
__description__ = "多租户邮件发送API系统"

# 导入主要组件
from .main import app
from .config import settings
from .database import engine, SessionLocal, Base, get_db

# 版本信息
VERSION_INFO = {
    "version": __version__,
    "description": __description__,
    "author": __author__,
    "license": __license__,
    "features": [
        "多租户支持",
        "SMTP配置管理",
        "单发/群发邮件",
        "附件支持",
        "邮件队列管理",
        "发送状态跟踪",
        "安全文件验证",
        "统计分析",
    ],
}

__all__ = [
    "app",
    "settings",
    "engine",
    "SessionLocal",
    "Base",
    "get_db",
    "VERSION_INFO",
    "__version__",
]
