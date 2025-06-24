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
        # 修复：将 schema_extra 改为 json_schema_extra
        json_schema_extra = {
            "example": {
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                "max_matches": 10,
                "min_score": 0.7,
                "filters": {"japanese_level": ["N1", "N2"], "status": ["available"]},
            }
        }


class ProjectToEngineersMatchRequest(AIMatchingRequest):
    """案件匹配技术者请求 - 为指定项目找到合适的技术者"""

    project_id: UUID = Field(description="要匹配的项目ID")

    # 案件特定的匹配权重
    weights: Optional[Dict[str, float]] = Field(
        default={
            "skill_match": 0.3,
            "experience_match": 0.25,
            "project_experience_match": 0.2,
            "japanese_level_match": 0.15,
            "location_match": 0.1,
        },
        description="匹配权重配置 (当前版本使用AI向量相似度)",
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "project_id": "c744bb81-c4f5-4550-bdc3-5dd217e81f68",
                "tenant_id": "60714cf2-ec23-4cce-9029-fb4af9c799c5",
                "max_matches": 10,
                "min_score": 0.7,
                "filters": {
                    "japanese_level": ["N1", "N2"],
                    "current_status": ["available"]
                }
            }
        }


class EngineerToProjectsMatchRequest(AIMatchingRequest):
    """技术者匹配案件请求 - 为指定技术者找到合适的项目"""

    engineer_id: UUID = Field(description="要匹配的技术者ID")

    # 简历特定的匹配权重
    weights: Optional[Dict[str, float]] = Field(
        default={
            "skill_match": 0.35,
            "experience_match": 0.3,
            "budget_match": 0.2,
            "location_match": 0.15,
        },
        description="匹配权重配置 (当前版本使用AI向量相似度)",
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "engineer_id": "307bdf0a-f7eb-4466-9f78-21b67db244b0",
                "tenant_id": "60714cf2-ec23-4cce-9029-fb4af9c799c5",
                "max_matches": 10,
                "min_score": 0.7,
                "filters": {}
            }
        }


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
    project_title: Optional[str] = Field(None, description="项目标题")
    engineer_name: Optional[str] = Field(None, description="技术者姓名")
    status: str = Field("未保存", description="匹配状态")
    created_at: datetime = Field(description="匹配创建时间")
    
    # 项目担当者信息
    project_manager_name: Optional[str] = Field(None, description="案件担当者姓名")
    project_manager_email: Optional[str] = Field(None, description="案件担当者邮箱")
    project_created_by: Optional[str] = Field(None, description="项目所属担当者ID")
    
    # 技术者公司信息
    engineer_company_name: Optional[str] = Field(None, description="技术者所属公司/组织名称 (从engineers.company_name获取)")
    engineer_company_type: Optional[str] = Field(None, description="技术者公司类型 (自社/他社等)")
    engineer_manager_name: Optional[str] = Field(None, description="技术者担当者姓名 (从engineers.manager_name获取)")
    engineer_manager_email: Optional[str] = Field(None, description="技术者担当者邮箱 (从engineers.manager_email获取)")

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


class ProjectToEngineersResponse(BaseModel):
    """案件匹配技术者响应 - 根据项目匹配合适的技术者"""

    matching_history: MatchingHistoryResponse = Field(description="匹配历史信息")
    project_info: Dict[str, Any] = Field(description="项目基本信息，包含担当者信息")
    matched_engineers: List[MatchResult] = Field(description="匹配到的技术者列表，包含公司和担当者信息")
    
    # 统计信息
    total_matches: int = Field(description="总匹配数量")
    high_quality_matches: int = Field(description="高质量匹配数量 (分数>=0.8)")
    processing_time_seconds: float = Field(description="处理时间(秒)")
    
    # 建议
    recommendations: List[str] = Field(default_factory=list, description="匹配建议和说明")
    
    class Config:
        json_schema_extra = {
            "example": {
                "matching_history": {
                    "id": "496dc472-4d15-448c-bdf6-804e69082066",
                    "tenant_id": "60714cf2-ec23-4cce-9029-fb4af9c799c5",
                    "matching_type": "project_to_engineers",
                    "execution_status": "completed"
                },
                "project_info": {
                    "id": "c744bb81-c4f5-4550-bdc3-5dd217e81f68",
                    "title": "案件タイトル *",
                    "skills": ["Java", "Spring Boot", "SQL"],
                    "manager": {
                        "name": "案件担当者名",
                        "email": "project-manager@company.com"
                    },
                    "created_by": "60714cf2-ec23-4cce-9029-fb4af9c799c5"
                },
                "matched_engineers": [
                    {
                        "project_title": "案件タイトル *",
                        "engineer_name": "技术者姓名",
                        "match_score": 0.95,
                        "project_manager_name": "案件担当者名",
                        "project_manager_email": "project-manager@company.com",
                        "engineer_company_name": "技术者公司名",
                        "engineer_company_type": "自社",
                        "engineer_manager_name": "技术者担当者名",
                        "engineer_manager_email": "engineer-manager@company.com"
                    }
                ],
                "total_matches": 1,
                "high_quality_matches": 1,
                "processing_time_seconds": 0.8,
                "recommendations": ["找到 1 个高质量匹配"]
            }
        }


class EngineerToProjectsResponse(BaseModel):
    """技术者匹配案件响应 - 根据技术者匹配合适的项目"""

    matching_history: MatchingHistoryResponse = Field(description="匹配历史信息")
    engineer_info: Dict[str, Any] = Field(description="技术者基本信息，包含公司信息")
    matched_projects: List[MatchResult] = Field(description="匹配到的项目列表，包含担当者和技术者信息")
    
    # 统计信息
    total_matches: int = Field(description="总匹配数量")
    high_quality_matches: int = Field(description="高质量匹配数量 (分数>=0.8)")
    processing_time_seconds: float = Field(description="处理时间(秒)")
    
    # 建议
    recommendations: List[str] = Field(default_factory=list, description="匹配建议和说明")
    
    class Config:
        json_schema_extra = {
            "example": {
                "matching_history": {
                    "id": "496dc472-4d15-448c-bdf6-804e69082066",
                    "tenant_id": "60714cf2-ec23-4cce-9029-fb4af9c799c5",
                    "matching_type": "engineer_to_projects",
                    "execution_status": "completed"
                },
                "engineer_info": {
                    "id": "307bdf0a-f7eb-4466-9f78-21b67db244b0",
                    "name": "山本",
                    "skills": ["Java", "Spring Boot", "SQL"],
                    "company_name": "株式会社テック",
                    "company_type": "自社",
                    "manager_email": "tech@company.com"
                },
                "matched_projects": [
                    {
                        "project_title": "案件タイトル *",
                        "engineer_name": "山本",
                        "match_score": 1.0,
                        "project_manager_name": "担当者名",
                        "project_manager_email": "manager@company.com",
                        "engineer_company_name": "株式会社テック",
                        "engineer_manager_name": "株式会社テック",
                        "engineer_manager_email": "tech@company.com"
                    }
                ],
                "total_matches": 1,
                "high_quality_matches": 1,
                "processing_time_seconds": 0.5,
                "recommendations": ["找到 1 个高质量匹配"]
            }
        }


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
