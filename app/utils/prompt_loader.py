"""Prompt 模板加载器"""
import os
from pathlib import Path
from typing import Dict, Optional


# 缓存 Prompt 模板
_cached_prompts: Optional[Dict[str, str]] = None


def load_prompts() -> Dict[str, str]:
    """
    加载 Prompt 模板文件
    
    Returns:
        包含 'system'、'user' 和 'tags_section_template' 键的字典
    """
    global _cached_prompts
    
    # 如果已缓存，直接返回
    if _cached_prompts is not None:
        return _cached_prompts
    
    # 获取 prompts.md 文件路径
    current_dir = Path(__file__).parent.parent.parent
    prompts_file = current_dir / "prompts" / "prompts.md"
    
    if not prompts_file.exists():
        raise FileNotFoundError(f"Prompt 模板文件不存在: {prompts_file}")
    
    # 读取文件内容
    content = prompts_file.read_text(encoding="utf-8")
    
    # 解析 System Prompt、User Prompt 和 Tags Section Template
    prompts = {}
    
    # 查找各个部分的位置
    system_start = content.find("## System Prompt")
    user_start = content.find("## User Prompt")
    tags_template_start = content.find("## Tags Section Template")
    
    if system_start == -1 or user_start == -1:
        raise ValueError("Prompt 模板格式错误：未找到 System Prompt 或 User Prompt 部分")
    
    # 提取 System Prompt（从 System Prompt 标题到 User Prompt 标题之间）
    system_content = content[system_start:user_start].strip()
    # 移除标题行
    system_lines = system_content.split("\n")
    system_lines = [line for line in system_lines if not line.startswith("##")]
    prompts["system"] = "\n".join(system_lines).strip()
    
    # 提取 User Prompt（从 User Prompt 标题到 Tags Section Template 或文件末尾）
    if tags_template_start != -1:
        user_content = content[user_start:tags_template_start].strip()
    else:
        user_content = content[user_start:].strip()
    # 移除标题行
    user_lines = user_content.split("\n")
    user_lines = [line for line in user_lines if not line.startswith("##")]
    prompts["user"] = "\n".join(user_lines).strip()
    
    # 提取 Tags Section Template（如果存在）
    if tags_template_start != -1:
        tags_template_content = content[tags_template_start:].strip()
        # 移除标题行
        tags_template_lines = tags_template_content.split("\n")
        tags_template_lines = [line for line in tags_template_lines if not line.startswith("##")]
        prompts["tags_section_template"] = "\n".join(tags_template_lines).strip()
    else:
        prompts["tags_section_template"] = ""
    
    # 缓存结果
    _cached_prompts = prompts
    
    return prompts


def replace_prompt_variables(
    prompt_template: str,
    variables: Dict[str, str]
) -> str:
    """
    替换 Prompt 模板中的变量
    
    Args:
        prompt_template: Prompt 模板字符串
        variables: 变量字典
    
    Returns:
        替换后的 Prompt 字符串
    """
    result = prompt_template
    for key, value in variables.items():
        result = result.replace(f"{{{key}}}", str(value))
    return result


def get_prompts_with_variables(variables: Dict[str, str]) -> Dict[str, str]:
    """
    获取替换变量后的 Prompt
    
    Args:
        variables: 变量字典
    
    Returns:
        包含 'system' 和 'user' 键的字典，变量已替换
    """
    prompts = load_prompts()
    return {
        "system": replace_prompt_variables(prompts["system"], variables),
        "user": replace_prompt_variables(prompts["user"], variables)
    }
