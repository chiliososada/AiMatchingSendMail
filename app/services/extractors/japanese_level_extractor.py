# -*- coding: utf-8 -*-
"""日语水平提取器 - 修复版：支持更多格式包括'N1かなり流暢'"""

from typing import List, Dict, Any
import pandas as pd
import re

from base.base_extractor import BaseExtractor
from base.constants import KEYWORDS


class JapaneseLevelExtractor(BaseExtractor):
    """日语水平信息提取器 - 修复版"""

    def extract(self, all_data: List[Dict[str, Any]]) -> str:
        """提取日语水平

        Args:
            all_data: 包含所有sheet数据的列表

        Returns:
            日语水平字符串，如果未找到返回空字符串
        """
        candidates = []

        for data in all_data:
            text = data["text"]
            df = data["df"]
            sheet_name = data.get("sheet_name", "Unknown")

            print(f"\n🔍 开始日语水平提取 - Sheet: {sheet_name}")

            # 搜索JLPT等级
            jlpt_candidates = self._extract_jlpt_levels(text)
            if jlpt_candidates:
                print(f"    从JLPT模式提取到 {len(jlpt_candidates)} 个候选")
            candidates.extend(jlpt_candidates)

            # 搜索包含流暢等描述的日语水平
            fluency_candidates = self._extract_fluency_levels(text)
            if fluency_candidates:
                print(f"    从流暢模式提取到 {len(fluency_candidates)} 个候选")
            candidates.extend(fluency_candidates)

            # 搜索其他日语水平描述
            other_candidates = self._extract_other_levels(text)
            if other_candidates:
                print(f"    从其他模式提取到 {len(other_candidates)} 个候选")
            candidates.extend(other_candidates)

        if candidates:
            # 按置信度排序，返回最高的
            candidates.sort(key=lambda x: x[1], reverse=True)
            result = candidates[0][0]
            print(f"\n✅ 最终日语水平: {result} (置信度: {candidates[0][1]:.2f})")
            return result

        print("\n❌ 未能提取到日语水平")
        return ""

    def _extract_jlpt_levels(self, text: str) -> List[tuple]:
        """提取JLPT等级"""
        candidates = []

        # 扩展的JLPT模式列表
        jlpt_patterns = [
            # 高置信度模式 - 包含流暢等描述
            (r"[NnＮ]([1-5１-５])\s*(?:かなり|とても|非常に)?\s*(?:流暢|流暢)", 4.0),
            (
                r"JLPT\s*[NnＮ]([1-5１-５])\s*(?:かなり|とても|非常に)?\s*(?:流暢|流暢)",
                4.5,
            ),
            # 标准JLPT模式
            (r"JLPT\s*[NnＮ]([1-5１-５])", 2.0),
            (r"[NnＮ]([1-5１-５])\s*(?:合格|取得|レベル|級)", 1.8),
            (r"日本語能力試験\s*[NnＮ]?([1-5１-５])\s*級?", 1.5),
            (r"(?:^|\s)[NnＮ]([1-5１-５])(?:\s|$|[\(（])", 1.0),
            (r"日本語.*?([一二三四五])級", 1.3),
            (r"([一二三四五])級.*?日本語", 1.3),
        ]

        for pattern, confidence in jlpt_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                level_str = match.group(1)

                # 汉字数字转换
                kanji_to_num = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5"}

                if level_str in kanji_to_num:
                    level_num = kanji_to_num[level_str]
                else:
                    level_num = level_str.translate(self.trans_table)

                level = f"N{level_num}"

                # 检查是否包含流暢等描述
                full_match = match.group(0)
                if any(
                    word in full_match
                    for word in ["かなり", "とても", "非常に", "流暢", "流暢"]
                ):
                    level += "かなり流暢"
                    confidence += 1.0
                    print(f"    发现JLPT+流暢: {level} (原文: {full_match})")
                else:
                    print(f"    发现JLPT: {level} (原文: {full_match})")

                candidates.append((level, confidence))

        return candidates

    def _extract_fluency_levels(self, text: str) -> List[tuple]:
        """提取包含流暢描述的日语水平"""
        candidates = []

        # 查找包含流暢等描述的模式
        fluency_patterns = [
            # N级别+流暢组合
            (r"[NnＮ]([1-5１-５])\s*(かなり|とても|非常に)?\s*(流暢|流暢)", 3.5),
            # 日本語+流暢
            (r"日本語\s*(かなり|とても|非常に)\s*(流暢|流暢)", 2.5),
            (r"日本語.*?(かなり|とても|非常に).*?(流暢|流暢)", 2.0),
            # 其他级别描述
            (r"(ビジネス|商务)\s*レベル", 2.0),
            (r"(母語|母国語|ネイティブ)\s*レベル", 3.0),
            (r"(上級|中級|初級)\s*(レベル)?", 1.5),
        ]

        for pattern, confidence in fluency_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                full_match = match.group(0)

                # 如果匹配到N级别+流暢
                if re.search(r"[NnＮ]([1-5１-５])", full_match):
                    level_match = re.search(r"[NnＮ]([1-5１-５])", full_match)
                    if level_match:
                        level_num = level_match.group(1).translate(self.trans_table)
                        level = f"N{level_num}かなり流暢"
                        candidates.append((level, confidence))
                        print(f"    发现N级别+流暢: {level} (原文: {full_match})")
                else:
                    # 其他流暢描述
                    if "ビジネス" in full_match or "商务" in full_match:
                        level = "ビジネスレベル"
                        candidates.append((level, confidence))
                        print(f"    发现商务级别: {level} (原文: {full_match})")
                    elif any(
                        word in full_match for word in ["母語", "母国語", "ネイティブ"]
                    ):
                        level = "ネイティブレベル"
                        candidates.append((level, confidence))
                        print(f"    发现母语级别: {level} (原文: {full_match})")
                    elif "上級" in full_match:
                        level = "上級"
                        candidates.append((level, confidence))
                        print(f"    发现上级: {level} (原文: {full_match})")
                    elif "中級" in full_match:
                        level = "中級"
                        candidates.append((level, confidence))
                        print(f"    发现中级: {level} (原文: {full_match})")
                    elif "流暢" in full_match or "流暢" in full_match:
                        level = "流暢"
                        candidates.append((level, confidence))
                        print(f"    发现流暢: {level} (原文: {full_match})")

        return candidates

    def _extract_other_levels(self, text: str) -> List[tuple]:
        """提取其他日语水平描述"""
        candidates = []

        # 检查其他级别描述
        other_patterns = [
            (r"日本語.*?(ビジネス)", 1.0),
            (r"日本語.*?(上級)", 0.8),
            (r"日本語.*?(中級)", 0.7),
            (r"日本語.*?(初級)", 0.5),
            (r"(JLPT|日本語能力)", 0.5),  # 如果只提到但没有具体级别
        ]

        for pattern, confidence in other_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                full_match = match.group(0)
                matched_level = match.group(1)

                if "ビジネス" in matched_level:
                    candidates.append(("ビジネスレベル", confidence))
                    print(f"    发现其他商务: ビジネスレベル (原文: {full_match})")
                elif "上級" in matched_level:
                    candidates.append(("上級", confidence))
                    print(f"    发现其他上级: 上級 (原文: {full_match})")
                elif "中級" in matched_level:
                    candidates.append(("中級", confidence))
                    print(f"    发现其他中级: 中級 (原文: {full_match})")
                elif "初級" in matched_level:
                    candidates.append(("初級", confidence))
                    print(f"    发现其他初级: 初級 (原文: {full_match})")

        return candidates
