# app/schemas/resume_upload_schemas.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from uuid import UUID


class ResumeUploadResponse(BaseModel):
    """简历上传响应模型"""

    success: bool = Field(..., description="上传是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[Dict[str, Any]] = Field(None, description="上传结果数据")
    error_code: Optional[str] = Field(None, description="错误代码")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "履歴書ファイルをアップロードしました",
                "data": {
                    "file_url": "https://storage.supabase.com/resumes/tenant123/engineer456/20240101_120000_resume.xlsx",
                    "file_name": "resume.xlsx",
                    "file_size": 245760,
                    "extracted_text": "抽出されたテキスト内容...",
                    "upload_id": "123e4567-e89b-12d3-a456-426614174000",
                    "storage_path": "resumes/tenant123/engineer456/20240101_120000_resume.xlsx"
                },
                "error_code": None
            }
        }


class FileMetadata(BaseModel):
    """文件元数据模型"""

    original_filename: str = Field(..., description="原始文件名")
    file_size: int = Field(..., description="文件大小（字节）")
    mime_type: str = Field(..., description="MIME类型")
    tenant_id: UUID = Field(..., description="租户ID")
    engineer_id: Optional[UUID] = Field(None, description="工程师ID（可选）")
    file_url: str = Field(..., description="文件访问URL")
    storage_path: str = Field(..., description="存储路径")
    upload_id: UUID = Field(..., description="上传ID")

    class Config:
        json_schema_extra = {
            "example": {
                "original_filename": "resume.xlsx",
                "file_size": 245760,
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                "engineer_id": "987fcdeb-89ab-cdef-0123-456789abcdef",
                "file_url": "https://storage.supabase.com/resumes/tenant123/engineer456/resume.xlsx",
                "storage_path": "resumes/tenant123/engineer456/20240101_120000_resume.xlsx",
                "upload_id": "456e7890-e89b-12d3-a456-426614174111"
            }
        }