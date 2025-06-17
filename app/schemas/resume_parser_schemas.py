# app/schemas/resume_parser_schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class ResumeParseRequest(BaseModel):
    """简历解析请求模型"""

    tenant_id: UUID = Field(..., description="租户ID")
    file_name: str = Field(..., description="文件名")

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                "file_name": "resume.xlsx",
            }
        }


class ResumeParseResponse(BaseModel):
    """简历解析响应模型"""

    success: bool = Field(..., description="解析是否成功")
    data: Optional[Dict[str, Any]] = Field(None, description="解析结果")
    error: Optional[str] = Field(None, description="错误信息")
    parse_time: float = Field(..., description="解析耗时（秒）")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "name": "张三",
                    "gender": "男",
                    "age": 30,
                    "birthdate": "1994-01-01",
                    "nationality": "中国",
                    "arrival_year_japan": 2020,
                    "experience": "5年",
                    "japanese_level": "N2",
                    "skills": ["Java", "Python", "MySQL"],
                    "work_scope": ["開発", "設計"],
                    "roles": ["SE", "PG"],
                },
                "error": None,
                "parse_time": 1.23,
            }
        }


class BatchResumeParseRequest(BaseModel):
    """批量简历解析请求"""

    tenant_id: UUID
    file_names: List[str] = Field(..., description="文件名列表")


class BatchResumeParseResponse(BaseModel):
    """批量简历解析响应"""

    total: int = Field(..., description="总数")
    success_count: int = Field(..., description="成功数")
    failed_count: int = Field(..., description="失败数")
    results: List[Dict[str, Any]] = Field(..., description="解析结果列表")
