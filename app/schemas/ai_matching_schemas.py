# app/schemas/ai_matching_schemas.py
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID


class AIMatchingRequest(BaseModel):
    """AI匹配基础请求"""

    tenant_id: UUID
    executed_by: Optional[UUID] = None
    matching_type: str = "auto"
    trigger_type: str = "api"

    # 匹配配置
    max_matches: int = Field(default=10, ge=1, le=100, description="最大匹配数量")
    min_score: float = Field(default=0.6, ge=0.0, le=1.0, description="最小匹配分数")

    # 筛选条件
    filters: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="筛选条件"
    )

    class Config:
        schema_extra = {
            "example": {
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                "max_matches": 10,
                "min_score": 0.7,
                "filters": {"japanese_level": ["N1", "N2"], "status": ["available"]},
            }
        }


class ProjectToEngineersMatchRequest(AIMatchingRequest):
    """案件匹配简历请求"""

    project_id: UUID

    # 案件特定的匹配权重
    weights: Optional[Dict[str, float]] = Field(
        default={
            "skill_match": 0.3,
            "experience_match": 0.25,
            "project_experience_match": 0.2,
            "japanese_level_match": 0.15,
            "location_match": 0.1,
        },
        description="匹配权重配置",
    )


class EngineerToProjectsMatchRequest(AIMatchingRequest):
    """简历匹配案件请求"""

    engineer_id: UUID

    # 简历特定的匹配权重
    weights: Optional[Dict[str, float]] = Field(
        default={
            "skill_match": 0.35,
            "experience_match": 0.3,
            "budget_match": 0.2,
            "location_match": 0.15,
        },
        description="匹配权重配置",
    )


class BulkMatchingRequest(AIMatchingRequest):
    """批量匹配请求"""

    project_ids: Optional[List[UUID]] = Field(
        default=None, description="案件ID列表，为空则匹配所有活跃案件"
    )
    engineer_ids: Optional[List[UUID]] = Field(
        default=None, description="简历ID列表，为空则匹配所有可用简历"
    )

    # 批量匹配特定设置
    batch_size: int = Field(default=50, ge=10, le=100, description="批处理大小")
    generate_top_matches_only: bool = Field(
        default=True, description="只生成高质量匹配"
    )

    @validator("project_ids", "engineer_ids")
    def validate_ids_not_empty_together(cls, v, values):
        """验证不能同时为空列表"""
        if isinstance(v, list) and len(v) == 0:
            raise ValueError("ID列表不能为空，请传入None或有效的ID列表")
        return v


class MatchResult(BaseModel):
    """单个匹配结果"""

    id: UUID
    project_id: UUID
    engineer_id: UUID
    match_score: float
    confidence_score: float

    # 详细分数
    skill_match_score: Optional[float] = None
    experience_match_score: Optional[float] = None
    project_experience_match_score: Optional[float] = None
    japanese_level_match_score: Optional[float] = None
    budget_match_score: Optional[float] = None
    location_match_score: Optional[float] = None

    # 匹配详情
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    matched_experiences: List[str] = Field(default_factory=list)
    missing_experiences: List[str] = Field(default_factory=list)
    project_experience_match: List[str] = Field(default_factory=list)
    missing_project_experience: List[str] = Field(default_factory=list)
    match_reasons: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)

    # 基础信息
    project_title: Optional[str] = None
    engineer_name: Optional[str] = None
    status: str = "未保存"
    created_at: datetime

    class Config:
        from_attributes = True


class MatchingHistoryResponse(BaseModel):
    """匹配历史响应"""

    id: UUID
    tenant_id: UUID
    executed_by: Optional[UUID]
    matching_type: str
    trigger_type: str
    execution_status: str

    started_at: datetime
    completed_at: Optional[datetime]

    # 统计信息
    total_projects_input: int
    total_engineers_input: int
    total_matches_generated: int
    high_quality_matches: int
    processing_time_seconds: Optional[int]

    # 数据
    project_ids: List[UUID] = Field(default_factory=list)
    engineer_ids: List[UUID] = Field(default_factory=list)

    # AI配置和统计
    ai_config: Dict[str, Any] = Field(default_factory=dict)
    ai_model_version: Optional[str] = None
    statistics: Dict[str, Any] = Field(default_factory=dict)
    filters: Dict[str, Any] = Field(default_factory=dict)

    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class AIMatchingResponse(BaseModel):
    """AI匹配响应"""

    matching_history: MatchingHistoryResponse
    matches: List[MatchResult]

    # 响应统计
    total_matches: int
    high_quality_matches: int
    processing_time_seconds: float

    # 额外信息
    recommendations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ProjectToEngineersResponse(AIMatchingResponse):
    """案件匹配简历响应"""

    project_info: Dict[str, Any]
    matched_engineers: List[MatchResult]


class EngineerToProjectsResponse(AIMatchingResponse):
    """简历匹配案件响应"""

    engineer_info: Dict[str, Any]
    matched_projects: List[MatchResult]


class BulkMatchingResponse(AIMatchingResponse):
    """批量匹配响应"""

    batch_summary: Dict[str, Any]
    top_matches_by_project: Dict[str, List[MatchResult]] = Field(default_factory=dict)
    top_matches_by_engineer: Dict[str, List[MatchResult]] = Field(default_factory=dict)


class MatchingStatsRequest(BaseModel):
    """匹配统计请求"""

    tenant_id: UUID
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    matching_type: Optional[str] = None


class MatchingStatsResponse(BaseModel):
    """匹配统计响应"""

    total_matching_sessions: int
    total_matches_generated: int
    average_match_score: float
    high_quality_match_rate: float

    # 按类型统计
    stats_by_type: Dict[str, Any] = Field(default_factory=dict)

    # 趋势数据
    daily_stats: List[Dict[str, Any]] = Field(default_factory=list)

    # 热门技能和需求
    top_matched_skills: List[Dict[str, Any]] = Field(default_factory=list)
    top_project_types: List[Dict[str, Any]] = Field(default_factory=list)
