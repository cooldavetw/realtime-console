import logging
import requests
import json
from typing import Dict, Any

from services.stt.base import STTProvider

logger = logging.getLogger(__name__)

class AzureSTTProvider:
    """Azure 语音转文本提供商"""

    @staticmethod
    async def transcribe(audio_bytes: bytes, config: Dict[str, Any]) -> str:
        """将音频转换为文本"""
        try:
            # 获取配置
            stt_config = config.get("stt_config", {})
            subscription_key = stt_config.get("subscription_key")
            service_region = stt_config.get("service_region")
            language = stt_config.get("language", "zh-CN")
            profanity_filter_mode = stt_config.get("profanity_filter_mode", "Masked")
            channels = stt_config.get("channels", "0,1")
            api_version = stt_config.get("api_version", "2024-05-15-preview")

            if not subscription_key or not service_region:
                raise ValueError("Azure STT requires subscription_key and service_region")

            # 构建 URL
            base_url = f"https://{service_region}.cognitiveservices.azure.com/speechtotext/transcriptions:transcribe"

            # 解析通道
            channels_list = [int(ch) for ch in channels.split(",")]

            # 构建请求
            headers = {
                "Ocp-Apim-Subscription-Key": subscription_key,
                "Accept": "application/json"
            }

            # 构建表单数据
            import io
            from requests_toolbelt.multipart.encoder import MultipartEncoder

            # 准备音频数据
            audio_io = io.BytesIO(audio_bytes)

            # 构建定义
            definition = {
                "locales": [language],
                "profanityFilterMode": profanity_filter_mode,
                "channels": channels_list
            }

            multipart_data = MultipartEncoder(
                fields={
                    'audio': ('audio.wav', audio_io, 'audio/wav'),
                    'definition': json.dumps(definition)
                }
            )

            headers["Content-Type"] = multipart_data.content_type

            # 发送请求
            logger.info(f"Transcribing audio using Azure Speech API in {language}")
            response = requests.post(
                f"{base_url}?api-version={api_version}",
                data=multipart_data,
                headers=headers
            )

            # 检查错误
            response.raise_for_status()

            # 解析响应
            result = response.json()

            # 提取文本
            if result.get("combinedPhrases") and len(result["combinedPhrases"]) > 0:
                transcription_text = result["combinedPhrases"][0].get("text", "")
            else:
                transcription_text = ""

            logger.info(f"Azure transcription completed: {transcription_text[:50]}...")

            return transcription_text

        except Exception as e:
            logger.error(f"Azure STT error: {e}", exc_info=True)
            raise
