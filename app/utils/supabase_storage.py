# app/utils/supabase_storage.py
import os
import logging
from typing import Optional, BinaryIO
from io import BytesIO
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None

logger = logging.getLogger(__name__)


class SupabaseStorageClient:
    """Supabase Storage 客户端"""

    def __init__(self):
        """初始化 Supabase 客户端"""
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
        self.supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.supabase_url or not self.supabase_anon_key:
            logger.warning("Supabase 配置缺失，存储功能将不可用")
            self.client = None
            self.admin_client = None
            return
            
        try:
            # 普通客户端（用于文件操作）
            self.client: Client = create_client(self.supabase_url, self.supabase_anon_key)
            
            # 管理员客户端（用于桶管理）
            if self.supabase_service_key:
                self.admin_client: Client = create_client(self.supabase_url, self.supabase_service_key)
                logger.info("Supabase Storage 客户端初始化成功（包含管理员权限）")
            else:
                self.admin_client = None
                logger.info("Supabase Storage 客户端初始化成功（仅普通权限）")
                
        except Exception as e:
            logger.error(f"Supabase Storage 客户端初始化失败: {str(e)}")
            self.client = None
            self.admin_client = None

    def is_available(self) -> bool:
        """检查存储服务是否可用"""
        return self.client is not None

    async def upload_file(
        self, 
        file_content: bytes, 
        bucket_name: str, 
        file_path: str, 
        content_type: Optional[str] = None
    ) -> str:
        """
        上传文件到 Supabase Storage

        Args:
            file_content: 文件内容（字节）
            bucket_name: 存储桶名称
            file_path: 文件路径
            content_type: 内容类型

        Returns:
            文件的公共访问 URL

        Raises:
            Exception: 上传失败时抛出异常
        """
        if not self.is_available():
            raise Exception("Supabase Storage 客户端未初始化")

        try:
            # 选择客户端：优先使用管理员客户端进行上传
            client_to_use = self.admin_client if self.admin_client else self.client
            client_type = "admin" if self.admin_client else "anon"
            
            logger.info(f"使用{client_type}客户端上传文件: {file_path}")
            
            # 上传文件
            file_options = {}
            if content_type:
                file_options["content-type"] = content_type
                
            response = client_to_use.storage.from_(bucket_name).upload(
                path=file_path,
                file=file_content,
                file_options=file_options
            )

            if hasattr(response, 'error') and response.error:
                raise Exception(f"文件上传失败: {response.error}")

            # 获取文件的公共 URL
            file_url = client_to_use.storage.from_(bucket_name).get_public_url(file_path)
            
            logger.info(f"文件上传成功: {file_path} -> {file_url}")
            return file_url

        except Exception as e:
            logger.error(f"文件上传失败: {str(e)}")
            raise Exception(f"文件上传失败: {str(e)}")

    async def delete_file(self, bucket_name: str, file_path: str) -> bool:
        """
        删除文件

        Args:
            bucket_name: 存储桶名称
            file_path: 文件路径

        Returns:
            是否删除成功
        """
        if not self.is_available():
            logger.warning("Supabase Storage 客户端未初始化，跳过删除操作")
            return False

        try:
            response = self.client.storage.from_(bucket_name).remove([file_path])
            
            if hasattr(response, 'error') and response.error:
                logger.error(f"文件删除失败: {response.error}")
                return False

            logger.info(f"文件删除成功: {file_path}")
            return True

        except Exception as e:
            logger.error(f"文件删除失败: {str(e)}")
            return False

    async def file_exists(self, bucket_name: str, file_path: str) -> bool:
        """
        检查文件是否存在

        Args:
            bucket_name: 存储桶名称
            file_path: 文件路径

        Returns:
            文件是否存在
        """
        if not self.is_available():
            return False

        try:
            # 尝试获取文件信息
            response = self.client.storage.from_(bucket_name).list(
                path=os.path.dirname(file_path),
                search=os.path.basename(file_path)
            )
            
            if hasattr(response, 'error') and response.error:
                return False

            # 检查是否找到文件
            return len(response) > 0

        except Exception as e:
            logger.error(f"检查文件存在性失败: {str(e)}")
            return False

    async def create_bucket_if_not_exists(self, bucket_name: str) -> bool:
        """
        创建存储桶（如果不存在）

        Args:
            bucket_name: 存储桶名称

        Returns:
            是否创建成功或已存在
        """
        if not self.is_available():
            logger.warning("Supabase Storage 客户端未初始化")
            return False

        try:
            # 使用管理员客户端检查和创建存储桶
            client_to_use = self.admin_client if self.admin_client else self.client
            
            # 检查存储桶是否存在
            buckets = client_to_use.storage.list_buckets()
            
            for bucket in buckets:
                if bucket.name == bucket_name:
                    logger.info(f"存储桶 '{bucket_name}' 已存在")
                    return True

            # 尝试创建存储桶
            if self.admin_client:
                try:
                    response = self.admin_client.storage.create_bucket(
                        bucket_name,
                        options={"public": True}  # 设置为公共访问
                    )
                    
                    if hasattr(response, 'error') and response.error:
                        logger.error(f"创建存储桶失败: {response.error}")
                        return False

                    logger.info(f"存储桶 '{bucket_name}' 创建成功")
                    return True
                    
                except Exception as create_error:
                    logger.error(f"使用服务角色密钥创建存储桶失败: {str(create_error)}")
                    return False
            else:
                logger.warning(f"无服务角色密钥，无法创建存储桶 '{bucket_name}'")
                logger.warning("请手动在Supabase控制台中创建存储桶，或添加SUPABASE_SERVICE_ROLE_KEY到环境变量")
                return False

        except Exception as e:
            logger.error(f"检查存储桶失败: {str(e)}")
            return False


# 创建全局实例（延迟初始化）
supabase_storage = None

def get_supabase_storage(force_refresh=False):
    """获取Supabase存储客户端实例（延迟初始化）"""
    global supabase_storage
    if supabase_storage is None or force_refresh:
        supabase_storage = SupabaseStorageClient()
    return supabase_storage

def refresh_supabase_storage():
    """强制刷新Supabase存储客户端"""
    return get_supabase_storage(force_refresh=True)