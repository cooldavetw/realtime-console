import os
import logging
import requests
from typing import Dict, Any
import asyncio

from services.query.base import QueryProvider

logger = logging.getLogger(__name__)

class OllamaQueryProvider:
    """Ollama 查询提供商"""

    @staticmethod
    async def query(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用 Ollama API 查询"""
        try:
            # 获取配置
            query_config = config.get("query_config", {})
            base_url = query_config.get("base_url", "http://localhost:11434")
            model = query_config.get("model", "llama2")
            system = query_config.get("system", "你是一个有帮助的助手。")

            # API 端点
            api_url = f"{base_url}/api/generate"

            # 构建请求体
            payload = {
                "model": model,
                "prompt": text,
                "system": system,
                "stream": False
            }

            logger.info(f"Sending Ollama query to model {model}")

            # 发送请求
            start_time = asyncio.get_event_loop().time()
            response = requests.post(api_url, json=payload)
            elapsed_time = asyncio.get_event_loop().time() - start_time

            # 请求失败
            response.raise_for_status()

            # 解析响应
            result = response.json()

            logger.info(f"Ollama response received in {elapsed_time:.2f}s")

            # 提取响应文本
            reply = result.get("response", "")
            return reply
        except Exception as e:
            logger.error(f"Ollama query failed: {e}", exc_info=True)
            raise
