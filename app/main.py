# app/main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import logging
import time
from pathlib import Path
import os

from .config import settings
from .api.email_routes import router as email_router
from .api.smtp_routes import router as smtp_router  # 修复：确保导入SMTP路由
from .database import engine, Base

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 创建上传目录
UPLOAD_DIR = Path("uploads")
ATTACHMENT_DIR = UPLOAD_DIR / "attachments"
TEMP_DIR = UPLOAD_DIR / "temp"

for directory in [UPLOAD_DIR, ATTACHMENT_DIR, TEMP_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# 创建FastAPI应用
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
    多租户邮件发送系统 API - 支持附件、SMTP配置管理、邮件队列等功能
    
    ## 主要功能
    - 邮件发送和管理
    - SMTP配置和密码解密（与aimachingmail项目兼容）
    - 附件上传和管理
    - 邮件队列和状态跟踪
    - 统计分析和监控
    
    ## SMTP密码解密接入
    - `/api/v1/smtp/config/{tenant_id}/default` - 获取默认SMTP配置（含解密密码）
    - `/api/v1/smtp/config/{tenant_id}/{setting_id}` - 获取特定SMTP配置
    - `/api/v1/smtp/test` - 测试SMTP连接
    - `/api/v1/smtp/password/test` - 测试加密解密功能
    
    ## 兼容性说明
    - 与aimachingmail项目使用相同的密钥派生算法（SHA256）
    - 支持多种密码存储格式（hex、base64、bytes）
    - 完全向后兼容现有的加密数据
    """,
    version="2.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 添加中间件

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# 可信主机中间件（生产环境安全）
if os.getenv("ENVIRONMENT") == "production":
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["yourdomain.com", "*.yourdomain.com"]
    )


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    # 记录请求开始
    logger.info(f"Request started: {request.method} {request.url}")

    try:
        response = await call_next(request)
        process_time = time.time() - start_time

        # 记录响应
        logger.info(
            f"Request completed: {request.method} {request.url} - "
            f"Status: {response.status_code} - Time: {process_time:.3f}s"
        )

        # 添加响应头
        response.headers["X-Process-Time"] = str(process_time)
        return response

    except Exception as e:
        process_time = time.time() - start_time
        logger.error(
            f"Request failed: {request.method} {request.url} - "
            f"Error: {str(e)} - Time: {process_time:.3f}s"
        )
        raise


# 文件大小限制中间件
@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    if request.method == "POST" and "multipart/form-data" in request.headers.get(
        "content-type", ""
    ):
        content_length = request.headers.get("content-length")
        if content_length:
            content_length = int(content_length)
            # 限制总请求大小为100MB（包括多个文件）
            max_size = 100 * 1024 * 1024
            if content_length > max_size:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"请求体过大，最大允许100MB，当前: {content_length/1024/1024:.2f}MB"
                    },
                )

    response = await call_next(request)
    return response


# 静态文件服务（用于提供上传的附件下载）
if UPLOAD_DIR.exists():
    app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# 异常处理器


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证错误"""
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422, content={"detail": "请求参数验证失败", "errors": exc.errors()}
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """处理HTTP异常"""
    logger.error(f"HTTP exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """处理一般异常"""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误", "message": "请稍后重试或联系管理员"},
    )


# 包含路由
app.include_router(
    email_router, prefix=f"{settings.API_V1_STR}/email", tags=["邮件服务"]
)

# 修复：确保包含SMTP密码解密API路由
app.include_router(
    smtp_router, prefix=f"{settings.API_V1_STR}/smtp", tags=["SMTP配置与解密"]
)

# 根路径和健康检查


@app.get("/", tags=["系统"])
async def root():
    """API根路径"""
    return {
        "message": "邮件发送API服务正在运行",
        "version": "2.0.0",
        "compatibility": "与aimachingmail项目完全兼容",
        "features": [
            "SMTP配置管理",
            "单发/群发邮件",
            "附件支持",
            "邮件队列管理",
            "发送状态跟踪",
            "多租户支持",
            "SMTP密码解密接入（兼容aimachingmail）",
        ],
        "api_endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "email_api": f"{settings.API_V1_STR}/email",
            "smtp_api": f"{settings.API_V1_STR}/smtp",
        },
        "smtp_decryption": {
            "guide": f"{settings.API_V1_STR}/smtp/usage/guide",
            "test": f"{settings.API_V1_STR}/smtp/password/test",
            "health": f"{settings.API_V1_STR}/smtp/health",
        },
    }


@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查"""
    try:
        # 检查数据库连接
        from .database import SessionLocal

        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()

        # 检查上传目录
        upload_accessible = ATTACHMENT_DIR.exists() and os.access(
            ATTACHMENT_DIR, os.W_OK
        )

        # 检查SMTP密码解密功能
        from .utils.security import smtp_password_manager

        encryption_test = smtp_password_manager.test_encryption()

        return {
            "status": "healthy",
            "timestamp": time.time(),
            "compatibility": "aimachingmail项目兼容",
            "services": {
                "database": "connected",
                "file_storage": "accessible" if upload_accessible else "error",
                "smtp_encryption": "working" if encryption_test else "error",
            },
            "upload_directories": {
                "attachments": str(ATTACHMENT_DIR),
                "temp": str(TEMP_DIR),
            },
            "smtp_decryption": {
                "status": "available",
                "compatible_with": "aimachingmail",
                "encryption_method": "Fernet with SHA256 key derivation",
                "test_endpoint": f"{settings.API_V1_STR}/smtp/password/test",
            },
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time(),
                "suggestion": "检查数据库连接和ENCRYPTION_KEY配置",
            },
        )


@app.get("/info", tags=["系统"])
async def system_info():
    """系统信息"""
    import sys
    import platform

    return {
        "application": {
            "name": settings.PROJECT_NAME,
            "version": "2.0.0",
            "api_version": settings.API_V1_STR,
            "compatibility": "与aimachingmail项目完全兼容",
        },
        "system": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "architecture": platform.architecture(),
        },
        "configuration": {
            "cors_origins": settings.BACKEND_CORS_ORIGINS,
            "upload_directory": str(ATTACHMENT_DIR),
            "max_file_size": "25MB",
            "max_attachments_per_email": 10,
        },
        "smtp_features": {
            "password_encryption": "Fernet (AES 128)",
            "key_derivation": "SHA256 (与aimachingmail一致)",
            "supported_protocols": ["TLS", "SSL", "None"],
            "decryption_api": "Available",
            "api_prefix": f"{settings.API_V1_STR}/smtp",
            "compatibility_tested": True,
        },
    }


@app.get("/limits", tags=["系统"])
async def get_system_limits():
    """获取系统限制信息"""
    return {
        "file_upload": {
            "max_file_size": "25MB",
            "max_files_per_request": 10,
            "max_total_request_size": "100MB",
            "supported_extensions": [
                ".pdf",
                ".doc",
                ".docx",
                ".xls",
                ".xlsx",
                ".ppt",
                ".pptx",
                ".jpg",
                ".jpeg",
                ".png",
                ".gif",
                ".bmp",
                ".svg",
                ".zip",
                ".rar",
                ".7z",
                ".txt",
                ".csv",
                ".json",
            ],
            "forbidden_extensions": [
                ".exe",
                ".bat",
                ".cmd",
                ".scr",
                ".pif",
                ".com",
                ".vbs",
                ".js",
            ],
        },
        "email_sending": {
            "max_recipients_per_email": 100,
            "max_bulk_emails": 1000,
            "max_retry_attempts": 3,
            "supported_protocols": ["TLS", "SSL", "None"],
        },
        "storage": {
            "attachment_retention_hours": 24,
            "auto_cleanup_enabled": True,
            "max_storage_per_tenant": "1GB",
        },
        "smtp_decryption": {
            "encryption_algorithm": "Fernet (AES 128)",
            "key_derivation": "SHA256 (与aimachingmail一致)",
            "supported_formats": ["hex", "base64", "bytes"],
            "api_rate_limit": "No limit (configure as needed)",
            "compatibility": "aimachingmail项目完全兼容",
        },
    }


# SMTP密码解密快速访问端点
@app.get("/smtp-info", tags=["系统"], summary="SMTP解密接入信息")
async def smtp_decryption_info():
    """SMTP密码解密接入信息"""
    return {
        "title": "SMTP密码解密接入",
        "description": "为外部系统提供SMTP配置和密码解密服务",
        "compatibility": {
            "projects": ["aimachingmail"],
            "encryption": "Fernet with SHA256 key derivation",
            "formats": ["hex", "base64", "bytes"],
        },
        "api_base": f"{settings.API_V1_STR}/smtp",
        "key_endpoints": {
            "get_default_config": f"{settings.API_V1_STR}/smtp/config/{{tenant_id}}/default",
            "get_config_by_id": f"{settings.API_V1_STR}/smtp/config/{{tenant_id}}/{{setting_id}}",
            "test_connection": f"{settings.API_V1_STR}/smtp/test",
            "test_encryption": f"{settings.API_V1_STR}/smtp/password/test",
            "health_check": f"{settings.API_V1_STR}/smtp/health",
            "usage_guide": f"{settings.API_V1_STR}/smtp/usage/guide",
        },
        "security": {
            "encryption": "Fernet对称加密",
            "key_derivation": "SHA256哈希（与aimachingmail一致）",
            "key_required": "ENCRYPTION_KEY环境变量",
            "password_format": "支持多种格式（hex/base64/bytes）",
        },
        "integration_steps": [
            "1. 确保与aimachingmail使用相同的ENCRYPTION_KEY",
            "2. 调用配置API获取SMTP设置",
            "3. 使用返回的明文密码进行SMTP连接",
            "4. 可选：调用测试接口验证连接",
            "5. 使用健康检查接口监控状态",
        ],
        "troubleshooting": [
            "检查ENCRYPTION_KEY是否与aimachingmail项目一致",
            "使用/smtp/password/test验证加密解密功能",
            "查看应用日志获取详细错误信息",
            "确认数据库中的密码格式",
        ],
        "documentation": "/docs#/SMTP配置与解密",
    }


# 快速测试端点
@app.get("/quick-test", tags=["系统"], summary="快速功能测试")
async def quick_test():
    """快速测试系统核心功能"""
    results = {}

    try:
        # 测试数据库连接
        from .database import SessionLocal

        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        results["database"] = "✅ 连接正常"
    except Exception as e:
        results["database"] = f"❌ 连接失败: {str(e)}"

    try:
        # 测试加密解密
        from .utils.security import smtp_password_manager

        test_result = smtp_password_manager.test_encryption()
        results["encryption"] = "✅ 加密解密正常" if test_result else "❌ 加密解密失败"
    except Exception as e:
        results["encryption"] = f"❌ 加密测试失败: {str(e)}"

    try:
        # 测试文件存储
        upload_accessible = ATTACHMENT_DIR.exists() and os.access(
            ATTACHMENT_DIR, os.W_OK
        )
        results["file_storage"] = (
            "✅ 文件存储正常" if upload_accessible else "❌ 文件存储不可用"
        )
    except Exception as e:
        results["file_storage"] = f"❌ 文件存储测试失败: {str(e)}"

    return {
        "status": "success",
        "message": "快速测试完成",
        "results": results,
        "timestamp": time.time(),
        "recommendations": [
            "如果有❌项目，请检查对应的配置",
            "确保ENCRYPTION_KEY与aimachingmail项目一致",
            "查看完整健康检查：/health",
            "查看SMTP专门测试：/api/v1/smtp/health",
        ],
    }


# 启动事件
@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    logger.info("邮件API服务启动...")
    logger.info(f"上传目录: {ATTACHMENT_DIR}")
    logger.info(f"API文档: http://localhost:8000/docs")
    logger.info(f"SMTP解密API: http://localhost:8000{settings.API_V1_STR}/smtp")
    logger.info("兼容性: 与aimachingmail项目完全兼容")

    # 确保必要的目录存在
    for directory in [ATTACHMENT_DIR, TEMP_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"确保目录存在: {directory}")

    # 测试SMTP密码加密功能
    try:
        from .utils.security import smtp_password_manager

        test_result = smtp_password_manager.test_encryption()
        logger.info(f"SMTP密码加密功能测试: {'正常' if test_result else '异常'}")

        if test_result:
            logger.info("✅ 加密解密功能正常，与aimachingmail项目兼容")
        else:
            logger.warning("⚠️ 加密解密功能异常，请检查ENCRYPTION_KEY配置")

    except Exception as e:
        logger.error(f"SMTP密码加密功能测试失败: {str(e)}")
        logger.error("❌ 请检查ENCRYPTION_KEY配置是否与aimachingmail项目一致")

    # 输出重要信息
    logger.info("=" * 60)
    logger.info("🚀 邮件API服务启动完成")
    logger.info(f"📖 API文档: http://localhost:8000/docs")
    logger.info(f"🔐 SMTP解密: http://localhost:8000{settings.API_V1_STR}/smtp")
    logger.info(f"🩺 健康检查: http://localhost:8000/health")
    logger.info(f"⚡ 快速测试: http://localhost:8000/quick-test")
    logger.info("🔗 兼容性: 与aimachingmail项目完全兼容")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行"""
    logger.info("邮件API服务正在关闭...")

    # 这里可以添加清理逻辑
    # 例如：清理临时文件、关闭数据库连接等


# 开发环境热重载支持
if __name__ == "__main__":
    import uvicorn

    # 开发环境配置
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app"],
        log_level="info",
        access_log=True,
    )

# 生产环境部署示例：
# uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
