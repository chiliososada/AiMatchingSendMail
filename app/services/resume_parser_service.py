# app/services/resume_parser_service.py
import asyncio
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

from app.utils.text_utils import dataframe_to_text
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

    def _normalize_result(self, value: Any) -> Optional[Any]:
        """标准化提取结果 - 关键修复函数

        Args:
            value: 提取的原始值

        Returns:
            标准化后的值：
            - 空字符串 -> None
            - 空列表 -> None
            - 其他空值 -> None
            - 有效值 -> 原值
        """
        if value is None:
            return None

        # 处理字符串
        if isinstance(value, str):
            value = value.strip()
            return value if value else None  # 空字符串转换为None

        # 处理列表
        if isinstance(value, list):
            return value if value else None  # 空列表转换为None

        # 其他类型直接返回
        return value

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
                            text = dataframe_to_text(df)
                            all_data.append(
                                {
                                    "sheet_name": sheet_name,
                                    "df": df,
                                    "text": text,
                                }
                            )

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
        """同步提取所有信息 - 关键修复：添加_normalize_result调用"""
        result = {}

        logger.info(f"开始提取信息，数据集数量: {len(all_data)}")

        # 验证数据结构
        for i, data in enumerate(all_data):
            logger.info(f"Sheet {i}: {data.get('sheet_name', 'Unknown')}")
            logger.info(f"  - 包含df: {'df' in data}")
            logger.info(f"  - 包含text: {'text' in data}")
            if "df" in data:
                df = data["df"]
                logger.info(f"  - DataFrame形状: {df.shape}")

        # 按顺序提取各项信息 - 关键修复：每个字段都调用_normalize_result
        name_result = self.name_extractor.extract(all_data)
        result["name"] = self._normalize_result(name_result)
        logger.info(f"姓名提取结果: {result['name']}")

        gender_result = self.gender_extractor.extract(all_data)
        result["gender"] = self._normalize_result(gender_result)
        logger.info(f"性别提取结果: {result['gender']}")

        birthdate_result = self.birthdate_extractor.extract(all_data)
        result["birthdate"] = self._normalize_result(birthdate_result)
        logger.info(f"生日提取结果: {result['birthdate']}")

        age_result = self.age_extractor.extract(all_data, result["birthdate"])
        result["age"] = self._normalize_result(age_result)
        logger.info(f"年龄提取结果: {result['age']}")

        nationality_result = self.nationality_extractor.extract(all_data)
        result["nationality"] = self._normalize_result(nationality_result)
        logger.info(f"国籍提取结果: {result['nationality']}")

        # 🔥 关键修复：来日年份提取结果标准化
        arrival_result = self.arrival_year_extractor.extract(
            all_data, result["birthdate"]
        )
        result["arrival_year_japan"] = self._normalize_result(arrival_result)
        logger.info(f"来日年份提取结果: {result['arrival_year_japan']}")

        # 🔥 关键修复：经验提取结果标准化
        experience_result = self.experience_extractor.extract(all_data)
        result["experience"] = self._normalize_result(experience_result)
        logger.info(f"经验提取结果: {result['experience']}")

        japanese_result = self.japanese_level_extractor.extract(all_data)
        result["japanese_level"] = self._normalize_result(japanese_result)
        logger.info(f"日语水平提取结果: {result['japanese_level']}")

        skills_result = self.skills_extractor.extract(all_data)
        result["skills"] = self._normalize_result(skills_result)
        logger.info(f"技能提取结果: {len(skills_result) if skills_result else 0}个")

        work_scope_result = self.work_scope_extractor.extract(all_data)
        result["work_scope"] = self._normalize_result(work_scope_result)
        logger.info(f"工作范围提取结果: {result['work_scope']}")

        roles_result = self.role_extractor.extract(all_data)
        result["roles"] = self._normalize_result(roles_result)
        logger.info(f"角色提取结果: {result['roles']}")

        return result

    async def _post_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """后处理结果 - 已有_normalize_result处理，这里主要做去重等逻辑"""

        # 技能去重（如果已经有值的话）
        if result.get("skills"):
            seen = set()
            unique_skills = []
            for skill in result["skills"]:
                if skill and skill.lower() not in seen:
                    seen.add(skill.lower())
                    unique_skills.append(skill)
            result["skills"] = unique_skills if unique_skills else None

        # 最终兜底处理：确保所有None值统一
        for key, value in result.items():
            if value == "" or (isinstance(value, list) and len(value) == 0):
                result[key] = None

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
