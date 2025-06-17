# -*- coding: utf-8 -*-
"""日期处理工具"""

from datetime import datetime, timedelta
from typing import Optional, Union


def convert_excel_serial_to_date(
    serial_number: Union[int, float],
) -> Optional[datetime]:
    """将Excel序列数字转换为日期

    Args:
        serial_number: Excel序列日期数字

    Returns:
        转换后的datetime对象，如果无法转换返回None
    """
    try:
        # Excel的序列日期：从1900年1月1日开始的天数
        # 注意：Excel错误地认为1900年是闰年，所以需要调整
        if serial_number < 1:
            return None

        # Excel的bug：1900年被错误地认为是闰年，所以1900年3月1日之后需要减去1天
        if serial_number >= 61:  # 1900年3月1日对应61
            serial_number -= 1

        base_date = datetime(1900, 1, 1)
        result_date = base_date + timedelta(days=serial_number - 1)

        # 验证日期是否合理
        if 1950 <= result_date.year <= 2030:
            return result_date

    except Exception as e:
        pass

    return None


def calculate_age_from_birthdate(birthdate: datetime) -> Optional[int]:
    """从生年月日计算年龄

    Args:
        birthdate: 出生日期

    Returns:
        年龄，如果不合理返回None
    """
    try:
        current_date = datetime(2024, 11, 1)
        age = current_date.year - birthdate.year

        # 如果还没过生日，年龄减1
        if (current_date.month, current_date.day) < (birthdate.month, birthdate.day):
            age -= 1

        # 验证年龄是否合理
        if 15 <= age <= 75:
            return age

    except:
        pass

    return None
