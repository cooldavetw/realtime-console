# 导入各种服务提供商的基类
from backend.services.stt.base import STTProvider
from backend.services.tts.base import TTSProvider
from backend.services.query.base import QueryProvider
from backend.services.vad.base import VADProvider

__all__ = ['STTProvider', 'TTSProvider', 'QueryProvider', 'VADProvider']
