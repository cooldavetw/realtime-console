import os
import logging
from typing import Dict, Any
import asyncio

from backend.services.query.base import QueryProvider

logger = logging.getLogger(__name__)

class LocalAIQueryProvider:
    """LocalAI 查询提供商"""

    @staticmethod
    async def query(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用 LocalAI 查询"""
        try:
            # 获取配置
            query_config = config.get("query_config", {})
            base_url = query_config.get("base_url", "http://localhost:8080/v1")
            model = query_config.get("model", "gpt-3.5-turbo")
            system_prompt = query_config.get("system_prompt", "你是一个有帮助的助手。")
            temperature = query_config.get("temperature", 0.7)
            api_key = query_config.get("api_key", "sk-no-key-required")

            # 创建 OpenAI 客户端指向 LocalAI
            from openai import OpenAI

            client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )

            logger.info(f"Sending LocalAI query with model {model}")

            # 发送请求
            start_time = asyncio.get_event_loop().time()
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=temperature
            )
            elapsed_time = asyncio.get_event_loop().time() - start_time

            logger.info(f"LocalAI response received in {elapsed_time:.2f}s")

            # 提取响应文本
            reply = response.choices[0].message.content
            return reply
        except Exception as e:
            logger.error(f"LocalAI query failed: {e}", exc_info=True)
            raise
