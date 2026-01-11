"""音频转录服务"""
import os
from typing import Optional
import httpx


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
            # 尝试两种路径：先尝试带 /backend 前缀，如果失败再尝试不带前缀
            endpoints = [
                f"{API_BASE}/backend/v1/audio/transcriptions",
                f"{API_BASE}/v1/audio/transcriptions"
            ]
            
            response = None
            last_error = None
            
            for endpoint in endpoints:
                try:
                    response = await client.post(
                        endpoint,
                        headers=headers,
                        files=files
                    )
                    # 如果成功（状态码 < 400），使用这个响应
                    if response.status_code < 400:
                        break
                    # 如果失败，保存错误并尝试下一个端点
                    last_error = httpx.HTTPStatusError(
                        f"Request failed with status {response.status_code}",
                        request=response.request,
                        response=response
                    )
                    response = None
                except httpx.HTTPStatusError as e:
                    last_error = e
                    response = None
                    continue
            
            # 如果所有端点都失败，抛出最后一个错误
            if response is None and last_error:
                raise last_error
            
            # 检查响应状态
            response.raise_for_status()
            result = response.json()
            
            # 提取转录文本
            if "text" not in result:
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
