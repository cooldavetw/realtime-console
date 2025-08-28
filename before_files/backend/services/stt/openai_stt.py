import logging
from typing import Dict, Any
from io import BytesIO

from openai import OpenAI
from services.stt.base import STTProvider

logger = logging.getLogger(__name__)

class OpenAISTTProvider:
    """OpenAI 语音转文本提供商"""

    @staticmethod
    async def transcribe(audio_bytes: bytes, config: Dict[str, Any]) -> str:
        """将音频转换为文本"""
        try:
            # 获取配置
            stt_config = config.get("stt_config", {})
            model = stt_config.get("model", "gpt-4o-transcribe")
            language = stt_config.get("language", "")
            prompt = stt_config.get("prompt", "")
            api_key = stt_config.get("api_key", None)

            # 创建客户端
            client = OpenAI(api_key=api_key)

            # 准备音频文件
            audio_file = BytesIO(audio_bytes)
            audio_file.name = "audio.wav"

            # 调用 API
            logger.info(f"Transcribing audio using OpenAI model: {model}")

            params = {
                "model": model,
                "file": audio_file,
            }

            if language:
                params["language"] = language

            if prompt:
                params["prompt"] = prompt

            tr = client.audio.transcriptions.create(**params)

            # 提取文本
            transcription_text = getattr(tr, "text", "")
            logger.info(f"Transcription completed: {transcription_text[:50]}...")

            return transcription_text

        except Exception as e:
            logger.error(f"OpenAI STT error: {e}", exc_info=True)
            raise
