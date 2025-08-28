
import os
import json
import sqlite3
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ConversationStore:
    """管理对话记录的 SQLite 存储"""

    def __init__(self, db_path: str = "conversations.db"):
        """初始化对话存储

        Args:
            db_path: SQLite 数据库文件路径
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 创建会话表
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS sessions (
                                                               session_id TEXT PRIMARY KEY,
                                                               created_at TEXT NOT NULL,
                                                               updated_at TEXT NOT NULL,
                                                               config TEXT
                       )
                       ''')

        # 创建对话项表
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS conversation_items (
                                                                         item_id TEXT PRIMARY KEY,
                                                                         session_id TEXT NOT NULL,
                                                                         role TEXT NOT NULL,
                                                                         type TEXT,
                                                                         content TEXT,
                                                                         created_at TEXT NOT NULL,
                                                                         FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                           )
                       ''')

        conn.commit()
        conn.close()

    def create_session(self, session_id: str, config: Dict[str, Any]) -> None:
        """创建新会话记录

        Args:
            session_id: 会话 ID
            config: 会话配置
        """
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT OR REPLACE INTO sessions (session_id, created_at, updated_at, config) VALUES (?, ?, ?, ?)",
            (session_id, now, now, json.dumps(config))
        )

        conn.commit()
        conn.close()

    def update_session(self, session_id: str, config: Dict[str, Any]) -> None:
        """更新会话记录

        Args:
            session_id: 会话 ID
            config: 更新的会话配置
        """
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 检查会话是否存在
        cursor.execute("SELECT config FROM sessions WHERE session_id = ?", (session_id,))
        result = cursor.fetchone()

        if result:
            # 更新现有会话
            current_config = json.loads(result[0])
            # 递归合并配置
            self._merge_config(current_config, config)

            cursor.execute(
                "UPDATE sessions SET updated_at = ?, config = ? WHERE session_id = ?",
                (now, json.dumps(current_config), session_id)
            )
        else:
            # 创建新会话
            cursor.execute(
                "INSERT INTO sessions (session_id, created_at, updated_at, config) VALUES (?, ?, ?, ?)",
                (session_id, now, now, json.dumps(config))
            )

        conn.commit()
        conn.close()

    def _merge_config(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """递归合并配置"""
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._merge_config(target[key], value)
            else:
                target[key] = value

    def add_conversation_item(self, item_id: str, session_id: str, role: str,
                              type_name: Optional[str] = None, content: Optional[Dict[str, Any]] = None) -> None:
        """添加对话项

        Args:
            item_id: 对话项 ID
            session_id: 会话 ID
            role: 角色 (user/assistant/system)
            type_name: 项类型
            content: 内容数据
        """
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        content_json = json.dumps(content) if content else None

        cursor.execute(
            "INSERT OR REPLACE INTO conversation_items (item_id, session_id, role, type, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (item_id, session_id, role, type_name, content_json, now)
        )

        conn.commit()
        conn.close()

    def get_conversation_items(self, session_id: str) -> List[Dict[str, Any]]:
        """获取会话的所有对话项

        Args:
            session_id: 会话 ID

        Returns:
            对话项列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM conversation_items WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,)
        )

        items = []
        for row in cursor.fetchall():
            item = dict(row)
            if item["content"]:
                item["content"] = json.loads(item["content"])
            items.append(item)

        conn.close()
        return items

    def delete_conversation(self, session_id: str) -> None:
        """删除会话及其所有对话项

        Args:
            session_id: 会话 ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 删除对话项
        cursor.execute("DELETE FROM conversation_items WHERE session_id = ?", (session_id,))
        # 删除会话
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

        conn.commit()
        conn.close()
