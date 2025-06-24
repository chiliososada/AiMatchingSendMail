# app/services/ai_matching_database.py
"""
AI匹配数据库操作层
专门负责所有数据库相关的操作，包括查询、保存、更新等
"""

import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from uuid import UUID

from ..database import (
    get_db_connection,
    fetch_one,
    fetch_all,
    fetch_val,
)
from ..schemas.ai_matching_schemas import MatchResult

logger = logging.getLogger(__name__)


class AIMatchingDatabase:
    """AI匹配数据库操作类"""

    def __init__(self):
        pass

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

    # ========== 项目相关查询 ==========

    async def get_project_info(
        self, project_id: UUID, tenant_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """获取项目信息"""
        query = """
        SELECT * FROM projects 
        WHERE id = $1 AND tenant_id = $2 AND is_active = true
        """
        return await fetch_one(query, project_id, tenant_id)

    async def get_candidate_projects(
        self, tenant_id: UUID, filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """获取候选项目"""
        base_query = """
        SELECT * FROM projects 
        WHERE tenant_id = $1 AND is_active = true
        """
        params = [tenant_id]
        conditions = []

        if filters:
            if "status" in filters:
                conditions.append(f"status = ANY(${len(params) + 1})")
                params.append(filters["status"])

            if "skills" in filters:
                conditions.append(f"skills && ${len(params) + 1}")
                params.append(filters["skills"])

        if conditions:
            base_query += " AND " + " AND ".join(conditions)

        # 只获取有embedding的项目
        base_query += " AND ai_match_embedding IS NOT NULL"
        base_query += " ORDER BY created_at DESC LIMIT 1000"

        return await fetch_all(base_query, *params)

    # ========== 工程师相关查询 ==========

    async def get_engineer_info(
        self, engineer_id: UUID, tenant_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """获取工程师信息"""
        query = """
        SELECT * FROM engineers 
        WHERE id = $1 AND tenant_id = $2 AND is_active = true
        """
        return await fetch_one(query, engineer_id, tenant_id)

    async def get_candidate_engineers(
        self, tenant_id: UUID, filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """获取候选工程师"""
        base_query = """
        SELECT * FROM engineers 
        WHERE tenant_id = $1 AND is_active = true
        """
        params = [tenant_id]
        conditions = []

        if filters:
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

        # 只获取有embedding的工程师
        base_query += " AND ai_match_embedding IS NOT NULL"
        base_query += " ORDER BY created_at DESC LIMIT 1000"

        return await fetch_all(base_query, *params)

    # ========== 相似度计算（数据库层） ==========

    async def calculate_similarities_by_database(
        self,
        target_embedding: List[float],
        candidate_ids: List[UUID],
        table_type: str,
        max_matches: int = 100,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        使用数据库pgvector直接计算相似度

        Args:
            target_embedding: 目标embedding向量
            candidate_ids: 候选对象ID列表
            table_type: 表类型 ('engineers' 或 'projects')
            max_matches: 最大匹配数量
            min_score: 最小相似度分数

        Returns:
            List[Dict]: 包含id和similarity_score的结果列表
        """
        if not candidate_ids:
            return []

        # 根据表类型选择正确的表名和字段名
        if table_type == "engineers":
            table_name = "engineers"
            name_field = "name"
        else:  # projects
            table_name = "projects"
            name_field = "title"  # 项目表使用title字段，不是name字段

        # 直接使用pgvector的余弦相似度计算
        # 注意：pgvector的 <=> 返回的是距离，需要转换为相似度
        query = f"""
        SELECT 
            id,
            {name_field} as name,
            1 - (ai_match_embedding <=> $1) as similarity_score
        FROM {table_name}
        WHERE id = ANY($2) 
            AND ai_match_embedding IS NOT NULL
            AND 1 - (ai_match_embedding <=> $1) >= $3
        ORDER BY ai_match_embedding <=> $1 ASC
        LIMIT $4
        """

        try:
            results = await fetch_all(
                query, target_embedding, candidate_ids, min_score, max_matches
            )

            logger.info(
                f"数据库相似度计算完成: {len(results)} 个结果 (表: {table_name})"
            )
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"数据库相似度计算失败 (表: {table_name}): {str(e)}")
            return []

    # ========== 匹配历史管理 ==========

    async def create_matching_history(
        self,
        tenant_id: UUID,
        matching_type: str,
        trigger_type: str,
        executed_by: Optional[UUID] = None,
        project_ids: Optional[List[UUID]] = None,
        engineer_ids: Optional[List[UUID]] = None,
        filters: Optional[Dict[str, Any]] = None,
        ai_model_version: str = "database_similarity",
    ) -> Dict[str, Any]:
        """创建匹配历史记录"""
        async with get_db_connection() as conn:
            filters_json = json.dumps(filters or {})
            project_ids_list = project_ids or []
            engineer_ids_list = engineer_ids or []
            ai_config_json = json.dumps({"algorithm": "database_pgvector_similarity"})
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
                ai_model_version,
                ai_config_json,
                statistics_json,
            )

            history_data = await conn.fetchrow(
                "SELECT * FROM ai_matching_history WHERE id = $1", history_id
            )

            return self._format_matching_history(dict(history_data))

    async def update_matching_history(
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

            ai_config_json = json.dumps(
                ai_config or {"algorithm": "database_pgvector_similarity"}
            )
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

    # ========== 匹配结果保存 ==========

    async def save_matches(
        self, matches: List[MatchResult], matching_history_id: UUID
    ) -> List[MatchResult]:
        """保存匹配结果 - 修复版"""
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

                    if not tenant_id:
                        logger.error(f"找不到项目的tenant_id: {match.project_id}")
                        continue

                    # 方法1: 先检查是否存在，然后决定INSERT或UPDATE
                    existing_match = await conn.fetchrow(
                        """
                        SELECT id FROM project_engineer_matches 
                        WHERE tenant_id = $1 AND project_id = $2 AND engineer_id = $3
                        """,
                        tenant_id,
                        match.project_id,
                        match.engineer_id,
                    )

                    if existing_match:
                        # 更新现有记录
                        await conn.execute(
                            """
                            UPDATE project_engineer_matches SET
                                match_score = $1,
                                confidence_score = $2,
                                matching_history_id = $3,
                                skill_match_score = $4,
                                experience_match_score = $5,
                                japanese_level_match_score = $6,
                                matched_skills = $7,
                                missing_skills = $8,
                                matched_experiences = $9,
                                missing_experiences = $10,
                                match_reasons = $11,
                                concerns = $12,
                                status = $13,
                                updated_at = NOW()
                            WHERE tenant_id = $14 AND project_id = $15 AND engineer_id = $16
                            """,
                            match.match_score,
                            match.confidence_score,
                            matching_history_id,
                            None,  # skill_match_score - 简化版不使用
                            None,  # experience_match_score - 简化版不使用
                            None,  # japanese_level_match_score - 简化版不使用
                            [],  # matched_skills - 简化版不使用
                            [],  # missing_skills - 简化版不使用
                            [],  # matched_experiences - 简化版不使用
                            [],  # missing_experiences - 简化版不使用
                            ["基于embedding相似度匹配"],  # match_reasons
                            [],  # concerns - 简化版不使用
                            match.status,
                            tenant_id,
                            match.project_id,
                            match.engineer_id,
                        )
                        logger.debug(
                            f"更新匹配记录: {match.project_id} -> {match.engineer_id}"
                        )
                    else:
                        # 插入新记录
                        await conn.execute(
                            """
                            INSERT INTO project_engineer_matches (
                                id, tenant_id, project_id, engineer_id, matching_history_id,
                                match_score, confidence_score, skill_match_score, 
                                experience_match_score, japanese_level_match_score,
                                matched_skills, missing_skills, matched_experiences, 
                                missing_experiences, match_reasons, concerns, status
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                            """,
                            match.id,
                            tenant_id,
                            match.project_id,
                            match.engineer_id,
                            matching_history_id,
                            match.match_score,
                            match.confidence_score,
                            None,  # skill_match_score - 简化版不使用
                            None,  # experience_match_score - 简化版不使用
                            None,  # japanese_level_match_score - 简化版不使用
                            [],  # matched_skills - 简化版不使用
                            [],  # missing_skills - 简化版不使用
                            [],  # matched_experiences - 简化版不使用
                            [],  # missing_experiences - 简化版不使用
                            ["基于embedding相似度匹配"],  # match_reasons
                            [],  # concerns - 简化版不使用
                            match.status,
                        )
                        logger.debug(
                            f"插入新匹配记录: {match.project_id} -> {match.engineer_id}"
                        )

                    saved_matches.append(match)

                except Exception as e:
                    logger.error(f"保存匹配记录失败: {match.id}, 错误: {str(e)}")
                    # 打印详细错误信息用于调试
                    import traceback

                    logger.error(f"详细错误: {traceback.format_exc()}")
                    continue

        logger.info(f"成功保存 {len(saved_matches)}/{len(matches)} 个匹配记录")
        return saved_matches

    # ========== 查询匹配结果 ==========

    async def get_matching_history(
        self, tenant_id: UUID, history_id: Optional[UUID] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
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
                return [formatted_data]
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
                    formatted_histories.append(formatted_data)

                return formatted_histories

        except Exception as e:
            logger.error(f"获取匹配历史失败: {str(e)}")
            return []

    async def get_matches_by_history(
        self, history_id: UUID, tenant_id: UUID, limit: int = 100
    ) -> List[Dict[str, Any]]:
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
            return [dict(row) for row in matches_data]

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
                    SET status = $1, comment = $2, reviewed_by = $3, 
                        reviewed_at = $4, updated_at = $5
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

    # ========== 统计查询 ==========

    async def get_match_statistics(
        self, tenant_id: UUID, days: int = 30
    ) -> Dict[str, Any]:
        """获取匹配统计信息"""
        try:
            from datetime import timedelta

            start_date = datetime.utcnow() - timedelta(days=days)

            # 基础统计
            stats = await fetch_one(
                """
                SELECT 
                    COUNT(*) as total_sessions,
                    SUM(total_matches_generated) as total_matches,
                    AVG(processing_time_seconds) as avg_processing_time,
                    SUM(high_quality_matches) as total_high_quality
                FROM ai_matching_history 
                WHERE tenant_id = $1 AND started_at >= $2
                """,
                tenant_id,
                start_date,
            )

            return {
                "total_sessions": stats["total_sessions"] or 0,
                "total_matches": stats["total_matches"] or 0,
                "avg_processing_time": stats["avg_processing_time"] or 0,
                "total_high_quality": stats["total_high_quality"] or 0,
                "period_days": days,
            }

        except Exception as e:
            logger.error(f"获取匹配统计失败: {str(e)}")
            return {
                "total_sessions": 0,
                "total_matches": 0,
                "avg_processing_time": 0,
                "total_high_quality": 0,
                "period_days": days,
                "error": str(e),
            }

    # ========== 向量生成相关查询 ==========

    async def get_projects_with_embeddings(
        self, project_ids: List[UUID], tenant_id: UUID
    ) -> Dict[str, Dict[str, Any]]:
        """
        获取带向量的项目列表，返回缺失向量的项目信息
        
        Args:
            project_ids: 项目ID列表
            tenant_id: 租户ID
            
        Returns:
            Dict[str, Dict[str, Any]]: {project_id: project_data} 缺失向量的项目数据
        """
        if not project_ids:
            return {}
        
        try:
            query = """
            SELECT id, title, description, required_skills, preferred_skills,
                   experience_required, japanese_level_required
            FROM projects
            WHERE id = ANY($1::uuid[]) 
            AND tenant_id = $2
            AND (ai_match_embedding IS NULL OR ai_match_paraphrase IS NULL)
            AND is_active = true
            """
            
            results = await fetch_all(query, project_ids, tenant_id)
            
            projects_missing_embeddings = {}
            for row in results:
                project_data = dict(row)
                projects_missing_embeddings[str(project_data["id"])] = project_data
            
            logger.info(f"找到 {len(projects_missing_embeddings)} 个缺失向量的项目")
            return projects_missing_embeddings
            
        except Exception as e:
            logger.error(f"获取项目向量信息失败: {str(e)}")
            return {}

    async def get_engineers_with_embeddings(
        self, engineer_ids: List[UUID], tenant_id: UUID
    ) -> Dict[str, Dict[str, Any]]:
        """
        获取带向量的工程师列表，返回缺失向量的工程师信息
        
        Args:
            engineer_ids: 工程师ID列表
            tenant_id: 租户ID
            
        Returns:
            Dict[str, Dict[str, Any]]: {engineer_id: engineer_data} 缺失向量的工程师数据
        """
        if not engineer_ids:
            return {}
        
        try:
            query = """
            SELECT id, name, skills, experience, japanese_level, 
                   current_status, work_scope, role
            FROM engineers
            WHERE id = ANY($1::uuid[]) 
            AND tenant_id = $2
            AND (ai_match_embedding IS NULL OR ai_match_paraphrase IS NULL)
            AND is_active = true
            """
            
            results = await fetch_all(query, engineer_ids, tenant_id)
            
            engineers_missing_embeddings = {}
            for row in results:
                engineer_data = dict(row)
                engineers_missing_embeddings[str(engineer_data["id"])] = engineer_data
            
            logger.info(f"找到 {len(engineers_missing_embeddings)} 个缺失向量的工程师")
            return engineers_missing_embeddings
            
        except Exception as e:
            logger.error(f"获取工程师向量信息失败: {str(e)}")
            return {}

    async def update_project_embeddings(
        self, project_embeddings: List[Dict[str, Any]]
    ) -> int:
        """
        批量更新项目向量
        
        Args:
            project_embeddings: 包含id, paraphrase, embedding的项目向量数据列表
            
        Returns:
            int: 成功更新的数量
        """
        if not project_embeddings:
            return 0
        
        updated_count = 0
        
        try:
            async with get_db_connection() as conn:
                for item in project_embeddings:
                    try:
                        await conn.execute(
                            """
                            UPDATE projects
                            SET ai_match_paraphrase = $1, 
                                ai_match_embedding = $2::vector,
                                updated_at = NOW()
                            WHERE id = $3
                            """,
                            item["paraphrase"],
                            item["embedding"],
                            item["id"]
                        )
                        updated_count += 1
                        logger.debug(f"✅ 项目向量更新成功: {item['id']}")
                        
                    except Exception as e:
                        logger.error(f"❌ 更新项目向量失败 {item['id']}: {str(e)}")
                        continue
            
            logger.info(f"✅ 批量更新项目向量完成: {updated_count}/{len(project_embeddings)}")
            return updated_count
            
        except Exception as e:
            logger.error(f"❌ 批量更新项目向量失败: {str(e)}")
            return updated_count

    async def update_engineer_embeddings(
        self, engineer_embeddings: List[Dict[str, Any]]
    ) -> int:
        """
        批量更新工程师向量
        
        Args:
            engineer_embeddings: 包含id, paraphrase, embedding的工程师向量数据列表
            
        Returns:
            int: 成功更新的数量
        """
        if not engineer_embeddings:
            return 0
        
        updated_count = 0
        
        try:
            async with get_db_connection() as conn:
                for item in engineer_embeddings:
                    try:
                        await conn.execute(
                            """
                            UPDATE engineers
                            SET ai_match_paraphrase = $1, 
                                ai_match_embedding = $2::vector,
                                updated_at = NOW()
                            WHERE id = $3
                            """,
                            item["paraphrase"],
                            item["embedding"],
                            item["id"]
                        )
                        updated_count += 1
                        logger.debug(f"✅ 工程师向量更新成功: {item['id']}")
                        
                    except Exception as e:
                        logger.error(f"❌ 更新工程师向量失败 {item['id']}: {str(e)}")
                        continue
            
            logger.info(f"✅ 批量更新工程师向量完成: {updated_count}/{len(engineer_embeddings)}")
            return updated_count
            
        except Exception as e:
            logger.error(f"❌ 批量更新工程师向量失败: {str(e)}")
            return updated_count

    # ========== 工具方法 ==========

    def format_project_info(self, project: Dict[str, Any]) -> Dict[str, Any]:
        """格式化项目信息"""
        return {
            "id": str(project["id"]),
            "title": project.get("title", ""),
            "company": project.get("client_company", ""),
            "skills": project.get("skills", []),
            "experience": project.get("experience", ""),
            "japanese_level": project.get("japanese_level", ""),
            "status": project.get("status", ""),
        }

    def format_engineer_info(self, engineer: Dict[str, Any]) -> Dict[str, Any]:
        """格式化工程师信息"""
        return {
            "id": str(engineer["id"]),
            "name": engineer.get("name", ""),
            "skills": engineer.get("skills", []),
            "experience": engineer.get("experience", ""),
            "japanese_level": engineer.get("japanese_level", ""),
            "current_status": engineer.get("current_status", ""),
        }
