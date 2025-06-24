# app/services/ai_matching_service.py
"""
AI匹配服务 - 简化版
仅使用数据库默认的embedding相似度匹配，去除所有自定义业务权重
"""

import asyncio
import time
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from fastapi import HTTPException

from .ai_matching_database import AIMatchingDatabase
from .embedding_generator_service import embedding_service
from ..schemas.ai_matching_schemas import (
    ProjectToEngineersMatchRequest,
    EngineerToProjectsMatchRequest,
    BulkMatchingRequest,
    MatchResult,
    MatchingHistoryResponse,
    ProjectToEngineersResponse,
    EngineerToProjectsResponse,
    BulkMatchingResponse,
)

logger = logging.getLogger(__name__)


class AIMatchingService:
    """AI匹配服务 - 简化版（仅使用数据库默认相似度）"""

    def __init__(self):
        self.db = AIMatchingDatabase()
        self.model_version = "pgvector_database_similarity"
        # 简化版不需要加载AI模型，直接使用数据库计算
        logger.info("AI匹配服务初始化完成（简化版-仅数据库相似度）")

    def _validate_similarity_score(self, score: float, context: str = "") -> float:
        """验证和修正相似度分数"""
        if score is None or not isinstance(score, (int, float)):
            logger.warning(f"无效相似度分数 {context}: {score}, 使用默认值0.5")
            return 0.5

        # 确保分数在[0,1]范围内
        if not (0 <= score <= 1):
            logger.warning(f"相似度分数超出范围 {context}: {score}, 进行修正")
            score = max(0, min(1, float(score)))

        return float(score)

    async def _create_match_results_from_db_results(
        self,
        similarity_results: List[Dict[str, Any]],
        target_info: Dict[str, Any],
        target_type: str,  # 'project' 或 'engineer'
        max_matches: int,
        tenant_id: UUID,
    ) -> List[MatchResult]:
        """
        从数据库相似度结果创建MatchResult对象

        Args:
            similarity_results: 数据库返回的相似度结果
            target_info: 目标对象信息（项目或工程师）
            target_type: 目标类型
            max_matches: 最大匹配数量
        """
        matches = []

        for result in similarity_results[:max_matches]:
            try:
                similarity_score = self._validate_similarity_score(
                    result.get("similarity_score", 0), f"{target_type} matching"
                )

                if target_type == "project":
                    # 项目匹配工程师
                    project_id = target_info["id"]
                    engineer_id = result["id"]
                    project_title = target_info.get("title", "")
                    engineer_name = result.get("name", "")
                else:
                    # 工程师匹配项目
                    project_id = result["id"]
                    engineer_id = target_info["id"]
                    # 需要从数据库获取项目信息
                    project_info = await self.db.get_project_info(project_id, tenant_id)
                    project_title = project_info.get("title", "") if project_info else ""
                    engineer_name = target_info.get("name", "")

                # 简化版：直接使用相似度分数作为匹配分数
                match_score = similarity_score
                confidence_score = similarity_score  # 简化版：信心分数等于匹配分数

                match = MatchResult(
                    id=uuid4(),
                    project_id=project_id,
                    engineer_id=engineer_id,
                    match_score=round(match_score, 3),
                    confidence_score=round(confidence_score, 3),
                    # 简化版：不使用详细分数
                    skill_match_score=None,
                    experience_match_score=None,
                    project_experience_match_score=None,
                    japanese_level_match_score=None,
                    budget_match_score=None,
                    location_match_score=None,
                    # 简化版：不分析详细技能匹配
                    matched_skills=[],
                    missing_skills=[],
                    matched_experiences=[],
                    missing_experiences=[],
                    project_experience_match=[],
                    missing_project_experience=[],
                    # 简化的匹配原因
                    match_reasons=[f"AI向量相似度: {similarity_score:.3f}"],
                    concerns=[],
                    project_title=project_title,
                    engineer_name=engineer_name,
                    status="未保存",
                    created_at=datetime.utcnow(),
                )

                matches.append(match)

            except Exception as e:
                logger.error(f"创建匹配结果失败: {str(e)}")
                continue

        # 按匹配分数排序
        matches.sort(key=lambda x: x.match_score, reverse=True)

        logger.info(f"创建了 {len(matches)} 个匹配结果")
        if matches:
            scores = [m.match_score for m in matches]
            logger.info(f"分数范围: {min(scores):.3f} - {max(scores):.3f}")

        return matches

    # ========== 向量生成相关方法 ==========

    async def _ensure_project_embeddings(
        self, project_ids: List[UUID], tenant_id: UUID
    ) -> None:
        """
        检查并生成缺失的项目向量
        
        Args:
            project_ids: 项目ID列表
            tenant_id: 租户ID
        """
        try:
            # 获取缺失向量的项目
            projects_missing = await self.db.get_projects_with_embeddings(
                project_ids, tenant_id
            )
            
            if not projects_missing:
                logger.debug("所有项目都已有向量，无需生成")
                return
            
            logger.info(f"发现 {len(projects_missing)} 个项目缺失向量，开始生成...")
            
            # 分批处理
            project_data_list = list(projects_missing.values())
            batches = self._batch_items(project_data_list)
            
            total_updated = 0
            
            for batch_idx, batch in enumerate(batches):
                logger.info(f"处理项目向量生成批次 {batch_idx + 1}/{len(batches)} ({len(batch)} 个项目)")
                
                # 生成paraphrase文本
                paraphrases = []
                for project in batch:
                    paraphrase = embedding_service.create_project_paraphrase(project)
                    paraphrases.append(paraphrase)
                
                # 生成向量
                embeddings = embedding_service.generate_embeddings(paraphrases)
                
                # 准备更新数据
                update_data = []
                for project, paraphrase, embedding in zip(batch, paraphrases, embeddings):
                    update_data.append({
                        "id": project["id"],
                        "paraphrase": paraphrase,
                        "embedding": embedding
                    })
                
                # 批量更新数据库
                updated_count = await self.db.update_project_embeddings(update_data)
                total_updated += updated_count
                
                logger.info(f"批次 {batch_idx + 1} 完成，更新了 {updated_count} 个项目向量")
            
            logger.info(f"✅ 项目向量生成完成，总计更新: {total_updated}/{len(projects_missing)}")
            
        except Exception as e:
            logger.error(f"❌ 项目向量生成失败: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"项目向量生成失败: {str(e)}"
            )

    async def _ensure_engineer_embeddings(
        self, engineer_ids: List[UUID], tenant_id: UUID
    ) -> None:
        """
        检查并生成缺失的工程师向量
        
        Args:
            engineer_ids: 工程师ID列表
            tenant_id: 租户ID
        """
        try:
            # 获取缺失向量的工程师
            engineers_missing = await self.db.get_engineers_with_embeddings(
                engineer_ids, tenant_id
            )
            
            if not engineers_missing:
                logger.debug("所有工程师都已有向量，无需生成")
                return
            
            logger.info(f"发现 {len(engineers_missing)} 个工程师缺失向量，开始生成...")
            
            # 分批处理
            engineer_data_list = list(engineers_missing.values())
            batches = self._batch_items(engineer_data_list)
            
            total_updated = 0
            
            for batch_idx, batch in enumerate(batches):
                logger.info(f"处理工程师向量生成批次 {batch_idx + 1}/{len(batches)} ({len(batch)} 个工程师)")
                
                # 生成paraphrase文本
                paraphrases = []
                for engineer in batch:
                    paraphrase = embedding_service.create_engineer_paraphrase(engineer)
                    paraphrases.append(paraphrase)
                
                # 生成向量
                embeddings = embedding_service.generate_embeddings(paraphrases)
                
                # 准备更新数据
                update_data = []
                for engineer, paraphrase, embedding in zip(batch, paraphrases, embeddings):
                    update_data.append({
                        "id": engineer["id"],
                        "paraphrase": paraphrase,
                        "embedding": embedding
                    })
                
                # 批量更新数据库
                updated_count = await self.db.update_engineer_embeddings(update_data)
                total_updated += updated_count
                
                logger.info(f"批次 {batch_idx + 1} 完成，更新了 {updated_count} 个工程师向量")
            
            logger.info(f"✅ 工程师向量生成完成，总计更新: {total_updated}/{len(engineers_missing)}")
            
        except Exception as e:
            logger.error(f"❌ 工程师向量生成失败: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"工程师向量生成失败: {str(e)}"
            )

    def _batch_items(self, items: List[Any], batch_size: int = 32) -> List[List[Any]]:
        """
        将列表分批处理
        
        Args:
            items: 要分批的项目列表
            batch_size: 批次大小，默认32
            
        Returns:
            List[List[Any]]: 分批后的列表
        """
        batches = []
        for i in range(0, len(items), batch_size):
            batches.append(items[i:i + batch_size])
        return batches

    # ========== 主要API方法 ==========

    async def match_project_to_engineers(
        self, request: ProjectToEngineersMatchRequest
    ) -> ProjectToEngineersResponse:
        """项目匹配工程师（简化版）"""
        start_time = time.time()

        try:
            logger.info(f"开始项目匹配工程师: project_id={request.project_id}")

            # 创建匹配历史
            matching_history = await self.db.create_matching_history(
                tenant_id=request.tenant_id,
                matching_type="project_to_engineers",
                trigger_type=request.trigger_type,
                executed_by=request.executed_by,
                project_ids=[request.project_id],
                filters=request.filters or {},
                ai_model_version=self.model_version,
            )

            try:
                # 步骤1: 获取项目信息并确保有向量
                project_info = await self.db.get_project_info(
                    request.project_id, request.tenant_id
                )
                if not project_info:
                    raise ValueError(f"项目不存在: {request.project_id}")

                # 自动检查并生成项目向量
                await self._ensure_project_embeddings([request.project_id], request.tenant_id)
                
                # 重新获取项目信息（现在应该有向量了）
                project_info = await self.db.get_project_info(
                    request.project_id, request.tenant_id
                )
                
                if not project_info.get("ai_match_embedding"):
                    raise ValueError(f"项目向量生成失败: {request.project_id}")

                # 首先获取所有活跃工程师ID并生成embeddings
                all_engineers = await self.db.get_all_active_engineers(request.tenant_id)
                if all_engineers:
                    all_engineer_ids = [e["id"] for e in all_engineers]
                    await self._ensure_engineer_embeddings(all_engineer_ids, request.tenant_id)

                # 获取候选工程师（现在所有活跃工程师都应该有embeddings了）
                candidate_engineers = await self.db.get_candidate_engineers(
                    request.tenant_id, request.filters or {}
                )

                logger.info(f"找到 {len(candidate_engineers)} 个候选工程师")

                if not candidate_engineers:
                    logger.warning("没有找到候选工程师")
                    matches = []
                else:
                    # 步骤4: 获取候选工程师ID列表并确保有向量
                    engineer_ids = [e["id"] for e in candidate_engineers]
                    
                    # 自动检查并生成工程师向量
                    await self._ensure_engineer_embeddings(engineer_ids, request.tenant_id)

                    # 使用数据库直接计算相似度
                    similarity_results = (
                        await self.db.calculate_similarities_by_database(
                            target_embedding=project_info["ai_match_embedding"],
                            candidate_ids=engineer_ids,
                            table_type="engineers",
                            max_matches=request.max_matches,
                            min_score=request.min_score,
                        )
                    )

                    # 创建匹配结果
                    matches = await self._create_match_results_from_db_results(
                        similarity_results=similarity_results,
                        target_info=project_info,
                        target_type="project",
                        max_matches=request.max_matches,
                        tenant_id=request.tenant_id,
                    )

                # 保存匹配结果
                saved_matches = await self.db.save_matches(
                    matches, matching_history["id"]
                )

                # 计算统计信息
                processing_time = int(time.time() - start_time)
                high_quality_matches = len(
                    [m for m in saved_matches if m.match_score >= 0.8]
                )

                # 更新匹配历史
                await self.db.update_matching_history(
                    matching_history["id"],
                    execution_status="completed",
                    total_engineers_input=len(candidate_engineers),
                    total_matches_generated=len(saved_matches),
                    high_quality_matches=high_quality_matches,
                    processing_time_seconds=processing_time,
                    ai_config={
                        "algorithm": "database_pgvector_similarity",
                        "model_version": self.model_version,
                        "use_custom_weights": False,
                    },
                    engineer_ids=[e["id"] for e in candidate_engineers],
                )

                logger.info(f"项目匹配完成: 生成 {len(saved_matches)} 个匹配")

                return ProjectToEngineersResponse(
                    matching_history=MatchingHistoryResponse(**matching_history),
                    matches=saved_matches,
                    total_matches=len(saved_matches),
                    high_quality_matches=high_quality_matches,
                    processing_time_seconds=processing_time,
                    project_info=self.db.format_project_info(project_info),
                    matched_engineers=saved_matches,
                    recommendations=self._generate_simple_recommendations(
                        "project", len(saved_matches), high_quality_matches
                    ),
                    warnings=[],
                )

            except Exception as e:
                await self.db.update_matching_history(
                    matching_history["id"],
                    execution_status="failed",
                    error_message=str(e),
                )
                raise

        except Exception as e:
            logger.error(f"项目匹配工程师失败: {str(e)}")
            raise Exception(f"匹配失败: {str(e)}")

    async def match_engineer_to_projects(
        self, request: EngineerToProjectsMatchRequest
    ) -> EngineerToProjectsResponse:
        """工程师匹配项目（简化版）"""
        start_time = time.time()

        try:
            logger.info(f"开始工程师匹配项目: engineer_id={request.engineer_id}")

            # 创建匹配历史
            matching_history = await self.db.create_matching_history(
                tenant_id=request.tenant_id,
                matching_type="engineer_to_projects",
                trigger_type=request.trigger_type,
                executed_by=request.executed_by,
                engineer_ids=[request.engineer_id],
                filters=request.filters or {},
                ai_model_version=self.model_version,
            )

            try:
                # 步骤1: 获取工程师信息并确保有向量
                engineer_info = await self.db.get_engineer_info(
                    request.engineer_id, request.tenant_id
                )
                if not engineer_info:
                    raise ValueError(f"工程师不存在: {request.engineer_id}")

                # 自动检查并生成工程师向量
                await self._ensure_engineer_embeddings([request.engineer_id], request.tenant_id)
                
                # 重新获取工程师信息（现在应该有向量了）
                engineer_info = await self.db.get_engineer_info(
                    request.engineer_id, request.tenant_id
                )
                
                if not engineer_info.get("ai_match_embedding"):
                    raise ValueError(f"工程师向量生成失败: {request.engineer_id}")

                # 首先获取所有活跃项目ID并生成embeddings
                all_projects = await self.db.get_all_active_projects(request.tenant_id)
                if all_projects:
                    all_project_ids = [p["id"] for p in all_projects]
                    await self._ensure_project_embeddings(all_project_ids, request.tenant_id)

                # 获取候选项目（现在所有活跃项目都应该有embeddings了）
                candidate_projects = await self.db.get_candidate_projects(
                    request.tenant_id, request.filters or {}
                )

                logger.info(f"找到 {len(candidate_projects)} 个候选项目")

                if not candidate_projects:
                    logger.warning("没有找到候选项目")
                    matches = []
                else:
                    # 步骤4: 获取候选项目ID列表并确保有向量
                    project_ids = [p["id"] for p in candidate_projects]
                    
                    # 自动检查并生成项目向量
                    await self._ensure_project_embeddings(project_ids, request.tenant_id)

                    # 使用数据库直接计算相似度
                    similarity_results = (
                        await self.db.calculate_similarities_by_database(
                            target_embedding=engineer_info["ai_match_embedding"],
                            candidate_ids=project_ids,
                            table_type="projects",
                            max_matches=request.max_matches,
                            min_score=request.min_score,
                        )
                    )

                    # 创建匹配结果
                    matches = await self._create_match_results_from_db_results(
                        similarity_results=similarity_results,
                        target_info=engineer_info,
                        target_type="engineer",
                        max_matches=request.max_matches,
                        tenant_id=request.tenant_id,
                    )

                # 保存匹配结果
                saved_matches = await self.db.save_matches(
                    matches, matching_history["id"]
                )

                # 计算统计信息
                processing_time = int(time.time() - start_time)
                high_quality_matches = len(
                    [m for m in saved_matches if m.match_score >= 0.8]
                )

                # 更新匹配历史
                await self.db.update_matching_history(
                    matching_history["id"],
                    execution_status="completed",
                    total_projects_input=len(candidate_projects),
                    total_matches_generated=len(saved_matches),
                    high_quality_matches=high_quality_matches,
                    processing_time_seconds=processing_time,
                    ai_config={
                        "algorithm": "database_pgvector_similarity",
                        "model_version": self.model_version,
                        "use_custom_weights": False,
                    },
                    project_ids=[p["id"] for p in candidate_projects],
                )

                logger.info(f"工程师匹配完成: 生成 {len(saved_matches)} 个匹配")

                return EngineerToProjectsResponse(
                    matching_history=MatchingHistoryResponse(**matching_history),
                    matches=saved_matches,
                    total_matches=len(saved_matches),
                    high_quality_matches=high_quality_matches,
                    processing_time_seconds=processing_time,
                    engineer_info=self.db.format_engineer_info(engineer_info),
                    matched_projects=saved_matches,
                    recommendations=self._generate_simple_recommendations(
                        "engineer", len(saved_matches), high_quality_matches
                    ),
                    warnings=[],
                )

            except Exception as e:
                await self.db.update_matching_history(
                    matching_history["id"],
                    execution_status="failed",
                    error_message=str(e),
                )
                raise

        except Exception as e:
            logger.error(f"工程师匹配项目失败: {str(e)}")
            raise Exception(f"匹配失败: {str(e)}")

    async def bulk_matching(self, request: BulkMatchingRequest) -> BulkMatchingResponse:
        """批量匹配（简化版）"""
        start_time = time.time()

        try:
            logger.info("开始批量匹配")

            # 创建匹配历史
            matching_history = await self.db.create_matching_history(
                tenant_id=request.tenant_id,
                matching_type="bulk_matching",
                trigger_type=request.trigger_type,
                executed_by=request.executed_by,
                project_ids=request.project_ids,
                engineer_ids=request.engineer_ids,
                filters=request.filters or {},
                ai_model_version=self.model_version,
            )

            try:
                # 获取项目和工程师数据
                if request.project_ids:
                    candidate_projects = []
                    for project_id in request.project_ids:
                        project = await self.db.get_project_info(
                            project_id, request.tenant_id
                        )
                        if project:
                            candidate_projects.append(project)
                else:
                    candidate_projects = await self.db.get_candidate_projects(
                        request.tenant_id, request.filters or {}
                    )

                if request.engineer_ids:
                    candidate_engineers = []
                    for engineer_id in request.engineer_ids:
                        engineer = await self.db.get_engineer_info(
                            engineer_id, request.tenant_id
                        )
                        if engineer:
                            candidate_engineers.append(engineer)
                else:
                    candidate_engineers = await self.db.get_candidate_engineers(
                        request.tenant_id, request.filters or {}
                    )

                # 确保所有项目和工程师都有向量
                if candidate_projects:
                    project_ids = [p["id"] for p in candidate_projects]
                    await self._ensure_project_embeddings(project_ids, request.tenant_id)
                    
                    # 重新获取项目数据（现在应该都有向量了）
                    candidate_projects = []
                    for project_id in project_ids:
                        project = await self.db.get_project_info(
                            project_id, request.tenant_id
                        )
                        if project and project.get("ai_match_embedding"):
                            candidate_projects.append(project)

                if candidate_engineers:
                    engineer_ids = [e["id"] for e in candidate_engineers]
                    await self._ensure_engineer_embeddings(engineer_ids, request.tenant_id)
                    
                    # 重新获取工程师数据（现在应该都有向量了）
                    candidate_engineers = []
                    for engineer_id in engineer_ids:
                        engineer = await self.db.get_engineer_info(
                            engineer_id, request.tenant_id
                        )
                        if engineer and engineer.get("ai_match_embedding"):
                            candidate_engineers.append(engineer)

                logger.info(
                    f"批量匹配：{len(candidate_projects)} 个项目 × {len(candidate_engineers)} 个工程师"
                )

                all_matches = []
                top_matches_by_project = {}

                # 限制处理数量以避免超时
                max_projects = min(
                    len(candidate_projects), 20
                )  # 简化版：最多处理20个项目

                for i, project in enumerate(candidate_projects[:max_projects]):
                    logger.info(
                        f"处理项目 {i+1}/{max_projects}: {project.get('title', '')}"
                    )

                    try:
                        # 获取工程师ID列表
                        engineer_ids = [e["id"] for e in candidate_engineers]

                        # 使用数据库计算相似度
                        similarity_results = (
                            await self.db.calculate_similarities_by_database(
                                target_embedding=project["ai_match_embedding"],
                                candidate_ids=engineer_ids,
                                table_type="engineers",
                                max_matches=request.max_matches,
                                min_score=request.min_score,
                            )
                        )

                        # 创建匹配结果
                        project_matches = (
                            await self._create_match_results_from_db_results(
                                similarity_results=similarity_results,
                                target_info=project,
                                target_type="project",
                                max_matches=request.max_matches,
                                tenant_id=request.tenant_id,
                            )
                        )

                        if project_matches:
                            all_matches.extend(project_matches)
                            top_matches_by_project[str(project["id"])] = (
                                project_matches[:3]
                            )

                    except Exception as e:
                        logger.error(f"处理项目失败 {project['id']}: {str(e)}")
                        continue

                # 保存所有匹配
                saved_matches = await self.db.save_matches(
                    all_matches, matching_history["id"]
                )

                # 计算统计信息
                processing_time = int(time.time() - start_time)
                high_quality_matches = len(
                    [m for m in saved_matches if m.match_score >= 0.8]
                )

                # 更新匹配历史
                await self.db.update_matching_history(
                    matching_history["id"],
                    execution_status="completed",
                    total_projects_input=len(candidate_projects),
                    total_engineers_input=len(candidate_engineers),
                    total_matches_generated=len(saved_matches),
                    high_quality_matches=high_quality_matches,
                    processing_time_seconds=processing_time,
                    ai_config={
                        "algorithm": "database_pgvector_similarity",
                        "batch_size": request.batch_size,
                        "model_version": self.model_version,
                        "use_custom_weights": False,
                    },
                    project_ids=[p["id"] for p in candidate_projects],
                    engineer_ids=[e["id"] for e in candidate_engineers],
                )

                logger.info(f"批量匹配完成: 生成 {len(saved_matches)} 个匹配")

                return BulkMatchingResponse(
                    matching_history=MatchingHistoryResponse(**matching_history),
                    matches=saved_matches,
                    total_matches=len(saved_matches),
                    high_quality_matches=high_quality_matches,
                    processing_time_seconds=processing_time,
                    batch_summary={
                        "total_projects": len(candidate_projects),
                        "total_engineers": len(candidate_engineers),
                        "processed_projects": max_projects,
                        "average_match_score": (
                            sum(m.match_score for m in saved_matches)
                            / len(saved_matches)
                            if saved_matches
                            else 0
                        ),
                        "algorithm": "database_pgvector_similarity",
                    },
                    top_matches_by_project=top_matches_by_project,
                    top_matches_by_engineer={},  # 简化版暂不实现
                    recommendations=self._generate_simple_recommendations(
                        "bulk", len(saved_matches), high_quality_matches
                    ),
                    warnings=(
                        [] if len(saved_matches) > 0 else ["没有找到符合条件的匹配"]
                    ),
                )

            except Exception as e:
                await self.db.update_matching_history(
                    matching_history["id"],
                    execution_status="failed",
                    error_message=str(e),
                )
                raise

        except Exception as e:
            logger.error(f"批量匹配失败: {str(e)}")
            raise Exception(f"批量匹配失败: {str(e)}")

    # ========== 查询方法（代理到数据库层） ==========

    async def get_matching_history(
        self, tenant_id: UUID, history_id: Optional[UUID] = None, limit: int = 20
    ) -> List[MatchingHistoryResponse]:
        """获取匹配历史"""
        try:
            histories_data = await self.db.get_matching_history(
                tenant_id, history_id, limit
            )
            return [MatchingHistoryResponse(**data) for data in histories_data]
        except Exception as e:
            logger.error(f"获取匹配历史失败: {str(e)}")
            return []

    async def get_matches_by_history(
        self, history_id: UUID, tenant_id: UUID, limit: int = 100
    ) -> List[MatchResult]:
        """根据历史ID获取匹配结果"""
        try:
            matches_data = await self.db.get_matches_by_history(
                history_id, tenant_id, limit
            )

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
                    # 简化版：不使用详细分数
                    skill_match_score=None,
                    experience_match_score=None,
                    project_experience_match_score=None,
                    japanese_level_match_score=None,
                    budget_match_score=None,
                    location_match_score=None,
                    matched_skills=[],
                    missing_skills=[],
                    matched_experiences=[],
                    missing_experiences=[],
                    project_experience_match=[],
                    missing_project_experience=[],
                    match_reasons=data["match_reasons"] or ["基于embedding相似度"],
                    concerns=[],
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
        return await self.db.update_match_status(
            match_id, tenant_id, status, comment, reviewed_by
        )

    # ========== 工具方法 ==========

    def _generate_simple_recommendations(
        self, match_type: str, total_matches: int, high_quality_matches: int
    ) -> List[str]:
        """生成简化的推荐建议"""
        recommendations = []

        if total_matches == 0:
            recommendations.append(
                "没有找到匹配结果，建议调整筛选条件或降低最小分数要求"
            )
        elif high_quality_matches == 0:
            recommendations.append("没有高质量匹配（0.8+），建议查看较低分数的匹配")
        elif high_quality_matches >= 5:
            recommendations.append("有多个高质量匹配，建议优先关注前几个")
        else:
            recommendations.append(f"找到 {high_quality_matches} 个高质量匹配")

        if match_type == "bulk":
            recommendations.append("批量匹配基于AI向量相似度，无人工业务规则干预")
        else:
            recommendations.append("匹配结果基于AI向量相似度计算，分数越高表示越相似")

        return recommendations
