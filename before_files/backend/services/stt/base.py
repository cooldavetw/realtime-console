from abc import ABC, abstractmethod
from typing import Dict, Any

class STTProvider(ABC):
    """语音转文本提供商基础接口"""

    @staticmethod
    @abstractmethod
    async def transcribe(audio_bytes: bytes, config: Dict[str, Any]) -> str:
        """将音频转换为文本"""
        pass

    @classmethod
    async def get_provider(cls, config: Dict[str, Any]):
        """获取适当的提供商实现"""
        provider = config.get("stt_provider", "openai").lower()

        if provider == "openai":
            from services.stt.openai_stt import OpenAISTTProvider
            return OpenAISTTProvider
        elif provider == "azure":
            from services.stt.azure_stt import AzureSTTProvider
            return AzureSTTProvider
        elif provider == "assemblyai":
            from services.stt.assemblyai_stt import AssemblyAISTTProvider
            return AssemblyAISTTProvider
        elif provider == "groq":
            from services.stt.groq_stt import GroqSTTProvider
            return GroqSTTProvider
        elif provider == "localai":
            from services.stt.localai_stt import LocalAISTTProvider
            return LocalAISTTProvider
        else:
            raise ValueError(f"Unknown STT provider: {provider}")
