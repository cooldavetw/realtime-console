import logging
from typing import Dict, Any
from io import BytesIO

from backend.services.stt.base import STTProvider

logger = logging.getLogger(__name__)

class GroqSTTProvider:
    """Groq 语音转文本提供商"""

    @staticmethod
    async def transcribe(audio_bytes: bytes, config: Dict[str, Any]) -> str:
        """将音频转换为文本"""
        try:
            # 获取配置
            stt_config = config.get("stt_config", {})
            api_key = stt_config.get("api_key")
            model = stt_config.get("model", "whisper-large-v3")
            language = stt_config.get("language", "")
            temperature = stt_config.get("temperature", 0)

            if not api_key:
                raise ValueError("Groq STT requires api_key")

            # 这需要 groq 包
            # pip install groq
            from groq import Groq

            # 创建客户端
            client = Groq(api_key=api_key)

            # 准备音频文件
            audio_file = BytesIO(audio_bytes)
            audio_file.name = "audio.wav"

            # 调用 API
            logger.info(f"Transcribing audio using Groq model: {model}")

            params = {
                "file": audio_file,
                "model": model,
                "response_format": "verbose_json"
            }

            if language:
                params["language"] = language

            if temperature is not None:
                params["temperature"] = temperature

            transcription = client.audio.transcriptions.create(**params)

            # 提取文本
            transcription_text = transcription.text
            logger.info(f"Groq transcription completed: {transcription_text[:50]}...")

            return transcription_text

        except Exception as e:
            logger.error(f"Groq STT error: {e}", exc_info=True)
            raise
