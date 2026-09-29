import os
import logging
from typing import Dict, Any
import asyncio

from openai import OpenAI
from backend.services.query.base import QueryProvider

logger = logging.getLogger(__name__)

class OpenAIQueryProvider:
    """OpenAI 查询提供商"""

    @staticmethod
    async def query(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用 OpenAI API 查询"""
        try:
            # 获取配置
            query_config = config.get("query_config", {})
            model = query_config.get("model", "gpt-4o")
            system_prompt = query_config.get("system_prompt", "你是一个有帮助的助手。")
            temperature = query_config.get("temperature", 0.7)
            max_tokens = query_config.get("max_tokens")
            api_key = query_config.get("api_key", os.getenv("OPENAI_API_KEY"))

            # 创建 OpenAI 客户端
            openai_client = OpenAI(api_key=api_key)

            # 构建消息
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]

            # 创建参数
            params = {
                "model": model,
                "messages": messages,
                "temperature": temperature
            }

            if max_tokens:
                params["max_tokens"] = max_tokens

            logger.info(f"Sending OpenAI query with model {model}")

            # 发送请求
            start_time = asyncio.get_event_loop().time()
            response = openai_client.chat.completions.create(**params)
            elapsed_time = asyncio.get_event_loop().time() - start_time

            logger.info(f"OpenAI response received in {elapsed_time:.2f}s")

            # 提取响应文本
            reply = response.choices[0].message.content
            return reply
        except Exception as e:
            logger.error(f"OpenAI query failed: {e}", exc_info=True)
            raise
