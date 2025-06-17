# app/api/resume_parser_routes.py
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import List, Optional
from uuid import UUID, uuid4
import logging
from pathlib import Path
import aiofiles
import os
import asyncio
import time

from ..services.resume_parser_service import ResumeParserService
from ..schemas.resume_parser_schemas import (
    ResumeParseRequest,
    ResumeParseResponse,
    BatchResumeParseRequest,
    BatchResumeParseResponse,
)
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# 创建临时文件目录
TEMP_DIR = Path("uploads/temp/resumes")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# 创建解析服务实例
resume_parser_service = ResumeParserService()


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
    }


@router.post("/validate")
async def validate_resume_format(
    file: UploadFile = File(...), tenant_id: UUID = Form(...)
):
    """
    验证简历文件格式是否可以解析

    不进行实际解析，只检查文件格式和基本结构
    """
    if not file.filename.endswith((".xls", ".xlsx")):
        return {
            "valid": False,
            "reason": "不支持的文件格式",
            "supported_formats": [".xls", ".xlsx"],
        }

    # 使用时间戳和UUID创建唯一的临时文件名
    timestamp = int(time.time() * 1000000)  # 微秒级时间戳
    unique_id = uuid4().hex[:8]
    safe_filename = file.filename.replace(" ", "_")
    temp_file_path = (
        TEMP_DIR / f"validate_{tenant_id}_{timestamp}_{unique_id}_{safe_filename}"
    )

    try:
        # 保存临时文件
        async with aiofiles.open(temp_file_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        # 确保文件写入完成
        await asyncio.sleep(0.01)  # 短暂等待确保文件系统同步

        # 创建新的服务实例，避免任何潜在的状态问题
        service = ResumeParserService()

        # 尝试加载文件
        data = await asyncio.to_thread(service._load_excel_data, str(temp_file_path))

        if data:
            # 添加调试日志
            logger.info(
                f"验证文件: {file.filename}, 工作表数: {len(data)}, 总行数: {sum(len(d['df']) for d in data)}"
            )

            return {
                "valid": True,
                "sheets": len(data),
                "preview": {
                    "sheet_names": [d["sheet_name"] for d in data],
                    "total_rows": sum(len(d["df"]) for d in data),
                },
            }
        else:
            return {"valid": False, "reason": "无法读取文件内容"}

    except Exception as e:
        logger.error(f"验证文件格式失败: {str(e)}", exc_info=True)
        return {"valid": False, "reason": str(e)}
    finally:
        # 确保文件被删除
        if temp_file_path.exists():
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logger.warning(f"删除临时文件失败: {str(e)}")
