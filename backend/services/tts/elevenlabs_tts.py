import logging
import requests
from typing import Dict, Any

from backend.services.tts.base import TTSProvider

logger = logging.getLogger(__name__)

class ElevenLabsTTSProvider:
    """ElevenLabs 文本转语音提供商"""

    @staticmethod
    async def synthesize(text: str, config: Dict[str, Any]) -> bytes:
        """将文本转换为语音"""
        try:
            # 获取配置
            tts_config = config.get("tts_config", {})
            api_key = tts_config.get("api_key")
            voice_id = tts_config.get("voice_id", "21m00Tcm4TlvDq8ikWAM")  # Josh 声音
            model_id = tts_config.get("model_id", "eleven_multilingual_v2")
            stability = tts_config.get("stability", 0.5)
            similarity_boost = tts_config.get("similarity_boost", 0.75)

            if not api_key:
                raise ValueError("ElevenLabs TTS requires api_key")

            # 构建 URL
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

            # 构建请求头
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": api_key
            }

            # 构建请求体
            data = {
                "text": text,
                "model_id": model_id,
                "voice_settings": {
                    "stability": stability,
                    "similarity_boost": similarity_boost
                }
            }

            # 发送请求
            logger.info(f"Synthesizing speech using ElevenLabs voice: {voice_id}, model: {model_id}")
            response = requests.post(url, json=data, headers=headers)

            # 检查错误
            response.raise_for_status()

            # 获取音频字节
            audio_bytes = response.content

            if not audio_bytes:
                raise Exception("TTS produced no audio")

            logger.info(f"Speech synthesis completed, audio size: {len(audio_bytes)} bytes")

            return audio_bytes

        except Exception as e:
            logger.error(f"ElevenLabs TTS error: {e}", exc_info=True)
            raise
