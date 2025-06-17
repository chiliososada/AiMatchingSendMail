# app/services/resume_parser_service.py
import asyncio
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
import time

from .extractors import (
    NameExtractor,
    GenderExtractor,
    AgeExtractor,
    BirthdateExtractor,
    NationalityExtractor,
    ArrivalYearExtractor,
    ExperienceExtractor,
    JapaneseLevelExtractor,
    SkillsExtractor,
    WorkScopeExtractor,
    RoleExtractor,
)

logger = logging.getLogger(__name__)


class ResumeParserService:
    """简历解析服务"""

    def __init__(self):
        """初始化所有提取器"""
        self.name_extractor = NameExtractor()
        self.gender_extractor = GenderExtractor()
        self.age_extractor = AgeExtractor()
        self.birthdate_extractor = BirthdateExtractor()
        self.nationality_extractor = NationalityExtractor()
        self.arrival_year_extractor = ArrivalYearExtractor()
        self.experience_extractor = ExperienceExtractor()
        self.japanese_level_extractor = JapaneseLevelExtractor()
        self.skills_extractor = SkillsExtractor()
        self.work_scope_extractor = WorkScopeExtractor()
        self.role_extractor = RoleExtractor()

        logger.info("简历解析服务初始化完成")

    async def parse_resume(self, file_path: str) -> Dict[str, Any]:
        """
        解析简历文件

        Args:
            file_path: Excel文件路径

        Returns:
            解析结果字典
        """
        start_time = time.time()

        try:
            # 在异步环境中运行同步的pandas操作
            all_data = await asyncio.to_thread(self._load_excel_data, file_path)

            if not all_data:
                return {
                    "success": False,
                    "error": "无法读取Excel文件或文件为空",
                    "parse_time": time.time() - start_time,
                }

            # 提取各项信息
            result = await self._extract_all_info(all_data)

            # 后处理
            result = await self._post_process(result)

            return {
                "success": True,
                "data": result,
                "error": None,
                "parse_time": time.time() - start_time,
            }

        except Exception as e:
            logger.error(f"解析简历失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "parse_time": time.time() - start_time,
            }

    def _load_excel_data(self, file_path: str) -> List[Dict[str, Any]]:
        """加载Excel数据"""
        all_data = []
        file_obj = Path(file_path)

        # 使用不同的引擎尝试读取
        engines = ["openpyxl", "xlrd"]

        for engine in engines:
            try:
                if file_obj.suffix == ".xls" and engine == "openpyxl":
                    continue
                if file_obj.suffix == ".xlsx" and engine == "xlrd":
                    continue

                excel_file = pd.ExcelFile(file_path, engine=engine)

                for sheet_name in excel_file.sheet_names:
                    try:
                        df = pd.read_excel(
                            excel_file,
                            sheet_name=sheet_name,
                            header=None,
                            dtype=str,
                            na_values=[""],
                            keep_default_na=False,
                        )

                        if not df.empty:
                            all_data.append({"sheet_name": sheet_name, "df": df})

                    except Exception as e:
                        logger.warning(f"读取工作表 {sheet_name} 失败: {e}")

                if all_data:
                    break

            except Exception as e:
                logger.warning(f"使用引擎 {engine} 读取失败: {e}")
                continue

        return all_data

    async def _extract_all_info(self, all_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """提取所有信息"""
        # 在异步环境中运行同步的提取操作
        result = await asyncio.to_thread(self._sync_extract_all_info, all_data)
        return result

    def _sync_extract_all_info(self, all_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """同步提取所有信息"""
        result = {}

        # 按顺序提取各项信息
        result["name"] = self.name_extractor.extract(all_data)
        result["gender"] = self.gender_extractor.extract(all_data)
        result["birthdate"] = self.birthdate_extractor.extract(all_data)
        result["age"] = self.age_extractor.extract(all_data, result["birthdate"])
        result["nationality"] = self.nationality_extractor.extract(all_data)
        result["arrival_year_japan"] = self.arrival_year_extractor.extract(
            all_data, result["birthdate"]
        )
        result["experience"] = self.experience_extractor.extract(all_data)
        result["japanese_level"] = self.japanese_level_extractor.extract(all_data)
        result["skills"] = self.skills_extractor.extract(all_data)
        result["work_scope"] = self.work_scope_extractor.extract(all_data)
        result["roles"] = self.role_extractor.extract(all_data)

        return result

    async def _post_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """后处理结果"""
        # 确保所有None值正确处理
        for key, value in result.items():
            if value is None or (isinstance(value, list) and len(value) == 0):
                result[key] = None

        # 技能去重
        if result.get("skills"):
            seen = set()
            unique_skills = []
            for skill in result["skills"]:
                if skill.lower() not in seen:
                    seen.add(skill.lower())
                    unique_skills.append(skill)
            result["skills"] = unique_skills

        return result

    async def parse_batch(self, file_paths: List[str]) -> Dict[str, Any]:
        """批量解析简历"""
        results = []
        success_count = 0
        failed_count = 0

        for file_path in file_paths:
            result = await self.parse_resume(file_path)

            if result["success"]:
                success_count += 1
            else:
                failed_count += 1

            results.append({"file_name": Path(file_path).name, "result": result})

        return {
            "total": len(file_paths),
            "success_count": success_count,
            "failed_count": failed_count,
            "results": results,
        }
