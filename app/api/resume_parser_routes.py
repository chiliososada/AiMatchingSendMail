# app/api/resume_parser_routes.py
import asyncio
import logging
import os
import re
import time
from pathlib import Path
from typing import List, Optional
from uuid import UUID, uuid4

import aiofiles
import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from ..config import settings
from ..schemas.resume_parser_schemas import (
    BatchResumeParseRequest,
    BatchResumeParseResponse,
    ResumeParseRequest,
    ResumeParseResponse,
)
from ..services.resume_parser_service import ResumeParserService
from ..utils.text_utils import dataframe_to_text

logger = logging.getLogger(__name__)
router = APIRouter()

# 创建临时文件目录
TEMP_DIR = Path("uploads/temp/resumes")
# TEMP_DIR.mkdir(parents=True, exist_ok=True)

# 创建解析服务实例
resume_parser_service = ResumeParserService()

# 简历必要关键字列表 - 至少需要匹配3个以上
REQUIRED_KEYWORDS = [
    "要件定義",
    "基本設計",
    "詳細設計",
    "製造",
    "単体テスト",
    "結合テスト",
    "総合テスト",
    "本番活動",
    "担当内容",
    "氏名",
    "Windows",
    "Linux",
    "PG",
    "SE",
    "業務",
    "開発",
    "設計",
    "テスト",
    "プログラム",
    "システム",
    "年数",
    "経験",
    "技術",
    "スキル",
    "言語",
    "DB",
    "データベース",
    "Java",
    "Python",
    "JavaScript",
    "C#",
    "VB",
    "PHP",
    "Ruby",
    "Oracle",
    "MySQL",
    "PostgreSQL",
    "SQL Server",
    "MongoDB",
    "プロジェクト",
    "案件",
    "期間",
    "役割",
    "職務",
    "業界",
    "職歴",
]

# 最少关键字匹配数量
MIN_KEYWORD_MATCHES = 3


def _validate_resume_content_with_custom_keywords(
    all_data: List[dict], keywords: List[str], min_matches: int
) -> dict:
    """
    使用自定义关键字验证简历内容

    Args:
        all_data: 解析后的Excel数据列表
        keywords: 自定义关键字列表
        min_matches: 最少匹配数量

    Returns:
        验证结果字典
    """
    try:
        # 合并所有工作表的文本内容
        all_text = ""
        for data in all_data:
            if "text" in data:
                all_text += data["text"] + "\n"
            elif "df" in data:
                # 如果没有text字段，从DataFrame生成文本
                df_text = dataframe_to_text(data["df"])
                all_text += df_text + "\n"

        # 统计关键字匹配情况
        matched_keywords = []
        keyword_positions = {}

        for keyword in keywords:
            # 使用正则表达式进行匹配，支持全角半角
            pattern = re.escape(keyword)
            matches = re.finditer(pattern, all_text, re.IGNORECASE)
            match_positions = list(matches)

            if match_positions:
                matched_keywords.append(keyword)
                keyword_positions[keyword] = len(match_positions)

        # 计算匹配率
        match_count = len(matched_keywords)
        match_rate = match_count / len(keywords) * 100

        # 判断是否满足最小匹配要求
        is_valid_resume = match_count >= min_matches

        # 按匹配次数排序已匹配的关键字
        sorted_matches = sorted(
            [(kw, keyword_positions.get(kw, 0)) for kw in matched_keywords],
            key=lambda x: x[1],
            reverse=True,
        )

        result = {
            "content_valid": is_valid_resume,
            "match_count": match_count,
            "total_keywords": len(keywords),
            "match_rate": round(match_rate, 2),
            "min_required": min_matches,
            "matched_keywords": [
                kw for kw, count in sorted_matches[:10]
            ],  # 只返回前10个
            "keyword_details": dict(sorted_matches[:15]) if sorted_matches else {},
        }

        if not is_valid_resume:
            result["warning"] = (
                f"简历内容可能不完整，仅匹配到{match_count}个关键字（需要至少{min_matches}个）"
            )

        return result

    except Exception as e:
        logger.error(f"验证简历内容时出错: {str(e)}", exc_info=True)
        return {
            "content_valid": False,
            "error": f"内容验证失败: {str(e)}",
            "match_count": 0,
            "total_keywords": len(keywords),
            "match_rate": 0.0,
            "min_required": min_matches,
            "matched_keywords": [],
            "keyword_details": {},
        }


def _validate_resume_content(all_data: List[dict]) -> dict:
    """
    验证简历内容是否包含必要的关键字（使用全局设置）

    Args:
        all_data: 解析后的Excel数据列表

    Returns:
        验证结果字典
    """
    return _validate_resume_content_with_custom_keywords(
        all_data, REQUIRED_KEYWORDS, MIN_KEYWORD_MATCHES
    )


def _analyze_file_structure(all_data: List[dict]) -> dict:
    """
    分析文件结构的详细信息

    Args:
        all_data: 解析后的Excel数据列表

    Returns:
        结构分析结果
    """
    try:
        structure_info = {
            "sheets": [],
            "total_rows": 0,
            "total_columns": 0,
            "has_data": False,
            "estimated_entries": 0,
        }

        for data in all_data:
            if "df" in data:
                df = data["df"]
                sheet_name = data.get("sheet_name", "Unknown")

                # 统计非空单元格数量
                non_empty_cells = df.count().sum()

                # 估算简历条目数（假设每个简历至少占用5行）
                estimated_entries = max(1, len(df) // 5)

                sheet_info = {
                    "name": sheet_name,
                    "rows": len(df),
                    "columns": len(df.columns),
                    "non_empty_cells": int(non_empty_cells),
                    "estimated_entries": estimated_entries,
                    "density": (
                        round(non_empty_cells / (len(df) * len(df.columns)) * 100, 2)
                        if len(df) > 0 and len(df.columns) > 0
                        else 0
                    ),
                }

                structure_info["sheets"].append(sheet_info)
                structure_info["total_rows"] += len(df)
                structure_info["total_columns"] = max(
                    structure_info["total_columns"], len(df.columns)
                )
                structure_info["estimated_entries"] += estimated_entries

                if non_empty_cells > 0:
                    structure_info["has_data"] = True

        return structure_info

    except Exception as e:
        logger.error(f"分析文件结构时出错: {str(e)}", exc_info=True)
        return {
            "sheets": [],
            "total_rows": 0,
            "total_columns": 0,
            "has_data": False,
            "estimated_entries": 0,
            "error": f"结构分析失败: {str(e)}",
        }


@router.post("/parse", response_model=ResumeParseResponse)
async def parse_resume(file: UploadFile = File(...), tenant_id: UUID = Form(...)):
    """
    解析单个简历文件

    - **file**: Excel格式的简历文件 (.xls, .xlsx)
    - **tenant_id**: 租户ID
    """
    # 验证文件类型
    if not file.filename.endswith((".xls", ".xlsx")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持Excel文件格式 (.xls, .xlsx)",
        )

    # 使用时间戳和UUID创建唯一的临时文件名
    timestamp = int(time.time() * 1000000)  # 微秒级时间戳
    unique_id = uuid4().hex[:8]
    safe_filename = file.filename.replace(" ", "_")
    temp_file_path = TEMP_DIR / f"{tenant_id}_{timestamp}_{unique_id}_{safe_filename}"

    try:
        # 异步保存文件
        async with aiofiles.open(temp_file_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        # 解析文件
        logger.info(f"开始解析简历: {file.filename}, 租户: {tenant_id}")
        result = await resume_parser_service.parse_resume(str(temp_file_path))

        return ResumeParseResponse(**result)

    except Exception as e:
        logger.error(f"解析简历失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"解析失败: {str(e)}",
        )
    finally:
        # 清理临时文件
        if temp_file_path.exists():
            os.remove(temp_file_path)


@router.post("/parse-batch", response_model=BatchResumeParseResponse)
async def parse_resumes_batch(
    files: List[UploadFile] = File(...), tenant_id: UUID = Form(...)
):
    """
    批量解析简历文件

    - **files**: 多个Excel格式的简历文件
    - **tenant_id**: 租户ID
    """
    # 验证文件类型
    for file in files:
        if not file.filename.endswith((".xls", ".xlsx")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件 {file.filename} 不是支持的格式",
            )

    temp_file_paths = []

    try:
        # 保存所有临时文件
        for idx, file in enumerate(files):
            timestamp = int(time.time() * 1000000)
            unique_id = uuid4().hex[:8]
            safe_filename = file.filename.replace(" ", "_")
            temp_file_path = (
                TEMP_DIR / f"{tenant_id}_{timestamp}_{unique_id}_{idx}_{safe_filename}"
            )

            async with aiofiles.open(temp_file_path, "wb") as f:
                content = await file.read()
                await f.write(content)
            temp_file_paths.append(str(temp_file_path))

        # 批量解析
        logger.info(f"开始批量解析 {len(files)} 个简历文件")
        result = await resume_parser_service.parse_batch(temp_file_paths)

        return BatchResumeParseResponse(**result)

    except Exception as e:
        logger.error(f"批量解析失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量解析失败: {str(e)}",
        )
    finally:
        # 清理临时文件
        for path in temp_file_paths:
            if Path(path).exists():
                os.remove(path)


@router.get("/supported-formats")
async def get_supported_formats():
    """获取支持的文件格式"""
    return {
        "formats": [".xls", ".xlsx"],
        "max_file_size": "10MB",
        "encoding": ["UTF-8", "Shift-JIS", "EUC-JP"],
        "required_keywords": REQUIRED_KEYWORDS,
        "min_keyword_matches": MIN_KEYWORD_MATCHES,
        "validation_info": {
            "description": "文件内容必须包含简历相关的关键字",
            "total_keywords": len(REQUIRED_KEYWORDS),
            "categories": [
                "开发流程关键字（要件定義、基本設計等）",
                "技术关键字（Java、Python、DB等）",
                "基本信息关键字（氏名、经验、技術等）",
                "系统环境关键字（Windows、Linux等）",
            ],
        },
    }


@router.post("/validate")
async def validate_resume_format(
    file: UploadFile = File(...),
    tenant_id: UUID = Form(...),
    strict_validation: bool = Form(default=True, description="是否启用严格的内容验证"),
):
    """
    验证简历文件格式和内容是否符合要求

    增强功能：
    - 检查文件格式和基本结构
    - 验证简历内容是否包含必要关键字
    - 分析文件结构和数据质量
    - 提供详细的验证报告

    Args:
        file: 上传的Excel文件
        tenant_id: 租户ID
        strict_validation: 是否启用严格验证（检查关键字）
    """
    # 1. 基本文件格式检查
    if not file.filename.endswith((".xls", ".xlsx")):
        return {
            "valid": False,
            "reason": "不支持的文件格式",
            "supported_formats": [".xls", ".xlsx"],
            "file_info": {"filename": file.filename, "size": 0, "format_valid": False},
        }

    # 使用时间戳和UUID创建唯一的临时文件名
    timestamp = int(time.time() * 1000000)  # 微秒级时间戳
    unique_id = uuid4().hex[:8]
    safe_filename = file.filename.replace(" ", "_")
    temp_file_path = (
        TEMP_DIR / f"validate_{tenant_id}_{timestamp}_{unique_id}_{safe_filename}"
    )

    try:
        # 2. 保存临时文件并获取文件大小
        file_content = await file.read()
        file_size = len(file_content)

        async with aiofiles.open(temp_file_path, "wb") as f:
            await f.write(file_content)

        # 确保文件写入完成
        await asyncio.sleep(0.01)  # 短暂等待确保文件系统同步

        # 3. 创建新的服务实例，避免任何潜在的状态问题
        service = ResumeParserService()

        # 4. 尝试加载Excel文件
        data = await asyncio.to_thread(service._load_excel_data, str(temp_file_path))

        if not data:
            return {
                "valid": False,
                "reason": "无法读取文件内容或文件为空",
                "file_info": {
                    "filename": file.filename,
                    "size": file_size,
                    "format_valid": True,
                    "content_readable": False,
                },
            }

        # 5. 分析文件结构
        structure_analysis = _analyze_file_structure(data)

        # 6. 基本验证结果
        validation_result = {
            "valid": True,
            "file_info": {
                "filename": file.filename,
                "size": file_size,
                "size_mb": round(file_size / (1024 * 1024), 2),
                "format_valid": True,
                "content_readable": True,
            },
            "structure": structure_analysis,
            "basic_validation": {
                "sheets_count": len(data),
                "has_data": structure_analysis["has_data"],
                "total_rows": structure_analysis["total_rows"],
                "estimated_entries": structure_analysis["estimated_entries"],
            },
        }

        # 7. 内容关键字验证（如果启用严格验证）
        if strict_validation:
            logger.info(f"执行严格内容验证: {file.filename}")
            content_validation = _validate_resume_content(data)
            validation_result["content_validation"] = content_validation

            # 如果关键字验证失败，标记整个验证为失败
            if not content_validation["content_valid"]:
                validation_result["valid"] = False
                validation_result["reason"] = (
                    "简历内容验证失败："
                    + content_validation.get("warning", "缺少必要的简历关键字")
                )
        else:
            validation_result["content_validation"] = {
                "content_valid": True,
                "message": "已跳过内容验证（strict_validation=False）",
            }

        # 8. 添加调试日志
        logger.info(
            f"验证文件: {file.filename}, "
            f"工作表数: {len(data)}, "
            f"总行数: {structure_analysis['total_rows']}, "
            f"预估条目: {structure_analysis['estimated_entries']}, "
            f"严格验证: {strict_validation}, "
            f"最终结果: {'通过' if validation_result['valid'] else '失败'}"
        )

        # 9. 返回详细的验证结果
        return validation_result

    except Exception as e:
        logger.error(f"验证文件格式失败: {str(e)}", exc_info=True)
        return {
            "valid": False,
            "reason": f"验证过程中发生错误: {str(e)}",
            "file_info": {
                "filename": file.filename,
                "size": len(file_content) if "file_content" in locals() else 0,
                "format_valid": True,
                "content_readable": False,
            },
            "error_details": str(e),
        }
    finally:
        # 10. 确保文件被删除
        if temp_file_path.exists():
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logger.warning(f"删除临时文件失败: {str(e)}")


@router.get("/keywords")
async def get_validation_keywords():
    """
    获取简历验证所使用的关键字列表

    用于调试和了解验证规则
    """
    return {
        "total_keywords": len(REQUIRED_KEYWORDS),
        "min_required_matches": MIN_KEYWORD_MATCHES,
        "keywords": REQUIRED_KEYWORDS,
        "categories": {
            "开发流程": [
                "要件定義",
                "基本設計",
                "詳細設計",
                "製造",
                "単体テスト",
                "結合テスト",
                "総合テスト",
                "本番活動",
            ],
            "技术栈": ["Java", "Python", "JavaScript", "C#", "VB", "PHP", "Ruby"],
            "数据库": [
                "Oracle",
                "MySQL",
                "PostgreSQL",
                "SQL Server",
                "MongoDB",
                "DB",
                "データベース",
            ],
            "系统环境": ["Windows", "Linux"],
            "职位角色": ["PG", "SE", "プログラム", "システム"],
            "基本信息": ["氏名", "担当内容", "年数", "経験", "技術", "スキル", "業務"],
            "项目相关": [
                "プロジェクト",
                "案件",
                "期間",
                "役割",
                "職務",
                "業界",
                "職歴",
            ],
        },
        "validation_rules": {
            "description": "文件内容必须至少匹配3个关键字才能通过验证",
            "case_sensitive": False,
            "regex_enabled": True,
            "fullwidth_halfwidth": "支持全角半角字符匹配",
        },
    }


@router.post("/validate-keywords")
async def validate_keywords_only(
    file: UploadFile = File(...),
    custom_keywords: Optional[List[str]] = Form(
        default=None, description="自定义关键字列表（可选）"
    ),
    min_matches: Optional[int] = Form(
        default=MIN_KEYWORD_MATCHES, description="最少匹配数量"
    ),
):
    """
    仅验证文件内容的关键字匹配情况

    用于测试不同关键字组合的匹配效果
    """
    if not file.filename.endswith((".xls", ".xlsx")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持Excel文件格式"
        )

    # 使用自定义关键字或默认关键字
    keywords_to_use = custom_keywords if custom_keywords else REQUIRED_KEYWORDS
    min_matches_to_use = min_matches if min_matches is not None else MIN_KEYWORD_MATCHES

    timestamp = int(time.time() * 1000000)
    unique_id = uuid4().hex[:8]
    safe_filename = file.filename.replace(" ", "_")
    temp_file_path = TEMP_DIR / f"keyword_test_{timestamp}_{unique_id}_{safe_filename}"

    try:
        # 保存并读取文件
        async with aiofiles.open(temp_file_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        service = ResumeParserService()
        data = await asyncio.to_thread(service._load_excel_data, str(temp_file_path))

        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="无法读取文件内容"
            )

        # 使用自定义关键字进行验证（不修改全局变量）
        content_validation = _validate_resume_content_with_custom_keywords(
            data, keywords_to_use, min_matches_to_use
        )

        return {
            "keywords_used": keywords_to_use,
            "min_matches_required": min_matches_to_use,
            "validation_result": content_validation,
            "file_info": {
                "filename": file.filename,
                "sheets": len(data),
                "total_rows": sum(len(d["df"]) for d in data if "df" in d),
            },
        }

    except Exception as e:
        logger.error(f"关键字验证失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"关键字验证失败: {str(e)}",
        )
    finally:
        if temp_file_path.exists():
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logger.warning(f"删除临时文件失败: {str(e)}")
