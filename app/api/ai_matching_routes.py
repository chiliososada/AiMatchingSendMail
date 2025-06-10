# app/api/ai_matching_routes.py
from fastapi import APIRouter, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
from datetime import datetime

from ..services.ai_matching_service import AIMatchingService
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

# 创建AI匹配服务实例
ai_matching_service = AIMatchingService()


# ==================== 核心匹配API ====================


@router.post("/project-to-engineers", response_model=ProjectToEngineersResponse)
async def match_project_to_engineers(
    request: ProjectToEngineersMatchRequest, background_tasks: BackgroundTasks
):
    """
    案件匹配简历API

    为指定案件找到最匹配的简历候选人

    - **project_id**: 案件ID
    - **max_matches**: 最大匹配数量 (1-100)
    - **min_score**: 最小匹配分数 (0.0-1.0)
    - **weights**: 匹配权重配置
    - **filters**: 筛选条件
    """
    try:
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
    简历匹配案件API

    为指定简历找到最匹配的案件机会

    - **engineer_id**: 简历ID
    - **max_matches**: 最大匹配数量 (1-100)
    - **min_score**: 最小匹配分数 (0.0-1.0)
    - **weights**: 匹配权重配置
    - **filters**: 筛选条件
    """
    try:
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
    批量匹配API

    执行大规模的案件和简历匹配

    - **project_ids**: 案件ID列表 (可选，为空则匹配所有活跃案件)
    - **engineer_ids**: 简历ID列表 (可选，为空则匹配所有可用简历)
    - **max_matches**: 最大匹配数量
    - **min_score**: 最小匹配分数
    - **batch_size**: 批处理大小
    - **generate_top_matches_only**: 是否只生成高质量匹配
    """
    try:
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

        # 验证指定的ID是否存在
        if request.project_ids:
            from ..database import fetch_val

            existing_count = await fetch_val(
                "SELECT COUNT(*) FROM projects WHERE id = ANY($1) AND tenant_id = $2 AND is_active = true",
                request.project_ids,
                request.tenant_id,
            )
            if existing_count != len(request.project_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="部分案件ID不存在或已删除",
                )

        if request.engineer_ids:
            from ..database import fetch_val

            existing_count = await fetch_val(
                "SELECT COUNT(*) FROM engineers WHERE id = ANY($1) AND tenant_id = $2 AND is_active = true",
                request.engineer_ids,
                request.tenant_id,
            )
            if existing_count != len(request.engineer_ids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="部分简历ID不存在或已删除",
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
    """
    获取匹配历史记录

    返回指定租户的AI匹配历史记录列表
    """
    try:
        histories = await ai_matching_service.get_matching_history(
            tenant_id=tenant_id, limit=limit
        )

        # 按匹配类型筛选
        if matching_type:
            histories = [h for h in histories if h.matching_type == matching_type]

        return histories

    except Exception as e:
        logger.error(f"获取匹配历史失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取历史记录失败: {str(e)}",
        )


@router.get("/history/{tenant_id}/{history_id}", response_model=MatchingHistoryResponse)
async def get_matching_history_detail(tenant_id: UUID, history_id: UUID):
    """
    获取特定匹配历史详情

    返回指定历史记录的详细信息
    """
    try:
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
    """
    根据历史ID获取匹配结果

    返回特定匹配历史的所有匹配结果
    """
    try:
        matches = await ai_matching_service.get_matches_by_history(
            history_id=history_id, tenant_id=tenant_id, limit=limit
        )

        # 按最小分数筛选
        if min_score > 0.0:
            matches = [m for m in matches if m.match_score >= min_score]

        return matches

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
    """
    更新匹配状态

    更新特定匹配结果的状态和备注

    常用状态：
    - 未保存: 初始状态
    - 已保存: 用户保存到收藏
    - 已联系: 已联系候选人
    - 面试安排: 安排了面试
    - 通过: 匹配成功
    - 拒绝: 匹配被拒绝
    - 无效: 无效匹配
    """
    try:
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


@router.get(
    "/matches/{tenant_id}/project/{project_id}", response_model=List[MatchResult]
)
async def get_matches_by_project(
    tenant_id: UUID,
    project_id: UUID,
    limit: int = Query(50, ge=1, le=100, description="返回数量限制"),
    status_filter: Optional[str] = Query(None, description="状态筛选"),
):
    """
    获取特定案件的所有匹配结果

    返回指定案件的历史匹配结果
    """
    try:
        from ..database import fetch_all

        base_query = """
        SELECT m.*, p.title as project_title, e.name as engineer_name
        FROM project_engineer_matches m
        LEFT JOIN projects p ON m.project_id = p.id
        LEFT JOIN engineers e ON m.engineer_id = e.id
        WHERE m.project_id = $1 AND m.tenant_id = $2 AND m.is_active = true
        """
        params = [project_id, tenant_id]

        if status_filter:
            base_query += " AND m.status = $3"
            params.append(status_filter)

        base_query += " ORDER BY m.match_score DESC LIMIT $" + str(len(params) + 1)
        params.append(limit)

        matches_data = await fetch_all(base_query, *params)

        matches = []
        for data in matches_data:
            match = MatchResult(
                id=data["id"],
                project_id=data["project_id"],
                engineer_id=data["engineer_id"],
                match_score=float(data["match_score"]) if data["match_score"] else 0.0,
                confidence_score=(
                    float(data["confidence_score"]) if data["confidence_score"] else 0.0
                ),
                skill_match_score=(
                    float(data["skill_match_score"])
                    if data["skill_match_score"]
                    else None
                ),
                experience_match_score=(
                    float(data["experience_match_score"])
                    if data["experience_match_score"]
                    else None
                ),
                project_experience_match_score=(
                    float(data["project_experience_match_score"])
                    if data["project_experience_match_score"]
                    else None
                ),
                japanese_level_match_score=(
                    float(data["japanese_level_match_score"])
                    if data["japanese_level_match_score"]
                    else None
                ),
                budget_match_score=(
                    float(data["budget_match_score"])
                    if data["budget_match_score"]
                    else None
                ),
                location_match_score=(
                    float(data["location_match_score"])
                    if data["location_match_score"]
                    else None
                ),
                matched_skills=data["matched_skills"] or [],
                missing_skills=data["missing_skills"] or [],
                matched_experiences=data["matched_experiences"] or [],
                missing_experiences=data["missing_experiences"] or [],
                project_experience_match=data["project_experience_match"] or [],
                missing_project_experience=data["missing_project_experience"] or [],
                match_reasons=data["match_reasons"] or [],
                concerns=data["concerns"] or [],
                project_title=data["project_title"],
                engineer_name=data["engineer_name"],
                status=data["status"],
                created_at=data["created_at"],
            )
            matches.append(match)

        return matches

    except Exception as e:
        logger.error(f"获取案件匹配结果失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取匹配结果失败: {str(e)}",
        )


@router.get(
    "/matches/{tenant_id}/engineer/{engineer_id}", response_model=List[MatchResult]
)
async def get_matches_by_engineer(
    tenant_id: UUID,
    engineer_id: UUID,
    limit: int = Query(50, ge=1, le=100, description="返回数量限制"),
    status_filter: Optional[str] = Query(None, description="状态筛选"),
):
    """
    获取特定简历的所有匹配结果

    返回指定简历的历史匹配结果
    """
    try:
        from ..database import fetch_all

        base_query = """
        SELECT m.*, p.title as project_title, e.name as engineer_name
        FROM project_engineer_matches m
        LEFT JOIN projects p ON m.project_id = p.id
        LEFT JOIN engineers e ON m.engineer_id = e.id
        WHERE m.engineer_id = $1 AND m.tenant_id = $2 AND m.is_active = true
        """
        params = [engineer_id, tenant_id]

        if status_filter:
            base_query += " AND m.status = $3"
            params.append(status_filter)

        base_query += " ORDER BY m.match_score DESC LIMIT $" + str(len(params) + 1)
        params.append(limit)

        matches_data = await fetch_all(base_query, *params)

        matches = []
        for data in matches_data:
            match = MatchResult(
                id=data["id"],
                project_id=data["project_id"],
                engineer_id=data["engineer_id"],
                match_score=float(data["match_score"]) if data["match_score"] else 0.0,
                confidence_score=(
                    float(data["confidence_score"]) if data["confidence_score"] else 0.0
                ),
                skill_match_score=(
                    float(data["skill_match_score"])
                    if data["skill_match_score"]
                    else None
                ),
                experience_match_score=(
                    float(data["experience_match_score"])
                    if data["experience_match_score"]
                    else None
                ),
                project_experience_match_score=(
                    float(data["project_experience_match_score"])
                    if data["project_experience_match_score"]
                    else None
                ),
                japanese_level_match_score=(
                    float(data["japanese_level_match_score"])
                    if data["japanese_level_match_score"]
                    else None
                ),
                budget_match_score=(
                    float(data["budget_match_score"])
                    if data["budget_match_score"]
                    else None
                ),
                location_match_score=(
                    float(data["location_match_score"])
                    if data["location_match_score"]
                    else None
                ),
                matched_skills=data["matched_skills"] or [],
                missing_skills=data["missing_skills"] or [],
                matched_experiences=data["matched_experiences"] or [],
                missing_experiences=data["missing_experiences"] or [],
                project_experience_match=data["project_experience_match"] or [],
                missing_project_experience=data["missing_project_experience"] or [],
                match_reasons=data["match_reasons"] or [],
                concerns=data["concerns"] or [],
                project_title=data["project_title"],
                engineer_name=data["engineer_name"],
                status=data["status"],
                created_at=data["created_at"],
            )
            matches.append(match)

        return matches

    except Exception as e:
        logger.error(f"获取简历匹配结果失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取匹配结果失败: {str(e)}",
        )


# ==================== 统计和分析 ====================


@router.get("/statistics/{tenant_id}")
async def get_matching_statistics(
    tenant_id: UUID,
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    matching_type: Optional[str] = Query(None, description="匹配类型筛选"),
):
    """
    获取匹配统计信息

    返回指定时间段内的匹配统计数据
    """
    try:
        from ..database import fetch_one, fetch_all
        from datetime import timedelta

        start_date = datetime.utcnow() - timedelta(days=days)

        # 基础统计
        base_query = """
        SELECT 
            COUNT(*) as total_sessions,
            SUM(total_matches_generated) as total_matches,
            AVG(processing_time_seconds) as avg_processing_time,
            SUM(high_quality_matches) as total_high_quality
        FROM ai_matching_history 
        WHERE tenant_id = $1 AND started_at >= $2
        """
        params = [tenant_id, start_date]

        if matching_type:
            base_query += " AND matching_type = $3"
            params.append(matching_type)

        stats = await fetch_one(base_query, *params)

        # 按类型统计
        type_stats_query = """
        SELECT 
            matching_type,
            COUNT(*) as sessions,
            SUM(total_matches_generated) as matches,
            AVG(CASE WHEN total_matches_generated > 0 THEN high_quality_matches::float / total_matches_generated ELSE 0 END) as quality_rate
        FROM ai_matching_history 
        WHERE tenant_id = $1 AND started_at >= $2
        GROUP BY matching_type
        """
        type_stats = await fetch_all(type_stats_query, tenant_id, start_date)

        # 每日统计
        daily_stats_query = """
        SELECT 
            DATE(started_at) as date,
            COUNT(*) as sessions,
            SUM(total_matches_generated) as matches,
            SUM(high_quality_matches) as high_quality_matches
        FROM ai_matching_history 
        WHERE tenant_id = $1 AND started_at >= $2
        GROUP BY DATE(started_at)
        ORDER BY date DESC
        LIMIT 30
        """
        daily_stats = await fetch_all(daily_stats_query, tenant_id, start_date)

        # 匹配分数分析
        score_analysis_query = """
        SELECT 
            AVG(match_score) as avg_score,
            COUNT(CASE WHEN match_score >= 0.8 THEN 1 END) as high_score_count,
            COUNT(*) as total_count
        FROM project_engineer_matches 
        WHERE tenant_id = $1 AND created_at >= $2 AND is_active = true
        """
        score_analysis = await fetch_one(score_analysis_query, tenant_id, start_date)

        # 热门技能统计
        skill_stats_query = """
        SELECT 
            unnest(matched_skills) as skill,
            COUNT(*) as frequency
        FROM project_engineer_matches 
        WHERE tenant_id = $1 AND created_at >= $2 AND is_active = true 
        AND array_length(matched_skills, 1) > 0
        GROUP BY skill
        ORDER BY frequency DESC
        LIMIT 10
        """
        skill_stats = await fetch_all(skill_stats_query, tenant_id, start_date)

        total_sessions = stats["total_sessions"] or 0
        total_matches = stats["total_matches"] or 0
        avg_score = (
            float(score_analysis["avg_score"]) if score_analysis["avg_score"] else 0.0
        )
        high_score_count = score_analysis["high_score_count"] or 0
        total_match_count = score_analysis["total_count"] or 0
        high_quality_rate = (
            (high_score_count / total_match_count * 100) if total_match_count > 0 else 0
        )

        return {
            "total_matching_sessions": total_sessions,
            "total_matches_generated": total_matches,
            "average_match_score": round(avg_score, 3),
            "high_quality_match_rate": round(high_quality_rate, 2),
            "stats_by_type": {
                item["matching_type"]: {
                    "sessions": item["sessions"],
                    "matches": item["matches"],
                    "quality_rate": (
                        round(float(item["quality_rate"]) * 100, 2)
                        if item["quality_rate"]
                        else 0
                    ),
                }
                for item in type_stats
            },
            "daily_stats": [
                {
                    "date": item["date"].isoformat() if item["date"] else None,
                    "sessions": item["sessions"],
                    "matches": item["matches"],
                    "high_quality_matches": item["high_quality_matches"],
                }
                for item in daily_stats
            ],
            "top_matched_skills": [
                {"skill": item["skill"], "frequency": item["frequency"]}
                for item in skill_stats
            ],
        }

    except Exception as e:
        logger.error(f"获取匹配统计失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计数据失败: {str(e)}",
        )


# ==================== 系统信息 ====================


@router.get("/system/info")
async def get_ai_matching_system_info():
    """
    获取AI匹配系统信息

    返回系统配置和状态信息
    """
    try:
        return {
            "service": "AI匹配服务",
            "version": "1.0.0",
            "model": {
                "name": ai_matching_service.model_version,
                "type": "sentence-transformer",
                "status": "loaded" if ai_matching_service.model else "error",
            },
            "database": {
                "type": "PostgreSQL + pgvector",
                "vector_similarity": "cosine similarity (<#>)",
                "embedding_dimension": 768,
            },
            "features": [
                "案件匹配简历",
                "简历匹配案件",
                "批量智能匹配",
                "多维度评分算法",
                "实时相似度计算",
                "匹配历史追踪",
                "自定义权重配置",
                "灵活筛选条件",
            ],
            "match_dimensions": [
                "技能匹配度",
                "经验匹配度",
                "项目经验匹配度",
                "日语水平匹配度",
                "预算匹配度",
                "地点匹配度",
                "语义相似度",
            ],
            "status": "active",
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
    """
    AI匹配服务健康检查

    检查模型状态、数据库连接等
    """
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {},
        }

        # 检查AI模型
        try:
            model_status = "healthy" if ai_matching_service.model else "error"
            health_status["checks"]["ai_model"] = {
                "status": model_status,
                "model": ai_matching_service.model_version,
            }
        except Exception as e:
            health_status["checks"]["ai_model"] = {"status": "error", "error": str(e)}
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
