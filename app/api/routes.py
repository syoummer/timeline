"""API 路由"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import JSONResponse

from app.models.response import AnalyzeResponse, ErrorResponse, ErrorDetail
from app.services.transcription import transcribe_audio
from app.services.llm_extractor import extract_events_with_llm


router = APIRouter()


@router.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze_audio(
    audio: UploadFile = File(..., description="音频文件"),
    timezone: str = Form(..., description="时区字符串，如 'Asia/Shanghai' 或 '+08:00'"),
    current_time: str = Form(..., description="ISO 8601 格式的当前时间")
):
    """
    分析音频文件，提取时间和事件信息
    
    - **audio**: 音频文件（支持 m4a、mp3、wav、flac 等格式）
    - **timezone**: 时区字符串
    - **current_time**: 当前时间（ISO 8601 格式）
    
    返回转录文本和提取的事件列表
    """
    try:
        # 读取音频文件
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code="INVALID_AUDIO",
                        message="音频文件为空",
                        details="请上传有效的音频文件"
                    )
                ).model_dump()
            )
        
        # 步骤1: 音频转录
        try:
            transcript = await transcribe_audio(
                audio_bytes=audio_bytes,
                filename=audio.filename or "audio.m4a",
                content_type=audio.content_type
            )
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"转录错误: {str(e)}")
            print(f"错误详情: {error_trace}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code="TRANSCRIPTION_FAILED",
                        message="语音识别失败，请重试",
                        details=str(e)
                    )
                ).model_dump()
            )
        
        # 如果转录文本为空，返回错误
        if not transcript or not transcript.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code="EMPTY_TRANSCRIPT",
                        message="无法识别音频内容",
                        details="音频文件可能无法识别或内容为空"
                    )
                ).model_dump()
            )
        
        # 步骤2: LLM 事件提取
        try:
            events = await extract_events_with_llm(
                transcript=transcript,
                current_time_iso=current_time,
                timezone_str=timezone
            )
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"事件提取错误: {str(e)}")
            print(f"错误详情: {error_trace}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code="EVENT_EXTRACTION_FAILED",
                        message="事件提取失败",
                        details=str(e)
                    )
                ).model_dump()
            )
        
        # 返回成功响应
        return AnalyzeResponse(
            success=True,
            transcription=transcript,
            events=events
        )
    
    except HTTPException:
        # 重新抛出 HTTP 异常
        raise
    except Exception as e:
        # 处理其他未预期的错误
        import traceback
        error_trace = traceback.format_exc()
        print(f"未预期的错误: {str(e)}")
        print(f"错误详情: {error_trace}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="服务器内部错误",
                    details=str(e)
                )
            ).model_dump()
        )


@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy"}


@router.get("/api")
async def api_info():
    """API 信息端点"""
    return {
        "name": "Timeline API",
        "version": "1.0.0",
        "description": "语音驱动的日程记录工具 API",
        "endpoints": {
            "analyze": "/api/v1/analyze",
            "health": "/health"
        }
    }
