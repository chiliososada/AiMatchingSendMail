# app/api/email_routes.py - asyncpg版本
"""
メール送信API ルート - 完全版
メール送信、添付ファイル管理、キュー管理、統計などの完全な機能を含む
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
    """SMTP設定を作成"""
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
        logger.error(f"SMTP設定の作成に失敗しました: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SMTP設定の作成に失敗しました: {str(e)}",
        )


@router.get("/smtp-settings/{tenant_id}", response_model=List[SMTPSettingsResponse])
async def get_smtp_settings_list(tenant_id: UUID):
    """テナントのSMTP設定リストを取得"""
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
        logger.error(f"SMTP設定リストの取得に失敗しました: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SMTP設定の取得に失敗しました: {str(e)}",
        )


@router.post("/smtp-settings/test")
async def test_smtp_connection(test_request: EmailTestRequest):
    """SMTP接続をテスト"""
    try:
        email_service = EmailService()
        result = await email_service.test_smtp_connection(
            test_request.tenant_id, test_request.smtp_setting_id
        )
        return result

    except Exception as e:
        logger.error(f"SMTP接続テストに失敗しました: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SMTP接続テストに失敗しました: {str(e)}",
        )


# ==================== 添付ファイル管理 ====================


@router.post("/attachments/upload", response_model=AttachmentUploadResponse)
async def upload_attachment(
    tenant_id: UUID = Form(...),
    file: UploadFile = File(...),
):
    """単一の添付ファイルをアップロード"""
    try:
        # 验证文件大小
        file_content = await file.read()
        if len(file_content) > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"ファイルが大きすぎます。最大{settings.MAX_FILE_SIZE/1024/1024:.1f}MBまで許可されています",
            )

        # 验证文件
        validation_result = file_validator.validate_file(
            file_content, file.filename, file.content_type
        )

        if not validation_result["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ファイル検証に失敗しました: {', '.join(validation_result['errors'])}",
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
            message="添付ファイルのアップロードが成功しました",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添付ファイルのアップロードに失敗しました: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添付ファイルのアップロードに失敗しました: {str(e)}",
        )


@router.post(
    "/attachments/upload-multiple", response_model=List[AttachmentUploadResponse]
)
async def upload_multiple_attachments(
    tenant_id: UUID = Form(...),
    files: List[UploadFile] = File(...),
):
    """添付ファイルを一括アップロード"""
    try:
        if len(files) > settings.MAX_FILES_PER_REQUEST:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ファイル数が制限を超えています。最大{settings.MAX_FILES_PER_REQUEST}個まで",
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
                    detail=f"総ファイルサイズが制限を超えています。最大{settings.MAX_TOTAL_REQUEST_SIZE/1024/1024:.1f}MB",
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
                            message=f"検証に失敗しました: {', '.join(validation_result['errors'])}",
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
                        message="アップロード成功",
                    )
                )

            except Exception as e:
                logger.error(f"ファイル {file.filename} のアップロードに失敗しました: {str(e)}")
                results.append(
                    AttachmentUploadResponse(
                        attachment_id=UUID("00000000-0000-0000-0000-000000000000"),
                        filename=file.filename,
                        content_type=file.content_type or "unknown",
                        file_size=len(file_content),
                        status="failed",
                        message=f"アップロードに失敗しました: {str(e)}",
                    )
                )

        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添付ファイルの一括アップロードに失敗しました: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"一括アップロードに失敗しました: {str(e)}",
        )


@router.delete("/attachments/{tenant_id}/{attachment_id}")
async def delete_attachment(
    tenant_id: UUID,
    attachment_id: UUID,
    filename: str = Query(..., description="ファイル名"),
):
    """添付ファイルを削除"""
    try:
        email_service = EmailService()
        success = email_service.delete_attachment(tenant_id, attachment_id, filename)

        if success:
            return {"status": "success", "message": "添付ファイルの削除が成功しました"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="添付ファイルが存在しないか、すでに削除されています"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添付ファイルの削除に失敗しました: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添付ファイルの削除に失敗しました: {str(e)}",
        )


@router.get("/attachments/{tenant_id}", response_model=AttachmentListResponse)
async def get_attachments_list(tenant_id: UUID):
    """テナントの添付ファイルリストを取得"""
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
                    "content_type": "application/octet-stream",  # デフォルトタイプ
                    "file_size": file_info["size"],
                }
            )

        return AttachmentListResponse(
            attachments=attachments,
            total_count=storage_usage["file_count"],
            total_size=storage_usage["total_size"],
        )

    except Exception as e:
        logger.error(f"添付ファイルリストの取得に失敗しました: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添付ファイルリストの取得に失敗しました: {str(e)}",
        )


# ==================== メール送信 ====================


@router.post("/send", response_model=EmailSendResponse)
async def send_email(
    email_request: EmailSendRequest,
    background_tasks: BackgroundTasks,
):
    """通常のメールを送信"""
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
        logger.error(f"メール送信に失敗しました: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"メール送信に失敗しました: {str(e)}",
        )


@router.post("/send-with-attachments", response_model=EmailSendResponse)
async def send_email_with_attachments(
    email_request: EmailWithAttachmentsRequest,
    background_tasks: BackgroundTasks,
):
    """
    添付ファイル付きのメールを送信
    
    パラメータ説明：
    - attachment_ids: アップロード済みの添付ファイルIDリスト
    - attachment_filenames: 添付ファイルの元のファイル名リスト、attachment_idsと対応
      - このパラメータを提供すると、メール内の添付ファイルはサーバーにGUIDで保存されたファイル名ではなく、指定されたファイル名で表示されます
      - 数量はattachment_idsと一致する必要があります
      - オプションパラメータ、提供されない場合はサーバーファイル名を使用
    """
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
        logger.error(f"添付ファイル付きメールの送信に失敗しました: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"メール送信に失敗しました: {str(e)}",
        )


@router.post("/send-test")
async def send_test_email(test_request: EmailTestRequest):
    """テストメールを送信"""
    try:
        email_service = EmailService()
        result = await email_service.send_test_email(
            test_request.tenant_id,
            test_request.smtp_setting_id,
            test_request.test_email,
        )

        return result

    except Exception as e:
        logger.error(f"テストメールの送信に失敗しました: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"テストメールの送信に失敗しました: {str(e)}",
        )


# ==================== キュー管理 ====================


@router.get("/queue/{tenant_id}/{queue_id}", response_model=EmailStatusResponse)
async def get_email_status(tenant_id: UUID, queue_id: UUID):
    """メール送信状態を取得"""
    try:
        email_service = EmailService()
        queue_item = await email_service.get_email_queue_status(tenant_id, queue_id)

        if not queue_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="メールレコードが存在しません"
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
        logger.error(f"メール状態の取得に失敗しました: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"メール状態の取得に失敗しました: {str(e)}",
        )


@router.get("/queue/{tenant_id}")
async def get_email_queue_list(
    tenant_id: UUID,
    limit: int = Query(50, ge=1, le=100, description="ページあたりの数量"),
    offset: int = Query(0, ge=0, description="オフセット"),
):
    """メールキューリストを取得"""
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
        logger.error(f"メールキューリストの取得に失敗しました: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"メールキューの取得に失敗しました: {str(e)}",
        )


# ==================== 统计分析 ====================


@router.get("/statistics/{tenant_id}", response_model=EmailStatistics)
async def get_email_statistics(
    tenant_id: UUID,
    days: int = Query(30, ge=1, le=365, description="統計日数"),
):
    """メール送信統計を取得"""
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
        logger.error(f"メール統計の取得に失敗しました: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"統計データの取得に失敗しました: {str(e)}",
        )


# ==================== 维护和管理 ====================


@router.post("/maintenance/cleanup-attachments/{tenant_id}")
async def cleanup_tenant_attachments(
    tenant_id: UUID,
    days: int = Query(7, ge=1, le=365, description="何日前のファイルをクリーンアップするか"),
):
    """テナントの期限切れ添付ファイルをクリーンアップ"""
    try:
        email_service = EmailService()
        cleanup_count = email_service.cleanup_old_attachments(tenant_id, days)

        return {
            "status": "success",
            "message": f"クリーンアップ完了、{cleanup_count}個の期限切れ添付ファイルを削除しました",
            "cleanup_count": cleanup_count,
            "days": days,
        }

    except Exception as e:
        logger.error(f"添付ファイルのクリーンアップに失敗しました: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添付ファイルのクリーンアップに失敗しました: {str(e)}",
        )


@router.get("/maintenance/storage-usage/{tenant_id}")
async def get_storage_usage(tenant_id: UUID):
    """ストレージ使用状況を取得"""
    try:
        email_service = EmailService()
        usage = email_service.attachment_manager.get_tenant_storage_usage(tenant_id)

        return {
            "tenant_id": str(tenant_id),
            "total_size": usage["total_size"],
            "total_size_mb": round(usage["total_size"] / 1024 / 1024, 2),
            "file_count": usage["file_count"],
            "files": usage["files"][:20],  # 最初の20個のファイル情報のみ返す
            "storage_path": usage.get("storage_path", ""),
        }

    except Exception as e:
        logger.error(f"ストレージ使用状況の取得に失敗しました: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ストレージ情報の取得に失敗しました: {str(e)}",
        )


# ==================== 系统信息 ====================


@router.get("/system/info")
async def get_system_info():
    """システム情報を取得"""
    return {
        "service": "メール送信API",
        "version": "2.0.0",
        "database": "asyncpg接続プール",
        "supported_features": [
            "SMTP設定管理",
            "単発メール",
            "一括メール",
            "添付ファイルサポート",
            "メールキュー",
            "状態追跡",
            "統計分析",
            "高性能非同期データベースアクセス",
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
    """ヘルスチェック"""
    try:
        # データベース接続をテスト
        from ..database import check_database_connection

        db_connected = await check_database_connection()

        # アップロードディレクトリをチェック
        upload_dir = Path(settings.ATTACHMENT_DIR)
        upload_accessible = upload_dir.exists() and os.access(upload_dir, os.W_OK)

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected" if db_connected else "error",
            "database_type": "asyncpg接続プール",
            "storage": "accessible" if upload_accessible else "error",
            "upload_directory": str(upload_dir),
        }

    except Exception as e:
        logger.error(f"ヘルスチェックに失敗しました: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )


# app/api/email_routes.py に追加された新しいルート


@router.post("/send-individual", response_model=EmailSendResponse)
async def send_email_individual(
    email_request: EmailSendRequest,
    background_tasks: BackgroundTasks,
):
    """
    個別メール送信（各受信者が独立したメールを受信）

    /send インターフェースとの違い：
    - /send: 複数の受信者に1通のメールを送信（受信者同士が見える）
    - /send-individual: 個別メールをループ送信（受信者が他の人を見えない）

    リクエスト形式は /send と完全に同じですが、動作が異なります
    """
    try:
        logger.info(f"{len(email_request.to_emails)}人の受信者に個別メール送信を開始")

        email_service = EmailService()
        result = await email_service.send_email_individual(email_request)

        return EmailSendResponse(
            queue_id=result["queue_id"],
            status=result["status"],
            message=result["message"],
            to_emails=result["to_emails"],
            scheduled_at=result.get("scheduled_at"),
            attachments_count=result.get("attachment_count", 0),
        )

    except Exception as e:
        logger.error(f"個別メール送信に失敗しました: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"個別メール送信に失敗しました: {str(e)}",
        )


@router.post("/send-individual-with-attachments", response_model=EmailSendResponse)
async def send_email_individual_with_attachments(
    email_request: EmailWithAttachmentsRequest,
    background_tasks: BackgroundTasks,
):
    """
    添付ファイル付き個別メール送信（各受信者が独立したメールを受信）

    /send-with-attachments インターフェースとの違い：
    - /send-with-attachments: 複数の受信者に1通のメールを送信（受信者同士が見える）
    - /send-individual-with-attachments: 個別メールをループ送信（受信者が他の人を見えない）
    
    パラメータ説明：
    - attachment_ids: アップロード済みの添付ファイルIDリスト
    - attachment_filenames: 添付ファイルの元のファイル名リスト、attachment_idsと対応
      - このパラメータを提供すると、メール内の添付ファイルはサーバーにGUIDで保存されたファイル名ではなく、指定されたファイル名で表示されます
      - 数量はattachment_idsと一致する必要があります
      - オプションパラメータ、提供されない場合はサーバーファイル名を使用
    """
    try:
        logger.info(f"{len(email_request.to_emails)}人の受信者に添付ファイル付き個別メール送信を開始")

        email_service = EmailService()
        result = await email_service.send_email_individual_with_attachments(
            email_request
        )

        return EmailSendResponse(
            queue_id=result["queue_id"],
            status=result["status"],
            message=result["message"],
            to_emails=result["to_emails"],
            scheduled_at=result.get("scheduled_at"),
            attachments_count=result.get("attachment_count", 0),
        )

    except Exception as e:
        logger.error(f"添付ファイル付き個別メール送信に失敗しました: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"個別メール送信に失敗しました: {str(e)}",
        )
