# base/__init__.py
# -*- coding: utf-8 -*-
"""基础模块"""

from .base_extractor import BaseExtractor
from .constants import (
    KEYWORDS,
    VALID_NATIONALITIES,
    VALID_SKILLS,
    SKILL_MARKS,
    EXCLUDE_PATTERNS,
    WORK_SCOPE_OPTIONS,
    ROLE_OPTIONS,
)

# 🔥 关键修复：确保KEYWORDS被正确导出
__all__ = [
    "BaseExtractor",
    "KEYWORDS",  # 添加KEYWORDS导出
    "VALID_NATIONALITIES",
    "VALID_SKILLS",
    "SKILL_MARKS",
    "EXCLUDE_PATTERNS",
    "WORK_SCOPE_OPTIONS",
    "ROLE_OPTIONS",
]
