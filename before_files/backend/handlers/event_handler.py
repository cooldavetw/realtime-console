import json
import logging
import base64
import os
from typing import Dict, Any

from core.session import SessionManager
from core.utils import send_event, generate_id
from services.stt.base import STTProvider
from services.tts.base import TTSProvider
from services.query.base import QueryProvider

logger = logging.getLogger(__name__)

class EventHandler:
    """处理客户端事件"""

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def process_event(self, websocket, event: Dict[str, Any], session_id: str):
        """处理客户端事件"""
        event_type = event.get("type")

        if not event_type:
            await send_event(websocket, "error", {
                "code": "missing_event_type",
                "message": "Missing event type"
            })
            return

        logger.info(f"Received event: {event_type}")
        session = self.session_manager.get_session(session_id)

        if not session:
            await send_event(websocket, "error", {
                "code": "session_not_found",
                "message": "Session not found"
            })
            return

        # 事件处理
        if event_type == "session.create":
            await self._handle_session_create(websocket, event, session_id)

        elif event_type == "session.update":
            await self._handle_session_update(websocket, event, session_id)

        elif event_type == "audio.chunk":
            await self._handle_audio_chunk(websocket, event, session_id)

        elif event_type == "audio.done":
            await self._handle_audio_done(websocket, event, session_id)

        elif event_type == "audio.clear":
            await self._handle_audio_clear(websocket, event, session_id)

        elif event_type == "query.custom":
            await self._handle_query_custom(websocket, event, session_id)

        elif event_type == "response.create":
            await self._handle_response_create(websocket, event, session_id)
        elif event_type == "response.cancel":
            await self._handle_response_cancel(websocket, event, session_id)

        else:
            await send_event(websocket, "error", {
                "code": "unknown_event",
                "message": f"Unknown event type: {event_type}"
            })

    async def _handle_session_create(self, websocket, event, session_id):
        """处理 session.create 事件"""
        config = event.get("config", {})
        old_mode = self.session_manager.get_session(session_id)["config"]["mode"]

        # 更新配置
        self.session_manager.update_session(session_id, config)
        session = self.session_manager.get_session(session_id)
        new_mode = session["config"]["mode"]

        # 如果模式发生变化，需要处理VAD连接
        if old_mode != new_mode:
            from handlers.audio_handler import AudioHandler
            audio_handler = AudioHandler(self.session_manager)

            if new_mode == "vad":
                await audio_handler.setup_vad_mode(websocket, session_id)
            elif old_mode == "vad" and new_mode == "push_to_talk":
                # 关闭 VAD 连接
                if session.get("openai_task"):
                    session["openai_task"].cancel()
                if session.get("openai_ws"):
                    await session["openai_ws"].close()
                    session["openai_ws"] = None

        # 发送会话创建事件
        await send_event(websocket, "session.created", {
            "session_id": session_id,
            "config": session["config"]
        })

    async def _handle_session_update(self, websocket, event, session_id):
        """处理 session.update 事件"""
        config = event.get("config", {})
        old_mode = self.session_manager.get_session(session_id)["config"]["mode"]

        # 更新配置
        self.session_manager.update_session(session_id, config)
        session = self.session_manager.get_session(session_id)
        new_mode = session["config"]["mode"]

        # 如果模式发生变化，需要处理VAD连接
        if old_mode != new_mode:
            from handlers.audio_handler import AudioHandler
            audio_handler = AudioHandler(self.session_manager)

            if new_mode == "vad":
                await audio_handler.setup_vad_mode(websocket, session_id)
            elif old_mode == "vad" and new_mode == "push_to_talk":
                # 关闭 VAD 连接
                if session.get("openai_task"):
                    session["openai_task"].cancel()
                if session.get("openai_ws"):
                    await session["openai_ws"].close()
                    session["openai_ws"] = None

        # 发送会话更新事件
        await send_event(websocket, "session.updated", {
            "session_id": session_id,
            "config": session["config"]
        })

    async def _handle_audio_chunk(self, websocket, event, session_id):
        """处理 audio.chunk 事件"""
        format_type = event.get("format", "pcm16")
        audio_data_b64 = event.get("data")

        if not audio_data_b64:
            await send_event(websocket, "error", {
                "code": "missing_audio_data",
                "message": "Missing audio data"
            })
            return

        try:
            # 解码 base64 音频数据
            audio_data = base64.b64decode(audio_data_b64)

            # 根据模式处理音频
            session = self.session_manager.get_session(session_id)

            if session["config"]["mode"] == "push_to_talk":
                # Push-to-talk 模式：累积音频数据
                session["audio_buffer"].extend(audio_data)

            elif session["config"]["mode"] == "vad":
                # VAD 模式：转发到 OpenAI Realtime API
                from handlers.audio_handler import AudioHandler
                audio_handler = AudioHandler(self.session_manager)
                await audio_handler.forward_to_vad(websocket, audio_data, session_id)

                # 检查是否需要发送 conversation.interrupted 事件
                if len(audio_data) == 0:  # 假设 0 数据长度可以表示中断
                    await send_event(websocket, "conversation.interrupted", {
                        "session_id": session_id,
                        "response_id": None  # VAD 中断可能没有具体的 response_id
                    })

        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}", exc_info=True)
            await send_event(websocket, "error", {
                "code": "audio_processing_error",
                "message": f"Error processing audio: {e}"
            })

    async def _handle_audio_done(self, websocket, event, session_id):
        """处理 audio.done 事件"""
        # 仅在 Push-to-talk 模式处理
        session = self.session_manager.get_session(session_id)

        if session["config"]["mode"] == "push_to_talk":
            if not session["audio_buffer"]:
                await send_event(websocket, "error", {
                    "code": "empty_audio",
                    "message": "No audio received before done"
                })
                return

            # 处理完整音频
            from config.settings import get_config
            from core.utils import pcm_bytes_to_wav_bytes

            audio_id = generate_id("audio")

            # 发送音频已提交事件
            await send_event(websocket, "audio.committed", {
                "audio_id": audio_id
            })

            # 处理音频数据
            audio_data = bytes(session["audio_buffer"])

            # 创建 WAV
            wav_bytes = pcm_bytes_to_wav_bytes(
                audio_data,
                sample_rate=get_config("PCM_SAMPLE_RATE"),
                channels=get_config("PCM_CHANNELS"),
                sampwidth=get_config("PCM_SAMPWIDTH"),
            )

            try:
                # 转录音频
                stt_provider = await STTProvider.get_provider(session["config"])
                text = await stt_provider.transcribe(wav_bytes, session["config"])

                # 记录用户音频转录到对话历史
                self.session_manager.add_conversation_item(
                    audio_id,
                    session_id,
                    "user",
                    "audio_transcript",
                    {"transcript": text, "audio_id": audio_id},
                    websocket=websocket
                )

                # 发送转录结果
                await send_event(websocket, "transcript.created", {
                    "audio_id": audio_id,
                    "text": text
                })

                # 查询后端
                await self._process_query(websocket, text, session_id)

                # 清空音频缓冲区
                session["audio_buffer"].clear()

            except Exception as e:
                logger.error(f"Error processing audio: {e}", exc_info=True)
                await send_event(websocket, "error", {
                    "code": "processing_error",
                    "message": f"Error processing audio: {e}"
                })
                session["audio_buffer"].clear()

    async def _handle_audio_clear(self, websocket, event, session_id):
        """处理 audio.clear 事件"""
        session = self.session_manager.get_session(session_id)
        # 清除音频缓冲区
        session["audio_buffer"].clear()
        session["id"] = None

        # VAD 模式：发送清除命令到 OpenAI
        if session["config"]["mode"] == "vad" and session.get("openai_ws"):
            clear_evt = {
                "type": "input_audio_buffer.clear"
            }
            await session["openai_ws"].send(json.dumps(clear_evt))

        await send_event(websocket, "audio.cleared", {})

    async def _handle_query_custom(self, websocket, event, session_id):
        """处理 query.custom 事件"""
        text = event.get("text")
        if not text:
            await send_event(websocket, "error", {
                "code": "missing_text",
                "message": "Missing query text"
            })
            return

        await self._process_query(websocket, text, session_id)

    async def _handle_response_create(self, websocket, event, session_id):
        """处理 response.create 事件"""
        session = self.session_manager.get_session(session_id)

        if not session:
            await send_event(websocket, "error", {
                "code": "session_not_found",
                "message": "Session not found"
            })
            return

        # 检查音频缓冲区是否有数据
        audio_buffer = session.get("audio_buffer", bytearray())
        if not audio_buffer:
            await send_event(websocket, "error", {
                "code": "empty_audio_buffer",
                "message": "No audio data in buffer to process"
            })
            return

        # 创建响应ID
        response_id = generate_id("resp")


        try:

            # 将音频数据转为 WAV 格式
            from core.utils import pcm_bytes_to_wav_bytes
            from config.settings import get_config

            wav_bytes = pcm_bytes_to_wav_bytes(
                audio_buffer,
                sample_rate=get_config("PCM_SAMPLE_RATE", 16000),
                channels=get_config("PCM_CHANNELS", 1),
                sampwidth=get_config("PCM_SAMPWIDTH", 2)
            )

            # 使用 STTProvider 转录音频
            stt_provider = await STTProvider.get_provider(session["config"])
            transcription = await stt_provider.transcribe(wav_bytes, session["config"])


            # 更新会话历史，记录转录文本
            transcription_id = generate_id("transcript")

            # 发送转录结果
            await send_event(websocket, "transcript.created", {
                "session_id": session_id,
                "audio_id": transcription_id,
                "text": transcription
            })

            self.session_manager.add_conversation_item(
                transcription_id,
                session_id,
                role="user",
                type_name="audio_transcript",
                content={"transcript": transcription},
                websocket=websocket
            )

            # 清空音频缓冲区
            session["audio_buffer"].clear()

            # 查询后端
            query_provider = await QueryProvider.get_provider(session["config"])
            reply = await query_provider.query(transcription, session["config"], session_id)

            # 使用 TTSProvider 合成音频
            tts_provider = await TTSProvider.get_provider(session["config"])
            audio_bytes = await tts_provider.synthesize(reply, session["config"])

            # 将生成的音频转为 base64
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

            # 保存活动响应
            session["active_response"] = {
                "id": response_id,
                "text": reply
            }

            # 将响应文本或状态更新到对话历史
            self.session_manager.add_conversation_item(
                response_id,
                session_id,
                role="assistant",
                type_name="text",
                content={"text": reply, "audio": audio_base64},
                websocket=websocket
            )

            # 发送响应已创建事件
            await send_event(websocket, "response.created", {
                "response_id": response_id,
                "text": reply,
                "audio": audio_base64
            })

        except Exception as e:
            logging.error(f"Error processing response.create: {str(e)}", exc_info=True)
            await send_event(websocket, "error", {
                "code": "response_create_error",
                "message": f"Error while generating response: {str(e)}"
            })


    async def _handle_response_cancel(self, websocket, event, session_id):
        """处理 response.cancel 事件"""
        session = self.session_manager.get_session(session_id)

        if session["active_response"]:
            response_id = session["active_response"].get("id")

            # 发送对话中断事件
            await send_event(websocket, "conversation.interrupted", {
                "session_id": session_id,
                "response_id": response_id
            })

            await send_event(websocket, "response.cancelled", {
                "response_id": response_id
            })

            session["active_response"] = None
        else:
            await send_event(websocket, "error", {
                "code": "no_active_response",
                "message": "No active response to cancel"
            })

    async def _process_query(self, websocket, text, session_id):
        logger.info(f"Processing query: {text}")
        """处理查询流程"""
        # 创建查询 ID
        query_id = generate_id("query")

        # 获取会话
        session = self.session_manager.get_session(session_id)

        try:
            # 查询后端
            query_provider = await QueryProvider.get_provider(session["config"])
            reply = await query_provider.query(text, session["config"], session_id)

            # 创建响应 ID
            response_id = generate_id("resp")

            # 跟踪活动响应
            session["active_response"] = {
                "id": response_id,
                "text": reply
            }

            # 记录助手回复到对话历史
            self.session_manager.add_conversation_item(
                response_id,
                session_id,
                "assistant",
                "text",
                {"text": reply},
                websocket=websocket
            )

            tts_provider = await TTSProvider.get_provider(session["config"])
            audio_bytes = await tts_provider.synthesize(reply, session["config"])
            # 将生成的音频转为 base64
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

            # 发送响应已创建事件
            await send_event(websocket, "response.created", {
                "response_id": response_id,
                "text": reply,
                "audio": audio_base64
            })

            # 发送对话更新事件
            await send_event(websocket, "conversation.updated", {
                "session_id": session_id,
                "item": {
                    "id": response_id,
                    "role": "assistant",
                    "type": "text",
                    "content": {"text": reply}
                },
                "delta": {"text": reply}
            })
        except Exception as e:
            logger.error(f"Query failed: {e}", exc_info=True)
            await send_event(websocket, "error", {
                "code": "query_error",
                "message": f"Query failed: {e}"
            })
