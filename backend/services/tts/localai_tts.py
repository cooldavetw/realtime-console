import logging
from typing import Dict, Any

from openai import OpenAI
from backend.services.tts.base import TTSProvider

logger = logging.getLogger(__name__)

class LocalAITTSProvider:
    """LocalAI 文本转语音提供商"""

    @staticmethod
    async def synthesize(text: str, config: Dict[str, Any]) -> bytes:
        """将文本转换为语音"""
        try:
            # 获取配置
            tts_config = config.get("tts_config", {})
            base_url = tts_config.get("base_url", "http://localhost:8080/v1")
            model = tts_config.get("model", "tts-1")
            voice = tts_config.get("voice", "alloy")
            api_key = tts_config.get("api_key", "sk-no-key-required")

            # 创建 OpenAI 客户端指向 LocalAI
            client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )

            # 调用 API
            logger.info(f"Synthesizing speech using LocalAI model: {model}, voice: {voice}")

            tts = client.audio.speech.create(
                model=model,
                voice=voice,
                input=text
            )

            # 获取音频字节
            audio_bytes = getattr(tts, "content", None)
            if audio_bytes is None and hasattr(tts, "read"):
                audio_bytes = tts.read()

            if not audio_bytes:
                raise Exception("TTS produced no audio")

            logger.info(f"Speech synthesis completed, audio size: {len(audio_bytes)} bytes")

            return audio_bytes

        except Exception as e:
            logger.error(f"LocalAI TTS error: {e}", exc_info=True)
            raise
