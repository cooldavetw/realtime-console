from abc import ABC, abstractmethod
from typing import Dict, Any

class QueryProvider(ABC):
    """查询提供商基础接口"""

    @staticmethod
    @abstractmethod
    async def query(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """发送查询到后端服务获取回答"""
        pass

    @classmethod
    async def get_provider(cls, config: Dict[str, Any]):
        """获取适当的提供商实现"""
        provider = config.get("query_provider", "flowise").lower()

        if provider == "flowise":
            from services.query.flowise import FlowiseQueryProvider
            return FlowiseQueryProvider
        elif provider == "openai":
            from services.query.openai import OpenAIQueryProvider
            return OpenAIQueryProvider
        elif provider == "anthropic":
            from services.query.anthropic import AnthropicQueryProvider
            return AnthropicQueryProvider
        elif provider == "azure_openai":
            from services.query.azure_openai import AzureOpenAIQueryProvider
            return AzureOpenAIQueryProvider
        elif provider == "langchain":
            from services.query.langchain import LangChainQueryProvider
            return LangChainQueryProvider
        elif provider == "huggingface":
            from services.query.huggingface import HuggingFaceQueryProvider
            return HuggingFaceQueryProvider
        elif provider == "localai":
            from services.query.localai import LocalAIQueryProvider
            return LocalAIQueryProvider
        elif provider == "ollama":
            from services.query.ollama import OllamaQueryProvider
            return OllamaQueryProvider
        elif provider == "google_ai":
            from services.query.google_ai import GoogleAIQueryProvider
            return GoogleAIQueryProvider
        elif provider == "custom_api":
            from services.query.custom_api import CustomAPIQueryProvider
            return CustomAPIQueryProvider
        else:
            raise ValueError(f"Unknown query provider: {provider}")
