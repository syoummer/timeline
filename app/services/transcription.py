"""音频转录服务"""
import os
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


API_BASE = os.getenv("AI_BUILDER_API_BASE", "https://space.ai-builders.com")


async def transcribe_audio(
    audio_bytes: bytes,
    filename: str,
    content_type: Optional[str] = None
) -> str:
    """
    调用 AI Builder Space API 进行音频转录
    
    Args:
        audio_bytes: 音频文件的字节数据
        filename: 音频文件名
        content_type: 音频文件的 MIME 类型（可选）
    
    Returns:
        转录文本
    
    Raises:
        httpx.HTTPStatusError: API 调用失败
        ValueError: 响应格式错误
    """
    token = os.getenv("AI_BUILDER_TOKEN")
    if not token:
        raise ValueError("AI_BUILDER_TOKEN 环境变量未设置")
    
    # 如果没有指定 content_type，根据文件扩展名推断
    if not content_type:
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        content_type_map = {
            "m4a": "audio/m4a",
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
            "flac": "audio/flac",
            "webm": "audio/webm",  # 添加 webm 支持
        }
        content_type = content_type_map.get(ext, "audio/webm")  # 默认使用 webm
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {"Authorization": f"Bearer {token}"}
        files = {"audio_file": (filename, audio_bytes, content_type)}
        
        try:
            # 根据 OpenAPI 文档，服务器基础 URL 是 /backend
            # 转录端点是 /v1/audio/transcriptions
            # 所以完整路径是: https://space.ai-builders.com/backend/v1/audio/transcriptions
            endpoint = f"{API_BASE}/backend/v1/audio/transcriptions"
            
            logger.info(f"[TRANSCRIPTION] 调用转录 API: {endpoint}")
            logger.info(f"[TRANSCRIPTION] 文件信息: filename={filename}, content_type={content_type}, size={len(audio_bytes)} bytes")
            
            # 使用 multipart/form-data 格式，字段名为 audio_file
            # httpx 会自动设置正确的 Content-Type 和 boundary
            response = await client.post(
                endpoint,
                headers=headers,
                files=files,
                timeout=120.0  # 增加超时时间，因为音频转录可能需要更长时间
            )
            
            logger.info(f"[TRANSCRIPTION] API 响应状态: {response.status_code}")
            
            # 检查响应状态
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"[TRANSCRIPTION] API 响应: {result.keys() if isinstance(result, dict) else 'non-dict response'}")
            
            # 提取转录文本
            if "text" not in result:
                logger.error(f"[TRANSCRIPTION] API 响应格式错误，缺少 'text' 字段。完整响应: {result}")
                raise ValueError(f"API 响应格式错误：缺少 'text' 字段。响应: {result}")
            
            return result["text"]
        except httpx.HTTPStatusError as e:
            # 尝试解析错误响应
            try:
                error_data = e.response.json()
                error_msg = error_data.get("detail", {}).get("message", str(e))
            except:
                error_msg = f"API 调用失败: {e.response.status_code} {e.response.text[:200]}"
            raise ValueError(f"音频转录失败: {error_msg}")
        except httpx.RequestError as e:
            raise ValueError(f"网络请求失败: {str(e)}")
