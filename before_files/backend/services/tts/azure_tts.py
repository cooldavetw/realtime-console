import logging
import requests
import os
import uuid
from typing import Dict, Any

from services.tts.base import TTSProvider

logger = logging.getLogger(__name__)

class AzureTTSProvider:
    """Azure 文本转语音提供商"""

    @staticmethod
    async def synthesize(text: str, config: Dict[str, Any]) -> bytes:
        """将文本转换为语音"""
        try:
            # 获取配置
            tts_config = config.get("tts_config", {})
            subscription_key = tts_config.get("subscription_key")
            service_region = tts_config.get("service_region")
            language = tts_config.get("language", "zh-CN")
            voice_name = tts_config.get("voice_name", "zh-CN-XiaoxiaoNeural")
            output_format = tts_config.get("output_format", "audio-24khz-96kbitrate-mono-mp3")

            if not subscription_key or not service_region:
                raise ValueError("Azure TTS requires subscription_key and service_region")

            # 构建 URL
            url = f"https://{service_region}.tts.speech.microsoft.com/cognitiveservices/v1"

            # 构建请求头
            headers = {
                "Ocp-Apim-Subscription-Key": subscription_key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": output_format,
                "User-Agent": "PythonVoiceAgent"
            }

            # 构建 SSML
            ssml = f"""
            <speak version='1.0' xml:lang='{language}'>
                <voice xml:lang='{language}' xml:gender='Female' name='{voice_name}'>
                    {text}
                </voice>
            </speak>
            """

            # 发送请求
            logger.info(f"Synthesizing speech using Azure voice: {voice_name}")
            response = requests.post(url, headers=headers, data=ssml.encode('utf-8'))

            # 检查错误
            response.raise_for_status()

            # 获取音频字节
            audio_bytes = response.content

            if not audio_bytes:
                raise Exception("TTS produced no audio")

            logger.info(f"Speech synthesis completed, audio size: {len(audio_bytes)} bytes")

            return audio_bytes

        except Exception as e:
            logger.error(f"Azure TTS error: {e}", exc_info=True)
            raise
