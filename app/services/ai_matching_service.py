# app/services/ai_matching_service.py - 修复版（保持向后兼容）
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
    fetch_val,
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
    """AI匹配服务 - 修复版（解决相似度计算问题）"""

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

    def _parse_vector_string(self, vector_str) -> np.ndarray:
        """将PostgreSQL vector字符串转换为numpy数组"""
        try:
            if not vector_str:
                return np.array([])

            if isinstance(vector_str, str):
                # 移除外层方括号并分割
                vector_str = vector_str.strip()
                if vector_str.startswith("[") and vector_str.endswith("]"):
                    vector_str = vector_str[1:-1]

                if vector_str:
                    values = [
                        float(x.strip()) for x in vector_str.split(",") if x.strip()
                    ]
                    return np.array(values, dtype=np.float32)
                else:
                    return np.array([])
            elif isinstance(vector_str, (list, tuple)):
                return np.array(vector_str, dtype=np.float32)
            else:
                return np.array([])

        except Exception as e:
            logger.error(f"解析vector失败: {str(e)}")
            return np.array([])

    def _validate_similarity_score(self, score: float, context: str = "") -> float:
        """验证和修正相似度分数"""
        if score is None or not isinstance(score, (int, float)):
            logger.warning(f"无效相似度分数 {context}: {score}, 使用默认值")
            return 0.5

        if not (0 <= score <= 1):
            logger.warning(f"相似度分数超出范围 {context}: {score}, 进行修正")
            # 尝试修正异常值
            if score > 10:
                score = 1.0  # 可能是内积值，设为最高相似度
            elif score < -10:
                score = 0.0  # 可能是负距离值，设为最低相似度
            elif score > 1:
                score = 1.0  # 限制上界
            elif score < 0:
                score = 0.0  # 限制下界

        return float(score)

    async def _calculate_similarities_batch(
        self,
        target_embedding: List[float],
        candidates: List[Dict[str, Any]],
        table_type: str,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """修复版：批量计算相似度"""
        if not candidates:
            return []

        candidate_ids = [c["id"] for c in candidates]
        table_name = "engineers" if table_type == "engineers" else "projects"

        # 修复：使用正确的pgvector操作符
        query = f"""
        SELECT id, 
               ai_match_embedding <=> $1 as cosine_distance
        FROM {table_name}
        WHERE id = ANY($2) AND ai_match_embedding IS NOT NULL
        ORDER BY ai_match_embedding <=> $1 ASC
        """

        try:
            similarities = await fetch_all(query, target_embedding, candidate_ids)
        except Exception as e:
            logger.error(f"pgvector查询失败，回退到手动计算: {str(e)}")
            return await self._manual_similarity_calculation(
                target_embedding, candidates
            )

        results = []
        similarity_dict = {}

        for s in similarities:
            # 修复：使用余弦距离计算相似度
            cosine_distance = s["cosine_distance"]

            # 验证距离值的合理性
            if cosine_distance is None or not isinstance(cosine_distance, (int, float)):
                logger.warning(f"无效的余弦距离值: {cosine_distance}")
                continue

            # 余弦距离通常在[0, 2]范围内，转换为相似度[0, 1]
            cosine_distance = max(0, min(2, float(cosine_distance)))
            similarity_score = 1 - cosine_distance

            # 确保相似度在[0, 1]范围内
            similarity_score = max(0, min(1, similarity_score))

            similarity_dict[s["id"]] = similarity_score

        # 组合结果
        for candidate in candidates:
            if candidate["id"] in similarity_dict:
                similarity_score = similarity_dict[candidate["id"]]
                results.append((candidate, similarity_score))

        return results

    async def _manual_similarity_calculation(
        self, target_embedding, candidates
    ) -> List[Tuple[Dict[str, Any], float]]:
        """手动计算相似度（备选方案）"""
        logger.info("使用手动相似度计算")

        results = []
        target_vector = self._parse_vector_string(target_embedding)

        if target_vector.size == 0:
            logger.warning("目标向量解析失败，无法计算相似度")
            return results

        target_norm = np.linalg.norm(target_vector)
        if target_norm == 0:
            logger.warning("目标向量模长为0，无法计算相似度")
            return results

        for candidate in candidates:
            try:
                candidate_embedding = candidate.get("ai_match_embedding")
                if not candidate_embedding:
                    continue

                candidate_vector = self._parse_vector_string(candidate_embedding)

                if candidate_vector.size == 0:
                    continue

                candidate_norm = np.linalg.norm(candidate_vector)
                if candidate_norm == 0:
                    continue

                # 计算余弦相似度
                dot_product = np.dot(target_vector, candidate_vector)
                cosine_similarity = dot_product / (target_norm * candidate_norm)

                # 确保在[0, 1]范围内（假设原始值在[-1, 1]）
                cosine_similarity = (cosine_similarity + 1) / 2
                cosine_similarity = max(0, min(1, cosine_similarity))

                results.append((candidate, cosine_similarity))

            except Exception as e:
                logger.error(f"手动计算相似度失败: {candidate['id']}, 错误: {str(e)}")
                continue

        # 按相似度排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _calculate_weighted_score(
        self,
        detailed_scores: Dict[str, Any],
        weights: Dict[str, float],
        similarity_score: float,
    ) -> float:
        """修复版：计算加权综合分数"""

        # 验证并修正相似度分数
        similarity_score = self._validate_similarity_score(
            similarity_score, "语义相似度"
        )

        # 默认权重
        default_weights = {
            "skill_match": 0.5,
            "experience_match": 0.3,
            "japanese_level_match": 0.2,
        }

        # 合并权重
        final_weights = {**default_weights, **weights}

        # 计算结构化匹配分数
        weighted_sum = 0
        total_weight = 0

        for score_type, weight in final_weights.items():
            if (
                score_type in detailed_scores
                and detailed_scores[score_type] is not None
            ):
                score = detailed_scores[score_type]
                # 验证每个分数
                score = max(0, min(1, float(score)))
                weighted_sum += score * weight
                total_weight += weight

        # 基础分数
        base_score = weighted_sum / total_weight if total_weight > 0 else 0
        base_score = max(0, min(1, base_score))

        # 修复：使用更合理的权重分配
        # 语义相似度权重30%，结构化匹配权重70%
        final_score = base_score * 0.7 + similarity_score * 0.3

        # 确保最终分数在合理范围内
        final_score = max(0, min(1, final_score))

        return final_score

    def _calculate_detailed_match_scores(
        self, project: Dict[str, Any], engineer: Dict[str, Any]
    ) -> Dict[str, Any]:
        """计算详细匹配分数"""
        scores = {}

        # 技能匹配
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
            scores["skill_match"] = 0.5

        # 经验匹配
        project_exp = project.get("experience", "").lower()
        engineer_exp = engineer.get("experience", "").lower()

        exp_keywords = {
            "年": 0.1,
            "経験": 0.2,
            "開発": 0.2,
            "設計": 0.15,
            "運用": 0.1,
            "保守": 0.1,
            "管理": 0.1,
            "リーダー": 0.05,
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

        if total_exp_weight > 0:
            scores["experience_match"] = matched_exp_weight / total_exp_weight
        else:
            scores["experience_match"] = 0.7

        # 日语水平匹配
        project_jp = project.get("japanese_level", "")
        engineer_jp = engineer.get("japanese_level", "")

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
            if engineer_jp_score >= project_jp_score:
                scores["japanese_level_match"] = 1.0
            elif engineer_jp_score > 0:
                scores["japanese_level_match"] = engineer_jp_score / project_jp_score
            else:
                scores["japanese_level_match"] = 0.2
        else:
            scores["japanese_level_match"] = 0.9 if engineer_jp_score > 0 else 0.7

        # 确保所有分数在[0,1]范围内
        for key in ["skill_match", "experience_match", "japanese_level_match"]:
            if key in scores:
                scores[key] = max(0, min(1, scores[key]))

        return scores

    def _generate_match_analysis(
        self, project: Dict[str, Any], engineer: Dict[str, Any], scores: Dict[str, Any]
    ) -> Tuple[List[str], List[str]]:
        """生成匹配分析"""
        reasons = []
        concerns = []

        # 技能匹配分析
        skill_score = scores.get("skill_match", 0)
        if skill_score >= 0.8:
            reasons.append(
                f"技能高度匹配: {', '.join(scores.get('matched_skills', []))}"
            )
        elif skill_score >= 0.5:
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
        """修复版：保存匹配结果（处理重复记录）"""
        if not matches:
            return []

        saved_matches = []

        async with get_db_connection() as conn:
            for match in matches:
                try:
                    # 获取tenant_id
                    tenant_id = await fetch_val(
                        "SELECT tenant_id FROM projects WHERE id = $1", match.project_id
                    )

                    # 修复：使用UPSERT处理重复记录
                    await conn.execute(
                        """
                        INSERT INTO project_engineer_matches (
                            id, tenant_id, project_id, engineer_id, matching_history_id,
                            match_score, confidence_score, skill_match_score, experience_match_score,
                            japanese_level_match_score, matched_skills, missing_skills,
                            matched_experiences, missing_experiences, match_reasons, concerns, status
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                        ON CONFLICT (tenant_id, project_id, engineer_id) 
                        DO UPDATE SET
                            match_score = EXCLUDED.match_score,
                            confidence_score = EXCLUDED.confidence_score,
                            skill_match_score = EXCLUDED.skill_match_score,
                            experience_match_score = EXCLUDED.experience_match_score,
                            japanese_level_match_score = EXCLUDED.japanese_level_match_score,
                            matched_skills = EXCLUDED.matched_skills,
                            missing_skills = EXCLUDED.missing_skills,
                            matched_experiences = EXCLUDED.matched_experiences,
                            missing_experiences = EXCLUDED.missing_experiences,
                            match_reasons = EXCLUDED.match_reasons,
                            concerns = EXCLUDED.concerns,
                            matching_history_id = EXCLUDED.matching_history_id,
                            updated_at = NOW()
                        """,
                        match.id,
                        tenant_id,
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

    async def _calculate_project_engineer_matches(
        self,
        project_info: Dict[str, Any],
        engineers: List[Dict[str, Any]],
        weights: Dict[str, float],
        max_matches: int,
        min_score: float,
        matching_history_id: UUID,
    ) -> List[MatchResult]:
        """修复版：计算案件-简历匹配"""
        matches = []

        if not project_info.get("ai_match_embedding"):
            logger.warning(f"案件 {project_info['id']} 没有embedding数据")
            return matches

        # 使用修复版的相似度计算
        engineer_similarities = await self._calculate_similarities_batch(
            project_info["ai_match_embedding"],
            [e for e in engineers if e.get("ai_match_embedding")],
            "engineers",
        )

        logger.info(f"计算了 {len(engineer_similarities)} 个相似度分数")

        for engineer, similarity_score in engineer_similarities:
            try:
                # 验证相似度分数
                similarity_score = self._validate_similarity_score(
                    similarity_score, f"工程师 {engineer['id']}"
                )

                # 计算详细匹配分数
                detailed_scores = self._calculate_detailed_match_scores(
                    project_info, engineer
                )

                # 使用修复版的权重分数计算
                final_score = self._calculate_weighted_score(
                    detailed_scores, weights, similarity_score
                )

                # 验证最终分数
                final_score = self._validate_similarity_score(
                    final_score, f"最终分数 {engineer['id']}"
                )

                if final_score >= min_score:
                    # 生成匹配分析
                    reasons, concerns = self._generate_match_analysis(
                        project_info, engineer, detailed_scores
                    )

                    match = MatchResult(
                        id=uuid4(),
                        project_id=project_info["id"],
                        engineer_id=engineer["id"],
                        match_score=round(final_score, 3),
                        confidence_score=round(
                            similarity_score * 0.6 + final_score * 0.4, 3
                        ),
                        skill_match_score=detailed_scores.get("skill_match"),
                        experience_match_score=detailed_scores.get("experience_match"),
                        japanese_level_match_score=detailed_scores.get(
                            "japanese_level_match"
                        ),
                        project_experience_match_score=None,
                        budget_match_score=None,
                        location_match_score=None,
                        matched_skills=detailed_scores.get("matched_skills", []),
                        missing_skills=detailed_scores.get("missing_skills", []),
                        matched_experiences=detailed_scores.get(
                            "matched_experiences", []
                        ),
                        missing_experiences=detailed_scores.get(
                            "missing_experiences", []
                        ),
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

        # 按分数排序
        matches.sort(key=lambda x: x.match_score, reverse=True)

        # 记录分数分布
        if matches:
            scores = [m.match_score for m in matches]
            logger.info(
                f"分数分布: 最高={max(scores):.3f}, 最低={min(scores):.3f}, 平均={np.mean(scores):.3f}"
            )

        return matches[:max_matches]

    # ========== 主要API方法 ==========

    async def match_project_to_engineers(
        self, request: ProjectToEngineersMatchRequest
    ) -> ProjectToEngineersResponse:
        """案件匹配简历（使用修复版计算）"""
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
            logger.error(f"案件匹配简历失败: {str(e)}")
            raise Exception(f"匹配失败: {str(e)}")

    # ========== 辅助方法 ==========

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

    # ========== 其他API方法（保持兼容性） ==========

    async def match_engineer_to_projects(
        self, request: EngineerToProjectsMatchRequest
    ) -> EngineerToProjectsResponse:
        """简历匹配案件（简化实现）"""
        # 这里可以实现简历匹配案件的逻辑
        # 为了保持兼容性，先返回一个基本的响应
        raise NotImplementedError("简历匹配案件功能待实现")

    async def bulk_matching(self, request: BulkMatchingRequest) -> BulkMatchingResponse:
        """批量匹配（简化实现）"""
        # 这里可以实现批量匹配的逻辑
        raise NotImplementedError("批量匹配功能待实现")

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
                    project_experience_match_score=None,
                    budget_match_score=None,
                    location_match_score=None,
                    matched_skills=data["matched_skills"] or [],
                    missing_skills=data["missing_skills"] or [],
                    matched_experiences=data["matched_experiences"] or [],
                    missing_experiences=data["missing_experiences"] or [],
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
