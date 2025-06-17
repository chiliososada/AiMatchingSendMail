# app/main.py - asyncpg版本
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
import asyncio

from .config import settings
from .api.email_routes import router as email_router
from .api.smtp_routes import router as smtp_router
from .database import db_manager, health_check as db_health_check
from .api.ai_matching_routes import router as ai_matching_router
from .api.resume_parser_routes import router as resume_parser_router


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

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
    
    ## 数据库
    - 使用asyncpg连接池提供高性能异步数据库访问
    - 支持连接池管理和自动重连
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

app.include_router(
    smtp_router, prefix=f"{settings.API_V1_STR}/smtp", tags=["SMTP配置与解密"]
)
app.include_router(
    ai_matching_router, prefix=f"{settings.API_V1_STR}/ai-matching", tags=["AI智能匹配"]
)
app.include_router(
    resume_parser_router,
    prefix=f"{settings.API_V1_STR}/resume-parser",
    tags=["简历解析"],
)

# 根路径和健康检查


@app.get("/", tags=["系统"])
async def root():
    """API根路径"""
    return {
        "message": "邮件发送API服务正在运行",
        "version": "2.0.0",
        "database": "asyncpg连接池",
        "compatibility": "与aimachingmail项目完全兼容",
        "features": [
            "SMTP配置管理",
            "单发/群发邮件",
            "附件支持",
            "邮件队列管理",
            "发送状态跟踪",
            "多租户支持",
            "SMTP密码解密接入（兼容aimachingmail）",
            "高性能异步数据库访问",
            "AI智能匹配系统",  # 新增
            "案件简历智能推荐",  # 新增
            "多维度匹配算法",  # 新增
            "简历解析服务",  # 新增
            "支持Excel格式简历解析",  # 新增
            "批量简历处理",  # 新增
        ],
        "api_endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "email_api": f"{settings.API_V1_STR}/email",
            "smtp_api": f"{settings.API_V1_STR}/smtp",
            "ai_matching_api": f"{settings.API_V1_STR}/ai-matching",  # 新增
        },
        "ai_matching_features": {  # 新增
            "project_to_engineers": f"{settings.API_V1_STR}/ai-matching/project-to-engineers",
            "engineer_to_projects": f"{settings.API_V1_STR}/ai-matching/engineer-to-projects",
            "bulk_matching": f"{settings.API_V1_STR}/ai-matching/bulk-matching",
            "matching_history": f"{settings.API_V1_STR}/ai-matching/history",
            "system_info": f"{settings.API_V1_STR}/ai-matching/system/info",
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
        # 检查数据库连接池
        db_health = await db_health_check()

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
            "database": "asyncpg连接池",
            "compatibility": "aimachingmail项目兼容",
            "services": {
                "database_pool": db_health.get("status", "unknown"),
                "file_storage": "accessible" if upload_accessible else "error",
                "smtp_encryption": "working" if encryption_test else "error",
            },
            "database_info": db_health.get("database_info", {}),
            "connection_pool": db_health.get("connection_pool", {}),
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
                "suggestion": "检查数据库连接池和ENCRYPTION_KEY配置",
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
            "database": "asyncpg连接池",
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
            "database_pool_size": settings.DATABASE_POOL_SIZE,
            "database_max_overflow": settings.DATABASE_MAX_OVERFLOW,
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


@app.get("/quick-test", tags=["系统"], summary="快速功能测试")
async def quick_test():
    """快速测试系统核心功能"""
    results = {}

    try:
        # 测试数据库连接池
        from .database import check_database_connection

        db_connected = await check_database_connection()
        results["database"] = "✅ 连接池正常" if db_connected else "❌ 连接池失败"
    except Exception as e:
        results["database"] = f"❌ 连接池测试失败: {str(e)}"

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
        "database_type": "asyncpg连接池",
        "results": results,
        "timestamp": time.time(),
        "recommendations": [
            "如果有❌项目，请检查对应的配置",
            "确保ENCRYPTION_KEY与aimachingmail项目一致",
            "查看完整健康检查：/health",
            "查看SMTP专门测试：/api/v1/smtp/health",
            "数据库连接池状态：/health",
        ],
    }


# 启动和关闭事件
@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    logger.info("邮件API服务启动...")
    logger.info("数据库类型: asyncpg连接池")
    logger.info(f"上传目录: {ATTACHMENT_DIR}")
    logger.info(f"API文档: http://localhost:8000/docs")
    logger.info(f"SMTP解密API: http://localhost:8000{settings.API_V1_STR}/smtp")
    logger.info("兼容性: 与aimachingmail项目完全兼容")

    # 确保必要的目录存在
    for directory in [ATTACHMENT_DIR, TEMP_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"确保目录存在: {directory}")

    # 初始化数据库连接池
    try:
        await db_manager.initialize()
        logger.info("✅ 数据库连接池初始化成功")
    except Exception as e:
        logger.error(f"❌ 数据库连接池初始化失败: {str(e)}")
        raise

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
    logger.info("🗄️  数据库: asyncpg连接池（高性能异步访问）")
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

    # 关闭数据库连接池
    try:
        await db_manager.close()
        logger.info("✅ 数据库连接池已关闭")
    except Exception as e:
        logger.error(f"❌ 关闭数据库连接池失败: {str(e)}")

    logger.info("邮件API服务已关闭")


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
