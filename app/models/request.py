"""请求模型定义"""
from fastapi import UploadFile
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """分析请求模型"""
    timezone: str = Field(..., description="时区字符串，如 'Asia/Shanghai' 或 '+08:00'")
    current_time: str = Field(..., description="ISO 8601 格式的当前时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "timezone": "Asia/Shanghai",
                "current_time": "2024-01-15T10:30:00+08:00"
            }
        }
