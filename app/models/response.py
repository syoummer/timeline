"""响应模型定义"""
from typing import List, Optional
from pydantic import BaseModel, Field


class Event(BaseModel):
    """单个日历事件"""
    title: str = Field(..., description="事件标题")
    start_time: str = Field(..., description="开始时间，ISO 8601 格式")
    end_time: str = Field(..., description="结束时间，ISO 8601 格式")
    description: Optional[str] = Field(None, description="事件描述（包含地点、参与人等）")
    tag: Optional[str] = Field(None, description="事件标签/分类（可选）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "买菜",
                "start_time": "2024-01-15T14:00:00+08:00",
                "end_time": "2024-01-15T15:00:00+08:00",
                "description": "地点：超市",
                "tag": "生活"
            }
        }


class TranscribeResponse(BaseModel):
    """转录响应模型"""
    success: bool = Field(True, description="是否成功")
    transcription: str = Field(..., description="转录文本")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "transcription": "我2点去买菜，3点去理发，4点到家"
            }
        }


class AnalyzeResponse(BaseModel):
    """分析响应模型"""
    success: bool = Field(True, description="是否成功")
    events: List[Event] = Field(default_factory=list, description="提取的事件列表")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "events": [
                    {
                        "title": "买菜",
                        "start_time": "2024-01-15T14:00:00+08:00",
                        "end_time": "2024-01-15T15:00:00+08:00",
                        "description": "地点：超市"
                    }
                ]
            }
        }


class ErrorDetail(BaseModel):
    """错误详情"""
    code: str = Field(..., description="错误代码")
    message: str = Field(..., description="错误消息")
    details: Optional[str] = Field(None, description="详细错误信息")


class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: ErrorDetail
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": {
                    "code": "TRANSCRIPTION_FAILED",
                    "message": "语音识别失败，请重试",
                    "details": "无法识别音频格式"
                }
            }
        }
