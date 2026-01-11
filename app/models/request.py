"""请求模型定义"""
from fastapi import UploadFile
from pydantic import BaseModel, Field
from typing import Optional


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


class AnalyzeJSONRequest(BaseModel):
    """JSON 格式的分析请求模型（用于 Shortcut 等场景）"""
    timezone: str = Field(..., description="时区字符串，如 'Asia/Shanghai' 或 '+08:00'")
    current_time: str = Field(..., description="ISO 8601 格式的当前时间")
    audio_data: str = Field(..., description="音频数据（base64编码）")
    audio_filename: Optional[str] = Field("audio.m4a", description="音频文件名")
    audio_content_type: Optional[str] = Field("audio/m4a", description="音频MIME类型")
    
    class Config:
        json_schema_extra = {
            "example": {
                "timezone": "Asia/Shanghai",
                "current_time": "2024-01-15T10:30:00+08:00",
                "audio_data": "base64_encoded_audio_data_here",
                "audio_filename": "recording.m4a",
                "audio_content_type": "audio/m4a"
            }
        }
