# app/api/ai_matching_routes.py - 修复版
from fastapi import APIRouter, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
from datetime import datetime

# 修复导入 - 使用新的拆分后的服务
from ..services.ai_matching_service import AIMatchingService
from ..services.ai_matching_database import AIMatchingDatabase
from ..schemas.ai_matching_schemas import (
    ProjectToEngineersMatchRequest,
    EngineerToProjectsMatchRequest,
    BulkMatchingRequest,
    ProjectToEngineersResponse,
    EngineerToProjectsResponse,
    BulkMatchingResponse,
    MatchingHistoryResponse,
    MatchResult,
    MatchingStatsRequest,
    MatchingStatsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# 创建AI匹配服务实例 - 修复版
try:
    ai_matching_service = AIMatchingService()
    ai_matching_db = AIMatchingDatabase()
    logger.info("AI匹配服务初始化成功")
except Exception as e:
    logger.error(f"AI匹配服务初始化失败: {str(e)}")
    ai_matching_service = None
    ai_matching_db = None


# ==================== 核心匹配API ====================


@router.post("/project-to-engineers", response_model=ProjectToEngineersResponse)
async def match_project_to_engineers(
    request: ProjectToEngineersMatchRequest, background_tasks: BackgroundTasks
):
    """
    案件匹配简历API - 简化版（仅使用AI相似度）
    """
    try:
        if not ai_matching_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI匹配服务未初始化",
            )

        logger.info(f"收到案件匹配简历请求: project_id={request.project_id}")

        # 验证案件是否存在
        from ..database import fetch_one

        project_exists = await fetch_one(
            "SELECT id FROM projects WHERE id = $1 AND tenant_id = $2 AND is_active = true",
            request.project_id,
            request.tenant_id,
        )

        if not project_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"案件不存在或已删除: {request.project_id}",
            )

        # 执行匹配
        result = await ai_matching_service.match_project_to_engineers(request)

        logger.info(f"案件匹配完成: 生成 {result.total_matches} 个匹配")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"案件匹配简历失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"匹配处理失败: {str(e)}",
        )


@router.post("/engineer-to-projects", response_model=EngineerToProjectsResponse)
async def match_engineer_to_projects(
    request: EngineerToProjectsMatchRequest, background_tasks: BackgroundTasks
):
    """
    简历匹配案件API - 简化版（仅使用AI相似度）
    """
    try:
        if not ai_matching_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI匹配服务未初始化",
            )

        logger.info(f"收到简历匹配案件请求: engineer_id={request.engineer_id}")

        # 验证简历是否存在
        from ..database import fetch_one

        engineer_exists = await fetch_one(
            "SELECT id FROM engineers WHERE id = $1 AND tenant_id = $2 AND is_active = true",
            request.engineer_id,
            request.tenant_id,
        )

        if not engineer_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"简历不存在或已删除: {request.engineer_id}",
            )

        # 执行匹配
        result = await ai_matching_service.match_engineer_to_projects(request)

        logger.info(f"简历匹配完成: 生成 {result.total_matches} 个匹配")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"简历匹配案件失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"匹配处理失败: {str(e)}",
        )


@router.post("/bulk-matching", response_model=BulkMatchingResponse)
async def bulk_matching(
    request: BulkMatchingRequest, background_tasks: BackgroundTasks
):
    """
    批量匹配API - 简化版（仅使用AI相似度）
    """
    try:
        if not ai_matching_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI匹配服务未初始化",
            )

        logger.info("收到批量匹配请求")

        # 验证请求参数
        if request.project_ids is not None and len(request.project_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="project_ids不能为空列表，请传入None或有效的ID列表",
            )

        if request.engineer_ids is not None and len(request.engineer_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="engineer_ids不能为空列表，请传入None或有效的ID列表",
            )

        # 执行批量匹配
        result = await ai_matching_service.bulk_matching(request)

        logger.info(f"批量匹配完成: 生成 {result.total_matches} 个匹配")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量匹配失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量匹配处理失败: {str(e)}",
        )


# ==================== 匹配历史管理 ====================


@router.get("/history/{tenant_id}", response_model=List[MatchingHistoryResponse])
async def get_matching_history(
    tenant_id: UUID,
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    matching_type: Optional[str] = Query(None, description="匹配类型筛选"),
):
    """获取匹配历史记录"""
    try:
        if not ai_matching_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI匹配服务未初始化",
            )

        histories = await ai_matching_service.get_matching_history(
            tenant_id=tenant_id, limit=limit
        )

        # 按匹配类型筛选
        if matching_type:
            histories = [h for h in histories if h.matching_type == matching_type]

        return histories

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取匹配历史失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取历史记录失败: {str(e)}",
        )


@router.get("/history/{tenant_id}/{history_id}", response_model=MatchingHistoryResponse)
async def get_matching_history_detail(tenant_id: UUID, history_id: UUID):
    """获取特定匹配历史详情"""
    try:
        if not ai_matching_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI匹配服务未初始化",
            )

        histories = await ai_matching_service.get_matching_history(
            tenant_id=tenant_id, history_id=history_id
        )

        if not histories:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"匹配历史不存在: {history_id}",
            )

        return histories[0]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取匹配历史详情失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取历史详情失败: {str(e)}",
        )


@router.get("/matches/{tenant_id}/{history_id}", response_model=List[MatchResult])
async def get_matches_by_history(
    tenant_id: UUID,
    history_id: UUID,
    limit: int = Query(100, ge=1, le=500, description="返回数量限制"),
    min_score: float = Query(0.0, ge=0.0, le=1.0, description="最小分数筛选"),
):
    """根据历史ID获取匹配结果"""
    try:
        if not ai_matching_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI匹配服务未初始化",
            )

        matches = await ai_matching_service.get_matches_by_history(
            history_id=history_id, tenant_id=tenant_id, limit=limit
        )

        # 按最小分数筛选
        if min_score > 0.0:
            matches = [m for m in matches if m.match_score >= min_score]

        return matches

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取匹配结果失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取匹配结果失败: {str(e)}",
        )


# ==================== 匹配结果管理 ====================


@router.put("/matches/{tenant_id}/{match_id}/status")
async def update_match_status(
    tenant_id: UUID,
    match_id: UUID,
    status: str = Query(..., description="新状态"),
    comment: Optional[str] = Query(None, description="备注"),
    reviewed_by: Optional[UUID] = Query(None, description="审核人ID"),
):
    """更新匹配状态"""
    try:
        if not ai_matching_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI匹配服务未初始化",
            )

        success = await ai_matching_service.update_match_status(
            match_id=match_id,
            tenant_id=tenant_id,
            status=status,
            comment=comment,
            reviewed_by=reviewed_by,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="匹配记录不存在或更新失败"
            )

        return {
            "status": "success",
            "message": "匹配状态更新成功",
            "match_id": str(match_id),
            "new_status": status,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新匹配状态失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"状态更新失败: {str(e)}",
        )


# ==================== 系统信息接口 ====================


@router.get("/system/info")
async def get_ai_matching_system_info():
    """获取AI匹配系统信息"""
    try:
        return {
            "service": "AI匹配服务",
            "version": "2.0.0-simplified",
            "model": {
                "name": "pgvector_database_similarity",
                "type": "database-native",
                "status": "active" if ai_matching_service else "error",
            },
            "database": {
                "type": "PostgreSQL + pgvector",
                "vector_similarity": "cosine similarity (<=>)",
                "embedding_dimension": 768,
            },
            "features": [
                "案件匹配简历（简化版）",
                "简历匹配案件（简化版）",
                "批量智能匹配（简化版）",
                "纯AI相似度算法",
                "数据库原生计算",
                "匹配历史追踪",
                "无自定义权重",
                "高性能pgvector",
            ],
            "algorithm": {
                "type": "database_pgvector_similarity",
                "description": "仅使用AI embedding向量相似度",
                "custom_weights": False,
                "business_rules": False,
            },
            "status": "active" if ai_matching_service else "error",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"获取系统信息失败: {str(e)}")
        return {
            "service": "AI匹配服务",
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@router.get("/system/health")
async def ai_matching_health_check():
    """AI匹配服务健康检查 - 修复版"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {},
        }

        # 检查AI匹配服务
        try:
            if ai_matching_service:
                health_status["checks"]["ai_matching_service"] = {
                    "status": "healthy",
                    "model": ai_matching_service.model_version,
                    "algorithm": "database_pgvector_similarity",
                }
            else:
                health_status["checks"]["ai_matching_service"] = {
                    "status": "error",
                    "error": "服务未初始化",
                }
                health_status["status"] = "unhealthy"
        except Exception as e:
            health_status["checks"]["ai_matching_service"] = {
                "status": "error",
                "error": str(e),
            }
            health_status["status"] = "unhealthy"

        # 检查数据库连接
        try:
            from ..database import check_database_connection

            db_connected = await check_database_connection()
            health_status["checks"]["database"] = {
                "status": "healthy" if db_connected else "error",
                "type": "PostgreSQL + pgvector",
            }
            if not db_connected:
                health_status["status"] = "unhealthy"
        except Exception as e:
            health_status["checks"]["database"] = {"status": "error", "error": str(e)}
            health_status["status"] = "unhealthy"

        # 检查必要的表
        try:
            from ..database import fetch_val

            table_checks = {}
            tables = [
                "projects",
                "engineers",
                "ai_matching_history",
                "project_engineer_matches",
            ]

            for table in tables:
                try:
                    count = await fetch_val(f"SELECT COUNT(*) FROM {table} LIMIT 1")
                    table_checks[table] = "healthy"
                except Exception:
                    table_checks[table] = "error"
                    health_status["status"] = "unhealthy"

            health_status["checks"]["tables"] = table_checks
        except Exception as e:
            health_status["checks"]["tables"] = {"status": "error", "error": str(e)}
            health_status["status"] = "unhealthy"

        # 检查pgvector扩展
        try:
            from ..database import fetch_val

            pgvector_check = await fetch_val(
                "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
            )
            if pgvector_check:
                health_status["checks"]["pgvector"] = {"status": "healthy"}
            else:
                health_status["checks"]["pgvector"] = {
                    "status": "error",
                    "error": "pgvector扩展未安装",
                }
                health_status["status"] = "unhealthy"
        except Exception as e:
            health_status["checks"]["pgvector"] = {"status": "error", "error": str(e)}
            health_status["status"] = "unhealthy"

        # 简单的相似度计算测试
        try:
            if ai_matching_db:
                # 获取一个测试样本
                from ..database import fetch_one

                test_project = await fetch_one(
                    "SELECT id, ai_match_embedding FROM projects WHERE ai_match_embedding IS NOT NULL LIMIT 1"
                )

                if test_project and test_project["ai_match_embedding"]:
                    # 测试向量查询
                    test_result = await fetch_val(
                        "SELECT ai_match_embedding <=> $1 FROM projects WHERE id = $2",
                        test_project["ai_match_embedding"],
                        test_project["id"],
                    )

                    if test_result is not None:
                        health_status["checks"]["similarity_calculation"] = {
                            "status": "healthy",
                            "test_distance": float(test_result),
                        }
                    else:
                        health_status["checks"]["similarity_calculation"] = {
                            "status": "error",
                            "error": "相似度计算返回None",
                        }
                else:
                    health_status["checks"]["similarity_calculation"] = {
                        "status": "warning",
                        "message": "没有embedding数据可供测试",
                    }
        except Exception as e:
            health_status["checks"]["similarity_calculation"] = {
                "status": "error",
                "error": str(e),
            }

        # 根据检查结果决定整体状态
        if health_status["status"] == "unhealthy":
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=health_status
            )

        return health_status

    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )


# ==================== 使用说明接口 ====================


@router.get("/usage/guide")
def get_usage_guide():
    """获取使用指南"""
    return {
        "title": "AI匹配服务使用指南 - 简化版",
        "version": "v2.0-simplified",
        "algorithm": "仅使用数据库pgvector相似度",
        "base_url": "/api/v1/ai-matching",
        "key_changes": {
            "removed_features": [
                "自定义技能权重",
                "经验年限权重",
                "日语水平权重",
                "地点预算权重",
                "复杂业务规则",
            ],
            "current_algorithm": "match_score = 1 - (embedding <=> target_embedding)",
            "advantages": [
                "性能更高（数据库原生计算）",
                "代码更简洁",
                "纯AI相似度",
                "无业务偏见",
            ],
        },
        "endpoints": {
            "project_to_engineers": {
                "url": "POST /project-to-engineers",
                "description": "项目匹配工程师（仅AI相似度）",
                "example": {
                    "tenant_id": "33723dd6-cf28-4dab-975c-f883f5389d04",
                    "project_id": "12345678-1234-1234-1234-123456789abc",
                    "max_matches": 10,
                    "min_score": 0.1,
                    "weights": {},  # 简化版不使用权重
                    "filters": {},
                },
            },
            "engineer_to_projects": {
                "url": "POST /engineer-to-projects",
                "description": "工程师匹配项目（仅AI相似度）",
                "example": {
                    "tenant_id": "33723dd6-cf28-4dab-975c-f883f5389d04",
                    "engineer_id": "12345678-1234-1234-1234-123456789abc",
                    "max_matches": 10,
                    "min_score": 0.1,
                    "weights": {},  # 简化版不使用权重
                    "filters": {},
                },
            },
            "bulk_matching": {
                "url": "POST /bulk-matching",
                "description": "批量匹配（仅AI相似度）",
            },
        },
        "response_format": {
            "success": {
                "total_matches": "匹配总数",
                "matches": "匹配结果列表",
                "match_score": "AI相似度分数 (0-1)",
                "confidence_score": "等于match_score（简化版）",
            }
        },
        "migration_notes": [
            "从复杂权重版本迁移：直接移除weights参数或传空字典",
            "分数含义变化：现在完全基于AI embedding相似度",
            "性能提升：使用数据库原生pgvector计算",
            "结果更客观：无人工业务规则干预",
        ],
        "troubleshooting": [
            "503错误：检查pgvector扩展是否安装",
            "无匹配结果：降低min_score到0.1或更低",
            "相似度异常：检查embedding数据是否存在",
            "使用/ai-matching/system/health检查系统状态",
        ],
    }
