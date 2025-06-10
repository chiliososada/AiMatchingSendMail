#!/usr/bin/env python3
# embedding_matching_debugger_vector_fixed.py - 修复vector数据类型问题
import asyncio
import sys
from pathlib import Path
import numpy as np
import json
import re
from typing import List, Tuple, Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.database import fetch_one, fetch_all


class VectorFixedEmbeddingDebugger:
    """修复版：解决vector数据类型转换问题"""

    def __init__(self):
        self.tenant_id = "33723dd6-cf28-4dab-975c-f883f5389d04"

    def _parse_vector_string(self, vector_str: str) -> np.ndarray:
        """将PostgreSQL vector字符串转换为numpy数组"""
        try:
            if not vector_str:
                return np.array([])

            # 处理PostgreSQL vector格式：'[1,2,3]' 或 '[1.0, 2.0, 3.0]'
            if isinstance(vector_str, str):
                # 移除外层的方括号
                vector_str = vector_str.strip()
                if vector_str.startswith("[") and vector_str.endswith("]"):
                    vector_str = vector_str[1:-1]

                # 分割并转换为浮点数
                if vector_str:
                    values = [
                        float(x.strip()) for x in vector_str.split(",") if x.strip()
                    ]
                    return np.array(values, dtype=np.float32)
                else:
                    return np.array([])
            elif isinstance(vector_str, (list, tuple)):
                # 如果已经是列表或元组
                return np.array(vector_str, dtype=np.float32)
            else:
                print(f"未知的vector数据类型: {type(vector_str)}")
                return np.array([])

        except Exception as e:
            print(f"解析vector失败: {str(e)}, 数据: {str(vector_str)[:100]}...")
            return np.array([])

    async def check_vector_data_format(self):
        """检查vector数据格式"""
        print("🔍 检查vector数据格式...")

        try:
            # 检查项目的embedding数据
            project = await fetch_one(
                """
                SELECT id, title, ai_match_embedding
                FROM projects 
                WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
                ORDER BY created_at DESC LIMIT 1
                """,
                self.tenant_id,
            )

            engineer = await fetch_one(
                """
                SELECT id, name, ai_match_embedding
                FROM engineers 
                WHERE tenant_id = $1 AND is_active = true AND ai_match_embedding IS NOT NULL
                ORDER BY created_at DESC LIMIT 1
                """,
                self.tenant_id,
            )

            if not project or not engineer:
                print("❌ 没有找到测试数据")
                return False

            print(f"✅ 找到测试数据:")
            print(f"   项目: {project['title']}")
            print(f"   简历: {engineer['name']}")

            # 分析embedding数据类型和格式
            project_emb_raw = project["ai_match_embedding"]
            engineer_emb_raw = engineer["ai_match_embedding"]

            print(f"\n📊 原始数据类型分析:")
            print(f"   项目embedding类型: {type(project_emb_raw)}")
            print(f"   简历embedding类型: {type(engineer_emb_raw)}")

            if isinstance(project_emb_raw, str):
                print(f"   项目embedding长度: {len(project_emb_raw)} 字符")
                print(f"   项目embedding预览: {project_emb_raw[:100]}...")
            else:
                print(
                    f"   项目embedding长度: {len(project_emb_raw) if hasattr(project_emb_raw, '__len__') else 'Unknown'}"
                )

            # 尝试转换为numpy数组
            print(f"\n🔄 转换为numpy数组:")

            project_emb = self._parse_vector_string(project_emb_raw)
            engineer_emb = self._parse_vector_string(engineer_emb_raw)

            if project_emb.size == 0 or engineer_emb.size == 0:
                print("❌ vector转换失败")
                return False

            print(
                f"   项目embedding数组: 形状={project_emb.shape}, 类型={project_emb.dtype}"
            )
            print(
                f"   简历embedding数组: 形状={engineer_emb.shape}, 类型={engineer_emb.dtype}"
            )
            print(
                f"   项目向量范围: [{project_emb.min():.4f}, {project_emb.max():.4f}]"
            )
            print(
                f"   简历向量范围: [{engineer_emb.min():.4f}, {engineer_emb.max():.4f}]"
            )

            # 测试数学运算
            print(f"\n🧮 测试数学运算:")
            try:
                dot_product = np.dot(project_emb, engineer_emb)
                project_norm = np.linalg.norm(project_emb)
                engineer_norm = np.linalg.norm(engineer_emb)

                if project_norm > 0 and engineer_norm > 0:
                    cosine_similarity = dot_product / (project_norm * engineer_norm)
                    print(f"   ✅ 点积计算成功: {dot_product:.6f}")
                    print(
                        f"   ✅ 向量模长: 项目={project_norm:.6f}, 简历={engineer_norm:.6f}"
                    )
                    print(f"   ✅ 余弦相似度: {cosine_similarity:.6f}")

                    # 转换为[0,1]范围
                    normalized_similarity = (cosine_similarity + 1) / 2
                    print(f"   ✅ 标准化相似度: {normalized_similarity:.6f}")

                    return True
                else:
                    print("   ❌ 向量模长为0，无法计算相似度")
                    return False

            except Exception as e:
                print(f"   ❌ 数学运算失败: {str(e)}")
                return False

        except Exception as e:
            print(f"❌ 检查vector数据格式失败: {str(e)}")
            import traceback

            print(f"详细错误:\n{traceback.format_exc()}")
            return False

    async def test_pgvector_operators_fixed(self):
        """测试修复版pgvector操作符"""
        print("\n🧮 测试修复版pgvector操作符...")

        try:
            # 获取测试数据
            project = await fetch_one(
                "SELECT * FROM projects WHERE tenant_id = $1 AND ai_match_embedding IS NOT NULL LIMIT 1",
                self.tenant_id,
            )

            engineer = await fetch_one(
                "SELECT * FROM engineers WHERE tenant_id = $1 AND ai_match_embedding IS NOT NULL LIMIT 1",
                self.tenant_id,
            )

            if not project or not engineer:
                print("❌ 没有测试数据")
                return

            print(f"测试对象: {project['title']} vs {engineer['name']}")

            # 手动计算作为基准
            project_emb = self._parse_vector_string(project["ai_match_embedding"])
            engineer_emb = self._parse_vector_string(engineer["ai_match_embedding"])

            if project_emb.size == 0 or engineer_emb.size == 0:
                print("❌ vector解析失败")
                return

            manual_dot = np.dot(project_emb, engineer_emb)
            manual_norm_p = np.linalg.norm(project_emb)
            manual_norm_e = np.linalg.norm(engineer_emb)
            manual_cosine = manual_dot / (manual_norm_p * manual_norm_e)

            print(f"\n📊 手动计算基准:")
            print(f"   点积: {manual_dot:.6f}")
            print(f"   余弦相似度: {manual_cosine:.6f}")
            print(f"   标准化相似度: {(manual_cosine + 1) / 2:.6f}")

            # 测试各种pgvector操作符
            operators = [
                ("<=>", "余弦距离"),
                ("<#>", "负内积"),
                ("<->", "欧几里得距离"),
            ]

            print(f"\n🔬 pgvector操作符测试:")
            for op, desc in operators:
                try:
                    result = await fetch_one(
                        f"SELECT ai_match_embedding {op} $1 as result FROM engineers WHERE id = $2",
                        project["ai_match_embedding"],
                        engineer["id"],
                    )

                    if result:
                        value = result["result"]
                        print(f"   {op} ({desc}): {value:.6f}")

                        # 如果是余弦距离，计算相似度
                        if op == "<=>":
                            similarity = 1 - value
                            print(f"      → 余弦相似度: {similarity:.6f}")
                            print(
                                f"      → 与手动计算差异: {abs(similarity - manual_cosine):.6f}"
                            )

                        # 如果是负内积，计算实际内积
                        elif op == "<#>":
                            actual_dot = -value
                            print(f"      → 实际内积: {actual_dot:.6f}")
                            print(
                                f"      → 与手动计算差异: {abs(actual_dot - manual_dot):.6f}"
                            )

                except Exception as e:
                    print(f"   {op}: 操作失败 - {str(e)}")

        except Exception as e:
            print(f"❌ pgvector操作符测试失败: {str(e)}")

    async def test_corrected_similarity_calculation(self):
        """测试修正的相似度计算"""
        print("\n🎯 测试修正的相似度计算...")

        try:
            # 获取测试数据
            project = await fetch_one(
                "SELECT * FROM projects WHERE tenant_id = $1 AND ai_match_embedding IS NOT NULL LIMIT 1",
                self.tenant_id,
            )

            engineers = await fetch_all(
                "SELECT * FROM engineers WHERE tenant_id = $1 AND ai_match_embedding IS NOT NULL LIMIT 3",
                self.tenant_id,
            )

            if not project or not engineers:
                print("❌ 缺少测试数据")
                return

            print(f"测试项目: {project['title']}")
            print(f"测试简历数: {len(engineers)}")

            # 方法1：使用pgvector余弦距离
            print(f"\n🔬 方法1: pgvector余弦距离")
            try:
                pgvector_results = await fetch_all(
                    """
                    SELECT id, name, ai_match_embedding <=> $1 as cosine_distance
                    FROM engineers 
                    WHERE tenant_id = $2 AND ai_match_embedding IS NOT NULL
                    ORDER BY ai_match_embedding <=> $1 ASC
                    LIMIT 3
                    """,
                    project["ai_match_embedding"],
                    self.tenant_id,
                )

                for result in pgvector_results:
                    distance = result["cosine_distance"]
                    similarity = 1 - distance
                    # 确保在[0,1]范围内
                    similarity = max(0, min(1, similarity))
                    print(
                        f"   {result['name']}: 距离={distance:.6f}, 相似度={similarity:.6f}"
                    )

            except Exception as e:
                print(f"   pgvector方法失败: {str(e)}")

            # 方法2：手动计算
            print(f"\n🔬 方法2: 手动计算")
            project_emb = self._parse_vector_string(project["ai_match_embedding"])

            if project_emb.size > 0:
                for engineer in engineers:
                    engineer_emb = self._parse_vector_string(
                        engineer["ai_match_embedding"]
                    )

                    if engineer_emb.size > 0:
                        # 计算余弦相似度
                        dot_product = np.dot(project_emb, engineer_emb)
                        norm_p = np.linalg.norm(project_emb)
                        norm_e = np.linalg.norm(engineer_emb)

                        if norm_p > 0 and norm_e > 0:
                            cosine_sim = dot_product / (norm_p * norm_e)
                            # 转换到[0,1]范围
                            normalized_sim = (cosine_sim + 1) / 2
                            print(
                                f"   {engineer['name']}: 原始={cosine_sim:.6f}, 标准化={normalized_sim:.6f}"
                            )

            # 方法3：推荐的实现
            print(f"\n🎯 推荐实现:")
            recommended_results = await self._calculate_similarities_recommended(
                project["ai_match_embedding"], engineers
            )

            for engineer, similarity in recommended_results:
                print(f"   {engineer['name']}: 相似度={similarity:.6f}")

        except Exception as e:
            print(f"❌ 相似度计算测试失败: {str(e)}")
            import traceback

            print(f"详细错误:\n{traceback.format_exc()}")

    async def _calculate_similarities_recommended(
        self, target_embedding, candidates
    ) -> List[Tuple[Dict[str, Any], float]]:
        """推荐的相似度计算方法"""
        results = []

        try:
            # 方法1: 尝试pgvector余弦距离
            candidate_ids = [c["id"] for c in candidates]

            pgvector_results = await fetch_all(
                """
                SELECT id, ai_match_embedding <=> $1 as cosine_distance
                FROM engineers 
                WHERE id = ANY($2) AND ai_match_embedding IS NOT NULL
                ORDER BY ai_match_embedding <=> $1 ASC
                """,
                target_embedding,
                candidate_ids,
            )

            # 创建ID到相似度的映射
            similarity_map = {}
            for result in pgvector_results:
                distance = result["cosine_distance"]
                if distance is not None:
                    # 转换为相似度并确保在[0,1]范围内
                    similarity = 1 - distance
                    similarity = max(0, min(1, similarity))
                    similarity_map[result["id"]] = similarity

            # 组合结果
            for candidate in candidates:
                if candidate["id"] in similarity_map:
                    similarity = similarity_map[candidate["id"]]
                    results.append((candidate, similarity))

        except Exception as e:
            print(f"pgvector方法失败，使用手动计算: {str(e)}")

            # 方法2: 手动计算作为备选
            target_emb = self._parse_vector_string(target_embedding)

            if target_emb.size > 0:
                for candidate in candidates:
                    candidate_emb = self._parse_vector_string(
                        candidate["ai_match_embedding"]
                    )

                    if candidate_emb.size > 0:
                        try:
                            # 计算余弦相似度
                            dot_product = np.dot(target_emb, candidate_emb)
                            norm_t = np.linalg.norm(target_emb)
                            norm_c = np.linalg.norm(candidate_emb)

                            if norm_t > 0 and norm_c > 0:
                                cosine_sim = dot_product / (norm_t * norm_c)
                                # 转换到[0,1]范围
                                normalized_sim = (cosine_sim + 1) / 2
                                normalized_sim = max(0, min(1, normalized_sim))
                                results.append((candidate, normalized_sim))

                        except Exception as calc_error:
                            print(
                                f"计算相似度失败: {candidate['id']}, 错误: {str(calc_error)}"
                            )
                            continue

        return results

    async def clean_duplicate_matches(self):
        """清理重复的匹配记录"""
        print("\n🧹 清理重复匹配记录...")

        try:
            # 查询重复记录
            duplicates = await fetch_all(
                """
                SELECT tenant_id, project_id, engineer_id, COUNT(*) as count
                FROM project_engineer_matches 
                WHERE tenant_id = $1
                GROUP BY tenant_id, project_id, engineer_id
                HAVING COUNT(*) > 1
                """,
                self.tenant_id,
            )

            if duplicates:
                print(f"发现 {len(duplicates)} 组重复记录")

                # 删除重复记录（保留最新的）
                from app.database import execute_query

                for dup in duplicates:
                    await execute_query(
                        """
                        DELETE FROM project_engineer_matches 
                        WHERE tenant_id = $1 AND project_id = $2 AND engineer_id = $3
                        AND id NOT IN (
                            SELECT id FROM project_engineer_matches 
                            WHERE tenant_id = $1 AND project_id = $2 AND engineer_id = $3
                            ORDER BY created_at DESC LIMIT 1
                        )
                        """,
                        dup["tenant_id"],
                        dup["project_id"],
                        dup["engineer_id"],
                    )

                print("✅ 重复记录清理完成")
            else:
                print("✅ 没有发现重复记录")

        except Exception as e:
            print(f"❌ 清理重复记录失败: {str(e)}")

    async def generate_code_fixes(self):
        """生成代码修复建议"""
        print("\n💻 生成代码修复建议")
        print("=" * 60)

        print("1. 📝 vector数据解析函数:")
        print(
            """
def _parse_vector_string(self, vector_str) -> np.ndarray:
    '''将PostgreSQL vector字符串转换为numpy数组'''
    try:
        if not vector_str:
            return np.array([])
        
        if isinstance(vector_str, str):
            # 移除外层方括号并分割
            vector_str = vector_str.strip()
            if vector_str.startswith('[') and vector_str.endswith(']'):
                vector_str = vector_str[1:-1]
            
            if vector_str:
                values = [float(x.strip()) for x in vector_str.split(',') if x.strip()]
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
"""
        )

        print("\n2. 🔧 修复版相似度计算:")
        print(
            """
async def _calculate_similarities_batch_fixed(self, target_embedding, candidates, table_type):
    '''修复版批量相似度计算'''
    if not candidates:
        return []

    candidate_ids = [c["id"] for c in candidates]
    table_name = "engineers" if table_type == "engineers" else "projects"

    try:
        # 使用pgvector余弦距离
        query = f'''
        SELECT id, ai_match_embedding <=> $1 as cosine_distance
        FROM {table_name}
        WHERE id = ANY($2) AND ai_match_embedding IS NOT NULL
        ORDER BY ai_match_embedding <=> $1 ASC
        '''
        
        similarities = await fetch_all(query, target_embedding, candidate_ids)
        
        results = []
        for s in similarities:
            distance = s["cosine_distance"]
            if distance is not None:
                # 转换为相似度[0,1]
                similarity = 1 - distance
                similarity = max(0, min(1, similarity))
                
                # 找到对应的候选对象
                candidate = next(c for c in candidates if c["id"] == s["id"])
                results.append((candidate, similarity))
        
        return results
        
    except Exception as e:
        logger.error(f"pgvector查询失败，使用手动计算: {str(e)}")
        return await self._manual_similarity_calculation(target_embedding, candidates)
"""
        )

        print("\n3. 🔧 手动计算备选方案:")
        print(
            """
async def _manual_similarity_calculation(self, target_embedding, candidates):
    '''手动相似度计算备选方案'''
    results = []
    target_emb = self._parse_vector_string(target_embedding)
    
    if target_emb.size == 0:
        return results
    
    for candidate in candidates:
        try:
            candidate_emb = self._parse_vector_string(candidate["ai_match_embedding"])
            
            if candidate_emb.size > 0:
                # 计算余弦相似度
                dot_product = np.dot(target_emb, candidate_emb)
                norm_t = np.linalg.norm(target_emb)
                norm_c = np.linalg.norm(candidate_emb)
                
                if norm_t > 0 and norm_c > 0:
                    cosine_sim = dot_product / (norm_t * norm_c)
                    # 转换到[0,1]范围
                    normalized_sim = (cosine_sim + 1) / 2
                    normalized_sim = max(0, min(1, normalized_sim))
                    results.append((candidate, normalized_sim))
                    
        except Exception as e:
            logger.error(f"计算相似度失败: {candidate['id']}, 错误: {str(e)}")
            continue
    
    # 按相似度排序
    results.sort(key=lambda x: x[1], reverse=True)
    return results
"""
        )

        print("\n4. 🛡️ 分数验证函数:")
        print(
            """
def _validate_similarity_score(self, score: float, context: str = "") -> float:
    '''验证和修正相似度分数'''
    if score is None or not isinstance(score, (int, float)):
        logger.warning(f"无效相似度分数 {context}: {score}")
        return 0.5
        
    if not (0 <= score <= 1):
        logger.warning(f"相似度分数超出范围 {context}: {score}")
        # 修正异常值
        if score > 1:
            score = 1.0
        elif score < 0:
            score = 0.0
            
    return float(score)
"""
        )

    async def run_complete_vector_fix_diagnosis(self):
        """运行完整的vector修复诊断"""
        print("🛠️ Vector数据类型修复诊断")
        print("=" * 80)

        try:
            # 1. 检查vector数据格式
            format_ok = await self.check_vector_data_format()

            if not format_ok:
                print("❌ Vector数据格式有问题，无法继续")
                return

            # 2. 测试pgvector操作符
            await self.test_pgvector_operators_fixed()

            # 3. 测试修正的相似度计算
            await self.test_corrected_similarity_calculation()

            # 4. 清理重复记录
            await self.clean_duplicate_matches()

            # 5. 生成代码修复建议
            await self.generate_code_fixes()

            print("\n" + "=" * 80)
            print("🎉 Vector修复诊断完成！")
            print("💡 关键修复点:")
            print("1. ✅ Vector数据需要从字符串转换为numpy数组")
            print("2. ✅ 使用 <=> 操作符计算余弦距离")
            print("3. ✅ 相似度 = 1 - 余弦距离")
            print("4. ✅ 确保所有分数在[0,1]范围内")
            print("5. ✅ 添加手动计算作为备选方案")
            print("=" * 80)

        except Exception as e:
            print(f"❌ Vector修复诊断失败: {str(e)}")
            import traceback

            print(f"详细错误:\n{traceback.format_exc()}")


async def main():
    """主函数"""
    debugger = VectorFixedEmbeddingDebugger()
    await debugger.run_complete_vector_fix_diagnosis()


if __name__ == "__main__":
    asyncio.run(main())
