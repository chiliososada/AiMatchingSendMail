# app/services/resume_upload_service.py
import re
import time
import logging
from typing import Optional, Dict, Any, BinaryIO
from uuid import uuid4, UUID
from datetime import datetime
from pathlib import Path
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    
from fastapi import UploadFile, HTTPException

from ..utils.supabase_storage import get_supabase_storage, refresh_supabase_storage
from ..schemas.resume_upload_schemas import FileMetadata
from .resume_parser_service import ResumeParserService

logger = logging.getLogger(__name__)


class ResumeUploadService:
    """简历上传服务"""

    def __init__(self):
        self.bucket_name = "resumes"
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.allowed_extensions = [".xls", ".xlsx"]
        self.allowed_mime_types = [
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ]
        self.resume_parser = ResumeParserService()
        
        logger.info("简历上传服务初始化完成")

    async def upload_resume(
        self, 
        file: UploadFile, 
        tenant_id: UUID, 
        engineer_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        上传简历文件

        Args:
            file: 上传的文件
            tenant_id: 租户ID
            engineer_id: 工程师ID（可选）

        Returns:
            上传结果字典

        Raises:
            HTTPException: 验证失败或上传失败时抛出
        """
        upload_id = uuid4()
        
        try:
            logger.info(f"开始上传简历: {file.filename}, 租户: {tenant_id}, 工程师: {engineer_id}")

            # 1. 文件验证
            await self._validate_file(file)
            
            # 2. 读取文件内容
            file_content = await file.read()
            
            # 3. 安全性检查
            await self._security_check(file_content, file.filename)
            
            # 4. 生成存储路径
            storage_path = self._generate_storage_path(
                tenant_id, engineer_id or uuid4(), file.filename
            )
            
            # 5. 获取存储客户端（强制刷新以确保使用最新配置）并确保存储桶存在
            storage_client = refresh_supabase_storage()
            bucket_ready = await storage_client.create_bucket_if_not_exists(self.bucket_name)
            if not bucket_ready:
                logger.warning(f"存储桶 '{self.bucket_name}' 可能不存在，尝试直接上传文件")
            
            # 6. 上传到 Supabase Storage
            file_url = await storage_client.upload_file(
                file_content=file_content,
                bucket_name=self.bucket_name,
                file_path=storage_path,
                content_type=file.content_type
            )
            
            # 7. 创建文件元数据
            metadata = FileMetadata(
                original_filename=file.filename,
                file_size=len(file_content),
                mime_type=file.content_type,
                tenant_id=tenant_id,
                engineer_id=engineer_id,
                file_url=file_url,
                storage_path=storage_path,
                upload_id=upload_id
            )
            
            # 8. 可选：提取文本内容
            extracted_text = await self._extract_text_content(file_content, file.filename)
            
            result = {
                "file_url": file_url,
                "file_name": file.filename,
                "file_size": len(file_content),
                "upload_id": str(upload_id),
                "storage_path": storage_path,
                "metadata": metadata.dict()
            }
            
            # 如果成功提取文本，添加到结果中
            if extracted_text:
                result["extracted_text"] = extracted_text
            
            logger.info(f"简历上传成功: {file.filename} -> {file_url}")
            return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"简历上传失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

    async def _validate_file(self, file: UploadFile) -> None:
        """
        验证文件格式和大小

        Args:
            file: 上传的文件

        Raises:
            HTTPException: 验证失败时抛出
        """
        # 检查文件扩展名
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in self.allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"ファイル形式が対応していません。対応形式: {', '.join(self.allowed_extensions)}"
            )

        # 检查MIME类型
        if file.content_type not in self.allowed_mime_types:
            raise HTTPException(
                status_code=400,
                detail=f"ファイル形式が対応していません。MIME type: {file.content_type}"
            )

        # 检查文件大小
        file.file.seek(0, 2)  # 移动到文件末尾
        file_size = file.file.tell()
        file.file.seek(0)  # 移动回文件开头

        if file_size > self.max_file_size:
            max_size_mb = self.max_file_size / (1024 * 1024)
            raise HTTPException(
                status_code=400,
                detail=f"ファイルサイズが大きすぎます。最大サイズ: {max_size_mb}MB"
            )

        if file_size == 0:
            raise HTTPException(
                status_code=400,
                detail="ファイルが空です"
            )

        logger.info(f"文件验证通过: {file.filename} ({file_size} bytes)")

    async def _security_check(self, file_content: bytes, filename: str) -> None:
        """
        安全性检查

        Args:
            file_content: 文件内容
            filename: 文件名

        Raises:
            HTTPException: 安全检查失败时抛出
        """
        try:
            # 使用 python-magic 检查文件类型（如果可用）
            if MAGIC_AVAILABLE:
                file_type = magic.from_buffer(file_content, mime=True)
                
                if file_type not in self.allowed_mime_types:
                    logger.warning(f"文件类型不匹配: 实际={file_type}")
                    # 注意：这里可以选择是否严格检查
                    # raise HTTPException(status_code=400, detail="ファイル形式が一致しません")
            else:
                logger.info("python-magic 未安装，跳过MIME类型详细检查")

            # 基本的恶意文件检查（检查文件头）
            if self._is_suspicious_file(file_content):
                raise HTTPException(
                    status_code=400,
                    detail="ファイルが安全でない可能性があります"
                )

            logger.info(f"安全检查通过: {filename}")
        except Exception as e:
            logger.error(f"安全检查失败: {str(e)}")
            # 可以选择是否因为安全检查失败而拒绝上传
            # raise HTTPException(status_code=400, detail="セキュリティチェックに失敗しました")

    def _is_suspicious_file(self, file_content: bytes) -> bool:
        """
        检查是否为可疑文件

        Args:
            file_content: 文件内容

        Returns:
            是否为可疑文件
        """
        # 检查是否包含可疑的宏或脚本标识
        suspicious_patterns = [
            b"<script",
            b"javascript:",
            b"vbscript:",
            b"macro",
            b"ActiveX"
        ]
        
        file_content_lower = file_content.lower()
        for pattern in suspicious_patterns:
            if pattern in file_content_lower:
                logger.warning(f"发现可疑模式: {pattern}")
                return True
        
        return False

    def _generate_storage_path(
        self, 
        tenant_id: UUID, 
        engineer_id: UUID, 
        original_filename: str
    ) -> str:
        """
        生成存储路径

        Args:
            tenant_id: 租户ID
            engineer_id: 工程师ID
            original_filename: 原始文件名

        Returns:
            存储路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 清理文件名（移除特殊字符）
        clean_filename = self._sanitize_filename(original_filename)
        
        # 构建路径: tenant_id/engineer_id/timestamp_filename
        storage_path = f"{tenant_id}/{engineer_id}/{timestamp}_{clean_filename}"
        
        logger.info(f"生成存储路径: {storage_path}")
        return storage_path

    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，移除危险字符和不兼容字符

        Args:
            filename: 原始文件名

        Returns:
            清理后的文件名
        """
        # 获取文件扩展名
        file_path = Path(filename)
        name_part = file_path.stem
        ext_part = file_path.suffix
        
        # 移除或替换特殊字符和空格
        # 只保留ASCII字母、数字、连字符、下划线
        clean_name = re.sub(r'[^a-zA-Z0-9\-_]', '_', name_part)
        
        # 移除连续的下划线
        clean_name = re.sub(r'_+', '_', clean_name)
        
        # 移除开头和结尾的下划线
        clean_name = clean_name.strip('_')
        
        # 如果名称为空，使用默认名称
        if not clean_name:
            clean_name = 'resume'
        
        # 限制文件名长度
        if len(clean_name) > 50:
            clean_name = clean_name[:50]
        
        # 重新组合文件名
        sanitized_filename = clean_name + ext_part
        
        # 添加调试日志
        if filename != sanitized_filename:
            logger.info(f"文件名清理: '{filename}' -> '{sanitized_filename}'")
        
        return sanitized_filename

    async def _extract_text_content(
        self, 
        file_content: bytes, 
        filename: str
    ) -> Optional[str]:
        """
        直接从Excel文件中提取原始文本内容

        Args:
            file_content: 文件内容
            filename: 文件名

        Returns:
            提取的文本内容，失败时返回None
        """
        try:
            import pandas as pd
            from io import BytesIO
            
            # 将文件内容转换为BytesIO对象
            file_buffer = BytesIO(file_content)
            
            # 根据文件扩展名选择读取方式
            file_ext = Path(filename).suffix.lower()
            
            if file_ext == '.xlsx':
                # 读取xlsx文件
                excel_file = pd.ExcelFile(file_buffer, engine='openpyxl')
            elif file_ext == '.xls':
                # 读取xls文件
                excel_file = pd.ExcelFile(file_buffer, engine='xlrd')
            else:
                logger.warning(f"不支持的文件格式: {file_ext}")
                return None
            
            # 提取所有工作表的文本内容
            all_text = []
            
            for sheet_name in excel_file.sheet_names:
                try:
                    # 读取工作表
                    df = pd.read_excel(file_buffer, sheet_name=sheet_name, header=None)
                    
                    # 重置文件指针
                    file_buffer.seek(0)
                    
                    # 将所有单元格的内容转换为字符串并连接
                    sheet_text = []
                    for _, row in df.iterrows():
                        for cell_value in row:
                            if pd.notna(cell_value) and str(cell_value).strip():
                                sheet_text.append(str(cell_value).strip())
                    
                    if sheet_text:
                        all_text.append(f"=== {sheet_name} ===")
                        all_text.extend(sheet_text)
                        all_text.append("")  # 添加空行分隔
                        
                except Exception as sheet_error:
                    logger.warning(f"读取工作表 '{sheet_name}' 失败: {str(sheet_error)}")
                    continue
            
            if all_text:
                # 合并所有文本，去除重复的空行
                result_text = "\n".join(all_text).strip()
                # 清理多余的空行
                result_text = re.sub(r'\n\s*\n+', '\n\n', result_text)
                
                logger.info(f"成功从Excel文件提取文本，共 {len(result_text)} 个字符")
                return result_text
            else:
                logger.warning("Excel文件中未找到有效文本内容")
                return None
                
        except Exception as e:
            logger.warning(f"Excel文本提取失败: {str(e)}")
            return None

    async def delete_resume(
        self, 
        storage_path: str
    ) -> bool:
        """
        删除简历文件

        Args:
            storage_path: 存储路径

        Returns:
            是否删除成功
        """
        try:
            storage_client = get_supabase_storage()
            result = await storage_client.delete_file(self.bucket_name, storage_path)
            
            if result:
                logger.info(f"简历文件删除成功: {storage_path}")
            else:
                logger.warning(f"简历文件删除失败: {storage_path}")
            
            return result

        except Exception as e:
            logger.error(f"删除简历文件时出错: {str(e)}")
            return False

    async def delete_resume_with_db_update(
        self, 
        storage_path: str, 
        tenant_id, 
        engineer_id
    ) -> dict:
        """
        删除简历文件并更新数据库

        Args:
            storage_path: 存储路径
            tenant_id: 租户ID
            engineer_id: 工程师ID

        Returns:
            删除结果字典
        """
        try:
            from ..database import get_db_connection
            
            # 1. 先删除存储文件
            storage_client = get_supabase_storage()
            file_deleted = await storage_client.delete_file(self.bucket_name, storage_path)
            
            if not file_deleted:
                return {
                    "success": False,
                    "message": "文件删除失败",
                    "error": "Storage file deletion failed",
                    "database_updated": False
                }
            
            # 2. 更新数据库中的engineers表
            try:
                async with get_db_connection() as conn:
                    # 清空resume_url和resume_text字段
                    await conn.execute(
                        """
                        UPDATE engineers 
                        SET resume_url = NULL, resume_text = NULL
                        WHERE id = $1 AND tenant_id = $2
                        """,
                        engineer_id,
                        tenant_id
                    )
                    
                    logger.info(f"数据库更新成功: engineer_id={engineer_id}, tenant_id={tenant_id}")
                    database_updated = True
                    
            except Exception as db_error:
                logger.error(f"数据库更新失败: {str(db_error)}")
                # 文件已删除但数据库更新失败
                return {
                    "success": True,  # 文件删除成功
                    "message": "文件删除成功，但数据库更新失败",
                    "error": f"Database update failed: {str(db_error)}",
                    "database_updated": False
                }
            
            logger.info(f"简历完全删除成功: {storage_path}")
            return {
                "success": True,
                "message": "简历文件和数据库记录删除成功",
                "database_updated": database_updated
            }

        except Exception as e:
            logger.error(f"删除简历时出错: {str(e)}")
            return {
                "success": False,
                "message": "删除简历失败",
                "error": str(e),
                "database_updated": False
            }

    async def file_exists(self, storage_path: str) -> bool:
        """
        检查文件是否存在

        Args:
            storage_path: 存储路径

        Returns:
            文件是否存在
        """
        try:
            storage_client = get_supabase_storage()
            return await storage_client.file_exists(self.bucket_name, storage_path)
        except Exception as e:
            logger.error(f"检查文件存在性时出错: {str(e)}")
            return False