# app/api/__init__.py
"""
API路由模块

包含系统的所有API路由定义。

路由列表：
- email_routes: 邮件相关API路由
"""

from .email_routes import router as email_router

# 导出所有路由
__all__ = ["email_router"]

# API版本信息
API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"

# 路由注册表
ROUTE_REGISTRY = {
    "email": {
        "router": email_router,
        "prefix": f"{API_PREFIX}/email",
        "tags": ["邮件服务"],
        "description": "邮件发送和管理相关接口",
    }
}


# 路由统计信息
def get_route_stats():
    """获取路由统计信息"""
    stats = {}
    for name, config in ROUTE_REGISTRY.items():
        router = config["router"]
        routes = [route for route in router.routes if hasattr(route, "methods")]

        stats[name] = {
            "total_routes": len(routes),
            "methods": {},
            "paths": [route.path for route in routes],
        }

        # 统计HTTP方法
        for route in routes:
            for method in route.methods:
                if method not in stats[name]["methods"]:
                    stats[name]["methods"][method] = 0
                stats[name]["methods"][method] += 1

    return stats


# 健康检查路由配置
HEALTH_CHECK_CONFIG = {
    "path": "/health",
    "description": "系统健康检查",
    "response_model": dict,
}

# API限制配置
API_LIMITS = {
    "rate_limit": {"requests_per_minute": 60, "burst_limit": 100},
    "file_upload": {
        "max_file_size": 25 * 1024 * 1024,  # 25MB
        "max_files_per_request": 10,
        "allowed_extensions": [
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
    },
    "email": {
        "max_recipients": 100,
        "max_bulk_emails": 1000,
        "max_subject_length": 255,
        "max_body_length": 1024 * 1024,  # 1MB
    },
}

# 错误码定义
ERROR_CODES = {
    # 通用错误
    1000: "未知错误",
    1001: "参数验证失败",
    1002: "权限不足",
    1003: "资源不存在",
    1004: "请求过于频繁",
    # SMTP相关错误
    2001: "SMTP配置不存在",
    2002: "SMTP连接失败",
    2003: "SMTP认证失败",
    2004: "SMTP发送失败",
    # 邮件相关错误
    3001: "收件人列表为空",
    3002: "邮件内容为空",
    3003: "邮件发送失败",
    3004: "邮件队列已满",
    # 附件相关错误
    4001: "文件上传失败",
    4002: "文件类型不支持",
    4003: "文件大小超限",
    4004: "附件不存在",
    4005: "文件病毒扫描失败",
    # 数据库相关错误
    5001: "数据库连接失败",
    5002: "数据查询失败",
    5003: "数据保存失败",
    5004: "数据删除失败",
}
