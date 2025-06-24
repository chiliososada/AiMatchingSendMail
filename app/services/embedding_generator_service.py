# app/services/embedding_generator_service.py
"""
向量生成服务 - 单例模式
用于自动生成AI匹配用的embedding向量，支持延迟加载和批量处理
"""

import logging
import time
from typing import List, Dict, Any, Optional
from threading import Lock
import asyncio

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
except ImportError:
    SentenceTransformer = None
    np = None

logger = logging.getLogger(__name__)


class EmbeddingGeneratorService:
    """向量生成服务 - 单例模式"""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.model_name = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
        self.model = None
        self.batch_size = 32
        self.vector_dimension = 768
        self._model_load_lock = Lock()
        self._initialized = True
        
        logger.info("向量生成服务初始化完成（延迟加载模式）")
    
    def _load_model(self):
        """延迟加载模型（线程安全）"""
        if self.model is not None:
            return
            
        with self._model_load_lock:
            # 双重检查锁定模式
            if self.model is not None:
                return
                
            if SentenceTransformer is None:
                raise ImportError(
                    "缺少依赖库，请运行: pip install sentence-transformers torch numpy"
                )
            
            try:
                start_time = time.time()
                logger.info(f"正在加载向量模型: {self.model_name}")
                
                self.model = SentenceTransformer(self.model_name)
                
                load_time = time.time() - start_time
                logger.info(f"✅ 向量模型加载成功，耗时: {load_time:.2f}秒")
                
            except Exception as e:
                logger.error(f"❌ 向量模型加载失败: {str(e)}")
                raise Exception(f"向量模型加载失败: {str(e)}")
    
    def create_project_paraphrase(self, project: Dict[str, Any]) -> str:
        """
        从项目数据生成用于向量化的文本
        
        Args:
            project: 项目数据字典
            
        Returns:
            str: 用于向量化的文本
        """
        parts = []
        
        # 项目标题
        if project.get("title"):
            parts.append(f"项目: {project['title']}")
        
        # 项目描述
        if project.get("description"):
            description = str(project["description"])[:200]  # 限制长度
            parts.append(f"描述: {description}")
        
        # 技能要求
        if project.get("required_skills"):
            skills = project["required_skills"]
            if isinstance(skills, list):
                parts.append(f"必需技能: {', '.join(skills)}")
            elif isinstance(skills, str):
                parts.append(f"必需技能: {skills}")
        
        # 优选技能
        if project.get("preferred_skills"):
            skills = project["preferred_skills"]
            if isinstance(skills, list):
                parts.append(f"优选技能: {', '.join(skills)}")
            elif isinstance(skills, str):
                parts.append(f"优选技能: {skills}")
        
        # 经验要求
        if project.get("experience_required"):
            parts.append(f"经验要求: {project['experience_required']}")
        
        # 日语水平要求
        if project.get("japanese_level_required"):
            parts.append(f"日语要求: {project['japanese_level_required']}")
        
        # 如果没有任何有用信息，返回默认文本
        if not parts:
            return "项目信息不完整"
        
        return " | ".join(parts)
    
    def create_engineer_paraphrase(self, engineer: Dict[str, Any]) -> str:
        """
        从工程师数据生成用于向量化的文本
        
        Args:
            engineer: 工程师数据字典
            
        Returns:
            str: 用于向量化的文本
        """
        parts = []
        
        # 工程师姓名
        if engineer.get("name"):
            parts.append(f"工程师: {engineer['name']}")
        
        # 技能
        if engineer.get("skills"):
            skills = engineer["skills"]
            if isinstance(skills, list):
                parts.append(f"技能: {', '.join(skills)}")
            elif isinstance(skills, str):
                parts.append(f"技能: {skills}")
        
        # 经验描述
        if engineer.get("experience"):
            experience = str(engineer["experience"])[:200]  # 限制长度
            parts.append(f"经验: {experience}")
        
        # 日语水平
        if engineer.get("japanese_level"):
            parts.append(f"日语: {engineer['japanese_level']}")
        
        # 当前状态
        if engineer.get("current_status"):
            parts.append(f"状态: {engineer['current_status']}")
        
        # 工作范围偏好
        if engineer.get("work_scope"):
            parts.append(f"工作范围: {engineer['work_scope']}")
        
        # 角色类型
        if engineer.get("role"):
            parts.append(f"角色: {engineer['role']}")
        
        # 如果没有任何有用信息，返回默认文本
        if not parts:
            return "工程师信息不完整"
        
        return " | ".join(parts)
    
    def generate_embeddings(self, texts: List[str]) -> List[str]:
        """
        批量生成向量并转换为PostgreSQL VECTOR格式字符串
        
        Args:
            texts: 文本列表
            
        Returns:
            List[str]: PostgreSQL VECTOR格式的字符串列表
        """
        if not texts:
            return []
        
        # 确保模型已加载
        self._load_model()
        
        try:
            start_time = time.time()
            
            # 过滤和清理文本
            valid_texts = []
            for text in texts:
                if text and isinstance(text, str) and text.strip():
                    valid_texts.append(text.strip())
                else:
                    valid_texts.append("无内容")
            
            logger.info(f"开始生成 {len(valid_texts)} 个向量...")
            
            # 生成embeddings
            embeddings = self.model.encode(
                valid_texts, 
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            
            # 转换为PostgreSQL VECTOR格式字符串
            vector_strings = []
            for emb in embeddings:
                # 确保是numpy数组并转换为列表
                if hasattr(emb, 'tolist'):
                    emb_list = emb.tolist()
                else:
                    emb_list = list(emb)
                
                # 格式化为PostgreSQL VECTOR格式: [1.0,2.0,3.0]
                vector_str = "[" + ",".join(f"{x:.6f}" for x in emb_list) + "]"
                vector_strings.append(vector_str)
            
            generation_time = time.time() - start_time
            logger.info(f"✅ 向量生成完成，耗时: {generation_time:.2f}秒，平均: {generation_time/len(texts):.3f}秒/个")
            
            return vector_strings
            
        except Exception as e:
            logger.error(f"❌ 向量生成失败: {str(e)}")
            raise Exception(f"向量生成失败: {str(e)}")
    
    def generate_single_embedding(self, text: str) -> str:
        """
        生成单个向量
        
        Args:
            text: 输入文本
            
        Returns:
            str: PostgreSQL VECTOR格式的字符串
        """
        if not text or not isinstance(text, str):
            text = "无内容"
        
        vector_strings = self.generate_embeddings([text])
        return vector_strings[0] if vector_strings else "[" + ",".join(["0.0"] * self.vector_dimension) + "]"
    
    def _batch_items(self, items: List[Any], batch_size: Optional[int] = None) -> List[List[Any]]:
        """
        将列表分批处理
        
        Args:
            items: 要分批的项目列表
            batch_size: 批次大小，默认使用self.batch_size
            
        Returns:
            List[List[Any]]: 分批后的列表
        """
        if batch_size is None:
            batch_size = self.batch_size
        
        batches = []
        for i in range(0, len(items), batch_size):
            batches.append(items[i:i + batch_size])
        
        return batches
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息
        
        Returns:
            Dict[str, Any]: 模型信息
        """
        return {
            "model_name": self.model_name,
            "vector_dimension": self.vector_dimension,
            "batch_size": self.batch_size,
            "model_loaded": self.model is not None,
        }


# 创建全局实例
embedding_service = EmbeddingGeneratorService()