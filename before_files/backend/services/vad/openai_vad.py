import json
import base64
import logging
import websockets
from typing import Dict, Any, Callable, Awaitable

from config.settings import get_config
from services.vad.base import VADProvider
from core.utils import extract_transcript_from_event

logger = logging.getLogger(__name__)

class OpenAIVADProvider:
    """OpenAI Realtime API VAD 提供商"""

    @staticmethod
    async def setup(config: Dict[str, Any],
                    on_speech_start: Callable[[], Awaitable[None]],
                    on_speech_stop: Callable[[], Awaitable[None]],
                    on_transcription: Callable[[str], Awaitable[None]]) -> Any:
        """设置 VAD 服务，返回连接或会话对象"""
        try:
            # 连接到 OpenAI Realtime API
            openai_ws = await websockets.connect(
                get_config("OPENAI_REALTIME_URL"),
                extra_headers={
                    "Authorization": f"Bearer {get_config('OPENAI_API_KEY')}",
                    "OpenAI-Beta": get_config("OPENAI_BETA_HEADER"),
                },
                max_size=get_config("MAX_MESSAGE_SIZE"),
                ping_interval=get_config("PING_INTERVAL"),
                ping_timeout=get_config("PING_TIMEOUT"),
            )

            # 配置 VAD
            vad_config = config.get("vad_config", {})
            stt_config = config.get("stt_config", {})

            session_update = {
                "type": "session.update",
                "session": {
                    "input_audio_format": "pcm16",
                    "input_audio_transcription": {
                        "model": stt_config.get("model", "gpt-4o-transcribe"),
                        "prompt": stt_config.get("prompt", ""),
                        "language": stt_config.get("language", "")
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": vad_config.get("threshold", 0.5),
                        "prefix_padding_ms": vad_config.get("prefix_padding_ms", 300),
                        "silence_duration_ms": vad_config.get("silence_duration_ms", 500),
                        "create_response": False  # 不自动生成响应
                    },
                    "include": ["item.input_audio_transcription.logprobs"],
                }
            }

            await openai_ws.send(json.dumps(session_update))

            # 启动事件处理任务
            import asyncio

            async def event_handler():
                try:
                    async for raw in openai_ws:
                        try:
                            evt = json.loads(raw)
                        except Exception:
                            logger.warning(f"Non-JSON event from OpenAI: {type(raw)}")
                            continue

                        event_type = evt.get("type", "")

                        # VAD 事件
                        if event_type == "input_audio_buffer.speech_started":
                            logger.info("Speech started detected by VAD")
                            await on_speech_start()

                        elif event_type == "input_audio_buffer.speech_stopped":
                            logger.info("Speech stopped detected by VAD")
                            await on_speech_stop()

                        # 转录完成
                        elif event_type == "conversation.item.input_audio_transcription.completed":
                            # 提取转录文本
                            user_text = extract_transcript_from_event(evt)

                            if user_text:
                                logger.info(f"Transcription completed: {user_text}")
                                await on_transcription(user_text)

                        # 错误处理
                        elif event_type == "error":
                            logger.error(f"OpenAI Realtime API error: {evt}")

                except websockets.exceptions.ConnectionClosedError:
                    logger.info("OpenAI Realtime API connection closed")
                except Exception as e:
                    logger.error(f"Error handling OpenAI events: {e}", exc_info=True)

            # 创建任务
            task = asyncio.create_task(event_handler())

            # 返回会话对象
            return {
                "websocket": openai_ws,
                "task": task
            }

        except Exception as e:
            logger.error(f"Failed to setup OpenAI VAD: {e}", exc_info=True)
            raise

    @staticmethod
    async def process_audio(session: Any, audio_data: bytes) -> None:
        """处理音频数据"""
        try:
            openai_ws = session.get("websocket")
            if not openai_ws:
                raise ValueError("Invalid VAD session")

            # 编码为 base64
            audio_b64 = base64.b64encode(audio_data).decode("utf-8")

            # 发送到 OpenAI
            append_evt = {
                "type": "input_audio_buffer.append",
                "audio": audio_b64
            }
            await openai_ws.send(json.dumps(append_evt))

        except Exception as e:
            logger.error(f"Error processing audio in OpenAI VAD: {e}", exc_info=True)
            raise

    @staticmethod
    async def close(session: Any) -> None:
        """关闭 VAD 会话"""
        try:
            if session:
                if session.get("task"):
                    session["task"].cancel()

                if session.get("websocket"):
                    await session["websocket"].close()

        except Exception as e:
            logger.error(f"Error closing OpenAI VAD session: {e}", exc_info=True)
