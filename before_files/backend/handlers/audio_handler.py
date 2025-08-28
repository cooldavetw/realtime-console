import json
import base64
import logging
import asyncio
import websockets
from typing import Dict, Any

from core.session import SessionManager
from core.utils import send_event, extract_transcript_from_event, generate_id
from config.settings import get_config

logger = logging.getLogger(__name__)

class AudioHandler:
    """处理音频相关功能"""

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def process_binary_audio(self, websocket, audio_data, session_id):
        """处理二进制音频数据"""
        session = self.session_manager.get_session(session_id)

        if session["config"]["mode"] == "push_to_talk":
            # Push-to-talk 模式：累积音频数据
            session["audio_buffer"].extend(audio_data)

        elif session["config"]["mode"] == "vad":
            # VAD 模式：转发到 OpenAI Realtime API
            await self.forward_to_vad(websocket, audio_data, session_id)

    async def forward_to_vad(self, websocket, audio_data, session_id):
        """将音频转发到 VAD 服务"""
        session = self.session_manager.get_session(session_id)

        if session.get("openai_ws"):
            # 转发到 OpenAI Realtime API
            try:
                # 编码为 base64
                audio_b64 = base64.b64encode(audio_data).decode("utf-8")

                # 发送到 OpenAI
                append_evt = {
                    "type": "input_audio_buffer.append",
                    "audio": audio_b64
                }
                await session["openai_ws"].send(json.dumps(append_evt))
            except Exception as e:
                logger.error(f"Error forwarding audio to VAD: {e}", exc_info=True)
                await send_event(websocket, "error", {
                    "code": "vad_forward_error",
                    "message": f"Error forwarding audio to VAD: {e}"
                })
        else:
            await send_event(websocket, "error", {
                "code": "vad_not_connected",
                "message": "VAD mode is not properly connected"
            })

    async def setup_vad_mode(self, websocket, session_id):
        """设置 VAD 模式连接到 OpenAI Realtime API"""
        session = self.session_manager.get_session(session_id)

        # 关闭现有连接
        if session.get("openai_task"):
            session["openai_task"].cancel()
        if session.get("openai_ws"):
            await session["openai_ws"].close()

        # 连接到 OpenAI Realtime API

        url = get_config("OPENAI_REALTIME_URL")
        additional_headers={
            "Authorization": f"Bearer {get_config('OPENAI_API_KEY')}",
            "OpenAI-Beta": get_config("OPENAI_BETA_HEADER"),
        }
        openai_ws = await websockets.connect(
            url,
            additional_headers=additional_headers
        )

        session["openai_ws"] = openai_ws

        # 配置 VAD
        vad_config = session["config"]["vad_config"]

        session_update = {
            "type": "session.update",
            "session": {
                "input_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": session["config"]["stt_config"].get("model", "gpt-4o-transcribe")
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
        session["openai_task"] = asyncio.create_task(
            self._handle_openai_events(websocket, session_id)
        )

        logger.info("VAD mode connected to OpenAI Realtime API")


    async def _handle_openai_events(self, websocket, session_id):
        """处理来自 OpenAI Realtime API 的事件"""
        try:
            session = self.session_manager.get_session(session_id)
            openai_ws = session["openai_ws"]

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
                    session["id"] = generate_id("vad")
                    await send_event(websocket, "vad.speech_started", {})

                elif event_type == "input_audio_buffer.speech_stopped":
                    logger.info("Speech stopped detected by VAD")
                    session["id"] = None
                    await send_event(websocket, "vad.speech_stopped", {})

                elif event_type == "input_audio_buffer.committed":
                    audio_id = session.get("id")
                    session["id"] = None
                    logger.info(f"Audio buffer committed by VAD: {audio_id}")
                    await send_event(websocket, "vad.audio_committed", {
                        "audio_id": audio_id
                    })

                # 转录完成
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    # 提取转录文本
                    user_text = extract_transcript_from_event(evt)
                    transcription_id = generate_id("transcript")
                    session["id"] = None

                    if not user_text:
                        logger.warning("Transcription event without text")
                        continue

                    logger.info(f"Transcription completed: {user_text}, evt={evt}")

                    # 发送转录结果
                    await send_event(websocket, "transcript.created", {
                        "session_id": session_id,
                        "audio_id": transcription_id,
                        "text": user_text
                    })

                    self.session_manager.add_conversation_item(
                        transcription_id,
                        session_id,
                        role="user",
                        type_name="audio_transcript",
                        content={"transcript": user_text},
                        websocket=websocket
                    )

                    # 查询后端
                    from handlers.event_handler import EventHandler
                    event_handler = EventHandler(self.session_manager)
                    await event_handler._process_query(websocket, user_text, session_id)

                # 错误处理
                elif event_type == "error":
                    logger.error(f"OpenAI Realtime API error: {evt}")
                    await send_event(websocket, "error", {
                        "code": "openai_error",
                        "message": f"OpenAI Realtime API error: {json.dumps(evt)}"
                    })

        except websockets.exceptions.ConnectionClosedError:
            logger.info("OpenAI Realtime API connection closed")
        except Exception as e:
            logger.error(f"Error handling OpenAI events: {e}", exc_info=True)
        finally:
            # 清理
            session = self.session_manager.get_session(session_id)
            if session:
                session["openai_task"] = None
                session["openai_ws"] = None
