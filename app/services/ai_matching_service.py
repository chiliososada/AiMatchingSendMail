# app/services/ai_matching_service.py - 简化版（只匹配技能、经验、日语水平）
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple, Union
from uuid import UUID, uuid4
import logging
import numpy as np
from sentence_transformers import SentenceTransformer

from ..database import (
    get_db_connection,
    get_db_transaction,
    fetch_one,
    fetch_all,
    execute_query,
)
from ..schemas.ai_matching_schemas import (
    ProjectToEngineersMatchRequest,
    EngineerToProjectsMatchRequest,
    BulkMatchingRequest,
    MatchResult,
    MatchingHistoryResponse,
    AIMatchingResponse,
    ProjectToEngineersResponse,
    EngineerToProjectsResponse,
    BulkMatchingResponse,
)

logger = logging.getLogger(__name__)


class AIMatchingService:
    """AI匹配服务 - 简化版（只匹配技能、经验、日语水平）"""

    def __init__(self):
        self.model = None
        self.model_version = "paraphrase-multilingual-mpnet-base-v2"
        self._load_model()

    def _load_model(self):
        """加载embedding模型"""
        try:
            logger.info(f"正在加载AI模型: {self.model_version}")
            self.model = SentenceTransformer(self.model_version)
            logger.info("AI模型加载成功")
        except Exception as e:
            logger.error(f"AI模型加载失败: {str(e)}")
            raise Exception(f"无法加载AI模型: {str(e)}")

    def _serialize_for_db(self, value: Union[Dict[str, Any], List, None]) -> str:
        """序列化数据为数据库JSONB字段"""
        if value is None:
            return json.dumps({})
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            logger.warning(f"序列化失败，使用空对象: {e}")
            return json.dumps({})

    def _parse_jsonb_field(self, value: Union[str, dict, None]) -> Dict[str, Any]:
        """安全解析JSONB字段"""
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value) if value.strip() else {}
            except (json.JSONDecodeError, ValueError):
                logger.warning(f"无法解析JSON字符串: {value}")
                return {}
        return {}

    def _parse_list_field(self, value: Union[str, list, None]) -> List[UUID]:
        """安全解析列表字段"""
        if value is None:
            return []
        if isinstance(value, list):
            try:
                return [UUID(str(item)) for item in value]
            except (ValueError, TypeError):
                return []
        if isinstance(value, str):
            try:
                if not value.strip() or value.strip() in ["[]", "{}"]:
                    return []
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [UUID(str(item)) for item in parsed]
                return []
            except (json.JSONDecodeError, ValueError, TypeError):
                return []
        return []

    def _format_matching_history(self, history_data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化匹配历史数据"""
        history_data["ai_config"] = self._parse_jsonb_field(
            history_data.get("ai_config")
        )
        history_data["statistics"] = self._parse_jsonb_field(
            history_data.get("statistics")
        )
        history_data["filters"] = self._parse_jsonb_field(history_data.get("filters"))

        if isinstance(history_data.get("project_ids"), str):
            try:
                history_data["project_ids"] = json.loads(history_data["project_ids"])
            except:
                history_data["project_ids"] = []
        elif history_data.get("project_ids") is None:
            history_data["project_ids"] = []

        if isinstance(history_data.get("engineer_ids"), str):
            try:
                history_data["engineer_ids"] = json.loads(history_data["engineer_ids"])
            except:
                history_data["engineer_ids"] = []
        elif history_data.get("engineer_ids") is None:
            history_data["engineer_ids"] = []

        return history_data

    async def match_project_to_engineers(
        self, request: ProjectToEngineersMatchRequest
    ) -> ProjectToEngineersResponse:
        """案件匹配简历"""
        start_time = time.time()

        try:
            logger.info(f"开始案件匹配简历: project_id={request.project_id}")

            # 创建匹配历史记录
            matching_history = await self._create_matching_history(
                tenant_id=request.tenant_id,
                matching_type="project_to_engineers",
                trigger_type=request.trigger_type,
                executed_by=request.executed_by,
                project_ids=[request.project_id],
                filters=request.filters or {},
            )

            try:
                # 获取案件信息
                project_info = await self._get_project_info(
                    request.project_id, request.tenant_id
                )
                if not project_info:
                    raise ValueError(f"案件不存在: {request.project_id}")

                # 获取候选简历
                candidate_engineers = await self._get_candidate_engineers(
                    request.tenant_id, request.filters or {}
                )

                logger.info(f"找到 {len(candidate_engineers)} 个候选简历")

                # 执行匹配
                matches = await self._calculate_project_engineer_matches(
                    project_info,
                    candidate_engineers,
                    request.weights or {},
                    request.max_matches,
                    request.min_score,
                    matching_history["id"],
                )

                # 保存匹配结果
                saved_matches = await self._save_matches(
                    matches, matching_history["id"]
                )

                # 更新匹配历史
                processing_time = int(time.time() - start_time)
                high_quality_matches = len(
                    [m for m in saved_matches if m.match_score >= 0.8]
                )

                await self._update_matching_history(
                    matching_history["id"],
                    execution_status="completed",
                    total_engineers_input=len(candidate_engineers),
                    total_matches_generated=len(saved_matches),
                    high_quality_matches=high_quality_matches,
                    processing_time_seconds=processing_time,
                    ai_config={
                        "weights": request.weights,
                        "model_version": self.model_version,
                    },
                    engineer_ids=[e["id"] for e in candidate_engineers],
                )

                logger.info(f"案件匹配完成: 生成 {len(saved_matches)} 个匹配")

                return ProjectToEngineersResponse(
                    matching_history=MatchingHistoryResponse(**matching_history),
                    matches=saved_matches,
                    total_matches=len(saved_matches),
                    high_quality_matches=high_quality_matches,
                    processing_time_seconds=processing_time,
                    project_info=self._format_project_info(project_info),
                    matched_engineers=saved_matches,
                    recommendations=self._generate_project_recommendations(
                        project_info, saved_matches
                    ),
                    warnings=self._generate_warnings(project_info, saved_matches),
                )

            except Exception as e:
                # 更新失败状态
                await self._update_matching_history(
                    matching_history["id"],
                    execution_status="failed",
                    error_message=str(e),
                )
                raise

        except Exception as e:
            logger.error(f"案件匹配简历失败: {str(e)}")
            raise Exception(f"匹配失败: {str(e)}")

    async def match_engineer_to_projects(
        self, request: EngineerToProjectsMatchRequest
    ) -> EngineerToProjectsResponse:
        """简历匹配案件"""
        start_time = time.time()

        try:
            logger.info(f"开始简历匹配案件: engineer_id={request.engineer_id}")

            # 创建匹配历史记录
            matching_history = await self._create_matching_history(
                tenant_id=request.tenant_id,
                matching_type="engineer_to_projects",
                trigger_type=request.trigger_type,
                executed_by=request.executed_by,
                engineer_ids=[request.engineer_id],
                filters=request.filters or {},
            )

            try:
                # 获取简历信息
                engineer_info = await self._get_engineer_info(
                    request.engineer_id, request.tenant_id
                )
                if not engineer_info:
                    raise ValueError(f"简历不存在: {request.engineer_id}")

                # 获取候选案件
                candidate_projects = await self._get_candidate_projects(
                    request.tenant_id, request.filters or {}
                )

                logger.info(f"找到 {len(candidate_projects)} 个候选案件")

                # 执行匹配
                matches = await self._calculate_engineer_project_matches(
                    engineer_info,
                    candidate_projects,
                    request.weights or {},
                    request.max_matches,
                    request.min_score,
                    matching_history["id"],
                )

                # 保存匹配结果
                saved_matches = await self._save_matches(
                    matches, matching_history["id"]
                )

                # 更新匹配历史
                processing_time = int(time.time() - start_time)
                high_quality_matches = len(
                    [m for m in saved_matches if m.match_score >= 0.8]
                )

                await self._update_matching_history(
                    matching_history["id"],
                    execution_status="completed",
                    total_projects_input=len(candidate_projects),
                    total_matches_generated=len(saved_matches),
                    high_quality_matches=high_quality_matches,
                    processing_time_seconds=processing_time,
                    ai_config={
                        "weights": request.weights,
                        "model_version": self.model_version,
                    },
                    project_ids=[p["id"] for p in candidate_projects],
                )

                logger.info(f"简历匹配完成: 生成 {len(saved_matches)} 个匹配")

                return EngineerToProjectsResponse(
                    matching_history=MatchingHistoryResponse(**matching_history),
                    matches=saved_matches,
                    total_matches=len(saved_matches),
                    high_quality_matches=high_quality_matches,
                    processing_time_seconds=processing_time,
                    engineer_info=self._format_engineer_info(engineer_info),
                    matched_projects=saved_matches,
                    recommendations=self._generate_engineer_recommendations(
                        engineer_info, saved_matches
                    ),
                    warnings=self._generate_warnings_for_engineer(
                        engineer_info, saved_matches
                    ),
                )

            except Exception as e:
                # 更新失败状态
                await self._update_matching_history(
                    matching_history["id"],
                    execution_status="failed",
                    error_message=str(e),
                )
                raise

        except Exception as e:
            logger.error(f"简历匹配案件失败: {str(e)}")
            raise Exception(f"匹配失败: {str(e)}")

    async def bulk_matching(self, request: BulkMatchingRequest) -> BulkMatchingResponse:
        """批量匹配"""
        start_time = time.time()

        try:
            logger.info("开始批量匹配")

            # 获取目标案件和简历
            target_projects = await self._get_target_projects(
                request.tenant_id, request.project_ids, request.filters or {}
            )
            target_engineers = await self._get_target_engineers(
                request.tenant_id, request.engineer_ids, request.filters or {}
            )

            logger.info(
                f"批量匹配目标: {len(target_projects)} 个案件, {len(target_engineers)} 个简历"
            )

            # 创建匹配历史记录
            matching_history = await self._create_matching_history(
                tenant_id=request.tenant_id,
                matching_type="bulk_matching",
                trigger_type=request.trigger_type,
                executed_by=request.executed_by,
                project_ids=[p["id"] for p in target_projects],
                engineer_ids=[e["id"] for e in target_engineers],
                filters=request.filters or {},
            )

            try:
                # 批量执行匹配
                all_matches = []
                processed_pairs = 0
                total_pairs = len(target_projects) * len(target_engineers)

                # 分批处理
                for i in range(0, len(target_projects), request.batch_size):
                    project_batch = target_projects[i : i + request.batch_size]

                    batch_matches = await self._calculate_bulk_matches(
                        project_batch,
                        target_engineers,
                        request.max_matches,
                        request.min_score,
                        matching_history["id"],
                        request.generate_top_matches_only,
                    )

                    all_matches.extend(batch_matches)
                    processed_pairs += len(project_batch) * len(target_engineers)

                    logger.info(f"批量匹配进度: {processed_pairs}/{total_pairs}")

                    # 防止过载，添加小延迟
                    if i + request.batch_size < len(target_projects):
                        await asyncio.sleep(0.1)

                # 保存匹配结果
                saved_matches = await self._save_matches(
                    all_matches, matching_history["id"]
                )

                # 生成汇总数据
                top_matches_by_project, top_matches_by_engineer = (
                    self._generate_bulk_summary(saved_matches)
                )

                # 更新匹配历史
                processing_time = int(time.time() - start_time)
                high_quality_matches = len(
                    [m for m in saved_matches if m.match_score >= 0.8]
                )

                await self._update_matching_history(
                    matching_history["id"],
                    execution_status="completed",
                    total_projects_input=len(target_projects),
                    total_engineers_input=len(target_engineers),
                    total_matches_generated=len(saved_matches),
                    high_quality_matches=high_quality_matches,
                    processing_time_seconds=processing_time,
                    ai_config={
                        "batch_size": request.batch_size,
                        "generate_top_matches_only": request.generate_top_matches_only,
                        "model_version": self.model_version,
                    },
                )

                logger.info(f"批量匹配完成: 生成 {len(saved_matches)} 个匹配")

                return BulkMatchingResponse(
                    matching_history=MatchingHistoryResponse(**matching_history),
                    matches=saved_matches,
                    total_matches=len(saved_matches),
                    high_quality_matches=high_quality_matches,
                    processing_time_seconds=processing_time,
                    batch_summary={
                        "total_projects": len(target_projects),
                        "total_engineers": len(target_engineers),
                        "average_match_score": (
                            np.mean([m.match_score for m in saved_matches])
                            if saved_matches
                            else 0
                        ),
                        "processed_pairs": processed_pairs,
                        "match_success_rate": (
                            len(saved_matches) / processed_pairs
                            if processed_pairs > 0
                            else 0
                        ),
                    },
                    top_matches_by_project=top_matches_by_project,
                    top_matches_by_engineer=top_matches_by_engineer,
                    recommendations=self._generate_bulk_recommendations(saved_matches),
                    warnings=[],
                )

            except Exception as e:
                # 更新失败状态
                await self._update_matching_history(
                    matching_history["id"],
                    execution_status="failed",
                    error_message=str(e),
                )
                raise

        except Exception as e:
            logger.error(f"批量匹配失败: {str(e)}")
            raise Exception(f"批量匹配失败: {str(e)}")

    async def _create_matching_history(
        self,
        tenant_id: UUID,
        matching_type: str,
        trigger_type: str,
        executed_by: Optional[UUID] = None,
        project_ids: Optional[List[UUID]] = None,
        engineer_ids: Optional[List[UUID]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """创建匹配历史记录"""
        async with get_db_connection() as conn:
            filters_json = json.dumps(filters or {})
            project_ids_list = project_ids or []
            engineer_ids_list = engineer_ids or []
            ai_config_json = json.dumps({})
            statistics_json = json.dumps({})

            history_id = await conn.fetchval(
                """
                INSERT INTO ai_matching_history (
                    tenant_id, executed_by, matching_type, trigger_type,
                    project_ids, engineer_ids, filters, ai_model_version,
                    ai_config, statistics
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id
                """,
                tenant_id,
                executed_by,
                matching_type,
                trigger_type,
                project_ids_list,
                engineer_ids_list,
                filters_json,
                self.model_version,
                ai_config_json,
                statistics_json,
            )

            # 获取创建的记录并格式化
            history_data = await conn.fetchrow(
                "SELECT * FROM ai_matching_history WHERE id = $1", history_id
            )

            return self._format_matching_history(dict(history_data))

    async def _update_matching_history(
        self,
        history_id: UUID,
        execution_status: str,
        total_projects_input: int = 0,
        total_engineers_input: int = 0,
        total_matches_generated: int = 0,
        high_quality_matches: int = 0,
        processing_time_seconds: Optional[int] = None,
        error_message: Optional[str] = None,
        ai_config: Optional[Dict[str, Any]] = None,
        project_ids: Optional[List[UUID]] = None,
        engineer_ids: Optional[List[UUID]] = None,
    ):
        """更新匹配历史"""
        async with get_db_connection() as conn:
            statistics = {
                "total_projects_input": total_projects_input,
                "total_engineers_input": total_engineers_input,
                "total_matches_generated": total_matches_generated,
                "high_quality_matches": high_quality_matches,
                "processing_time_seconds": processing_time_seconds,
            }

            ai_config_json = json.dumps(ai_config or {})
            statistics_json = json.dumps(statistics)

            await conn.execute(
                """
                UPDATE ai_matching_history SET
                    execution_status = $2,
                    completed_at = $3,
                    total_projects_input = $4,
                    total_engineers_input = $5,
                    total_matches_generated = $6,
                    high_quality_matches = $7,
                    processing_time_seconds = $8,
                    error_message = $9,
                    ai_config = $10,
                    statistics = $11,
                    project_ids = COALESCE($12, project_ids),
                    engineer_ids = COALESCE($13, engineer_ids)
                WHERE id = $1
                """,
                history_id,
                execution_status,
                (
                    datetime.utcnow()
                    if execution_status in ["completed", "failed"]
                    else None
                ),
                total_projects_input,
                total_engineers_input,
                total_matches_generated,
                high_quality_matches,
                processing_time_seconds,
                error_message,
                ai_config_json,
                statistics_json,
                project_ids,
                engineer_ids,
            )

    async def _get_project_info(
        self, project_id: UUID, tenant_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """获取案件信息"""
        query = """
        SELECT * FROM projects 
        WHERE id = $1 AND tenant_id = $2 AND is_active = true
        """
        return await fetch_one(query, project_id, tenant_id)

    async def _get_engineer_info(
        self, engineer_id: UUID, tenant_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """获取简历信息"""
        query = """
        SELECT * FROM engineers 
        WHERE id = $1 AND tenant_id = $2 AND is_active = true
        """
        return await fetch_one(query, engineer_id, tenant_id)

    async def _get_candidate_engineers(
        self, tenant_id: UUID, filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """获取候选简历"""
        base_query = """
        SELECT * FROM engineers 
        WHERE tenant_id = $1 AND is_active = true
        """
        params = [tenant_id]
        conditions = []

        # 应用筛选条件
        if "japanese_level" in filters:
            conditions.append(f"japanese_level = ANY(${len(params) + 1})")
            params.append(filters["japanese_level"])

        if "current_status" in filters:
            conditions.append(f"current_status = ANY(${len(params) + 1})")
            params.append(filters["current_status"])

        if "skills" in filters:
            conditions.append(f"skills && ${len(params) + 1}")
            params.append(filters["skills"])

        if conditions:
            base_query += " AND " + " AND ".join(conditions)

        # 只获取有embedding的记录
        base_query += " AND ai_match_embedding IS NOT NULL"
        base_query += " ORDER BY created_at DESC LIMIT 1000"

        return await fetch_all(base_query, *params)

    async def _get_candidate_projects(
        self, tenant_id: UUID, filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """获取候选案件"""
        base_query = """
        SELECT * FROM projects 
        WHERE tenant_id = $1 AND is_active = true
        """
        params = [tenant_id]
        conditions = []

        # 应用筛选条件
        if "status" in filters:
            conditions.append(f"status = ANY(${len(params) + 1})")
            params.append(filters["status"])

        if "skills" in filters:
            conditions.append(f"skills && ${len(params) + 1}")
            params.append(filters["skills"])

        if "company_type" in filters:
            conditions.append(f"company_type = ANY(${len(params) + 1})")
            params.append(filters["company_type"])

        if conditions:
            base_query += " AND " + " AND ".join(conditions)

        # 只获取有embedding的记录
        base_query += " AND ai_match_embedding IS NOT NULL"
        base_query += " ORDER BY created_at DESC LIMIT 1000"

        return await fetch_all(base_query, *params)

    async def _calculate_project_engineer_matches(
        self,
        project_info: Dict[str, Any],
        engineers: List[Dict[str, Any]],
        weights: Dict[str, float],
        max_matches: int,
        min_score: float,
        matching_history_id: UUID,
    ) -> List[MatchResult]:
        """计算案件-简历匹配（简化版）"""
        matches = []

        # 使用pgvector进行相似度计算
        if not project_info.get("ai_match_embedding"):
            logger.warning(f"案件 {project_info['id']} 没有embedding数据")
            return matches

        # 批量计算相似度
        engineer_similarities = await self._calculate_similarities_batch(
            project_info["ai_match_embedding"],
            [e for e in engineers if e.get("ai_match_embedding")],
            "engineers",
        )

        for engineer, similarity_score in engineer_similarities:
            try:
                # 计算详细匹配分数（只保留3个维度）
                detailed_scores = self._calculate_detailed_match_scores(
                    project_info, engineer
                )

                # 计算综合匹配分数
                final_score = self._calculate_weighted_score(
                    detailed_scores, weights, similarity_score
                )

                if final_score >= min_score:
                    # 生成匹配原因和关注点
                    reasons, concerns = self._generate_match_analysis(
                        project_info, engineer, detailed_scores
                    )

                    match = MatchResult(
                        id=uuid4(),
                        project_id=project_info["id"],
                        engineer_id=engineer["id"],
                        match_score=round(final_score, 3),
                        confidence_score=round(
                            similarity_score * 0.8 + final_score * 0.2, 3
                        ),
                        # 只保留3个核心分数
                        skill_match_score=detailed_scores.get("skill_match"),
                        experience_match_score=detailed_scores.get("experience_match"),
                        japanese_level_match_score=detailed_scores.get(
                            "japanese_level_match"
                        ),
                        # 其他分数设为None
                        project_experience_match_score=None,
                        budget_match_score=None,
                        location_match_score=None,
                        # 简化的匹配详情
                        matched_skills=detailed_scores.get("matched_skills", []),
                        missing_skills=detailed_scores.get("missing_skills", []),
                        matched_experiences=detailed_scores.get(
                            "matched_experiences", []
                        ),
                        missing_experiences=detailed_scores.get(
                            "missing_experiences", []
                        ),
                        # 清空不需要的字段
                        project_experience_match=[],
                        missing_project_experience=[],
                        match_reasons=reasons,
                        concerns=concerns,
                        project_title=project_info.get("title"),
                        engineer_name=engineer.get("name"),
                        status="未保存",
                        created_at=datetime.utcnow(),
                    )

                    matches.append(match)

            except Exception as e:
                logger.error(
                    f"计算匹配失败 - 案件: {project_info['id']}, 简历: {engineer['id']}, 错误: {str(e)}"
                )
                continue

        # 按分数排序并限制数量
        matches.sort(key=lambda x: x.match_score, reverse=True)
        return matches[:max_matches]

    async def _calculate_similarities_batch(
        self,
        target_embedding: List[float],
        candidates: List[Dict[str, Any]],
        table_type: str,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """批量计算相似度"""
        if not candidates:
            return []

        # 构建查询
        candidate_ids = [c["id"] for c in candidates]
        table_name = "engineers" if table_type == "engineers" else "projects"

        query = f"""
        SELECT id, ai_match_embedding <#> $1 as similarity_distance
        FROM {table_name}
        WHERE id = ANY($2) AND ai_match_embedding IS NOT NULL
        ORDER BY similarity_distance ASC
        """

        # 执行查询
        similarities = await fetch_all(query, target_embedding, candidate_ids)

        # 转换距离为相似度分数 (cosine distance -> cosine similarity)
        results = []
        similarity_dict = {}

        for s in similarities:
            distance = s["similarity_distance"]
            # 确保距离在合理范围内，cosine distance应该在0-2之间
            distance = max(0, min(2, distance))
            # 转换为相似度分数：cosine_similarity = 1 - cosine_distance
            similarity_score = 1 - distance
            # 确保相似度在0-1之间
            similarity_score = max(0, min(1, similarity_score))
            similarity_dict[s["id"]] = similarity_score

        for candidate in candidates:
            if candidate["id"] in similarity_dict:
                similarity_score = similarity_dict[candidate["id"]]
                results.append((candidate, similarity_score))

        return results

    def _calculate_detailed_match_scores(
        self, project: Dict[str, Any], engineer: Dict[str, Any]
    ) -> Dict[str, Any]:
        """计算详细匹配分数（简化版 - 只保留3个维度）"""
        scores = {}

        # 1. 技能匹配
        project_skills = set(project.get("skills", []))
        engineer_skills = set(engineer.get("skills", []))

        if project_skills:
            matched_skills = project_skills.intersection(engineer_skills)
            scores["matched_skills"] = list(matched_skills)
            scores["missing_skills"] = list(project_skills - engineer_skills)
            scores["skill_match"] = len(matched_skills) / len(project_skills)
        else:
            scores["matched_skills"] = []
            scores["missing_skills"] = []
            scores["skill_match"] = 0.5  # 无特定要求时给中等分数

        # 2. 经验匹配（改进版）
        project_exp = project.get("experience", "").lower()
        engineer_exp = engineer.get("experience", "").lower()

        # 改进的经验关键词匹配
        exp_keywords = {
            "年": 0.1,  # 年数关键词
            "経験": 0.2,  # 经验关键词
            "開発": 0.2,  # 开发经验
            "設計": 0.15,  # 设计经验
            "運用": 0.1,  # 运维经验
            "保守": 0.1,  # 维护经验
            "管理": 0.1,  # 管理经验
            "リーダー": 0.05,  # 领导经验
        }

        matched_exp = []
        total_exp_weight = 0
        matched_exp_weight = 0

        for keyword, weight in exp_keywords.items():
            if keyword in project_exp:
                total_exp_weight += weight
                if keyword in engineer_exp:
                    matched_exp.append(keyword)
                    matched_exp_weight += weight

        scores["matched_experiences"] = matched_exp
        scores["missing_experiences"] = [
            kw
            for kw in exp_keywords.keys()
            if kw in project_exp and kw not in engineer_exp
        ]

        # 计算经验匹配分数（基于权重）
        if total_exp_weight > 0:
            scores["experience_match"] = matched_exp_weight / total_exp_weight
        else:
            scores["experience_match"] = 0.7  # 没有明确经验要求时给较高分数

        # 3. 日语水平匹配（改进版）
        project_jp = project.get("japanese_level", "")
        engineer_jp = engineer.get("japanese_level", "")

        # 日语等级映射（分数越高越好）
        jp_levels = {
            "N1": 5,
            "N2": 4,
            "N3": 3,
            "N4": 2,
            "N5": 1,
            "ネイティブ": 6,
            "native": 6,
            "母语": 6,
            "": 0,
        }

        project_jp_score = jp_levels.get(project_jp, 0)
        engineer_jp_score = jp_levels.get(engineer_jp, 0)

        if project_jp_score > 0:
            # 有明确日语要求
            if engineer_jp_score >= project_jp_score:
                scores["japanese_level_match"] = 1.0  # 完全满足
            elif engineer_jp_score > 0:
                # 部分满足，按比例计算
                scores["japanese_level_match"] = engineer_jp_score / project_jp_score
            else:
                scores["japanese_level_match"] = 0.2  # 完全不满足但给最低分
        else:
            # 没有明确日语要求
            if engineer_jp_score > 0:
                scores["japanese_level_match"] = 0.9  # 有日语能力加分
            else:
                scores["japanese_level_match"] = 0.7  # 中性分数

        # 确保所有分数都在0-1范围内
        for key in ["skill_match", "experience_match", "japanese_level_match"]:
            if key in scores:
                scores[key] = max(0, min(1, scores[key]))

        return scores

    def _calculate_weighted_score(
        self,
        detailed_scores: Dict[str, Any],
        weights: Dict[str, float],
        similarity_score: float,
    ) -> float:
        """计算加权综合分数（简化版 - 只考虑3个维度）"""
        # 确保相似度分数在0-1范围内
        similarity_score = max(0, min(1, similarity_score))

        # 默认权重（只有3个维度）
        default_weights = {
            "skill_match": 0.5,  # 技能匹配权重最高
            "experience_match": 0.3,  # 经验匹配次之
            "japanese_level_match": 0.2,  # 日语水平权重最低
        }

        # 合并用户自定义权重
        final_weights = {**default_weights, **weights}

        # 计算加权分数（只考虑这3个维度）
        weighted_sum = 0
        total_weight = 0

        for score_type, weight in final_weights.items():
            if (
                score_type in detailed_scores
                and detailed_scores[score_type] is not None
            ):
                score = detailed_scores[score_type]
                # 确保每个分数都在0-1范围内
                score = max(0, min(1, score))
                weighted_sum += score * weight
                total_weight += weight

        # 基础分数
        base_score = weighted_sum / total_weight if total_weight > 0 else 0
        # 确保基础分数在0-1范围内
        base_score = max(0, min(1, base_score))

        # 结合语义相似度 (权重 0.7 结构化匹配 + 0.3 语义相似度)
        final_score = base_score * 0.7 + similarity_score * 0.3

        # 确保最终分数在0-1范围内
        return max(0, min(1, final_score))

    def _generate_match_analysis(
        self, project: Dict[str, Any], engineer: Dict[str, Any], scores: Dict[str, Any]
    ) -> Tuple[List[str], List[str]]:
        """生成匹配分析（简化版）"""
        reasons = []
        concerns = []

        # 技能匹配分析
        if scores.get("skill_match", 0) >= 0.8:
            reasons.append(
                f"技能高度匹配: {', '.join(scores.get('matched_skills', []))}"
            )
        elif scores.get("skill_match", 0) >= 0.5:
            reasons.append("技能部分匹配")
            if scores.get("missing_skills"):
                concerns.append(
                    f"缺少技能: {', '.join(scores.get('missing_skills', []))}"
                )
        else:
            concerns.append("技能匹配度较低")

        # 日语水平分析
        jp_score = scores.get("japanese_level_match", 0)
        if jp_score >= 0.9:
            reasons.append("日语水平满足要求")
        elif jp_score < 0.5:
            concerns.append("日语水平可能不足")

        # 经验分析
        exp_score = scores.get("experience_match", 0)
        if exp_score >= 0.7:
            reasons.append("相关经验丰富")
        elif exp_score < 0.3:
            concerns.append("相关经验不足")

        return reasons, concerns

    async def _save_matches(
        self, matches: List[MatchResult], matching_history_id: UUID
    ) -> List[MatchResult]:
        """保存匹配结果（简化版）"""
        if not matches:
            return []

        saved_matches = []

        async with get_db_connection() as conn:
            for match in matches:
                try:
                    # 插入匹配记录（只保留核心字段）
                    await conn.execute(
                        """
                        INSERT INTO project_engineer_matches (
                            id, tenant_id, project_id, engineer_id, matching_history_id,
                            match_score, confidence_score, skill_match_score, experience_match_score,
                            japanese_level_match_score, matched_skills, missing_skills,
                            matched_experiences, missing_experiences, match_reasons, concerns, status
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                        """,
                        match.id,
                        # 需要从project或engineer获取tenant_id
                        await self._get_tenant_id_from_match(
                            match.project_id, match.engineer_id
                        ),
                        match.project_id,
                        match.engineer_id,
                        matching_history_id,
                        match.match_score,
                        match.confidence_score,
                        match.skill_match_score,
                        match.experience_match_score,
                        match.japanese_level_match_score,
                        match.matched_skills,
                        match.missing_skills,
                        match.matched_experiences,
                        match.missing_experiences,
                        match.match_reasons,
                        match.concerns,
                        match.status,
                    )

                    saved_matches.append(match)

                except Exception as e:
                    logger.error(f"保存匹配记录失败: {match.id}, 错误: {str(e)}")
                    continue

        logger.info(f"成功保存 {len(saved_matches)}/{len(matches)} 个匹配记录")
        return saved_matches

    async def _get_tenant_id_from_match(
        self, project_id: UUID, engineer_id: UUID
    ) -> UUID:
        """从匹配中获取tenant_id"""
        # 从project表获取tenant_id
        tenant_id = await fetch_val(
            "SELECT tenant_id FROM projects WHERE id = $1", project_id
        )
        return tenant_id

    # 辅助方法
    def _format_project_info(self, project: Dict[str, Any]) -> Dict[str, Any]:
        """格式化案件信息"""
        return {
            "id": str(project["id"]),
            "title": project.get("title", ""),
            "company": project.get("client_company", ""),
            "skills": project.get("skills", []),
            "experience": project.get("experience", ""),
            "japanese_level": project.get("japanese_level", ""),
            "status": project.get("status", ""),
        }

    def _format_engineer_info(self, engineer: Dict[str, Any]) -> Dict[str, Any]:
        """格式化简历信息"""
        return {
            "id": str(engineer["id"]),
            "name": engineer.get("name", ""),
            "skills": engineer.get("skills", []),
            "experience": engineer.get("experience", ""),
            "japanese_level": engineer.get("japanese_level", ""),
            "current_status": engineer.get("current_status", ""),
        }

    def _generate_project_recommendations(
        self, project: Dict[str, Any], matches: List[MatchResult]
    ) -> List[str]:
        """生成案件推荐"""
        recommendations = []

        if not matches:
            recommendations.append("没有找到匹配的简历，建议调整需求条件")
        elif len([m for m in matches if m.match_score >= 0.8]) == 0:
            recommendations.append("高质量匹配较少，建议放宽技能要求")

        if len(matches) >= 5:
            recommendations.append("建议优先联系前3名高分候选人")

        return recommendations

    def _generate_engineer_recommendations(
        self, engineer: Dict[str, Any], matches: List[MatchResult]
    ) -> List[str]:
        """生成简历推荐"""
        recommendations = []

        if not matches:
            recommendations.append("没有找到匹配的案件，建议完善技能信息")
        elif len([m for m in matches if m.match_score >= 0.8]) == 0:
            recommendations.append("高质量匹配较少，建议考虑技能提升")

        return recommendations

    def _generate_warnings(
        self, project: Dict[str, Any], matches: List[MatchResult]
    ) -> List[str]:
        """生成警告信息"""
        warnings = []

        if not project.get("ai_match_embedding"):
            warnings.append("案件缺少AI分析数据，匹配质量可能受影响")

        return warnings

    def _generate_warnings_for_engineer(
        self, engineer: Dict[str, Any], matches: List[MatchResult]
    ) -> List[str]:
        """生成简历警告信息"""
        warnings = []

        if not engineer.get("ai_match_embedding"):
            warnings.append("简历缺少AI分析数据，匹配质量可能受影响")

        return warnings

    async def _get_target_projects(
        self,
        tenant_id: UUID,
        project_ids: Optional[List[UUID]],
        filters: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """获取目标案件列表"""
        if project_ids:
            # 获取指定的案件
            query = """
            SELECT * FROM projects 
            WHERE id = ANY($1) AND tenant_id = $2 AND is_active = true
            AND ai_match_embedding IS NOT NULL
            """
            return await fetch_all(query, project_ids, tenant_id)
        else:
            # 获取所有符合条件的案件
            return await self._get_candidate_projects(tenant_id, filters)

    async def _get_target_engineers(
        self,
        tenant_id: UUID,
        engineer_ids: Optional[List[UUID]],
        filters: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """获取目标简历列表"""
        if engineer_ids:
            # 获取指定的简历
            query = """
            SELECT * FROM engineers 
            WHERE id = ANY($1) AND tenant_id = $2 AND is_active = true
            AND ai_match_embedding IS NOT NULL
            """
            return await fetch_all(query, engineer_ids, tenant_id)
        else:
            # 获取所有符合条件的简历
            return await self._get_candidate_engineers(tenant_id, filters)

    async def _calculate_bulk_matches(
        self,
        projects: List[Dict[str, Any]],
        engineers: List[Dict[str, Any]],
        max_matches_per_project: int,
        min_score: float,
        matching_history_id: UUID,
        generate_top_matches_only: bool,
    ) -> List[MatchResult]:
        """计算批量匹配"""
        all_matches = []

        for project in projects:
            try:
                # 为每个案件计算匹配
                project_matches = await self._calculate_project_engineer_matches(
                    project,
                    engineers,
                    {},  # 使用默认权重
                    max_matches_per_project,
                    min_score,
                    matching_history_id,
                )

                if generate_top_matches_only:
                    # 只保留高质量匹配
                    project_matches = [
                        m for m in project_matches if m.match_score >= 0.7
                    ]

                all_matches.extend(project_matches)

            except Exception as e:
                logger.error(
                    f"批量匹配计算失败 - 案件: {project['id']}, 错误: {str(e)}"
                )
                continue

        return all_matches

    async def _calculate_engineer_project_matches(
        self,
        engineer_info: Dict[str, Any],
        projects: List[Dict[str, Any]],
        weights: Dict[str, float],
        max_matches: int,
        min_score: float,
        matching_history_id: UUID,
    ) -> List[MatchResult]:
        """计算简历-案件匹配（简化版）"""
        matches = []

        # 使用pgvector进行相似度计算
        if not engineer_info.get("ai_match_embedding"):
            logger.warning(f"简历 {engineer_info['id']} 没有embedding数据")
            return matches

        # 批量计算相似度
        project_similarities = await self._calculate_similarities_batch(
            engineer_info["ai_match_embedding"],
            [p for p in projects if p.get("ai_match_embedding")],
            "projects",
        )

        for project, similarity_score in project_similarities:
            try:
                # 计算详细匹配分数
                detailed_scores = self._calculate_detailed_match_scores(
                    project, engineer_info
                )

                # 计算综合匹配分数
                final_score = self._calculate_weighted_score(
                    detailed_scores, weights, similarity_score
                )

                if final_score >= min_score:
                    # 生成匹配原因和关注点
                    reasons, concerns = self._generate_match_analysis(
                        project, engineer_info, detailed_scores
                    )

                    match = MatchResult(
                        id=uuid4(),
                        project_id=project["id"],
                        engineer_id=engineer_info["id"],
                        match_score=round(final_score, 3),
                        confidence_score=round(
                            similarity_score * 0.8 + final_score * 0.2, 3
                        ),
                        # 只保留3个核心分数
                        skill_match_score=detailed_scores.get("skill_match"),
                        experience_match_score=detailed_scores.get("experience_match"),
                        japanese_level_match_score=detailed_scores.get(
                            "japanese_level_match"
                        ),
                        # 其他分数设为None
                        project_experience_match_score=None,
                        budget_match_score=None,
                        location_match_score=None,
                        # 简化的匹配详情
                        matched_skills=detailed_scores.get("matched_skills", []),
                        missing_skills=detailed_scores.get("missing_skills", []),
                        matched_experiences=detailed_scores.get(
                            "matched_experiences", []
                        ),
                        missing_experiences=detailed_scores.get(
                            "missing_experiences", []
                        ),
                        # 清空不需要的字段
                        project_experience_match=[],
                        missing_project_experience=[],
                        match_reasons=reasons,
                        concerns=concerns,
                        project_title=project.get("title"),
                        engineer_name=engineer_info.get("name"),
                        status="未保存",
                        created_at=datetime.utcnow(),
                    )

                    matches.append(match)

            except Exception as e:
                logger.error(
                    f"计算匹配失败 - 简历: {engineer_info['id']}, 案件: {project['id']}, 错误: {str(e)}"
                )
                continue

        # 按分数排序并限制数量
        matches.sort(key=lambda x: x.match_score, reverse=True)
        return matches[:max_matches]

    def _generate_bulk_summary(
        self, matches: List[MatchResult]
    ) -> Tuple[Dict[str, List[MatchResult]], Dict[str, List[MatchResult]]]:
        """生成批量匹配汇总"""
        top_matches_by_project = {}
        top_matches_by_engineer = {}

        # 按案件分组，取每个案件的前5个匹配
        project_groups = {}
        for match in matches:
            project_id = str(match.project_id)
            if project_id not in project_groups:
                project_groups[project_id] = []
            project_groups[project_id].append(match)

        for project_id, project_matches in project_groups.items():
            project_matches.sort(key=lambda x: x.match_score, reverse=True)
            top_matches_by_project[project_id] = project_matches[:5]

        # 按简历分组，取每个简历的前5个匹配
        engineer_groups = {}
        for match in matches:
            engineer_id = str(match.engineer_id)
            if engineer_id not in engineer_groups:
                engineer_groups[engineer_id] = []
            engineer_groups[engineer_id].append(match)

        for engineer_id, engineer_matches in engineer_groups.items():
            engineer_matches.sort(key=lambda x: x.match_score, reverse=True)
            top_matches_by_engineer[engineer_id] = engineer_matches[:5]

        return top_matches_by_project, top_matches_by_engineer

    def _generate_bulk_recommendations(self, matches: List[MatchResult]) -> List[str]:
        """生成批量匹配推荐"""
        recommendations = []

        if not matches:
            recommendations.append("没有找到满足条件的匹配，建议调整筛选条件")
            return recommendations

        high_quality_count = len([m for m in matches if m.match_score >= 0.8])
        total_count = len(matches)

        if high_quality_count >= 10:
            recommendations.append("发现多个高质量匹配，建议优先处理评分最高的候选")
        elif high_quality_count >= 5:
            recommendations.append("发现一些高质量匹配，建议详细评估")
        else:
            recommendations.append("高质量匹配较少，建议放宽条件或优化需求描述")

        # 分析常见问题
        skill_issues = sum(1 for m in matches if len(m.missing_skills) > 2)
        if skill_issues > total_count * 0.5:
            recommendations.append("技能不匹配是主要问题，建议重新评估技能要求")

        return recommendations

    async def get_matching_history(
        self, tenant_id: UUID, history_id: Optional[UUID] = None, limit: int = 20
    ) -> List[MatchingHistoryResponse]:
        """获取匹配历史"""
        try:
            if history_id:
                query = """
                SELECT * FROM ai_matching_history 
                WHERE id = $1 AND tenant_id = $2
                """
                history_data = await fetch_one(query, history_id, tenant_id)
                if not history_data:
                    return []

                # 格式化数据
                formatted_data = self._format_matching_history(dict(history_data))
                return [MatchingHistoryResponse(**formatted_data)]
            else:
                query = """
                SELECT * FROM ai_matching_history 
                WHERE tenant_id = $1
                ORDER BY started_at DESC
                LIMIT $2
                """
                histories = await fetch_all(query, tenant_id, limit)

                # 格式化所有历史记录
                formatted_histories = []
                for history in histories:
                    formatted_data = self._format_matching_history(dict(history))
                    formatted_histories.append(
                        MatchingHistoryResponse(**formatted_data)
                    )

                return formatted_histories

        except Exception as e:
            logger.error(f"获取匹配历史失败: {str(e)}")
            return []

    async def get_matches_by_history(
        self, history_id: UUID, tenant_id: UUID, limit: int = 100
    ) -> List[MatchResult]:
        """根据历史ID获取匹配结果"""
        try:
            query = """
            SELECT m.*, p.title as project_title, e.name as engineer_name
            FROM project_engineer_matches m
            LEFT JOIN projects p ON m.project_id = p.id
            LEFT JOIN engineers e ON m.engineer_id = e.id
            WHERE m.matching_history_id = $1 AND m.tenant_id = $2
            ORDER BY m.match_score DESC
            LIMIT $3
            """

            matches_data = await fetch_all(query, history_id, tenant_id, limit)

            matches = []
            for data in matches_data:
                match = MatchResult(
                    id=data["id"],
                    project_id=data["project_id"],
                    engineer_id=data["engineer_id"],
                    match_score=(
                        float(data["match_score"]) if data["match_score"] else 0.0
                    ),
                    confidence_score=(
                        float(data["confidence_score"])
                        if data["confidence_score"]
                        else 0.0
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
                    japanese_level_match_score=(
                        float(data["japanese_level_match_score"])
                        if data["japanese_level_match_score"]
                        else None
                    ),
                    # 其他分数设为None（数据库中可能还有旧数据）
                    project_experience_match_score=None,
                    budget_match_score=None,
                    location_match_score=None,
                    matched_skills=data["matched_skills"] or [],
                    missing_skills=data["missing_skills"] or [],
                    matched_experiences=data["matched_experiences"] or [],
                    missing_experiences=data["missing_experiences"] or [],
                    # 清空不需要的字段
                    project_experience_match=[],
                    missing_project_experience=[],
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
            logger.error(f"根据历史获取匹配结果失败: {str(e)}")
            return []

    async def update_match_status(
        self,
        match_id: UUID,
        tenant_id: UUID,
        status: str,
        comment: Optional[str] = None,
        reviewed_by: Optional[UUID] = None,
    ) -> bool:
        """更新匹配状态"""
        try:
            async with get_db_connection() as conn:
                await conn.execute(
                    """
                    UPDATE project_engineer_matches 
                    SET status = $1, comment = $2, reviewed_by = $3, reviewed_at = $4, updated_at = $5
                    WHERE id = $6 AND tenant_id = $7
                    """,
                    status,
                    comment,
                    reviewed_by,
                    datetime.utcnow(),
                    datetime.utcnow(),
                    match_id,
                    tenant_id,
                )

            logger.info(f"匹配状态更新成功: {match_id} -> {status}")
            return True

        except Exception as e:
            logger.error(f"更新匹配状态失败: {str(e)}")
            return False
