# app/api/resume_upload_routes.py
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from typing import Optional
from uuid import UUID
import logging

from ..services.resume_upload_service import ResumeUploadService
from ..schemas.resume_upload_schemas import ResumeUploadResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# 创建简历上传服务实例
resume_upload_service = ResumeUploadService()


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(..., description="履歴書ファイル（Excel形式）"),
    tenant_id: UUID = Form(..., description="テナントID"),
    engineer_id: Optional[UUID] = Form(None, description="エンジニアID（更新時のみ）")
):
    """
    履歴書ファイルをアップロード

    ## 機能
    - Excel形式の履歴書ファイルを Supabase Storage に保存
    - ファイル形式・サイズの検証
    - セキュリティチェック
    - テキスト抽出（オプション）
    - メタデータ管理

    ## パラメータ
    - **file**: 履歴書ファイル（.xls, .xlsx）
    - **tenant_id**: テナントID
    - **engineer_id**: エンジニアID（オプション、更新時のみ）

    ## 制限
    - ファイルサイズ: 最大10MB
    - ファイル形式: Excel (.xls, .xlsx) のみ
    - セキュリティ: 悪意のあるファイルを検出・拒否

    ## 戻り値
    - 成功時: ファイルURL、メタデータ、抽出テキスト
    - エラー時: エラーメッセージとエラーコード
    """
    try:
        logger.info(f"履歴書アップロード開始: {file.filename}, テナント: {tenant_id}")

        # ファイル名の基本チェック
        if not file.filename:
            return ResumeUploadResponse(
                success=False,
                message="ファイル名が指定されていません",
                error_code="MISSING_FILENAME"
            )

        # ファイルが空でないことを確認
        if file.size == 0:
            return ResumeUploadResponse(
                success=False,
                message="ファイルが空です",
                error_code="EMPTY_FILE"
            )

        # 簡历上传服务处理
        result = await resume_upload_service.upload_resume(
            file=file,
            tenant_id=tenant_id,
            engineer_id=engineer_id
        )

        logger.info(f"履歴書アップロード成功: {file.filename}")

        return ResumeUploadResponse(
            success=True,
            message="履歴書ファイルをアップロードしました",
            data=result
        )

    except HTTPException as e:
        logger.error(f"履歴書アップロードHTTPエラー: {str(e.detail)}")
        
        # HTTPException の詳細からエラーコードを生成
        error_code = "UPLOAD_ERROR"
        if "ファイル形式" in str(e.detail):
            error_code = "INVALID_FILE_FORMAT"
        elif "ファイルサイズ" in str(e.detail):
            error_code = "FILE_TOO_LARGE"
        elif "安全" in str(e.detail):
            error_code = "SECURITY_CHECK_FAILED"
        elif "空" in str(e.detail):
            error_code = "EMPTY_FILE"

        return ResumeUploadResponse(
            success=False,
            message=str(e.detail),
            error_code=error_code
        )

    except Exception as e:
        logger.error(f"履歴書アップロード予期しないエラー: {str(e)}")
        
        return ResumeUploadResponse(
            success=False,
            message="アップロード中に予期しないエラーが発生しました",
            error_code="INTERNAL_SERVER_ERROR"
        )


@router.delete("/delete/{tenant_id}")
async def delete_resume(
    tenant_id: UUID,
    storage_path: str = Query(..., description="削除するファイルのストレージパス"),
    engineer_id: UUID = Query(..., description="エンジニアID（engineers表更新用）")
):
    """
    履歴書ファイルを削除

    ## 機能
    - Supabase Storageから履歴書ファイルを削除
    - engineers表のresume_urlとresume_textフィールドをクリア
    - データベースとストレージの整合性を保つ

    ## パラメータ
    - **tenant_id**: テナントID（パスパラメータ）
    - **storage_path**: 削除するファイルのストレージパス（クエリパラメータ）
    - **engineer_id**: エンジニアID（engineers表更新用、クエリパラメータ）

    ## 戻り値
    - 成功時: 削除成功メッセージ
    - エラー時: エラーメッセージ
    """
    try:
        logger.info(f"履歴書削除開始: {storage_path}, テナント: {tenant_id}")

        # テナントIDがパスに含まれているかチェック（セキュリティ）
        if str(tenant_id) not in storage_path:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="指定されたファイルへのアクセス権限がありません"
            )

        result = await resume_upload_service.delete_resume_with_db_update(
            storage_path, tenant_id, engineer_id
        )

        if result["success"]:
            logger.info(f"履歴書削除成功: {storage_path}")
            return {
                "success": True,
                "message": "履歴書ファイルとデータベース記録を削除しました",
                "storage_path": storage_path,
                "engineer_id": str(engineer_id),
                "database_updated": result["database_updated"]
            }
        else:
            logger.warning(f"履歴書削除失敗: {storage_path} - {result.get('error', '')}")
            return {
                "success": False,
                "message": result.get("message", "ファイルの削除に失敗しました"),
                "storage_path": storage_path,
                "error": result.get("error", "")
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"履歴書削除エラー: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"削除処理に失敗しました: {str(e)}"
        )


@router.get("/exists/{tenant_id}")
async def check_file_exists(
    tenant_id: UUID,
    storage_path: str
):
    """
    履歴書ファイルの存在確認

    ## パラメータ
    - **tenant_id**: テナントID
    - **storage_path**: 確認するファイルのストレージパス

    ## 戻り値
    - ファイルの存在状況
    """
    try:
        # テナントIDがパスに含まれているかチェック（セキュリティ）
        if str(tenant_id) not in storage_path:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="指定されたファイルへのアクセス権限がありません"
            )

        exists = await resume_upload_service.file_exists(storage_path)

        return {
            "success": True,
            "exists": exists,
            "storage_path": storage_path,
            "message": "ファイルが存在します" if exists else "ファイルが見つかりません"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ファイル存在確認エラー: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"存在確認に失敗しました: {str(e)}"
        )


@router.get("/info")
async def get_upload_info():
    """
    アップロード仕様情報を取得

    履歴書アップロードAPIの制限や仕様情報を返す
    """
    return {
        "service": "履歴書アップロードサービス",
        "version": "1.0.0",
        "storage": {
            "provider": "Supabase Storage",
            "bucket": "resumes",
            "max_file_size": "10MB",
            "path_format": "{tenant_id}/{engineer_id}/{timestamp}_{filename}"
        },
        "supported_formats": [".xls", ".xlsx"],
        "supported_mime_types": [
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ],
        "features": [
            "ファイル形式検証",
            "ファイルサイズ制限",
            "セキュリティチェック",
            "テキスト抽出（オプション）",
            "メタデータ管理",
            "Supabase Storage統合"
        ],
        "security": [
            "MIME typeチェック",
            "ファイルサイズ制限",
            "悪意のあるファイル検出",
            "テナント別ファイル分離",
            "ファイル名サニタイゼーション"
        ]
    }