import json
import base64
import logging
import asyncio
import websockets
from typing import Dict, Any

from core.session import SessionManager
from handlers.event_handler import EventHandler
from handlers.audio_handler import AudioHandler
from core.utils import send_event

logger = logging.getLogger(__name__)

class WebSocketHandler:
    """处理 WebSocket 连接和事件"""

    def __init__(self):
        self.session_manager = SessionManager()
        self.event_handler = EventHandler(self.session_manager)
        self.audio_handler = AudioHandler(self.session_manager)

    async def handle_client(self, websocket):
        """处理客户端 WebSocket 连接"""
        logger.info("Client connected")

        # 创建默认会话
        session_id = self.session_manager.create_session()
        session = self.session_manager.get_session(session_id)

        # 发送会话创建事件
        await send_event(websocket, "session.created", {
            "session_id": session_id,
            "config": session["config"]
        })

        # 如果是 VAD 模式，连接到 OpenAI Realtime API
        if session["config"]["mode"] == "vad":
            await self.audio_handler.setup_vad_mode(websocket, session_id)

        try:
            async for message in websocket:                
                try:
                    event = json.loads(message)
                    await self.event_handler.process_event(websocket, event, session_id)
                except json.JSONDecodeError:
                    await send_event(websocket, "error", {
                        "code": "invalid_json",
                        "message": "Invalid JSON format"
                    })
        except websockets.exceptions.ConnectionClosedError as e:
            logger.info(f"Client disconnected: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            try:
                await send_event(websocket, "error", {
                    "code": "server_error",
                    "message": f"Unexpected error: {str(e)}"
                })
            except Exception:
                pass
        finally:
            # 清理会话
            self.session_manager.delete_session(session_id)
            logger.info("Connection closed")
