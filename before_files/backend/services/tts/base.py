from abc import ABC, abstractmethod
from typing import Dict, Any

class TTSProvider(ABC):
    """文本转语音提供商基础接口"""

    @staticmethod
    @abstractmethod
    async def synthesize(text: str, config: Dict[str, Any]) -> bytes:
        """将文本转换为语音"""
        pass

    @classmethod
    async def get_provider(cls, config: Dict[str, Any]):
        """获取适当的提供商实现"""
        provider = config.get("tts_provider", "openai").lower()

        if provider == "openai":
            from services.tts.openai_tts import OpenAITTSProvider
            return OpenAITTSProvider
        elif provider == "azure":
            from services.tts.azure_tts import AzureTTSProvider
            return AzureTTSProvider
        elif provider == "elevenlabs":
            from services.tts.elevenlabs_tts import ElevenLabsTTSProvider
            return ElevenLabsTTSProvider
        elif provider == "localai":
            from services.tts.localai_tts import LocalAITTSProvider
            return LocalAITTSProvider
        else:
            raise ValueError(f"Unknown TTS provider: {provider}")
