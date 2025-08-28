import logging
from typing import Dict, Any
from io import BytesIO

from services.stt.base import STTProvider

logger = logging.getLogger(__name__)

class AssemblyAISTTProvider:
    """AssemblyAI 语音转文本提供商"""

    @staticmethod
    async def transcribe(audio_bytes: bytes, config: Dict[str, Any]) -> str:
        """将音频转换为文本"""
        try:
            # 获取配置
            stt_config = config.get("stt_config", {})
            api_key = stt_config.get("api_key")

            if not api_key:
                raise ValueError("AssemblyAI STT requires api_key")

            # 这需要 assemblyai 包
            # pip install assemblyai
            import assemblyai as aai

            # 创建客户端
            aai.settings.api_key = api_key

            # 保存音频到临时文件
            with BytesIO(audio_bytes) as audio_io:
                # 创建转录
                transcriber = aai.Transcriber()
                transcript = transcriber.transcribe(audio_io)

                # 获取文本
                if transcript.text:
                    logger.info(f"AssemblyAI transcription completed: {transcript.text[:50]}...")
                    return transcript.text
                else:
                    logger.warning("AssemblyAI transcription returned empty text")
                    return ""

        except Exception as e:
            logger.error(f"AssemblyAI STT error: {e}", exc_info=True)
            raise
