from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Awaitable

class VADProvider(ABC):
    """语音活动检测提供商基础接口"""

    @staticmethod
    @abstractmethod
    async def setup(config: Dict[str, Any],
                    on_speech_start: Callable[[], Awaitable[None]],
                    on_speech_stop: Callable[[], Awaitable[None]],
                    on_transcription: Callable[[str], Awaitable[None]]) -> Any:
        """设置 VAD 服务，返回连接或会话对象"""
        pass

    @staticmethod
    @abstractmethod
    async def process_audio(session: Any, audio_data: bytes) -> None:
        """处理音频数据"""
        pass

    @staticmethod
    @abstractmethod
    async def close(session: Any) -> None:
        """关闭 VAD 会话"""
        pass

    @classmethod
    async def get_provider(cls, config: Dict[str, Any]):
        """获取适当的提供商实现"""
        provider = config.get("vad_provider", "openai").lower()

        if provider == "openai":
            from backend.services.vad.openai_vad import OpenAIVADProvider
            return OpenAIVADProvider
        else:
            raise ValueError(f"Unknown VAD provider: {provider}")
