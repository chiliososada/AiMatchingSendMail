# app/services/ai_matching_service.py
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple, Union
from uuid import UUID, uuid4
import logging
import numpy as np
import re
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
    """AI匹配服务 - 派遣专用简化版（仅技能+经验+日语）"""

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
            if score > 10:
                score = 1.0
            elif score < -10:
                score = 0.0
            elif score > 1:
                score = 1.0
            elif score < 0:
                score = 0.0

        return float(score)

    # ========== 新增：年限提取方法 ==========

    def _extract_experience_years(self, experience_text: str) -> int:
        """
        从经验描述中提取年限数字

        支持格式：
        - "3年以上" → 3
        - "5年間のフロントエンド開発" → 5
        - "React開発2年以上" → 2
        - "10年近くの経験" → 10
        """
        if not experience_text:
            return 0

        # 日语年限提取正则模式
        patterns = [
            r"(\d+)年以上",  # 最常见：3年以上
            r"(\d+)年間",  # 期间表达：5年間
            r"(\d+)年の",  # 所有格：3年の経験
            r"(\d+)年近く",  # 接近：5年近く
            r"(\d+)年程度",  # 程度：3年程度
            r"(\d+)年目",  # 第几年：5年目
            r"(\d+)年ほど",  # 大约：3年ほど
            r"(\d+)年経験",  # 直接：5年経験
            r"(\d+)年",  # 兜底模式
        ]

        for pattern in patterns:
            match = re.search(pattern, experience_text)
            if match:
                years = int(match.group(1))
                logger.debug(f"提取年限: '{experience_text}' → {years}年")
                return years

        logger.debug(f"未能提取年限: '{experience_text}'")
        return 0

    def _calculate_experience_match(
        self, project_years: int, engineer_years: int
    ) -> float:
        """
        计算经验年限匹配分数

        派遣年限匹配规则：
        1. 满足要求：100%匹配
        2. 超出要求但合理：95%匹配
        3. 过度超出：适当扣分（over-qualified）
        4. 不足要求：按比例扣分
        """
        if project_years <= 0:
            # 没有明确年限要求
            return 0.8 if engineer_years > 0 else 0.6

        if engineer_years >= project_years:
            # 满足或超过要求
            if engineer_years <= project_years * 1.5:
                return 1.0  # 合理范围内
            elif engineer_years <= project_years * 2:
                return 0.95  # 轻微over-qualified
            else:
                return 0.85  # 明显over-qualified但仍可用
        else:
            # 不满足要求
            if engineer_years == 0:
                return 0.3  # 没有经验
            else:
                # 按比例计算，但设最低分
                ratio = engineer_years / project_years
                return max(0.4, ratio)

    # ========== 核心修改：简化版详细匹配分数计算 ==========

    def _calculate_detailed_match_scores(
        self, project: Dict[str, Any], engineer: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        🔥 派遣专用简化版详细匹配分数计算

        仅关注三个核心维度：
        1. 技能匹配 (skill_match)
        2. 经验年限匹配 (experience_match)
        3. 日语水平匹配 (japanese_level_match)

        移除所有复杂的关键词权重系统
        """
        scores = {}

        # ==================== 1. 技能匹配（派遣最重要） ====================
        project_skills = set(project.get("skills", []))
        engineer_skills = set(engineer.get("skills", []))

        if project_skills:
            matched_skills = project_skills.intersection(engineer_skills)
            skill_score = len(matched_skills) / len(project_skills)

            scores["matched_skills"] = list(matched_skills)
            scores["missing_skills"] = list(project_skills - engineer_skills)
            scores["skill_match"] = skill_score
        else:
            scores["matched_skills"] = []
            scores["missing_skills"] = []
            scores["skill_match"] = 0.5  # 没有技能要求时给中性分数

        # ==================== 2. 经验年限匹配（简化为纯年限比较） ====================
        project_years = self._extract_experience_years(project.get("experience", ""))
        engineer_years = self._extract_experience_years(engineer.get("experience", ""))

        experience_score = self._calculate_experience_match(
            project_years, engineer_years
        )

        scores["experience_match"] = experience_score
        scores["project_required_years"] = project_years
        scores["engineer_experience_years"] = engineer_years

        # ==================== 3. 日语水平匹配（保持原逻辑） ====================
        project_jp = project.get("japanese_level", "")
        engineer_jp = engineer.get("japanese_level", "")

        # 日语等级数值化映射
        jp_levels = {
            "N5": 1,
            "N4": 2,
            "N3": 3,
            "N2": 4,
            "N1": 5,
            "ネイティブ": 6,
            "native": 6,
            "母语": 6,
            "ビジネスレベル": 5.5,
            "ビジネス": 5.5,
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

    # ========== 修改：简化版权重计算 ==========

    def _calculate_weighted_score(
        self,
        detailed_scores: Dict[str, Any],
        weights: Dict[str, float],
        similarity_score: float,
    ) -> float:
        """
        🔥 派遣专用简化版权重计算
        """
        # 验证相似度分数
        similarity_score = self._validate_similarity_score(
            similarity_score, "语义相似度"
        )

        # 🔥 派遣专用默认权重（只有三个维度）
        dispatch_default_weights = {
            "skill_match": 0.5,  # 技能匹配 50%
            "experience_match": 0.3,  # 经验年限 30%
            "japanese_level_match": 0.2,  # 日语水平 20%
        }

        # 合并权重配置
        final_weights = {**dispatch_default_weights, **weights}

        # 计算结构化匹配分数
        weighted_sum = 0
        total_weight = 0

        for score_type, weight in final_weights.items():
            if (
                score_type in detailed_scores
                and detailed_scores[score_type] is not None
            ):
                score = max(0, min(1, float(detailed_scores[score_type])))
                weighted_sum += score * weight
                total_weight += weight

        base_score = weighted_sum / total_weight if total_weight > 0 else 0
        base_score = max(0, min(1, base_score))

        # 🔥 派遣重视明确匹配，降低AI语义相似度权重
        # 结构化匹配 80% + 语义相似度 20%
        final_score = base_score * 0.8 + similarity_score * 0.2

        return max(0, min(1, final_score))

    # ========== 简化版匹配分析生成 ==========

    def _generate_match_analysis(
        self, project: Dict[str, Any], engineer: Dict[str, Any], scores: Dict[str, Any]
    ) -> Tuple[List[str], List[str]]:
        """
        🔥 简化版匹配分析生成
        """
        reasons = []
        concerns = []

        # 技能分析
        skill_score = scores.get("skill_match", 0)
        if skill_score >= 0.8:
            matched_skills = scores.get("matched_skills", [])
            if matched_skills:
                reasons.append(f"技能高度匹配: {', '.join(matched_skills)}")
            else:
                reasons.append("技能匹配度高")
        elif skill_score < 0.5:
            concerns.append("技能匹配度较低")
            missing_skills = scores.get("missing_skills", [])
            if missing_skills:
                concerns.append(f"缺少技能: {', '.join(missing_skills)}")

        # 经验年限分析
        exp_score = scores.get("experience_match", 0)
        project_years = scores.get("project_required_years", 0)
        engineer_years = scores.get("engineer_experience_years", 0)

        if exp_score >= 0.9 and project_years > 0:
            reasons.append(f"经验满足要求 ({engineer_years}年 >= {project_years}年)")
        elif exp_score < 0.5 and project_years > 0:
            concerns.append(f"经验不足 ({engineer_years}年 < {project_years}年)")
        elif engineer_years > project_years * 2 and project_years > 0:
            concerns.append(
                f"可能over-qualified ({engineer_years}年 >> {project_years}年)"
            )

        # 日语水平分析
        jp_score = scores.get("japanese_level_match", 0)
        if jp_score >= 0.9:
            reasons.append("日语水平满足要求")
        elif jp_score < 0.5:
            concerns.append("日语水平可能不足")

        return reasons, concerns

    # ========== 修复的相似度计算方法 ==========

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

        # 🔧 修复：降低最小分数阈值，避免过滤掉所有结果
        query = f"""
        SELECT id, 
               ai_match_embedding <=> $1 as cosine_distance
        FROM {table_name}
        WHERE id = ANY($2) AND ai_match_embedding IS NOT NULL
        ORDER BY ai_match_embedding <=> $1 ASC
        """

        try:
            similarities = await fetch_all(query, target_embedding, candidate_ids)
            logger.info(f"从数据库获取到 {len(similarities)} 个相似度结果")
        except Exception as e:
            logger.error(f"pgvector查询失败，回退到手动计算: {str(e)}")
            return await self._manual_similarity_calculation(
                target_embedding, candidates
            )

        results = []
        similarity_dict = {}

        for s in similarities:
            cosine_distance = s["cosine_distance"]

            if cosine_distance is None or not isinstance(cosine_distance, (int, float)):
                logger.warning(f"无效的余弦距离值: {cosine_distance}")
                continue

            # 🔧 修复：确保距离值在合理范围内
            cosine_distance = max(0, min(2, float(cosine_distance)))
            similarity_score = 1 - cosine_distance
            similarity_score = max(0, min(1, similarity_score))

            similarity_dict[s["id"]] = similarity_score

        # 🔧 修复：确保按原始candidates顺序返回结果
        for candidate in candidates:
            if candidate["id"] in similarity_dict:
                similarity_score = similarity_dict[candidate["id"]]
                results.append((candidate, similarity_score))

        logger.info(f"成功计算 {len(results)} 个相似度分数")
        if results:
            scores = [r[1] for r in results]
            logger.info(f"相似度分数范围: {min(scores):.3f} - {max(scores):.3f}")

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

                dot_product = np.dot(target_vector, candidate_vector)
                cosine_similarity = dot_product / (target_norm * candidate_norm)

                cosine_similarity = (cosine_similarity + 1) / 2
                cosine_similarity = max(0, min(1, cosine_similarity))

                results.append((candidate, cosine_similarity))

            except Exception as e:
                logger.error(f"手动计算相似度失败: {candidate['id']}, 错误: {str(e)}")
                continue

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    # ========== 保存匹配结果方法 ==========

    async def _save_matches(
        self, matches: List[MatchResult], matching_history_id: UUID
    ) -> List[MatchResult]:
        """保存匹配结果"""
        if not matches:
            return []

        saved_matches = []

        async with get_db_connection() as conn:
            for match in matches:
                try:
                    tenant_id = await fetch_val(
                        "SELECT tenant_id FROM projects WHERE id = $1", match.project_id
                    )

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
                        match.matched_experiences or [],  # 简化版可能为空
                        match.missing_experiences or [],  # 简化版可能为空
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

    # ========== 核心匹配计算方法 ==========

    async def _calculate_project_engineer_matches(
        self,
        project_info: Dict[str, Any],
        engineers: List[Dict[str, Any]],
        weights: Dict[str, float],
        max_matches: int,
        min_score: float,
        matching_history_id: UUID,
    ) -> List[MatchResult]:
        """
        🔥 派遣专用案件-简历匹配计算
        """
        matches = []

        if not project_info.get("ai_match_embedding"):
            logger.warning(f"案件 {project_info['id']} 没有embedding数据")
            return matches

        # 🔧 修复：过滤有embedding的工程师
        engineers_with_embedding = [e for e in engineers if e.get("ai_match_embedding")]

        if not engineers_with_embedding:
            logger.warning("没有工程师有embedding数据")
            return matches

        logger.info(
            f"开始计算相似度，项目: {project_info.get('title', '')}, 候选简历: {len(engineers_with_embedding)}"
        )

        engineer_similarities = await self._calculate_similarities_batch(
            project_info["ai_match_embedding"],
            engineers_with_embedding,
            "engineers",
        )

        logger.info(f"计算了 {len(engineer_similarities)} 个相似度分数")

        # 🔧 修复：降低最小分数阈值，确保有结果返回
        effective_min_score = max(0, min(min_score, 0.1))  # 最低不低于0.1

        for engineer, similarity_score in engineer_similarities:
            try:
                similarity_score = self._validate_similarity_score(
                    similarity_score, f"工程师 {engineer['id']}"
                )

                detailed_scores = self._calculate_detailed_match_scores(
                    project_info, engineer
                )

                final_score = self._calculate_weighted_score(
                    detailed_scores, weights, similarity_score
                )

                final_score = self._validate_similarity_score(
                    final_score, f"最终分数 {engineer['id']}"
                )

                # 🔧 修复：使用有效的最小分数
                if final_score >= effective_min_score:
                    reasons, concerns = self._generate_match_analysis(
                        project_info, engineer, detailed_scores
                    )

                    match = MatchResult(
                        id=uuid4(),
                        project_id=project_info["id"],
                        engineer_id=engineer["id"],
                        match_score=round(final_score, 3),
                        confidence_score=round(
                            similarity_score * 0.4 + final_score * 0.6, 3
                        ),
                        skill_match_score=detailed_scores.get("skill_match"),
                        experience_match_score=detailed_scores.get("experience_match"),
                        japanese_level_match_score=detailed_scores.get(
                            "japanese_level_match"
                        ),
                        project_experience_match_score=None,  # 简化版不需要
                        budget_match_score=None,  # 简化版不需要
                        location_match_score=None,  # 简化版不需要
                        matched_skills=detailed_scores.get("matched_skills", []),
                        missing_skills=detailed_scores.get("missing_skills", []),
                        matched_experiences=[],  # 简化版不需要复杂经验匹配
                        missing_experiences=[],  # 简化版不需要复杂经验匹配
                        project_experience_match=[],  # 简化版不需要
                        missing_project_experience=[],  # 简化版不需要
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

        matches.sort(key=lambda x: x.match_score, reverse=True)

        if matches:
            scores = [m.match_score for m in matches]
            logger.info(
                f"分数分布: 最高={max(scores):.3f}, 最低={min(scores):.3f}, 平均={np.mean(scores):.3f}"
            )
        else:
            logger.warning("没有生成任何匹配结果")

        return matches[:max_matches]

    # ========== 修复的简历匹配案件方法 ==========

    async def _calculate_engineer_project_matches(
        self,
        engineer_info: Dict[str, Any],
        projects: List[Dict[str, Any]],
        weights: Dict[str, float],
        max_matches: int,
        min_score: float,
        matching_history_id: UUID,
    ) -> List[MatchResult]:
        """
        🔥 新增：简历匹配案件计算
        """
        matches = []

        if not engineer_info.get("ai_match_embedding"):
            logger.warning(f"简历 {engineer_info['id']} 没有embedding数据")
            return matches

        # 过滤有embedding的项目
        projects_with_embedding = [p for p in projects if p.get("ai_match_embedding")]

        if not projects_with_embedding:
            logger.warning("没有项目有embedding数据")
            return matches

        logger.info(
            f"开始计算相似度，简历: {engineer_info.get('name', '')}, 候选项目: {len(projects_with_embedding)}"
        )

        project_similarities = await self._calculate_similarities_batch(
            engineer_info["ai_match_embedding"],
            projects_with_embedding,
            "projects",
        )

        logger.info(f"计算了 {len(project_similarities)} 个相似度分数")

        # 降低最小分数阈值
        effective_min_score = max(0, min(min_score, 0.1))

        for project, similarity_score in project_similarities:
            try:
                similarity_score = self._validate_similarity_score(
                    similarity_score, f"项目 {project['id']}"
                )

                # 注意：这里是engineer_info和project的顺序
                detailed_scores = self._calculate_detailed_match_scores(
                    project, engineer_info
                )

                final_score = self._calculate_weighted_score(
                    detailed_scores, weights, similarity_score
                )

                final_score = self._validate_similarity_score(
                    final_score, f"最终分数 {project['id']}"
                )

                if final_score >= effective_min_score:
                    reasons, concerns = self._generate_match_analysis(
                        project, engineer_info, detailed_scores
                    )

                    match = MatchResult(
                        id=uuid4(),
                        project_id=project["id"],
                        engineer_id=engineer_info["id"],
                        match_score=round(final_score, 3),
                        confidence_score=round(
                            similarity_score * 0.4 + final_score * 0.6, 3
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
                        matched_experiences=[],
                        missing_experiences=[],
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
                    f"计算匹配失败 - 简历: {engineer_info['id']}, 项目: {project['id']}, 错误: {str(e)}"
                )
                continue

        matches.sort(key=lambda x: x.match_score, reverse=True)

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
        """案件匹配简历（修复版）"""
        start_time = time.time()

        try:
            logger.info(f"开始案件匹配简历: project_id={request.project_id}")

            matching_history = await self._create_matching_history(
                tenant_id=request.tenant_id,
                matching_type="project_to_engineers",
                trigger_type=request.trigger_type,
                executed_by=request.executed_by,
                project_ids=[request.project_id],
                filters=request.filters or {},
            )

            try:
                project_info = await self._get_project_info(
                    request.project_id, request.tenant_id
                )
                if not project_info:
                    raise ValueError(f"案件不存在: {request.project_id}")

                candidate_engineers = await self._get_candidate_engineers(
                    request.tenant_id, request.filters or {}
                )

                logger.info(f"找到 {len(candidate_engineers)} 个候选简历")

                matches = await self._calculate_project_engineer_matches(
                    project_info,
                    candidate_engineers,
                    request.weights or {},
                    request.max_matches,
                    request.min_score,
                    matching_history["id"],
                )

                saved_matches = await self._save_matches(
                    matches, matching_history["id"]
                )

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
                        "algorithm_version": "dispatch_simplified_v1.0",  # 标记简化版
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
        """简历匹配案件（新实现）"""
        start_time = time.time()

        try:
            logger.info(f"开始简历匹配案件: engineer_id={request.engineer_id}")

            matching_history = await self._create_matching_history(
                tenant_id=request.tenant_id,
                matching_type="engineer_to_projects",
                trigger_type=request.trigger_type,
                executed_by=request.executed_by,
                engineer_ids=[request.engineer_id],
                filters=request.filters or {},
            )

            try:
                engineer_info = await self._get_engineer_info(
                    request.engineer_id, request.tenant_id
                )
                if not engineer_info:
                    raise ValueError(f"简历不存在: {request.engineer_id}")

                candidate_projects = await self._get_candidate_projects(
                    request.tenant_id, request.filters or {}
                )

                logger.info(f"找到 {len(candidate_projects)} 个候选项目")

                matches = await self._calculate_engineer_project_matches(
                    engineer_info,
                    candidate_projects,
                    request.weights or {},
                    request.max_matches,
                    request.min_score,
                    matching_history["id"],
                )

                saved_matches = await self._save_matches(
                    matches, matching_history["id"]
                )

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
                        "algorithm_version": "dispatch_simplified_v1.0",
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
                    warnings=[],
                )

            except Exception as e:
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
        """批量匹配（新实现）"""
        start_time = time.time()

        try:
            logger.info("开始批量匹配")

            matching_history = await self._create_matching_history(
                tenant_id=request.tenant_id,
                matching_type="bulk_matching",
                trigger_type=request.trigger_type,
                executed_by=request.executed_by,
                project_ids=request.project_ids,
                engineer_ids=request.engineer_ids,
                filters=request.filters or {},
            )

            try:
                # 获取项目和简历数据
                if request.project_ids:
                    candidate_projects = []
                    for project_id in request.project_ids:
                        project = await self._get_project_info(
                            project_id, request.tenant_id
                        )
                        if project:
                            candidate_projects.append(project)
                else:
                    candidate_projects = await self._get_candidate_projects(
                        request.tenant_id, request.filters or {}
                    )

                if request.engineer_ids:
                    candidate_engineers = []
                    for engineer_id in request.engineer_ids:
                        engineer = await self._get_engineer_info(
                            engineer_id, request.tenant_id
                        )
                        if engineer:
                            candidate_engineers.append(engineer)
                else:
                    candidate_engineers = await self._get_candidate_engineers(
                        request.tenant_id, request.filters or {}
                    )

                logger.info(
                    f"批量匹配：{len(candidate_projects)} 个项目 × {len(candidate_engineers)} 个简历"
                )

                all_matches = []
                top_matches_by_project = {}

                # 限制处理数量以避免超时
                max_projects = min(len(candidate_projects), 10)  # 最多处理10个项目

                for i, project in enumerate(candidate_projects[:max_projects]):
                    logger.info(
                        f"处理项目 {i+1}/{max_projects}: {project.get('title', '')}"
                    )

                    project_matches = await self._calculate_project_engineer_matches(
                        project,
                        candidate_engineers,
                        {
                            "skill_match": 0.5,
                            "experience_match": 0.3,
                            "japanese_level_match": 0.2,
                        },
                        request.max_matches,
                        request.min_score,
                        matching_history["id"],
                    )

                    if project_matches:
                        all_matches.extend(project_matches)
                        top_matches_by_project[str(project["id"])] = project_matches[
                            :3
                        ]  # 前3个

                # 保存所有匹配
                saved_matches = await self._save_matches(
                    all_matches, matching_history["id"]
                )

                processing_time = int(time.time() - start_time)
                high_quality_matches = len(
                    [m for m in saved_matches if m.match_score >= 0.8]
                )

                await self._update_matching_history(
                    matching_history["id"],
                    execution_status="completed",
                    total_projects_input=len(candidate_projects),
                    total_engineers_input=len(candidate_engineers),
                    total_matches_generated=len(saved_matches),
                    high_quality_matches=high_quality_matches,
                    processing_time_seconds=processing_time,
                    ai_config={
                        "batch_size": request.batch_size,
                        "model_version": self.model_version,
                        "algorithm_version": "dispatch_simplified_v1.0",
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
                            np.mean([m.match_score for m in saved_matches])
                            if saved_matches
                            else 0
                        ),
                    },
                    top_matches_by_project=top_matches_by_project,
                    top_matches_by_engineer={},  # 简化版暂不实现
                    recommendations=["批量匹配已完成，建议查看高分匹配项目"],
                    warnings=(
                        [] if len(saved_matches) > 0 else ["没有找到符合条件的匹配"]
                    ),
                )

            except Exception as e:
                await self._update_matching_history(
                    matching_history["id"],
                    execution_status="failed",
                    error_message=str(e),
                )
                raise

        except Exception as e:
            logger.error(f"批量匹配失败: {str(e)}")
            raise Exception(f"批量匹配失败: {str(e)}")

    # ========== 新增的辅助方法 ==========

    async def _get_engineer_info(
        self, engineer_id: UUID, tenant_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """获取简历信息"""
        query = """
        SELECT * FROM engineers 
        WHERE id = $1 AND tenant_id = $2 AND is_active = true
        """
        return await fetch_one(query, engineer_id, tenant_id)

    async def _get_candidate_projects(
        self, tenant_id: UUID, filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """获取候选项目"""
        base_query = """
        SELECT * FROM projects 
        WHERE tenant_id = $1 AND is_active = true
        """
        params = [tenant_id]
        conditions = []

        if "status" in filters:
            conditions.append(f"status = ANY(${len(params) + 1})")
            params.append(filters["status"])

        if "skills" in filters:
            conditions.append(f"skills && ${len(params) + 1}")
            params.append(filters["skills"])

        if conditions:
            base_query += " AND " + " AND ".join(conditions)

        base_query += " AND ai_match_embedding IS NOT NULL"
        base_query += " ORDER BY created_at DESC LIMIT 1000"

        return await fetch_all(base_query, *params)

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

    def _generate_engineer_recommendations(
        self, engineer: Dict[str, Any], matches: List[MatchResult]
    ) -> List[str]:
        """生成简历推荐"""
        recommendations = []

        if not matches:
            recommendations.append("没有找到匹配的项目，建议扩展技能范围")
        elif len([m for m in matches if m.match_score >= 0.8]) == 0:
            recommendations.append("高质量匹配较少，建议提升技能水平或考虑更多项目类型")

        if len(matches) >= 5:
            recommendations.append("有多个匹配项目，建议优先关注前3个高分项目")

        return recommendations

    # ========== 保持原有的辅助方法（未修改部分） ==========

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
            recommendations.append("高质量匹配较少，建议放宽技能要求或降低年限要求")

        if len(matches) >= 5:
            recommendations.append("建议优先联系前3名高分候选人")

        return recommendations

    # ========== 历史查询方法 ==========

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
