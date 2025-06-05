# app/api/email_routes.py - asyncpg版本
"""
邮件发送API路由 - 完整版
包含邮件发送、附件管理、队列管理、统计等完整功能
"""

from fastapi import (
    APIRouter,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
    Query,
    BackgroundTasks,
)
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
from datetime import datetime
import os
from pathlib import Path

from ..services.email_service import EmailService
from ..schemas.email_schemas import (
    EmailSendRequest,
    EmailWithAttachmentsRequest,
    EmailSendResponse,
    EmailTestRequest,
    EmailStatusResponse,
    BulkEmailRequest,
    AttachmentUploadResponse,
    AttachmentDeleteRequest,
    AttachmentListResponse,
    EmailStatistics,
    SMTPSettingsCreate,
    SMTPSettingsResponse,
)
from ..utils.security import file_validator, generate_secure_filename
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# ==================== SMTP设置管理 ====================


@router.post("/smtp-settings", response_model=SMTPSettingsResponse)
async def create_smtp_settings(smtp_data: SMTPSettingsCreate):
    """创建SMTP配置"""
    try:
        email_service = EmailService()
        smtp_settings = await email_service.create_smtp_settings(smtp_data)

        return SMTPSettingsResponse(
            id=smtp_settings["id"],
            tenant_id=smtp_settings["tenant_id"],
            setting_name=smtp_settings["setting_name"],
            smtp_host=smtp_settings["smtp_host"],
            smtp_port=smtp_settings["smtp_port"],
            smtp_username=smtp_settings["smtp_username"],
            security_protocol=smtp_settings["security_protocol"],
            from_email=smtp_settings["from_email"],
            from_name=smtp_settings["from_name"],
            reply_to_email=smtp_settings["reply_to_email"],
            connection_status=smtp_settings["connection_status"],
            is_default=smtp_settings["is_default"],
            is_active=smtp_settings["is_active"],
            created_at=smtp_settings["created_at"],
        )

    except Exception as e:
        logger.error(f"创建SMTP设置失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建SMTP设置失败: {str(e)}",
        )


@router.get("/smtp-settings/{tenant_id}", response_model=List[SMTPSettingsResponse])
async def get_smtp_settings_list(tenant_id: UUID):
    """获取租户的SMTP设置列表"""
    try:
        email_service = EmailService()
        settings_list = await email_service.get_smtp_settings_list(tenant_id)

        return [
            SMTPSettingsResponse(
                id=settings_item["id"],
                tenant_id=settings_item["tenant_id"],
                setting_name=settings_item["setting_name"],
                smtp_host=settings_item["smtp_host"],
                smtp_port=settings_item["smtp_port"],
                smtp_username=settings_item["smtp_username"],
                security_protocol=settings_item["security_protocol"],
                from_email=settings_item["from_email"],
                from_name=settings_item["from_name"],
                reply_to_email=settings_item["reply_to_email"],
                connection_status=settings_item["connection_status"],
                is_default=settings_item["is_default"],
                is_active=settings_item["is_active"],
                created_at=settings_item["created_at"],
            )
            for settings_item in settings_list
        ]

    except Exception as e:
        logger.error(f"获取SMTP设置列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取SMTP设置失败: {str(e)}",
        )


@router.post("/smtp-settings/test")
async def test_smtp_connection(test_request: EmailTestRequest):
    """测试SMTP连接"""
    try:
        email_service = EmailService()
        result = await email_service.test_smtp_connection(
            test_request.tenant_id, test_request.smtp_setting_id
        )
        return result

    except Exception as e:
        logger.error(f"SMTP连接测试失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SMTP连接测试失败: {str(e)}",
        )


# ==================== 附件管理 ====================


@router.post("/attachments/upload", response_model=AttachmentUploadResponse)
async def upload_attachment(
    tenant_id: UUID = Form(...),
    file: UploadFile = File(...),
):
    """上传单个附件"""
    try:
        # 验证文件大小
        file_content = await file.read()
        if len(file_content) > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件过大，最大允许{settings.MAX_FILE_SIZE/1024/1024:.1f}MB",
            )

        # 验证文件
        validation_result = file_validator.validate_file(
            file_content, file.filename, file.content_type
        )

        if not validation_result["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件验证失败: {', '.join(validation_result['errors'])}",
            )

        # 保存附件
        email_service = EmailService()
        attachment_info, attachment_id = email_service.save_attachment(
            file_content, file.filename, tenant_id, file.content_type
        )

        return AttachmentUploadResponse(
            attachment_id=attachment_id,
            filename=attachment_info.filename,
            content_type=attachment_info.content_type,
            file_size=attachment_info.file_size,
            status="uploaded",
            message="附件上传成功",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传附件失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传附件失败: {str(e)}",
        )


@router.post(
    "/attachments/upload-multiple", response_model=List[AttachmentUploadResponse]
)
async def upload_multiple_attachments(
    tenant_id: UUID = Form(...),
    files: List[UploadFile] = File(...),
):
    """批量上传附件"""
    try:
        if len(files) > settings.MAX_FILES_PER_REQUEST:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件数量超过限制，最大{settings.MAX_FILES_PER_REQUEST}个",
            )

        results = []
        total_size = 0

        for file in files:
            file_content = await file.read()
            total_size += len(file_content)

            # 检查总大小
            if total_size > settings.MAX_TOTAL_REQUEST_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"总文件大小超过限制，最大{settings.MAX_TOTAL_REQUEST_SIZE/1024/1024:.1f}MB",
                )

            try:
                # 验证单个文件
                validation_result = file_validator.validate_file(
                    file_content, file.filename, file.content_type
                )

                if not validation_result["valid"]:
                    results.append(
                        AttachmentUploadResponse(
                            attachment_id=UUID("00000000-0000-0000-0000-000000000000"),
                            filename=file.filename,
                            content_type=file.content_type or "unknown",
                            file_size=len(file_content),
                            status="failed",
                            message=f"验证失败: {', '.join(validation_result['errors'])}",
                        )
                    )
                    continue

                # 保存附件
                email_service = EmailService()
                attachment_info, attachment_id = email_service.save_attachment(
                    file_content, file.filename, tenant_id, file.content_type
                )

                results.append(
                    AttachmentUploadResponse(
                        attachment_id=attachment_id,
                        filename=attachment_info.filename,
                        content_type=attachment_info.content_type,
                        file_size=attachment_info.file_size,
                        status="uploaded",
                        message="上传成功",
                    )
                )

            except Exception as e:
                logger.error(f"上传文件 {file.filename} 失败: {str(e)}")
                results.append(
                    AttachmentUploadResponse(
                        attachment_id=UUID("00000000-0000-0000-0000-000000000000"),
                        filename=file.filename,
                        content_type=file.content_type or "unknown",
                        file_size=len(file_content),
                        status="failed",
                        message=f"上传失败: {str(e)}",
                    )
                )

        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量上传附件失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量上传失败: {str(e)}",
        )


@router.delete("/attachments/{tenant_id}/{attachment_id}")
async def delete_attachment(
    tenant_id: UUID,
    attachment_id: UUID,
    filename: str = Query(..., description="文件名"),
):
    """删除附件"""
    try:
        email_service = EmailService()
        success = email_service.delete_attachment(tenant_id, attachment_id, filename)

        if success:
            return {"status": "success", "message": "附件删除成功"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在或已被删除"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除附件失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除附件失败: {str(e)}",
        )


@router.get("/attachments/{tenant_id}", response_model=AttachmentListResponse)
async def get_attachments_list(tenant_id: UUID):
    """获取租户的附件列表"""
    try:
        email_service = EmailService()
        storage_usage = email_service.attachment_manager.get_tenant_storage_usage(
            tenant_id
        )

        attachments = []
        for file_info in storage_usage.get("files", []):
            attachments.append(
                {
                    "filename": file_info["name"],
                    "content_type": "application/octet-stream",  # 默认类型
                    "file_size": file_info["size"],
                }
            )

        return AttachmentListResponse(
            attachments=attachments,
            total_count=storage_usage["file_count"],
            total_size=storage_usage["total_size"],
        )

    except Exception as e:
        logger.error(f"获取附件列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取附件列表失败: {str(e)}",
        )


# ==================== 邮件发送 ====================


@router.post("/send", response_model=EmailSendResponse)
async def send_email(
    email_request: EmailSendRequest,
    background_tasks: BackgroundTasks,
):
    """发送普通邮件"""
    try:
        email_service = EmailService()
        result = await email_service.send_email_immediately(email_request)

        return EmailSendResponse(
            queue_id=result["queue_id"],
            status=result["status"],
            message=result["message"],
            to_emails=result["to_emails"],
            scheduled_at=result.get("scheduled_at"),
            attachments_count=result.get("attachment_count", 0),
        )

    except Exception as e:
        logger.error(f"发送邮件失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发送邮件失败: {str(e)}",
        )


@router.post("/send-with-attachments", response_model=EmailSendResponse)
async def send_email_with_attachments(
    email_request: EmailWithAttachmentsRequest,
    background_tasks: BackgroundTasks,
):
    """发送带附件的邮件"""
    try:
        email_service = EmailService()
        result = await email_service.send_email_with_attachments(email_request)

        return EmailSendResponse(
            queue_id=result["queue_id"],
            status=result["status"],
            message=result["message"],
            to_emails=result["to_emails"],
            scheduled_at=result.get("scheduled_at"),
            attachments_count=result.get("attachment_count", 0),
        )

    except Exception as e:
        logger.error(f"发送带附件邮件失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发送邮件失败: {str(e)}",
        )


@router.post("/send-test")
async def send_test_email(test_request: EmailTestRequest):
    """发送测试邮件"""
    try:
        email_service = EmailService()
        result = await email_service.send_test_email(
            test_request.tenant_id,
            test_request.smtp_setting_id,
            test_request.test_email,
        )

        return result

    except Exception as e:
        logger.error(f"发送测试邮件失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发送测试邮件失败: {str(e)}",
        )


# ==================== 队列管理 ====================


@router.get("/queue/{tenant_id}/{queue_id}", response_model=EmailStatusResponse)
async def get_email_status(tenant_id: UUID, queue_id: UUID):
    """获取邮件发送状态"""
    try:
        email_service = EmailService()
        queue_item = await email_service.get_email_queue_status(tenant_id, queue_id)

        if not queue_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="邮件记录不存在"
            )

        # 解析附件信息
        attachments_info = []
        if queue_item["attachments"] and isinstance(queue_item["attachments"], dict):
            attachments_data = queue_item["attachments"].get("attachments", [])
            for att in attachments_data:
                attachments_info.append(
                    {
                        "filename": att.get("filename", ""),
                        "content_type": att.get("content_type", ""),
                        "file_size": att.get("file_size", 0),
                    }
                )

        return EmailStatusResponse(
            id=queue_item["id"],
            to_emails=queue_item["to_emails"],
            subject=queue_item["subject"],
            status=queue_item["status"],
            created_at=queue_item["created_at"],
            sent_at=queue_item["sent_at"],
            error_message=queue_item["error_message"],
            attachments_info=attachments_info,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取邮件状态失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取邮件状态失败: {str(e)}",
        )


@router.get("/queue/{tenant_id}")
async def get_email_queue_list(
    tenant_id: UUID,
    limit: int = Query(50, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """获取邮件队列列表"""
    try:
        email_service = EmailService()
        queue_list = await email_service.get_email_queue_list(tenant_id, limit, offset)

        result = []
        for item in queue_list:
            # 解析附件信息
            attachment_count = 0
            if item["attachments"] and isinstance(item["attachments"], dict):
                attachment_count = item["attachments"].get("attachment_count", 0)

            result.append(
                {
                    "id": item["id"],
                    "to_emails": item["to_emails"],
                    "subject": item["subject"],
                    "status": item["status"],
                    "priority": item["priority"],
                    "created_at": (
                        item["created_at"].isoformat() if item["created_at"] else None
                    ),
                    "sent_at": item["sent_at"].isoformat() if item["sent_at"] else None,
                    "scheduled_at": (
                        item["scheduled_at"].isoformat()
                        if item["scheduled_at"]
                        else None
                    ),
                    "attachment_count": attachment_count,
                    "send_duration_ms": item["send_duration_ms"],
                    "error_message": item["error_message"],
                    "retry_count": item["current_retry_count"],
                }
            )

        return {
            "items": result,
            "total_count": len(result),
            "limit": limit,
            "offset": offset,
            "has_more": len(result) == limit,
        }

    except Exception as e:
        logger.error(f"获取邮件队列列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取邮件队列失败: {str(e)}",
        )


# ==================== 统计分析 ====================


@router.get("/statistics/{tenant_id}", response_model=EmailStatistics)
async def get_email_statistics(
    tenant_id: UUID,
    days: int = Query(30, ge=1, le=365, description="统计天数"),
):
    """获取邮件发送统计"""
    try:
        email_service = EmailService()
        stats = await email_service.get_email_statistics(tenant_id, days)

        return EmailStatistics(
            total_sent=stats["total_sent"],
            total_failed=stats["total_failed"],
            total_pending=stats["total_pending"],
            success_rate=stats["success_rate"],
            total_attachments=stats["total_attachments"],
            total_attachment_size=stats["total_attachment_size"],
            avg_send_time=(
                stats.get("avg_send_time_ms", 0) / 1000
                if stats.get("avg_send_time_ms")
                else None
            ),
        )

    except Exception as e:
        logger.error(f"获取邮件统计失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计数据失败: {str(e)}",
        )


# ==================== 维护和管理 ====================


@router.post("/maintenance/cleanup-attachments/{tenant_id}")
async def cleanup_tenant_attachments(
    tenant_id: UUID,
    days: int = Query(7, ge=1, le=365, description="清理多少天前的文件"),
):
    """清理租户的过期附件"""
    try:
        email_service = EmailService()
        cleanup_count = email_service.cleanup_old_attachments(tenant_id, days)

        return {
            "status": "success",
            "message": f"清理完成，删除了{cleanup_count}个过期附件",
            "cleanup_count": cleanup_count,
            "days": days,
        }

    except Exception as e:
        logger.error(f"清理附件失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理附件失败: {str(e)}",
        )


@router.get("/maintenance/storage-usage/{tenant_id}")
async def get_storage_usage(tenant_id: UUID):
    """获取存储使用情况"""
    try:
        email_service = EmailService()
        usage = email_service.attachment_manager.get_tenant_storage_usage(tenant_id)

        return {
            "tenant_id": str(tenant_id),
            "total_size": usage["total_size"],
            "total_size_mb": round(usage["total_size"] / 1024 / 1024, 2),
            "file_count": usage["file_count"],
            "files": usage["files"][:20],  # 只返回前20个文件信息
            "storage_path": usage.get("storage_path", ""),
        }

    except Exception as e:
        logger.error(f"获取存储使用情况失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取存储信息失败: {str(e)}",
        )


# ==================== 系统信息 ====================


@router.get("/system/info")
async def get_system_info():
    """获取系统信息"""
    return {
        "service": "邮件发送API",
        "version": "2.0.0",
        "database": "asyncpg连接池",
        "supported_features": [
            "SMTP配置管理",
            "单发邮件",
            "群发邮件",
            "附件支持",
            "邮件队列",
            "状态跟踪",
            "统计分析",
            "高性能异步数据库访问",
        ],
        "limits": {
            "max_file_size_mb": settings.MAX_FILE_SIZE / 1024 / 1024,
            "max_files_per_request": settings.MAX_FILES_PER_REQUEST,
            "max_recipients_per_email": settings.MAX_RECIPIENTS_PER_EMAIL,
            "max_bulk_emails": settings.MAX_BULK_EMAILS,
        },
        "supported_file_types": {
            "documents": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"],
            "images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg"],
            "archives": [".zip", ".rar", ".7z"],
            "others": [".txt", ".csv", ".json", ".xml"],
        },
    }


@router.get("/system/health")
async def health_check():
    """健康检查"""
    try:
        # 测试数据库连接
        from ..database import check_database_connection

        db_connected = await check_database_connection()

        # 检查上传目录
        upload_dir = Path(settings.ATTACHMENT_DIR)
        upload_accessible = upload_dir.exists() and os.access(upload_dir, os.W_OK)

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected" if db_connected else "error",
            "database_type": "asyncpg连接池",
            "storage": "accessible" if upload_accessible else "error",
            "upload_directory": str(upload_dir),
        }

    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
