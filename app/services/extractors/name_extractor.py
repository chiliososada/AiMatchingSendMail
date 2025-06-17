# -*- coding: utf-8 -*-
"""姓名提取器 - 完整修复版：解决距离权重和搜索范围问题"""

from typing import List, Dict, Any
import pandas as pd
import re

from base.base_extractor import BaseExtractor
from base.constants import KEYWORDS
from utils.validation_utils import is_valid_name


class NameExtractor(BaseExtractor):
    """姓名信息提取器 - 完整修复版"""

    def __init__(self):
        super().__init__()
        # 学历相关关键词，用于避免在学历区域搜索姓名
        self.education_keywords = [
            "学歴",
            "最終学歴",
            "学校",
            "大学",
            "研究科",
            "学院",
            "専門学校",
            "高校",
            "卒業",
            "在学",
            "専攻",
            "学科",
            "学部",
            "研究室",
            "博士",
            "修士",
            "学士",
            "PhD",
            "Master",
            "Bachelor",
        ]

        # 关系和职业词汇
        self.relationship_keywords = [
            "配偶者",
            "配偶",
            "夫",
            "妻",
            "独身",
            "既婚",
            "未婚",
            "家族",
            "技術者",
            "開発者",
            "エンジニア",
            "プログラマー",
            "システムエンジニア",
        ]

    def extract(self, all_data: List[Dict[str, Any]]) -> str:
        """提取姓名

        Args:
            all_data: 包含所有sheet数据的列表

        Returns:
            提取的姓名，如果未找到返回空字符串
        """
        candidates = []

        for data in all_data:
            df = data["df"]
            sheet_name = data.get("sheet_name", "Unknown")

            print(f"\n🔍 开始姓名提取 - Sheet: {sheet_name}")
            print(f"    表格大小: {df.shape[0]}行 x {df.shape[1]}列")

            # 方法1: 精确搜索姓名关键词附近（修复距离权重问题）
            primary_candidates = self._search_name_by_keywords_fixed(df)
            if primary_candidates:
                print(f"    ✅ 通过关键词找到 {len(primary_candidates)} 个候选姓名")
                candidates.extend(primary_candidates)

            # 方法2: 如果主要方法失败，使用备用搜索（限制在前5行）
            if not candidates:
                print("    使用备用方法：前5行搜索")
                backup_candidates = self._search_name_in_top_rows(df)
                candidates.extend(backup_candidates)

        if candidates:
            # 过滤无效候选
            valid_candidates = []
            for name, confidence in candidates:
                if is_valid_name(name) and not self._is_relationship_word(name):
                    valid_candidates.append((name, confidence))
                    print(f"    ✅ 有效候选: '{name}' (置信度: {confidence:.2f})")
                else:
                    print(f"    ❌ 过滤候选: '{name}' (验证失败或关系词汇)")

            if valid_candidates:
                # 按置信度排序，返回最佳候选
                valid_candidates.sort(key=lambda x: x[1], reverse=True)
                best_name = valid_candidates[0][0].strip()
                print(
                    f"\n✅ 最终选择姓名: '{best_name}' (置信度: {valid_candidates[0][1]:.2f})"
                )
                return best_name

        print("\n❌ 未能提取到姓名")
        return ""

    def _search_name_by_keywords_fixed(self, df: pd.DataFrame) -> List[tuple]:
        """通过姓名关键词搜索姓名 - 修复版（解决距离权重问题）"""
        candidates = []

        # 只搜索前10行，避免在学历等区域搜索
        for idx in range(min(10, len(df))):
            for col in range(len(df.columns)):
                cell = df.iloc[idx, col]
                if pd.notna(cell) and any(k in str(cell) for k in KEYWORDS["name"]):
                    print(f"    找到姓名关键词 '{cell}' 在位置 [{idx}, {col}]")

                    # 修复后的邻近搜索：分层搜索，强化距离权重
                    nearby_candidates = self._search_name_nearby_fixed(df, idx, col)
                    candidates.extend(nearby_candidates)

        return candidates

    def _search_name_nearby_fixed(
        self, df: pd.DataFrame, row: int, col: int
    ) -> List[tuple]:
        """修复后的邻近搜索 - 分层搜索，强化距离权重"""
        candidates = []

        print(f"    开始分层搜索姓名关键词[{row},{col}]附近的姓名")

        # 策略1: 优先搜索直接邻近位置（距离1-3）
        priority_candidates = self._search_immediate_vicinity(df, row, col)

        # 策略2: 扩大搜索但强化距离权重（距离4-8）
        extended_candidates = self._search_extended_area(df, row, col)

        # 合并候选，优先级候选获得额外权重
        for name, conf in priority_candidates:
            enhanced_conf = conf * 2.0  # 邻近候选获得双倍权重
            candidates.append((name, enhanced_conf))
            print(
                f"      🎯 优先候选: '{name}' 置信度{enhanced_conf:.2f} (原{conf:.2f})"
            )

        for name, conf in extended_candidates:
            candidates.append((name, conf))
            print(f"      📍 扩展候选: '{name}' 置信度{conf:.2f}")

        return candidates

    def _search_immediate_vicinity(
        self, df: pd.DataFrame, row: int, col: int
    ) -> List[tuple]:
        """搜索直接邻近位置（距离1-3）"""
        candidates = []

        # 只搜索非常近的位置
        for r_offset in range(-1, 3):  # 4行范围：上1行到下2行
            for c_offset in range(-1, 8):  # 9列范围：左1列到右7列
                r = row + r_offset
                c = col + c_offset

                if 0 <= r < len(df) and 0 <= c < len(df.columns):
                    distance = abs(r_offset) + abs(c_offset)
                    if distance <= 3:  # 只考虑距离3以内
                        value = df.iloc[r, c]
                        if pd.notna(value):
                            value_str = str(value).strip()

                            if self._could_be_name(value_str):
                                confidence = self._calculate_proximity_confidence(
                                    r_offset, c_offset, value_str
                                )
                                candidates.append((value_str, confidence))
                                print(
                                    f"        📍 近距离候选[{r},{c}]: '{value_str}' 距离{distance} 置信度{confidence:.2f}"
                                )

        return candidates

    def _search_extended_area(
        self, df: pd.DataFrame, row: int, col: int
    ) -> List[tuple]:
        """搜索扩展区域（距离4-8）"""
        candidates = []

        # 扩大搜索但限制范围（比原来小很多）
        for r_offset in range(-2, 4):  # 6行范围
            for c_offset in range(-2, 12):  # 14列范围（原来是22列）
                r = row + r_offset
                c = col + c_offset

                if 0 <= r < len(df) and 0 <= c < len(df.columns):
                    distance = abs(r_offset) + abs(c_offset)
                    if 4 <= distance <= 8:  # 只考虑中等距离
                        value = df.iloc[r, c]
                        if pd.notna(value):
                            value_str = str(value).strip()

                            if self._could_be_name(value_str):
                                confidence = self._calculate_distance_confidence(
                                    r_offset, c_offset, value_str
                                )
                                candidates.append((value_str, confidence))
                                print(
                                    f"        📍 扩展候选[{r},{c}]: '{value_str}' 距离{distance} 置信度{confidence:.2f}"
                                )

        return candidates

    def _calculate_proximity_confidence(
        self, r_offset: int, c_offset: int, value: str
    ) -> float:
        """计算邻近候选的置信度"""
        confidence = 3.0  # 基础高置信度

        # 强化距离权重（邻近区域，距离权重很重要）
        distance = abs(r_offset) + abs(c_offset)
        distance_weight = 1.0 / (1 + distance * 0.5)  # 强化距离权重
        confidence *= distance_weight

        # 位置偏好：右侧和下方优先（符合日本简历布局）
        if c_offset > 0:  # 右侧
            confidence *= 1.4
        if r_offset >= 0:  # 同行或下方
            confidence *= 1.3
        if r_offset > 0 and c_offset > 0:  # 右下方
            confidence *= 1.2

        # 长度权重（但不要过度偏向长文本）
        if len(value) >= 2:
            confidence *= 1.2  # 降低长度权重影响
        elif len(value) == 1:
            # 单字符中文姓名仍然有效（如"付"）
            if re.search(r"[一-龥]", value):
                confidence *= 1.1  # 略微提升中文单字符
                print(f"          🈯 单字符中文姓名: '{value}'")

        return confidence

    def _calculate_distance_confidence(
        self, r_offset: int, c_offset: int, value: str
    ) -> float:
        """计算远距离候选的置信度"""
        confidence = 1.0  # 较低基础置信度

        # 强化距离惩罚（比原来强3倍）
        distance = abs(r_offset) + abs(c_offset)
        distance_weight = 1.0 / (1 + distance * 0.3)  # 更强的距离惩罚（原来是0.1）
        confidence *= distance_weight

        # 位置偏好
        if c_offset > 0:  # 右侧
            confidence *= 1.2
        if r_offset >= 0:  # 同行或下方
            confidence *= 1.1

        # 远距离时更依赖长度判断
        if len(value) >= 3:
            confidence *= 1.3
        elif len(value) == 2:
            confidence *= 1.1
        else:
            confidence *= 0.7  # 单字符在远距离置信度降低

        return confidence

    def _could_be_name(self, text: str) -> bool:
        """快速判断是否可能是姓名"""
        text = text.strip()

        if not text or len(text) > 10:
            return False

        # 必须包含文字字符
        if not re.search(r"[一-龥ぁ-んァ-ンa-zA-Z]", text):
            return False

        # 快速排除明显不是姓名的
        obvious_non_names = [
            "名前",
            "氏名",
            "フリガナ",
            "性別",
            "年齢",
            "国籍",
            "男",
            "女",
            "歳",
            "才",
            "年",
            "月",
            "日",
            "経験",
            "スキル",
            "技術",
            "開発",
            "学歴",
            "住所",
            "電話",
            "メール",
            "プロジェクト",
            "システム",
            "業務",
            "担当",
            "チーム",
            "部署",
        ]

        if any(word in text for word in obvious_non_names):
            return False

        # 排除关系词汇
        if any(word in text for word in self.relationship_keywords):
            return False

        # 排除学历相关
        if any(word in text for word in self.education_keywords):
            return False

        return True

    def _is_relationship_word(self, text: str) -> bool:
        """检查是否是关系词汇"""
        return any(word in text for word in self.relationship_keywords)

    def _search_name_in_top_rows(self, df: pd.DataFrame) -> List[tuple]:
        """在前几行搜索可能的姓名（备用方法）"""
        candidates = []

        print("    🔄 执行备用搜索：前5行×前8列")

        # 只搜索前5行，每行的前8列
        for row in range(min(5, len(df))):
            for col in range(min(8, len(df.columns))):
                cell = df.iloc[row, col]
                if pd.notna(cell):
                    cell_str = str(cell).strip()

                    # 跳过明显不是姓名的内容
                    if not self._could_be_name(cell_str):
                        continue

                    # 跳过学历区域
                    if self._is_in_education_area(df, row, col):
                        continue

                    if is_valid_name(cell_str) and not self._is_relationship_word(
                        cell_str
                    ):
                        # 给予较低的置信度
                        confidence = 0.5

                        # 位置权重：右上角个人信息区域
                        if row <= 3 and col >= 3:
                            confidence += 0.4

                        # 长度权重（平衡处理）
                        if len(cell_str.strip()) >= 2:
                            confidence += 0.3
                        elif len(cell_str.strip()) == 1 and re.search(
                            r"[一-龥]", cell_str
                        ):
                            # 单字符中文姓名也给予合理置信度
                            confidence += 0.2

                        candidates.append((cell_str, confidence))
                        print(
                            f"    📍 备用候选: '{cell_str}' 行{row}列{col} 置信度{confidence:.2f}"
                        )

        return candidates

    def _is_in_education_area(self, df: pd.DataFrame, row: int, col: int) -> bool:
        """检查是否在学历区域"""
        if 0 <= row < len(df):
            row_data = df.iloc[row]
            row_text = " ".join([str(cell) for cell in row_data if pd.notna(cell)])

            if any(keyword in row_text for keyword in self.education_keywords):
                return True

        return False
