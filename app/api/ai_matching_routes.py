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
    案件匹配技术者API - 基于AI向量相似度匹配
    
    根据指定的项目，使用AI向量相似度算法找到最匹配的技术者。
    返回匹配结果包含：
    - 项目基本信息和担当者信息
    - 匹配技术者列表，包含公司信息和担当者邮箱
    - 匹配分数和详细原因
    - 统计信息和建议
    
    匹配基于技能向量相似度计算，分数越高表示越匹配。
    """
    try:
        if not ai_matching_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AIマッチングサービスが初期化されていません",
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
                detail=f"案件が存在しないか削除されています: {request.project_id}",
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
            detail=f"マッチング処理に失敗しました: {str(e)}",
        )


@router.post("/engineer-to-projects", response_model=EngineerToProjectsResponse)
async def match_engineer_to_projects(
    request: EngineerToProjectsMatchRequest, background_tasks: BackgroundTasks
):
    """
    技术者匹配案件API - 基于AI向量相似度匹配
    
    根据指定的技术者，使用AI向量相似度算法找到最匹配的项目。
    返回匹配结果包含：
    - 技术者基本信息，包含公司信息和担当者邮箱
    - 匹配项目列表，包含担当者信息
    - 匹配分数和详细原因
    - 统计信息和建议
    
    匹配基于技能向量相似度计算，分数越高表示越匹配。
    """
    try:
        if not ai_matching_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AIマッチングサービスが初期化されていません",
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
                detail=f"履歴書が存在しないか削除されています: {request.engineer_id}",
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
            detail=f"マッチング処理に失敗しました: {str(e)}",
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
                detail="AIマッチングサービスが初期化されていません",
            )

        logger.info("收到批量匹配请求")

        # 验证请求参数
        if request.project_ids is not None and len(request.project_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="project_idsは空のリストにできません。Noneまたは有効なIDリストを入力してください",
            )

        if request.engineer_ids is not None and len(request.engineer_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="engineer_idsは空のリストにできません。Noneまたは有効なIDリストを入力してください",
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
            detail=f"一括マッチング処理に失敗しました: {str(e)}",
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
                detail="AIマッチングサービスが初期化されていません",
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
            detail=f"履歴の取得に失敗しました: {str(e)}",
        )


@router.get("/history/{tenant_id}/{history_id}", response_model=MatchingHistoryResponse)
async def get_matching_history_detail(tenant_id: UUID, history_id: UUID):
    """获取特定匹配历史详情"""
    try:
        if not ai_matching_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AIマッチングサービスが初期化されていません",
            )

        histories = await ai_matching_service.get_matching_history(
            tenant_id=tenant_id, history_id=history_id
        )

        if not histories:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"マッチング履歴が存在しません: {history_id}",
            )

        return histories[0]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取匹配历史详情失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"履歴詳細の取得に失敗しました: {str(e)}",
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
                detail="AIマッチングサービスが初期化されていません",
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
            detail=f"マッチング結果の取得に失敗しました: {str(e)}",
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
                detail="AIマッチングサービスが初期化されていません",
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
                status_code=status.HTTP_404_NOT_FOUND, detail="マッチング記録が存在しないか更新に失敗しました"
            )

        return {
            "status": "success",
            "message": "マッチング状態の更新が成功しました",
            "match_id": str(match_id),
            "new_status": status,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新匹配状态失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"状態更新に失敗しました: {str(e)}",
        )


# ==================== 系统信息接口 ====================


@router.get("/system/info")
async def get_ai_matching_system_info():
    """获取AI匹配系统信息"""
    try:
        return {
            "service": "AIマッチングサービス",
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
                "案件マッチング履歴書（簡易版）",
                "履歴書マッチング案件（簡易版）",
                "一括スマートマッチング（簡易版）",
                "純AI類似度アルゴリズム",
                "データベースネイティブ計算",
                "マッチング履歴追跡",
                "カスタム重みなし",
                "高性能pgvector",
            ],
            "algorithm": {
                "type": "database_pgvector_similarity",
                "description": "AI embeddingベクトル類似度のみを使用",
                "custom_weights": False,
                "business_rules": False,
            },
            "status": "active" if ai_matching_service else "error",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"获取系统信息失败: {str(e)}")
        return {
            "service": "AIマッチングサービス",
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
                    "error": "サービスが初期化されていません",
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
                    "error": "pgvector拡張がインストールされていません",
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
                            "error": "類似度計算がNoneを返しました",
                        }
                else:
                    health_status["checks"]["similarity_calculation"] = {
                        "status": "warning",
                        "message": "テスト用のembeddingデータがありません",
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
    """
    获取AI匹配服务使用指南
    
    **内容包含：**
    - API端点说明和示例
    - 请求参数格式
    - 响应结构说明
    - 算法变更说明（简化版）
    - 故障排查指南
    - 从复杂权重版本的迁移说明
    
    **适用对象：**
    - API集成开发者
    - 系统管理员
    - 业务用户
    """
    return {
        "title": "AIマッチングサービス使用ガイド - 簡易版",
        "version": "v2.0-simplified",
        "algorithm": "データベースpgvector類似度のみを使用",
        "base_url": "/api/v1/ai-matching",
        "key_changes": {
            "removed_features": [
                "カスタムスキル重み",
                "経験年数重み",
                "日本語レベル重み",
                "場所予算重み",
                "複雑なビジネスルール",
            ],
            "current_algorithm": "match_score = 1 - (embedding <=> target_embedding)",
            "advantages": [
                "高性能（データベースネイティブ計算）",
                "コードがより簡潔",
                "純AI類似度",
                "ビジネスバイアスなし",
            ],
        },
        "endpoints": {
            "project_to_engineers": {
                "url": "POST /project-to-engineers",
                "description": "プロジェクトマッチングエンジニア（AI類似度のみ）",
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
                "description": "エンジニアマッチングプロジェクト（AI類似度のみ）",
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
                "description": "一括マッチング（AI類似度のみ）",
            },
        },
        "response_format": {
            "success": {
                "total_matches": "マッチング総数",
                "matches": "マッチング結果リスト",
                "match_score": "AI類似度スコア (0-1)",
                "confidence_score": "match_scoreと同等（簡易版）",
            }
        },
        "migration_notes": [
            "複雑な重みバージョンからの移行：weightsパラメータを直接削除するか空の辞書を渡す",
            "スコアの意味の変化：現在は完全にAI embedding類似度に基づく",
            "性能向上：データベースネイティブpgvector計算を使用",
            "結果がより客観的：人工的なビジネスルールの介入なし",
        ],
        "troubleshooting": [
            "503エラー：pgvector拡張がインストールされているかを確認",
            "マッチング結果なし：min_scoreを0.1以下に下げる",
            "類似度異常：embeddingデータが存在するかを確認",
            "/ai-matching/system/healthを使用してシステム状態を確認",
        ],
    }
