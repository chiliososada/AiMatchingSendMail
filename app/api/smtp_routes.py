# app/api/smtp_routes.py
"""
SMTP密码解密接入API路由 - 修复版
为外部系统提供SMTP配置和密码解密接口，与aimachingmail项目完全兼容
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
from datetime import datetime

from ..database import get_db
from ..services.email_service import EmailService
from ..utils.security import smtp_password_manager, test_smtp_password_encryption
from ..schemas.email_schemas import SMTPSettingsCreate, SMTPSettingsResponse
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)
router = APIRouter()


# ==================== 请求/响应模型 ====================


class SMTPConfigResponse(BaseModel):
    """SMTP配置响应（包含解密密码）"""

    id: str
    tenant_id: str
    setting_name: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str  # 解密后的明文密码
    security_protocol: str
    from_email: str
    from_name: Optional[str] = None
    reply_to_email: Optional[str] = None
    daily_send_limit: int
    hourly_send_limit: int
    is_default: bool
    is_active: bool
    connection_status: str
    last_test_at: Optional[str] = None
    created_at: Optional[str] = None


class SMTPTestRequest(BaseModel):
    """SMTP连接测试请求"""

    tenant_id: UUID
    setting_id: UUID


class PasswordDecryptRequest(BaseModel):
    """密码解密请求"""

    encrypted_password: str


class PasswordEncryptRequest(BaseModel):
    """密码加密请求"""

    plain_password: str


class SMTPListResponse(BaseModel):
    """SMTP配置列表响应"""

    total_count: int
    configs: List[SMTPConfigResponse]


# ==================== API 端点 ====================


@router.get("/config/{tenant_id}/default", response_model=SMTPConfigResponse)
def get_default_smtp_config(tenant_id: UUID, db: Session = Depends(get_db)):
    """
    获取租户的默认SMTP配置（包含解密密码）

    此接口提供给其他系统使用，返回可直接用于SMTP连接的配置信息
    """
    try:
        email_service = EmailService(db)
        config_info = email_service.get_smtp_config_info(tenant_id, None)

        if not config_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"租户 {tenant_id} 未找到可用的SMTP配置",
            )

        logger.info(f"成功返回默认SMTP配置: {config_info['setting_name']}")
        return SMTPConfigResponse(**config_info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取默认SMTP配置失败: {str(e)}")
        import traceback

        logger.error(f"详细错误信息: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取SMTP配置失败: {str(e)}",
        )


@router.get("/config/{tenant_id}/{setting_id}", response_model=SMTPConfigResponse)
def get_smtp_config_by_id(
    tenant_id: UUID, setting_id: UUID, db: Session = Depends(get_db)
):
    """
    根据ID获取特定的SMTP配置（包含解密密码）

    此接口提供给其他系统使用，返回可直接用于SMTP连接的配置信息
    """
    try:
        email_service = EmailService(db)
        config_info = email_service.get_smtp_config_info(tenant_id, setting_id)

        if not config_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到SMTP配置 (tenant: {tenant_id}, setting: {setting_id})",
            )

        logger.info(f"成功返回SMTP配置: {config_info['setting_name']}")
        return SMTPConfigResponse(**config_info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取SMTP配置失败: {str(e)}")
        import traceback

        logger.error(f"详细错误信息: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取SMTP配置失败: {str(e)}",
        )


@router.get("/configs/{tenant_id}", response_model=SMTPListResponse)
def get_smtp_configs_list(
    tenant_id: UUID,
    include_password: bool = Query(False, description="是否包含解密后的密码"),
    db: Session = Depends(get_db),
):
    """
    获取租户的所有SMTP配置列表

    Args:
        tenant_id: 租户ID
        include_password: 是否包含解密后的密码（默认不包含，出于安全考虑）
    """
    try:
        email_service = EmailService(db)
        smtp_settings_list = email_service.get_smtp_settings_list(tenant_id)

        configs = []
        for settings in smtp_settings_list:
            if include_password:
                # 包含解密密码
                config_info = email_service.get_smtp_config_info(tenant_id, settings.id)
                if config_info:
                    configs.append(SMTPConfigResponse(**config_info))
            else:
                # 不包含密码
                config_data = {
                    "id": str(settings.id),
                    "tenant_id": str(settings.tenant_id),
                    "setting_name": settings.setting_name,
                    "smtp_host": settings.smtp_host,
                    "smtp_port": settings.smtp_port,
                    "smtp_username": settings.smtp_username,
                    "smtp_password": "***",  # 隐藏密码
                    "security_protocol": settings.security_protocol,
                    "from_email": settings.from_email,
                    "from_name": settings.from_name,
                    "reply_to_email": settings.reply_to_email,
                    "daily_send_limit": settings.daily_send_limit,
                    "hourly_send_limit": settings.hourly_send_limit,
                    "is_default": settings.is_default,
                    "is_active": settings.is_active,
                    "connection_status": settings.connection_status,
                    "last_test_at": (
                        settings.last_test_at.isoformat()
                        if settings.last_test_at
                        else None
                    ),
                    "created_at": (
                        settings.created_at.isoformat() if settings.created_at else None
                    ),
                }
                configs.append(SMTPConfigResponse(**config_data))

        return SMTPListResponse(total_count=len(configs), configs=configs)

    except Exception as e:
        logger.error(f"获取SMTP配置列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取SMTP配置列表失败: {str(e)}",
        )


@router.post("/config", response_model=SMTPConfigResponse)
def create_smtp_config(config_data: SMTPSettingsCreate, db: Session = Depends(get_db)):
    """
    创建新的SMTP配置

    此接口会自动加密密码并存储，返回包含解密密码的配置信息
    """
    try:
        email_service = EmailService(db)
        smtp_settings = email_service.create_smtp_settings(config_data)

        # 返回包含解密密码的配置信息
        config_info = email_service.get_smtp_config_info(
            config_data.tenant_id, smtp_settings.id
        )

        if not config_info:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="配置创建成功但获取配置信息失败",
            )

        return SMTPConfigResponse(**config_info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建SMTP配置失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建SMTP配置失败: {str(e)}",
        )


@router.post("/test")
async def test_smtp_connection(
    test_request: SMTPTestRequest, db: Session = Depends(get_db)
):
    """
    测试SMTP连接

    此接口会使用解密后的密码测试SMTP连接
    """
    try:
        logger.info(
            f"开始测试SMTP连接: tenant_id={test_request.tenant_id}, setting_id={test_request.setting_id}"
        )

        email_service = EmailService(db)
        result = await email_service.test_smtp_connection(
            test_request.tenant_id, test_request.setting_id
        )

        logger.info(f"SMTP连接测试完成: {result['status']}")
        return result

    except Exception as e:
        logger.error(f"SMTP连接测试失败: {str(e)}")
        import traceback

        logger.error(f"详细错误信息: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SMTP连接测试失败: {str(e)}",
        )


# ==================== 密码加密解密工具接口 ====================


@router.post("/password/decrypt")
def decrypt_password(request: PasswordDecryptRequest):
    """
    解密SMTP密码（工具接口）

    此接口仅用于调试和工具使用，生产环境应谨慎使用
    """
    try:
        decrypted = smtp_password_manager.decrypt(request.encrypted_password)
        return {
            "status": "success",
            "decrypted_password": decrypted,
            "message": "密码解密成功",
        }
    except Exception as e:
        logger.error(f"密码解密失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"密码解密失败: {str(e)}"
        )


@router.post("/password/encrypt")
def encrypt_password(request: PasswordEncryptRequest):
    """
    加密SMTP密码（工具接口）

    此接口用于生成加密后的密码，可用于直接插入数据库
    """
    try:
        encrypted = smtp_password_manager.encrypt(request.plain_password)
        return {
            "status": "success",
            "encrypted_password": encrypted,
            "message": "密码加密成功",
        }
    except Exception as e:
        logger.error(f"密码加密失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"密码加密失败: {str(e)}"
        )


@router.get("/password/test")
def test_password_encryption():
    """
    测试密码加密解密功能

    此接口用于验证加密解密功能是否正常工作
    """
    try:
        test_result = test_smtp_password_encryption()
        return test_result
    except Exception as e:
        logger.error(f"密码加密测试失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"密码加密测试失败: {str(e)}",
        )


# ==================== 系统信息接口 ====================


@router.get("/system/info")
def get_system_info():
    """
    获取系统信息

    包含加密密钥信息和系统状态
    """
    try:
        key_info = smtp_password_manager.get_key_info()
        return {
            "status": "active",
            "encryption_info": key_info,
            "supported_protocols": ["TLS", "SSL", "None"],
            "api_version": "v1",
            "compatible_with": "aimachingmail",
            "encryption_method": "Fernet with SHA256 key derivation",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"获取系统信息失败: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@router.get("/health")
def health_check():
    """
    健康检查接口

    检查SMTP密码解密功能是否正常
    """
    try:
        # 测试加密解密功能
        test_result = smtp_password_manager.test_encryption()

        return {
            "status": "healthy" if test_result else "unhealthy",
            "encryption_test": test_result,
            "compatible_with": "aimachingmail",
            "encryption_method": "Fernet with SHA256 key derivation",
            "timestamp": datetime.utcnow().isoformat(),
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


# ==================== 使用说明接口 ====================


@router.get("/usage/guide")
def get_usage_guide():
    """
    获取使用指南

    提供API使用说明和示例
    """
    return {
        "title": "SMTP密码解密接入API使用指南",
        "version": "v1.0",
        "compatibility": "与aimachingmail项目完全兼容",
        "base_url": "/api/v1/smtp",
        "encryption_info": {
            "algorithm": "Fernet对称加密",
            "key_derivation": "SHA256哈希（与aimachingmail一致）",
            "format": "Base64编码的加密数据",
        },
        "endpoints": {
            "get_default_config": {
                "url": "GET /config/{tenant_id}/default",
                "description": "获取租户默认SMTP配置（含解密密码）",
                "example": "GET /config/33723dd6-cf28-4dab-975c-f883f5389d04/default",
            },
            "get_config_by_id": {
                "url": "GET /config/{tenant_id}/{setting_id}",
                "description": "获取特定SMTP配置（含解密密码）",
                "example": "GET /config/33723dd6-cf28-4dab-975c-f883f5389d04/12345678-1234-1234-1234-123456789abc",
            },
            "list_configs": {
                "url": "GET /configs/{tenant_id}?include_password=true",
                "description": "获取所有SMTP配置列表",
                "example": "GET /configs/33723dd6-cf28-4dab-975c-f883f5389d04?include_password=true",
            },
            "test_connection": {
                "url": "POST /test",
                "description": "测试SMTP连接",
                "body": {
                    "tenant_id": "33723dd6-cf28-4dab-975c-f883f5389d04",
                    "setting_id": "12345678-1234-1234-1234-123456789abc",
                },
            },
        },
        "authentication": {
            "type": "API Key",
            "header": "Authorization: Bearer your-api-key",
            "note": "生产环境需要配置适当的认证机制",
        },
        "response_format": {
            "success": {"status": "success", "data": "响应数据"},
            "error": {"detail": "错误描述", "status_code": "HTTP状态码"},
        },
        "important_notes": [
            "与aimachingmail项目使用相同的加密算法（SHA256派生密钥）",
            "所有密码都使用Fernet加密算法加密存储",
            "返回的明文密码仅用于SMTP连接，请妥善保护",
            "建议在网络层面限制API访问权限",
            "定期更换加密密钥以提高安全性",
            "确保两个项目使用相同的ENCRYPTION_KEY环境变量",
        ],
        "troubleshooting": [
            "如果解密失败，请检查ENCRYPTION_KEY是否与aimachingmail项目一致",
            "使用/smtp/password/test接口验证加密解密功能",
            "使用/smtp/health接口检查系统状态",
            "查看应用日志获取详细错误信息",
        ],
    }


# ==================== 错误处理 ====================


@router.get("/errors/codes")
def get_error_codes():
    """
    获取错误代码说明
    """
    return {
        "error_codes": {
            "404": "资源不存在 - SMTP配置未找到",
            "400": "请求参数错误 - 检查输入数据格式",
            "500": "服务器内部错误 - 检查服务器日志",
            "503": "服务不可用 - 检查加密密钥配置",
        },
        "common_issues": {
            "encryption_key_missing": "ENCRYPTION_KEY环境变量未设置",
            "encryption_key_invalid": "加密密钥格式错误或损坏",
            "key_derivation_mismatch": "密钥派生算法与aimachingmail不一致",
            "database_connection_failed": "数据库连接失败",
            "smtp_config_not_found": "SMTP配置不存在或已删除",
            "password_format_error": "数据库中的密码格式不被识别",
        },
        "troubleshooting": {
            "check_logs": "查看应用日志文件获取详细错误信息",
            "verify_keys": "使用 /smtp/password/test 验证加密功能",
            "health_check": "使用 /smtp/health 检查系统状态",
            "compare_keys": "确保与aimachingmail使用相同的ENCRYPTION_KEY",
            "test_encryption": "使用加密/解密工具接口测试密码处理",
        },
    }
