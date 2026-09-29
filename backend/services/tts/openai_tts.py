import logging
from typing import Dict, Any

from openai import OpenAI
from backend.services.tts.base import TTSProvider

logger = logging.getLogger(__name__)

class OpenAITTSProvider:
    """OpenAI 文本转语音提供商"""

    @staticmethod
    async def synthesize(text: str, config: Dict[str, Any]) -> bytes:
        """将文本转换为语音"""
        try:
            # 获取配置
            tts_config = config.get("tts_config", {})
            model = tts_config.get("model", "gpt-4o-mini-tts")
            voice = tts_config.get("voice", "alloy")
            speed = tts_config.get("speed", 1.0)
            response_format = tts_config.get("response_format", "wav")
            api_key = tts_config.get("api_key", None)

            # 创建客户端
            client = OpenAI(api_key=api_key)

            # 调用 API
            logger.info(f"Synthesizing speech using OpenAI model: {model}, voice: {voice}")

            tts = client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                speed=speed,
                response_format=response_format
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
            logger.error(f"OpenAI TTS error: {e}", exc_info=True)
            raise
