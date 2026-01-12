"""LLM 事件提取服务"""
import os
import json
import re
import logging
from typing import List, Dict, Any, Optional
import httpx

from app.models.response import Event
from app.utils.prompt_loader import get_prompts_with_variables, load_prompts, replace_prompt_variables
from app.utils.timezone import (
    get_current_time_in_timezone,
    format_time_str,
    format_date_str,
    get_past_time_iso,
    extract_timezone_from_iso
)

logger = logging.getLogger(__name__)


API_BASE = os.getenv("AI_BUILDER_API_BASE", "https://space.ai-builders.com")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3-flash-preview")


async def _call_llm_and_parse(
    prompts: Dict[str, str],
    tags: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    内部函数：调用 LLM API 并解析 JSON 响应
    
    Args:
        prompts: 包含 system 和 user prompt 的字典
        tags: 可选的标签列表，用于验证
    
    Returns:
        解析后的事件数据列表
    
    Raises:
        httpx.HTTPStatusError: API 调用失败
        ValueError: LLM 返回格式错误或 JSON 解析失败
    """
    token = os.getenv("AI_BUILDER_TOKEN")
    if not token:
        raise ValueError("AI_BUILDER_TOKEN 环境变量未设置")
    
    # 调用 LLM API
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await client.post(
            f"{API_BASE}/backend/v1/chat/completions",
            headers=headers,
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": prompts["system"]},
                    {"role": "user", "content": prompts["user"]}
                ],
                "temperature": 0.3,
                "max_tokens": 4000
            }
        )
        
        response.raise_for_status()
        result = response.json()
        
        # 提取 LLM 返回的内容
        if "choices" not in result or len(result["choices"]) == 0:
            raise ValueError(f"LLM API 响应格式错误：缺少 'choices' 字段。响应: {result}")
        
        choice = result["choices"][0]
        
        # 检查响应是否被截断
        finish_reason = choice.get("finish_reason")
        if finish_reason == "length":
            raise ValueError(
                "LLM 响应被截断（达到 max_tokens 限制）。"
                "请尝试减少输入文本长度或增加 max_tokens 限制。"
            )
        
        content = choice["message"]["content"]
        if not content:
            raise ValueError("LLM 返回的内容为空")
        
        # 清理内容：移除可能的 markdown 代码块
        content = clean_json_content(content)
        
        # 解析 JSON
        try:
            events_data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"无法解析 LLM 返回的 JSON: {e}。内容: {content}")
        
        # 验证和转换事件数据
        if not isinstance(events_data, list):
            raise ValueError(f"LLM 返回的数据不是数组格式: {type(events_data)}")
        
        return events_data


async def extract_events_with_llm(
    transcript: str,
    current_time_iso: str,
    timezone_str: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> List[Event]:
    """
    使用 LLM 从转录文本中提取事件
    
    Args:
        transcript: 转录文本
        current_time_iso: ISO 8601 格式的当前时间（应包含时区信息）
        timezone_str: 时区字符串（可选，如果不提供则从 current_time_iso 中提取）
        tags: 可选的标签列表，用于事件分类
    
    Returns:
        事件列表
    
    Raises:
        httpx.HTTPStatusError: API 调用失败
        ValueError: LLM 返回格式错误
    """
    # 如果没有提供 timezone_str，从 ISO 字符串中提取
    if timezone_str is None:
        timezone_str = extract_timezone_from_iso(current_time_iso)
        # 如果提取的是 UTC 偏移，尝试转换为更友好的格式
        if timezone_str == '+00:00':
            timezone_str = 'UTC'
    
    # 获取当前时间（在指定时区）
    current_dt = get_current_time_in_timezone(current_time_iso, timezone_str)
    
    # 准备 Prompt 变量
    variables = {
        "current_time_str": format_time_str(current_dt),
        "current_time_iso": current_dt.isoformat(),
        "current_date": format_date_str(current_dt),
        "past_30min_str": get_past_time_iso(current_dt, minutes=30),
        "transcript": transcript,
        "timezone": timezone_str
    }
    
    # 加载 Prompt 模板（需要先加载以获取 tags_section_template）
    prompt_templates = load_prompts()
    
    # 如果有 tags，添加到变量中并生成 tags_section
    if tags and len(tags) > 0:
        variables["tags"] = ", ".join(tags)
        variables["tags_list"] = ", ".join([f'"{tag}"' for tag in tags])
        # 从模板中读取 tags_section_template 并替换变量
        tags_template = prompt_templates.get("tags_section_template", "")
        variables["tags_section"] = replace_prompt_variables(tags_template, variables)
        variables["tags_user_section"] = f"可用标签：{variables['tags']}"
        variables["tag_field_section"] = " 和 tag"
    else:
        variables["tags_section"] = ""
        variables["tags_user_section"] = ""
        variables["tag_field_section"] = ""
    
    # 加载并替换 Prompt 模板
    prompts = get_prompts_with_variables(variables)
    
    # 调用 LLM API，如果遇到 JSON 解析错误则重试一次
    max_retries = 1
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            events_data = await _call_llm_and_parse(prompts, tags)
            break  # 成功则跳出循环
        except ValueError as e:
            error_msg = str(e)
            # 检查是否是 JSON 解析错误
            if "无法解析 LLM 返回的 JSON" in error_msg:
                last_error = e
                if attempt < max_retries:
                    logger.warning(f"JSON 解析失败，正在重试 ({attempt + 1}/{max_retries + 1})...")
                    continue
                else:
                    # 最后一次尝试也失败了
                    raise
            else:
                # 其他类型的错误直接抛出
                raise
    else:
        # 所有重试都失败了
        if last_error:
            raise last_error
    
    # 转换为 Event 对象并验证 tag
    events = []
    for event_data in events_data:
        try:
            # 验证和设置 tag 字段
            event_tag = event_data.get("tag")
            if tags and len(tags) > 0:
                # 如果提供了 tags，验证 tag 是否在列表中
                if event_tag and event_tag in tags:
                    # tag 在列表中，使用该值
                    pass
                else:
                    # tag 不在列表中或为 None，设为 None
                    event_data["tag"] = None
            else:
                # 没有提供 tags，设为 None
                event_data["tag"] = None
            
            event = Event(**event_data)
            events.append(event)
        except Exception as e:
            # 跳过无效的事件数据，记录错误但继续处理其他事件
            logger.warning(f"警告：跳过无效的事件数据: {event_data}，错误: {e}")
            continue
    
    return events


def clean_json_content(content: str) -> str:
    """
    清理 LLM 返回的 JSON 内容，移除可能的 markdown 代码块标记
    
    Args:
        content: 原始内容
    
    Returns:
        清理后的内容
    """
    # 移除 markdown 代码块标记
    content = re.sub(r"^```(?:json)?\s*\n", "", content, flags=re.MULTILINE)
    content = re.sub(r"\n```\s*$", "", content, flags=re.MULTILINE)
    
    # 移除首尾空白
    content = content.strip()
    
    # 尝试提取 JSON 数组部分（如果内容包含其他文字）
    # 查找第一个 [ 和最后一个 ]
    start_idx = content.find("[")
    end_idx = content.rfind("]")
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        content = content[start_idx:end_idx + 1]
    
    return content
