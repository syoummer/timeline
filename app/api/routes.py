"""API 路由"""
import base64
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional

from app.models.response import AnalyzeResponse, ErrorResponse, ErrorDetail
from app.models.request import AnalyzeJSONRequest
from app.services.transcription import transcribe_audio
from app.services.llm_extractor import extract_events_with_llm


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
    try:
        transcript = await transcribe_audio(
            audio_bytes=audio_bytes,
            filename=filename,
            content_type=content_type
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


@router.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze_audio(
    timezone: str = Form(..., description="时区字符串，如 'Asia/Shanghai' 或 '+08:00'"),
    current_time: str = Form(..., description="ISO 8601 格式的当前时间"),
    audio: Optional[UploadFile] = File(None, description="音频文件（支持 m4a、mp3、wav、flac 等格式）"),
    audio_data: Optional[str] = Form(None, description="音频数据（base64编码），与audio二选一"),
    audio_filename: Optional[str] = Form(None, description="音频文件名（当使用audio_data时必需）"),
    audio_content_type: Optional[str] = Form(None, description="音频MIME类型（当使用audio_data时可选，默认audio/m4a）")
):
    """
    分析音频文件，提取时间和事件信息
    
    支持两种方式上传音频：
    1. **audio**: 音频文件上传（支持 m4a、mp3、wav、flac 等格式）
    2. **audio_data**: 音频数据（base64编码的字符串），需要配合audio_filename使用
    
    - **timezone**: 时区字符串
    - **current_time**: 当前时间（ISO 8601 格式）
    
    返回转录文本和提取的事件列表
    """
    try:
        audio_bytes = None
        filename = "audio.m4a"
        content_type = "audio/m4a"
        
        # 优先使用文件上传，如果没有则使用base64数据
        if audio:
            # 方式1: 文件上传
            audio_bytes = await audio.read()
            filename = audio.filename or "audio.m4a"
            content_type = audio.content_type or "audio/m4a"
        elif audio_data:
            # 方式2: base64编码的音频数据
            try:
                # 移除可能的换行符和空白字符（Shortcut 可能每76字符换行）
                audio_data_clean = audio_data.replace('\n', '').replace('\r', '').replace(' ', '')
                # 解码base64数据
                audio_bytes = base64.b64decode(audio_data_clean)
                filename = audio_filename or "audio.m4a"
                content_type = audio_content_type or "audio/m4a"
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorResponse(
                        error=ErrorDetail(
                            code="INVALID_AUDIO_DATA",
                            message="音频数据格式错误",
                            details=f"无法解码base64数据: {str(e)}"
                        )
                    ).model_dump()
                )
        else:
            # 两种方式都没有提供
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code="MISSING_AUDIO",
                        message="缺少音频数据",
                        details="请提供audio文件或audio_data（base64编码）"
                    )
                ).model_dump()
            )
        
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


@router.post("/api/v1/analyze-json", response_model=AnalyzeResponse)
@router.post("/api/v1/analyze_json", response_model=AnalyzeResponse)  # 兼容下划线版本
async def analyze_audio_json(request: AnalyzeJSONRequest):
    """
    分析音频文件（JSON格式，用于 Shortcut 等场景）
    
    接受 JSON 格式的请求，包含 base64 编码的音频数据
    
    - **timezone**: 时区字符串
    - **current_time**: ISO 8601 格式的当前时间
    - **audio_data**: base64 编码的音频数据
    - **audio_filename**: 音频文件名（可选，默认 audio.m4a）
    - **audio_content_type**: 音频MIME类型（可选，默认 audio/m4a）
    
    返回转录文本和提取的事件列表
    """
    try:
        # 解码base64数据
        try:
            # 移除可能的换行符和空白字符（Shortcut 可能每76字符换行）
            audio_data_clean = request.audio_data.replace('\n', '').replace('\r', '').replace(' ', '')
            audio_bytes = base64.b64decode(audio_data_clean)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code="INVALID_AUDIO_DATA",
                        message="音频数据格式错误",
                        details=f"无法解码base64数据: {str(e)}"
                    )
                ).model_dump()
            )
        
        # 使用通用处理函数
        return await process_audio_analysis(
            audio_bytes=audio_bytes,
            filename=request.audio_filename,
            content_type=request.audio_content_type,
            timezone=request.timezone,
            current_time=request.current_time
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
            "analyze_json": "/api/v1/analyze-json (或 /api/v1/analyze_json)",
            "health": "/health"
        }
    }
