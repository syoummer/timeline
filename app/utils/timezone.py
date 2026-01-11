"""时区处理工具"""
from datetime import datetime
from typing import Optional
import pytz
from dateutil import parser


def parse_timezone(timezone_str: str) -> pytz.BaseTzInfo:
    """
    解析时区字符串
    
    Args:
        timezone_str: 时区字符串，如 "Asia/Shanghai" 或 "+08:00"
    
    Returns:
        pytz 时区对象
    """
    # 尝试作为时区名称解析
    try:
        return pytz.timezone(timezone_str)
    except pytz.UnknownTimeZoneError:
        pass
    
    # 尝试作为偏移量解析（如 "+08:00"）
    if timezone_str.startswith(("+", "-")):
        # 解析偏移量
        sign = -1 if timezone_str.startswith("-") else 1
        parts = timezone_str[1:].split(":")
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
        offset_seconds = sign * (hours * 3600 + minutes * 60)
        return pytz.FixedOffset(offset_seconds // 60)
    
    raise ValueError(f"无法解析时区: {timezone_str}")


def get_current_time_in_timezone(
    current_time_iso: str,
    timezone_str: str
) -> datetime:
    """
    获取指定时区的当前时间
    
    Args:
        current_time_iso: ISO 8601 格式的当前时间字符串
        timezone_str: 时区字符串
    
    Returns:
        指定时区的 datetime 对象
    """
    # 解析 ISO 时间字符串
    dt = parser.isoparse(current_time_iso)
    
    # 如果时间没有时区信息，假设为 UTC
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    
    # 转换到目标时区
    target_tz = parse_timezone(timezone_str)
    return dt.astimezone(target_tz)


def format_time_str(dt: datetime) -> str:
    """
    格式化时间为字符串（YYYY-MM-DD HH:MM:SS，24小时制）
    
    Args:
        dt: datetime 对象
    
    Returns:
        格式化的时间字符串
    """
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_date_str(dt: datetime) -> str:
    """
    格式化日期为字符串（YYYY-MM-DD）
    
    Args:
        dt: datetime 对象
    
    Returns:
        格式化的日期字符串
    """
    return dt.strftime("%Y-%m-%d")


def get_past_time_iso(dt: datetime, minutes: int = 30) -> str:
    """
    获取过去某个时间点的 ISO 8601 格式字符串
    
    Args:
        dt: 当前时间
        minutes: 过去的分钟数
    
    Returns:
        ISO 8601 格式的时间字符串
    """
    from datetime import timedelta
    past_dt = dt - timedelta(minutes=minutes)
    return past_dt.isoformat()
