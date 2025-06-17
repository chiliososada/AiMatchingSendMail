# -*- coding: utf-8 -*-
"""验证工具 - 修复版：解决"氏 名"标签验证问题"""

import re
from typing import List


def is_valid_name(name: str) -> bool:
    """验证是否为有效的姓名 - 修复版

    Args:
        name: 待验证的姓名

    Returns:
        是否为有效姓名
    """
    name = str(name).strip()

    # 标准化：移除所有空格进行检查
    name_no_space = re.sub(r"\s+", "", name)

    # 需要排除的词 - 完整版，包含各种空格组合
    exclude_words = [
        # 基本标签词
        "氏名",
        "氏 名",
        "氏　名",
        "名前",
        "名 前",
        "名　前",
        "フリガナ",
        "ふりがな",
        "性別",
        "性 別",
        "性　別",
        "年齢",
        "年 齢",
        "年　齢",
        "国籍",
        "国 籍",
        "国　籍",
        "男",
        "女",
        "歳",
        "才",
        "経験",
        "資格",
        "学歴",
        "住所",
        "電話",
        "メール",
        "現在",
        "スキルシート",
        "履歴書",
        "職務経歴書",
        "技術",
        "年月",
        "生年月",
        # 简历专业术语标签
        "得意分野",
        "得意 分野",
        "得意　分野",  # 擅长领域
        "専門分野",
        "専門 分野",
        "専門　分野",  # 专业领域
        "技術分野",
        "技術 分野",
        "技術　分野",  # 技术领域
        "開発経験",
        "開発 経験",
        "開発　経験",  # 开发经验
        "プロジェクト経験",
        "プロジェクト 経験",  # 项目经验
        "業務経験",
        "業務 経験",
        "業務　経験",  # 业务经验
        "実務経験",
        "実務 経験",
        "実務　経験",  # 实务经验
        "担当業務",
        "担当 業務",
        "担当　業務",  # 负责业务
        "参画プロジェクト",
        "参画 プロジェクト",  # 参与项目
        "開発言語",
        "開発 言語",
        "開発　言語",  # 开发语言
        "使用技術",
        "使用 技術",
        "使用　技術",  # 使用技术
        "開発環境",
        "開発 環境",
        "開発　環境",  # 开发环境
        "作業内容",
        "作業 内容",
        "作業　内容",  # 作业内容
        "業務内容",
        "業務 内容",
        "業務　内容",  # 业务内容
        "担当工程",
        "担当 工程",
        "担当　工程",  # 负责工程
        "役割",
        "役 割",
        "役　割",  # 角色
        "職種",
        "職 種",
        "職　種",  # 职种
        "ポジション",  # 职位
        "自己PR",
        "自己 PR",
        "自己　PR",  # 自我介绍
        "アピールポイント",  # 亮点
        "強み",
        "つよみ",  # 优势
        "弱み",
        "よわみ",  # 弱势
        "志望動機",
        "志望 動機",
        "志望　動機",  # 志愿动机
        "転職理由",
        "転職 理由",
        "転職　理由",  # 转职理由
        "希望条件",
        "希望 条件",
        "希望　条件",  # 希望条件
        "資格・免許",
        "資格 免許",
        "資格　免許",  # 资格执照
        "語学力",
        "語学 力",
        "語学　力",  # 语言能力
        "日本語レベル",
        "日本語 レベル",  # 日语水平
        "JLPT",
        "日本語能力試験",  # 日语能力考试
        "趣味",
        "特技",
        "hobby",  # 兴趣特长
        "その他",
        "その 他",
        "その　他",  # 其他
        "備考",
        "備 考",
        "備　考",  # 备注
        "特記事項",
        "特記 事項",
        "特記　事項",  # 特记事项
        "コメント",  # 评论
        "概要",
        "詳細",
        "説明",  # 概要详细说明
        "期間",
        "時期",
        "年月日",  # 期间时期
        "プロジェクト名",
        "案件名",  # 项目名案件名
        "システム名",
        "サービス名",  # 系统名服务名
        "チーム構成",
        "人数規模",  # 团队构成人数规模
        "開発手法",
        "開発プロセス",  # 开发方法流程
        "OS",
        "DB",
        "言語",
        "FW",  # 技术缩写
        "ツール",
        "ミドルウェア",  # 工具中间件
        # 学校相关词汇
        "大学",
        "学校",
        "研究科",
        "学院",
        "専門学校",
        "高校",
        "中学校",
        "小学校",
        "大学院",
        "学部",
        "研究室",
        "工学部",
        "理学部",
        "文学部",
        "法学部",
        "経済学部",
        "医学部",
        "薬学部",
        "農学部",
        "教育学部",
        "商学部",
        "博士",
        "修士",
        "学士",
        "卒業",
        "在学",
        "専攻",
        "学科",
        "PhD",
        "Master",
        "Bachelor",
        "MBA",
        "修了",
        "取得",
        # 公司组织相关
        "会社名",
        "企業名",
        "所属",
        "部署",
        "部門",
        "株式会社",
        "有限会社",
        "合同会社",
        "LLC",
        "Inc",
        "Corp",
        "Ltd",
        # 联系方式相关
        "TEL",
        "電話番号",
        "FAX",
        "Email",
        "メールアドレス",
        "住所",
        "〒",
        "郵便番号",
        "最寄駅",
        "最寄り駅",
        # 其他常见标签
        "写真",
        "顔写真",
        "Photo",
        "Image",
        "印鑑",
        "印章",
        "署名",
        "サイン",
        "日付",
        "作成日",
        "更新日",
    ]

    # 检查是否包含排除词（移除空格后比较）
    for word in exclude_words:
        word_no_space = re.sub(r"\s+", "", word)
        if word_no_space == name_no_space:
            return False
        # 还要检查原始包含关系
        if word in name:
            return False

    # 检查是否是学校名称的模式
    school_patterns = [
        r".*大学.*",  # 包含"大学"
        r".*学院.*",  # 包含"学院"
        r".*研究科.*",  # 包含"研究科"
        r".*学校.*",  # 包含"学校"
        r".*専門.*",  # 包含"専門"
        r".*高等.*",  # 包含"高等"
        r".*University.*",  # 英文大学
        r".*College.*",  # 英文学院
        r".*Institute.*",  # 英文研究所
        r".*School.*",  # 英文学校
    ]

    for pattern in school_patterns:
        if re.match(pattern, name, re.IGNORECASE):
            return False

    # 排除单个假名标记
    single_kana_markers = [
        # "ア",
        # "イ",
        # "ウ",
        # "エ",
        # "オ",
        # "カ",
        # "キ",
        # "ク",
        # "ケ",
        # "コ",
        # "サ",
        # "シ",
        # "ス",
        # "セ",
        # "ソ",
        # "タ",
        # "チ",
        # "ツ",
        # "テ",
        # "ト",
        # "ナ",
        # "ニ",
        # "ヌ",
        # "ネ",
        # "ノ",
        # "ハ",
        # "ヒ",
        # "フ",
        # "ヘ",
        # "ホ",
        # "マ",
        # "ミ",
        # "ム",
        # "メ",
        # "モ",
        # "ヤ",
        # "ユ",
        # "ヨ",
        # "ラ",
        # "リ",
        # "ル",
        # "レ",
        # "ロ",
        # "ワ",
        # "ヲ",
        # "ン",
    ]

    if name in single_kana_markers:
        return False

    # 长度检查
    if len(name) < 1 or len(name) > 15:
        return False

    # 不能全是数字
    if name.replace(" ", "").replace("　", "").isdigit():
        return False

    # 必须包含文字字符
    if not re.search(r"[一-龥ぁ-んァ-ンa-zA-Z]", name):
        return False

    # 特殊情况：英文缩写名
    if re.match(r"^[A-Z]{2,4}$", name):
        return True

    # 空格分隔的姓名
    if " " in name or "　" in name:
        parts = re.split(r"[\s　]+", name)
        if len(parts) == 2 and all(len(p) >= 1 for p in parts):
            # 检查每部分都不是标签词
            for part in parts:
                part_no_space = re.sub(r"\s+", "", part)
                for word in exclude_words:
                    word_no_space = re.sub(r"\s+", "", word)
                    if part_no_space == word_no_space:
                        return False
            return True

    # 排除过长的组织名称（包含特殊符号）
    if len(name) > 10 and any(char in name for char in ["・", "・", "-", "ー"]):
        return False

    # 排除包含标签指示符的文本
    label_indicators = ["：", ":", "（", "）", "(", ")", "【", "】"]
    if any(indicator in name for indicator in label_indicators):
        return False

    return True


def is_valid_skill(skill: str, valid_skills: set, exclude_patterns: List[str]) -> bool:
    """验证是否为有效的技能

    Args:
        skill: 待验证的技能
        valid_skills: 有效技能集合
        exclude_patterns: 排除模式列表

    Returns:
        是否为有效技能
    """
    if not skill or not isinstance(skill, str):
        return False

    skill = skill.strip()

    # 长度检查
    if len(skill) < 1 or len(skill) > 50:
        return False

    # 检查排除模式
    for pattern in exclude_patterns:
        if re.match(pattern, skill, re.IGNORECASE):
            return False

    # 特殊情况
    if skill == "C":
        return True

    # 单字符且不是技能标记
    if len(skill) == 1:
        return False

    # 检查是否在有效技能列表中
    if skill in valid_skills or skill.lower() in {s.lower() for s in valid_skills}:
        return True

    # 包含英文字符的可能是技能
    if re.search(r"[a-zA-Z]", skill) and len(skill) <= 30:
        exclude_words = [
            "設計",
            "製造",
            "試験",
            "テスト",
            "管理",
            "経験",
            "担当",
            "年",
            "月",
        ]
        if not any(word in skill for word in exclude_words):
            return True

    return False
