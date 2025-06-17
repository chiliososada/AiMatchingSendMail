# -*- coding: utf-8 -*-
"""日语水平提取器 - 优先级优化版：N1/N2等级优先，其次描述性等级"""

from typing import List, Dict, Any, Tuple
import pandas as pd
import re

try:
    from app.base.constants import KEYWORDS
    from app.base.base_extractor import BaseExtractor
except ImportError:
    # 备用定义
    KEYWORDS = {"japanese": ["日本語", "JLPT", "日語", "語学力"]}

    class BaseExtractor:
        def __init__(self):
            self.trans_table = str.maketrans("０１２３４５６７８９", "0123456789")


class JapaneseLevelExtractor(BaseExtractor):
    """日语水平信息提取器 - 优先级优化版"""

    def extract(self, all_data: List[Dict[str, Any]]) -> str:
        """提取日语水平，按优先级排序

        优先级顺序：
        1. 精确等级 (N1, N2, N3, N4, N5) - 最高优先级
        2. 描述性等级 (ネイティブレベル, ビジネスレベル等) - 次优先级

        Args:
            all_data: 包含所有sheet数据的列表

        Returns:
            日语水平字符串，如果未找到返回空字符串
        """
        print("\n" + "=" * 60)
        print("🔍 开始日语水平提取器执行流程 (优先级优化版)")
        print("=" * 60)

        all_candidates = []

        for sheet_idx, data in enumerate(all_data):
            text = data["text"]
            df = data["df"]
            sheet_name = data.get("sheet_name", f"Sheet_{sheet_idx}")

            print(f"\n📊 处理数据表 {sheet_idx+1}/{len(all_data)}: '{sheet_name}'")

            # 🔥 步骤1: 优先提取精确等级 (N1-N5)
            print(f"\n   🎯 步骤1: 搜索精确等级 (N1-N5)")
            precise_levels = self._extract_precise_levels(text)
            if precise_levels:
                print(f"   ✅ 找到 {len(precise_levels)} 个精确等级")
                all_candidates.extend(precise_levels)
            else:
                print(f"   ❌ 未找到精确等级")

            # 🔥 步骤2: 提取描述性等级 (仅在没有精确等级时作为备选)
            print(f"\n   🎯 步骤2: 搜索描述性等级")
            descriptive_levels = self._extract_descriptive_levels(text)
            if descriptive_levels:
                print(f"   ✅ 找到 {len(descriptive_levels)} 个描述性等级")
                all_candidates.extend(descriptive_levels)
            else:
                print(f"   ❌ 未找到描述性等级")

        if not all_candidates:
            print(f"\n❌ 未能提取到任何日语水平")
            return ""

        # 🔥 步骤3: 按优先级选择最佳结果
        final_result = self._select_best_by_priority(all_candidates)

        print(f"\n🎯 最终结果: {final_result}")
        return final_result

    def _extract_precise_levels(self, text: str) -> List[Tuple[str, float, str]]:
        """提取精确的JLPT等级 (N1-N5)

        Returns:
            List of (level, confidence, category) tuples
        """
        candidates = []

        # 🔥 精确等级模式 - 高优先级
        precise_patterns = [
            # 最高置信度：明确的JLPT N级表述
            (r"JLPT\s*[NnＮ]([1-5１-５])", 5.0),
            (r"日本語能力試験\s*[NnＮ]([1-5１-５])", 5.0),
            # 🆕 旧格式JLPT支持：日本語能力試験1級 = N1
            (r"日本語能力試験\s*([1-4１-４])\s*級", 5.0),
            (r"JLPT\s*([1-4１-４])\s*級", 5.0),
            (r"日語能力試験\s*([1-4１-４])\s*級", 5.0),
            # 高置信度：N级 + 修饰词
            (r"[NnＮ]([1-5１-５])\s*(?:合格|取得|レベル|級)", 4.5),
            (r"[NnＮ]([1-5１-５])\s*(?:かなり|とても|非常に)?\s*(?:流暢|流暢)", 4.5),
            # 中等置信度：标准N级格式
            (r"(?:^|\s)[NnＮ]([1-5１-５])(?:\s|$|[、。,.\)])", 4.0),
            # 较低置信度：汉字数字级别
            (r"日本語.*?([一二三四五])級", 3.5),
            (r"([一二三四五])級.*?日本語", 3.5),
        ]

        for pattern, confidence in precise_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                level_str = match.group(1)
                full_match = match.group(0)

                # 🆕 处理旧格式JLPT (1級=N1, 2級=N2, 3級=N3, 4級=N4)
                if "級" in full_match and not "N" in full_match.upper():
                    # 旧格式：1級 -> N1, 2級 -> N2, etc.
                    old_level_map = {
                        "1": "1",
                        "2": "2",
                        "3": "3",
                        "4": "4",
                        "１": "1",
                        "２": "2",
                        "３": "3",
                        "４": "4",
                    }
                    if level_str in old_level_map:
                        level_num = old_level_map[level_str]
                        level = f"N{level_num}"
                        candidates.append((level, confidence, "precise"))
                        print(
                            f"      ✅ 旧格式JLPT: {level} (原文: '{full_match.strip()}' -> 转换为N{level_num})"
                        )
                        continue

                # 转换汉字数字
                kanji_to_num = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5"}
                if level_str in kanji_to_num:
                    level_num = kanji_to_num[level_str]
                else:
                    level_num = level_str.translate(self.trans_table)

                # 验证等级有效性
                if level_num in ["1", "2", "3", "4", "5"]:
                    level = f"N{level_num}"
                    candidates.append((level, confidence, "precise"))
                    print(f"      ✅ 精确等级: {level} (原文: '{full_match.strip()}')")

        return candidates

    def _extract_descriptive_levels(self, text: str) -> List[Tuple[str, float, str]]:
        """提取描述性日语等级

        Returns:
            List of (level, confidence, category) tuples
        """
        candidates = []

        # 🔥 描述性等级模式 - 中优先级
        descriptive_patterns = [
            # 高描述性置信度
            (r"(ネイティブ|母語|母国語)\s*(?:レベル|级)?", "ネイティブレベル", 3.0),
            (r"(ビジネス|商务)\s*(?:レベル|级)?", "ビジネスレベル", 2.8),
            # 中等描述性置信度
            (r"(?:かなり|とても|非常に)\s*(?:流暢|流暢)", "流暢", 2.5),
            (r"(?:流暢|流暢)", "流暢", 2.0),
            # 较低描述性置信度
            (r"(上級)\s*(?:レベル|级)?", "上級", 1.8),
            (r"(中級)\s*(?:レベル|级)?", "中級", 1.5),
            (r"(初級)\s*(?:レベル|级)?", "初級", 1.2),
            # 最低描述性置信度
            (r"日本語.*?(上級)", "上級", 1.0),
            (r"日本語.*?(中級)", "中級", 0.8),
            (r"日本語.*?(初級)", "初級", 0.6),
        ]

        for pattern, level_name, confidence in descriptive_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                full_match = match.group(0)
                candidates.append((level_name, confidence, "descriptive"))
                print(
                    f"      ✅ 描述性等级: {level_name} (原文: '{full_match.strip()}')"
                )

        return candidates

    def _select_best_by_priority(self, candidates: List[Tuple[str, float, str]]) -> str:
        """按优先级选择最佳日语水平

        优先级规则：
        1. 精确等级(precise) 永远优先于 描述性等级(descriptive)
        2. 同类型内按置信度排序
        3. 精确等级中，数字越小等级越高 (N1 > N2 > N3 > N4 > N5)
        """
        if not candidates:
            return ""

        print(f"\n📊 候选分析 (共 {len(candidates)} 个):")

        # 分类候选
        precise_candidates = [c for c in candidates if c[2] == "precise"]
        descriptive_candidates = [c for c in candidates if c[2] == "descriptive"]

        print(f"   精确等级候选: {len(precise_candidates)} 个")
        for level, conf, _ in precise_candidates:
            print(f"      - {level} (置信度: {conf:.1f})")

        print(f"   描述性等级候选: {len(descriptive_candidates)} 个")
        for level, conf, _ in descriptive_candidates:
            print(f"      - {level} (置信度: {conf:.1f})")

        # 🔥 核心逻辑：精确等级绝对优先
        if precise_candidates:
            print(f"\n🎯 发现精确等级，优先选择精确等级")

            # 在精确等级中选择最佳
            # 先按置信度排序，再按N级数字排序 (N1最优)
            def precise_sort_key(candidate):
                level, confidence, _ = candidate
                # 提取数字 (N1 -> 1)
                level_num = int(level[1]) if len(level) > 1 else 9
                # 置信度高且数字小的排在前面
                return (-confidence, level_num)

            best_precise = sorted(precise_candidates, key=precise_sort_key)[0]
            result = best_precise[0]
            print(f"   选择精确等级: {result}")
            return result

        elif descriptive_candidates:
            print(f"\n🎯 未发现精确等级，选择描述性等级")

            # 在描述性等级中选择置信度最高的
            best_descriptive = max(descriptive_candidates, key=lambda x: x[1])
            result = best_descriptive[0]
            print(f"   选择描述性等级: {result}")
            return result

        else:
            print(f"\n❌ 没有有效候选")
            return ""
