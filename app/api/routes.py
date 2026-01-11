"""API 路由"""
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import JSONResponse

from app.models.response import AnalyzeResponse, ErrorResponse, ErrorDetail
from app.services.transcription import transcribe_audio
from app.services.llm_extractor import extract_events_with_llm

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


router = APIRouter()


async def process_audio_analysis(
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    timezone: str,
    current_time: str
) -> AnalyzeResponse:
    """
    处理音频分析的通用逻辑
    
    Args:
        audio_bytes: 音频字节数据
        filename: 音频文件名
        content_type: 音频MIME类型
        timezone: 时区字符串
        current_time: ISO 8601 格式的当前时间
    
    Returns:
        AnalyzeResponse: 分析结果
    """
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
    logger.info(f"[TRANSCRIPTION] 开始转录 - filename: {filename}, content_type: {content_type}, 大小: {len(audio_bytes)} 字节")
    try:
        transcript = await transcribe_audio(
            audio_bytes=audio_bytes,
            filename=filename,
            content_type=content_type
        )
        logger.info(f"[TRANSCRIPTION] 转录成功 - 文本长度: {len(transcript)} 字符")
        logger.debug(f"[TRANSCRIPTION] 转录文本: {transcript[:200]}...")
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"[TRANSCRIPTION] 转录错误: {str(e)}")
        logger.error(f"[TRANSCRIPTION] 错误详情: {error_trace}")
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
    logger.info(f"[EXTRACTION] 开始事件提取 - timezone: {timezone}, current_time: {current_time}")
    try:
        events = await extract_events_with_llm(
            transcript=transcript,
            current_time_iso=current_time,
            timezone_str=timezone
        )
        logger.info(f"[EXTRACTION] 事件提取成功 - 提取到 {len(events)} 个事件")
        for i, event in enumerate(events):
            logger.debug(f"[EXTRACTION] 事件 {i+1}: {event.title} ({event.start_time} - {event.end_time})")
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"[EXTRACTION] 事件提取错误: {str(e)}")
        logger.error(f"[EXTRACTION] 错误详情: {error_trace}")
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


@router.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze_audio(
    timezone: str = Form(..., description="时区字符串，如 'Asia/Shanghai' 或 '+08:00'"),
    current_time: str = Form(..., description="ISO 8601 格式的当前时间"),
    audio: UploadFile = File(..., description="音频文件（支持 m4a、mp3、wav、flac、webm 等格式）")
):
    """
    分析音频文件，提取时间和事件信息
    
    - **timezone**: 时区字符串（如 'Asia/Shanghai' 或 '+08:00'）
    - **current_time**: 当前时间（ISO 8601 格式，如 '2024-01-15T14:30:00+08:00'）
    - **audio**: 音频文件（支持 m4a、mp3、wav、flac、webm 等格式）
    
    返回转录文本和提取的事件列表
    """
    try:
        # 添加详细的请求日志
        logger.info(f"[REQUEST] 收到分析请求 - timezone: {timezone}, current_time: {current_time[:50] if current_time else None}")
        logger.info(f"[REQUEST] audio 文件: filename={audio.filename}, content_type={audio.content_type}")
        
        # 读取音频文件
        audio_bytes = await audio.read()
        filename = audio.filename or "audio.m4a"
        content_type = audio.content_type or "audio/m4a"
        
        logger.info(f"[AUDIO] 文件读取成功，大小: {len(audio_bytes)} 字节")
        
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
        
        # 使用通用处理函数
        return await process_audio_analysis(
            audio_bytes=audio_bytes,
            filename=filename,
            content_type=content_type,
            timezone=timezone,
            current_time=current_time
        )
    
    except HTTPException:
        # 重新抛出 HTTP 异常
        raise
    except Exception as e:
        # 处理其他未预期的错误
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"[ERROR] 未预期的错误: {str(e)}")
        logger.error(f"[ERROR] 错误详情: {error_trace}")
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
