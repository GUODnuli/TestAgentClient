# -*- coding: utf-8 -*-
"""LLM 模型适配器

支持多种 LLM 提供商：DashScope、OpenAI、Ollama、Gemini、Anthropic
"""
import re
import agentscope
from agentscope.formatter import (
    DashScopeChatFormatter,
    OpenAIChatFormatter,
    FormatterBase,
    OllamaChatFormatter,
    GeminiChatFormatter,
    AnthropicChatFormatter,
)
from agentscope.model import (
    ChatModelBase,
    DashScopeChatModel,
    OpenAIChatModel,
    OllamaChatModel,
    GeminiChatModel,
    AnthropicChatModel,
)


def is_agentscope_version_ge(target_version: tuple) -> bool:
    """
    检查当前 agentscope 版本是否 >= 目标版本
    
    Args:
        target_version: (major, minor, patch) 版本元组
        
    Returns:
        当前版本 >= 目标版本返回 True
    """
    version_str = agentscope.__version__
    version_match = re.match(r'^(\d+)\.(\d+)\.(\d+)', version_str)
    if version_match:
        major, minor, patch = map(int, version_match.groups())
        current_version = (major, minor, patch)
        return current_version >= target_version
    return False


def get_formatter(llm_provider: str) -> FormatterBase:
    """
    根据 LLM 提供商获取格式化器
    
    Args:
        llm_provider: LLM 提供商名称
        
    Returns:
        对应的格式化器实例
    """
    provider = llm_provider.lower()
    
    if provider == "dashscope":
        return DashScopeChatFormatter()
    elif provider == "openai":
        return OpenAIChatFormatter()
    elif provider == "ollama":
        return OllamaChatFormatter()
    elif provider == "gemini":
        return GeminiChatFormatter()
    elif provider == "anthropic":
        return AnthropicChatFormatter()
    else:
        raise ValueError(f"不支持的 LLM 提供商: {llm_provider}")


def get_model(
    llm_provider: str,
    model_name: str,
    api_key: str,
    client_kwargs: dict = None,
    generate_kwargs: dict = None,
) -> ChatModelBase:
    """
    根据参数获取 LLM 模型实例
    
    Args:
        llm_provider: LLM 提供商名称
        model_name: 模型名称
        api_key: API Key
        client_kwargs: 客户端额外参数
        generate_kwargs: 生成额外参数
        
    Returns:
        LLM 模型实例
    """
    client_kwargs = client_kwargs or {}
    generate_kwargs = generate_kwargs or {}
    provider = llm_provider.lower()
    
    if provider == "dashscope":
        return DashScopeChatModel(
            model_name=model_name,
            api_key=api_key,
            stream=True,
            generate_kwargs=generate_kwargs,
        )
    elif provider == "openai":
        return OpenAIChatModel(
            model_name=model_name,
            api_key=api_key,
            stream=True,
            client_kwargs=client_kwargs,
            generate_kwargs=generate_kwargs,
        )
    elif provider == "ollama":
        if is_agentscope_version_ge((1, 0, 9)):
            return OllamaChatModel(
                model_name=model_name,
                stream=True,
                client_kwargs=client_kwargs,
                generate_kwargs=generate_kwargs,
            )
        else:
            return OllamaChatModel(
                model_name=model_name,
                stream=True,
                **client_kwargs,
            )
    elif provider == "gemini":
        return GeminiChatModel(
            model_name=model_name,
            api_key=api_key,
            stream=True,
            client_kwargs=client_kwargs,
            generate_kwargs=generate_kwargs,
        )
    elif provider == "anthropic":
        return AnthropicChatModel(
            model_name=model_name,
            api_key=api_key,
            stream=True,
            client_kwargs=client_kwargs,
            generate_kwargs=generate_kwargs,
        )
    else:
        raise ValueError(f"不支持的 LLM 提供商: {llm_provider}")
