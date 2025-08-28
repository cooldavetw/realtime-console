# 导入各种服务提供商的基类
from services.stt.base import STTProvider
from services.tts.base import TTSProvider
from services.query.base import QueryProvider
from services.vad.base import VADProvider

__all__ = ['STTProvider', 'TTSProvider', 'QueryProvider', 'VADProvider']
