# 日期工具

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd


def parse_date(value) -> Optional[str]:
    """
    解析日期（支持多种格式）

    返回格式: YYYY-MM-DD
    """
    if pd.isna(value):
        return None

    # 如果已经是日期类型
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")

    # 如果是 Excel 序列号（数字）
    if isinstance(value, (int, float)):
        try:
            date_obj = datetime(1899, 12, 30) + timedelta(days=value)
            return date_obj.strftime("%Y-%m-%d")
        except:
            return None

    # 尝试 pandas 自动解析
    try:
        date_obj = pd.to_datetime(value)
        return date_obj.strftime("%Y-%m-%d")
    except:
        return None


def calculate_months_between(start_date: str, end_date: Optional[str] = None) -> int:
    """
    计算两个日期之间的月数差

    如果 end_date 为 None，则使用当前日期
    """
    if not start_date:
        return 0

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")

        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        else:
            end_dt = datetime.now()

        months = (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month)
        return max(0, months)
    except:
        return 0


def get_current_period() -> str:
    """
    获取当前对账期间（YYYYMM）
    """
    now = datetime.now()
    return now.strftime("%Y%m")


def get_previous_period(period: str) -> str:
    """
    获取上一个对账期间

    例如: 202608 -> 202607
    """
    year = int(period[:4])
    month = int(period[4:6])

    if month == 1:
        year -= 1
        month = 12
    else:
        month -= 1

    return f"{year}{month:02d}"


def get_next_period(period: str) -> str:
    """
    获取下一个对账期间

    例如: 202608 -> 202609
    """
    year = int(period[:4])
    month = int(period[4:6])

    if month == 12:
        year += 1
        month = 1
    else:
        month += 1

    return f"{year}{month:02d}"
