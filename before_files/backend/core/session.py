import uuid
import asyncio
import logging
from typing import Dict, Any, Optional

from core.utils import send_event, generate_id
from core.conversation_store import ConversationStore

logger = logging.getLogger(__name__)

class SessionManager:
    """管理用户会话状态"""

    def __init__(self):
        self.sessions = {}
        self.conversation_store = ConversationStore()

    def create_session(self, config: Dict[str, Any] = None) -> str:
        """创建新会话"""
        session_id = generate_id("sess")

        # 设置默认配置
        from config.settings import get_config

        default_config = {
            "mode": "push_to_talk",
            "stt_provider": "openai",
            "stt_config": {
                "model": "gpt-4o-transcribe"
            },
            "tts_provider": "openai",
            "tts_config": {
                "model": "gpt-4o-mini-tts",
                "voice": "alloy",
                "response_format": "wav"
            },
            "query_provider": "flowise",
            "query_config": {
                "api_url": get_config("FLOWISE_API_URL"),
                "api_key": get_config("FLOWISE_API_KEY"),
                "chatflow_id": get_config("FLOWISE_CHATFLOW_ID", "")
            },
            "vad_config": {
                "threshold": 0.5,
                "silence_duration_ms": 500,
                "prefix_padding_ms": 300
            }
        }

        # 合并用户配置
        if config:
            self._merge_config(default_config, config)

        # 创建会话状态
        self.sessions[session_id] = {
            "config": default_config,
            "audio_buffer": bytearray(),
            "active_response": None,
            "openai_ws": None,
            "openai_task": None,
            "id": None
        }

        # 保存到持久化存储
        self.conversation_store.create_session(session_id, default_config)

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话状态"""
        return self.sessions.get(session_id)

    def update_session(self, session_id: str, config: Dict[str, Any]) -> bool:
        """更新会话配置"""
        session = self.get_session(session_id)
        if not session:
            return False

        self._merge_config(session["config"], config)

        # 更新持久化存储
        self.conversation_store.update_session(session_id, config)

        return True

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self.sessions:
            # 清理资源
            session = self.sessions[session_id]
            if session.get("openai_task"):
                session["openai_task"].cancel()
            if session.get("openai_ws"):
                asyncio.create_task(session["openai_ws"].close())

            del self.sessions[session_id]

            # 从持久化存储中删除
            self.conversation_store.delete_conversation(session_id)

            return True
        return False

    def add_conversation_item(self, item_id: str, session_id: str, role: str,
                              type_name: Optional[str] = None, content: Optional[Dict[str, Any]] = None,
                              websocket=None) -> None:
        """添加对话记录项并发送 conversation.updated 事件"""
        # 获取当前会话的所有会话项
        previous_items = self.conversation_store.get_conversation_items(session_id)
        previous_record = next((item for item in previous_items if item["item_id"] == item_id), None)

        # 添加到数据库
        self.conversation_store.add_conversation_item(item_id, session_id, role, type_name, content)

        # 计算 delta（差异部分）
        delta = {}
        if previous_record:
            # 如果记录已经存在，则计算变化部分
            for key, value in content.items():
                if previous_record["content"].get(key) != value:
                    delta[key] = value
        else:
            # 如果是新增项，整个内容都是 delta
            delta = content

        # 如果 websocket 存在，则发送 conversation.updated 事件
        if websocket:
            asyncio.create_task(send_event(websocket, "conversation.updated", {
                "session_id": session_id,
                "item": {
                    "id": item_id,
                    "role": role,
                    "type": type_name,
                    "content": content
                },
                "delta": delta
            }))


    def get_conversation_items(self, session_id: str) -> list:
        """获取会话的所有对话项"""
        return self.conversation_store.get_conversation_items(session_id)

    def _merge_config(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """递归合并配置"""
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._merge_config(target[key], value)
            else:
                target[key] = value

    def _merge_config(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """递归合并配置"""
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._merge_config(target[key], value)
            else:
                target[key] = value
