# app/api/email_routes.py
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import logging
import os
from pathlib import Path

from ..database import get_db
from ..services.email_service import EmailService
from ..schemas.email_schemas import (
    SMTPSettingsCreate,
    SMTPSettingsResponse,
    EmailSendRequest,
    EmailSendResponse,
    EmailWithAttachmentsRequest,
    EmailTestRequest,
    EmailStatusResponse,
    AttachmentUploadResponse,
    AttachmentDeleteRequest,
    BulkEmailRequest,
    AttachmentListResponse,
    EmailStatistics,
    AttachmentInfo,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# SMTP设置相关路由
@router.post("/smtp-settings", response_model=SMTPSettingsResponse)
def create_smtp_settings(settings: SMTPSettingsCreate, db: Session = Depends(get_db)):
    """创建SMTP设置"""
    try:
        email_service = EmailService(db)
        smtp_settings = email_service.create_smtp_settings(settings)
        return smtp_settings
    except Exception as e:
        logger.error(f"创建SMTP设置失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建SMTP设置失败: {str(e)}",
        )


@router.get("/smtp-settings/{tenant_id}", response_model=List[SMTPSettingsResponse])
def get_smtp_settings_list(tenant_id: UUID, db: Session = Depends(get_db)):
    """获取SMTP设置列表"""
    try:
        email_service = EmailService(db)
        settings_list = email_service.get_smtp_settings_list(tenant_id)
        return settings_list
    except Exception as e:
        logger.error(f"获取SMTP设置列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取SMTP设置失败: {str(e)}",
        )


@router.post("/smtp-settings/test")
async def test_smtp_connection(
    test_request: EmailTestRequest, db: Session = Depends(get_db)
):
    """测试SMTP连接"""
    try:
        email_service = EmailService(db)
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


# 附件管理相关路由
@router.post("/attachments/upload", response_model=AttachmentUploadResponse)
async def upload_attachment(tenant_id: UUID = Form(...), file: UploadFile = File(...)):
    """上传附件"""
    try:
        # 验证文件
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="文件名不能为空"
            )

        # 验证文件大小（25MB限制）
        max_size = 25 * 1024 * 1024  # 25MB
        content = await file.read()
        if len(content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件大小超过限制，最大25MB，当前: {len(content)/1024/1024:.2f}MB",
            )

        # 验证文件类型
        forbidden_extensions = [
            ".exe",
            ".bat",
            ".cmd",
            ".scr",
            ".pif",
            ".com",
            ".vbs",
            ".js",
        ]
        file_extension = Path(file.filename).suffix.lower()
        if file_extension in forbidden_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不允许上传 {file_extension} 类型的文件",
            )

        # 保存附件
        db = next(get_db())
        email_service = EmailService(db)

        attachment_info, attachment_id = email_service.save_attachment(
            file_content=content,
            filename=file.filename,
            tenant_id=tenant_id,
            content_type=file.content_type,
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


@router.post("/attachments/upload-multiple")
async def upload_multiple_attachments(
    tenant_id: UUID = Form(...), files: List[UploadFile] = File(...)
):
    """批量上传附件"""
    try:
        if len(files) > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="一次最多上传10个文件"
            )

        db = next(get_db())
        email_service = EmailService(db)

        results = []
        total_size = 0

        for file in files:
            try:
                if not file.filename:
                    results.append(
                        {
                            "filename": "unknown",
                            "status": "failed",
                            "message": "文件名不能为空",
                        }
                    )
                    continue

                content = await file.read()
                total_size += len(content)

                # 检查总大小限制（100MB）
                if total_size > 100 * 1024 * 1024:
                    results.append(
                        {
                            "filename": file.filename,
                            "status": "failed",
                            "message": "总文件大小超过100MB限制",
                        }
                    )
                    break

                attachment_info, attachment_id = email_service.save_attachment(
                    file_content=content,
                    filename=file.filename,
                    tenant_id=tenant_id,
                    content_type=file.content_type,
                )

                results.append(
                    {
                        "attachment_id": attachment_id,
                        "filename": attachment_info.filename,
                        "content_type": attachment_info.content_type,
                        "file_size": attachment_info.file_size,
                        "status": "uploaded",
                        "message": "上传成功",
                    }
                )

            except Exception as e:
                results.append(
                    {
                        "filename": file.filename if file.filename else "unknown",
                        "status": "failed",
                        "message": str(e),
                    }
                )

        return {
            "total_files": len(files),
            "successful_uploads": len(
                [r for r in results if r["status"] == "uploaded"]
            ),
            "failed_uploads": len([r for r in results if r["status"] == "failed"]),
            "total_size": total_size,
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量上传附件失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量上传失败: {str(e)}",
        )


@router.delete("/attachments/{tenant_id}/{attachment_id}")
def delete_attachment(
    tenant_id: UUID, attachment_id: UUID, filename: str, db: Session = Depends(get_db)
):
    """删除附件"""
    try:
        email_service = EmailService(db)
        success = email_service.delete_attachment(tenant_id, attachment_id, filename)

        if success:
            return {"message": "附件删除成功"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在或删除失败"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除附件失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除附件失败: {str(e)}",
        )


@router.get("/attachments/{tenant_id}/usage")
def get_attachment_usage(tenant_id: UUID, db: Session = Depends(get_db)):
    """获取附件存储使用情况"""
    try:
        email_service = EmailService(db)
        usage = email_service.attachment_manager.get_tenant_storage_usage(tenant_id)
        return usage
    except Exception as e:
        logger.error(f"获取存储使用情况失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取存储使用情况失败: {str(e)}",
        )


# 邮件发送相关路由
@router.post("/send", response_model=EmailSendResponse)
async def send_email(email_request: EmailSendRequest, db: Session = Depends(get_db)):
    """发送邮件（普通邮件，不带附件）"""
    try:
        email_service = EmailService(db)
        result = await email_service.send_email_immediately(email_request)

        return EmailSendResponse(
            queue_id=result["queue_id"],
            status=result["status"],
            message=result["message"],
            to_emails=result["to_emails"],
            scheduled_at=email_request.scheduled_at,
            attachments_count=0,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"发送邮件失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发送邮件失败: {str(e)}",
        )


@router.post("/send-with-attachments", response_model=EmailSendResponse)
async def send_email_with_attachments(
    email_request: EmailWithAttachmentsRequest, db: Session = Depends(get_db)
):
    """发送带附件的邮件"""
    try:
        email_service = EmailService(db)
        result = await email_service.send_email_with_attachments(email_request)

        return EmailSendResponse(
            queue_id=result["queue_id"],
            status=result["status"],
            message=result["message"],
            to_emails=result["to_emails"],
            scheduled_at=email_request.scheduled_at,
            attachments_count=result.get("attachment_count", 0),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"发送带附件邮件失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发送邮件失败: {str(e)}",
        )


@router.post("/send-bulk")
async def send_bulk_emails(
    bulk_request: BulkEmailRequest, db: Session = Depends(get_db)
):
    """批量发送邮件"""
    try:
        email_service = EmailService(db)
        result = await email_service.send_bulk_emails(bulk_request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"批量发送邮件失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量发送失败: {str(e)}",
        )


@router.post("/send-test")
async def send_test_email(
    test_request: EmailTestRequest, db: Session = Depends(get_db)
):
    """发送测试邮件"""
    try:
        email_service = EmailService(db)
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


# 邮件状态和队列管理
@router.get("/queue/{tenant_id}/{queue_id}", response_model=EmailStatusResponse)
def get_email_status(tenant_id: UUID, queue_id: UUID, db: Session = Depends(get_db)):
    """获取邮件发送状态"""
    try:
        email_service = EmailService(db)
        queue_item = email_service.get_email_queue_status(tenant_id, queue_id)

        if not queue_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="邮件队列记录不存在"
            )

        # 解析附件信息
        attachments_info = []
        if queue_item.attachments and isinstance(queue_item.attachments, dict):
            attachments_data = queue_item.attachments.get("attachments", [])
            for att_data in attachments_data:
                attachments_info.append(AttachmentInfo(**att_data))

        # 创建响应对象
        response = EmailStatusResponse(
            id=queue_item.id,
            to_emails=queue_item.to_emails,
            subject=queue_item.subject,
            status=queue_item.status,
            created_at=queue_item.created_at,
            sent_at=queue_item.sent_at,
            error_message=queue_item.error_message,
            attachments_info=attachments_info,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取邮件状态失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取邮件状态失败: {str(e)}",
        )


@router.get("/queue/{tenant_id}", response_model=List[EmailStatusResponse])
def get_email_queue_list(
    tenant_id: UUID,
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """获取邮件队列列表"""
    try:
        email_service = EmailService(db)
        queue_list = email_service.get_email_queue_list(tenant_id, limit, offset)

        # 如果有状态过滤
        if status_filter:
            queue_list = [item for item in queue_list if item.status == status_filter]

        # 转换为响应格式
        response_list = []
        for queue_item in queue_list:
            attachments_info = []
            if queue_item.attachments and isinstance(queue_item.attachments, dict):
                attachments_data = queue_item.attachments.get("attachments", [])
                for att_data in attachments_data:
                    attachments_info.append(AttachmentInfo(**att_data))

            response_list.append(
                EmailStatusResponse(
                    id=queue_item.id,
                    to_emails=queue_item.to_emails,
                    subject=queue_item.subject,
                    status=queue_item.status,
                    created_at=queue_item.created_at,
                    sent_at=queue_item.sent_at,
                    error_message=queue_item.error_message,
                    attachments_info=attachments_info,
                )
            )

        return response_list

    except Exception as e:
        logger.error(f"获取邮件队列列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取邮件队列失败: {str(e)}",
        )


# 统计和分析
@router.get("/statistics/{tenant_id}", response_model=EmailStatistics)
def get_email_statistics(
    tenant_id: UUID, days: int = 30, db: Session = Depends(get_db)
):
    """获取邮件发送统计"""
    try:
        email_service = EmailService(db)
        stats = email_service.get_email_statistics(tenant_id, days)
        return EmailStatistics(**stats)
    except Exception as e:
        logger.error(f"获取邮件统计失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计数据失败: {str(e)}",
        )


# 维护和清理
@router.post("/cleanup/{tenant_id}")
def cleanup_old_attachments(
    tenant_id: UUID, days: int = 7, db: Session = Depends(get_db)
):
    """清理过期附件"""
    try:
        email_service = EmailService(db)
        cleaned_count = email_service.cleanup_old_attachments(tenant_id, days)
        return {
            "message": f"清理完成，删除了 {cleaned_count} 个过期附件",
            "cleaned_count": cleaned_count,
            "days_threshold": days,
        }
    except Exception as e:
        logger.error(f"清理附件失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理附件失败: {str(e)}",
        )


# 健康检查和信息
@router.get("/supported-file-types")
def get_supported_file_types():
    """获取支持的文件类型"""
    from ..services.smtp_service import SMTPService

    smtp_service = SMTPService(None)  # 这里不需要实际的SMTP设置
    return smtp_service.get_supported_file_types()


@router.get("/limits")
def get_system_limits():
    """获取系统限制信息"""
    return {
        "max_attachment_size": "25MB",
        "max_attachments_per_email": 10,
        "max_total_attachment_size": "25MB",
        "max_recipients_per_email": 100,
        "max_bulk_emails": 1000,
        "supported_protocols": ["TLS", "SSL", "None"],
        "cleanup_threshold_hours": 24,
    }
