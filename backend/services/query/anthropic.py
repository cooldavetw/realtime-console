import os
import logging
from typing import Dict, Any
import asyncio

from backend.services.query.base import QueryProvider

logger = logging.getLogger(__name__)

class AnthropicQueryProvider:
    """Anthropic 查询提供商"""

    @staticmethod
    async def query(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用 Anthropic API 查询"""
        try:
            # 这需要 anthropic 包
            # pip install anthropic
            import anthropic

            # 获取配置
            query_config = config.get("query_config", {})
            model = query_config.get("model", "claude-3-opus-20240229")
            system_prompt = query_config.get("system_prompt", "你是 Claude，一个有帮助的 AI 助手。")
            max_tokens = query_config.get("max_tokens", 1024)
            temperature = query_config.get("temperature", 0.7)
            api_key = query_config.get("api_key", os.getenv("ANTHROPIC_API_KEY"))

            # 创建 Anthropic 客户端
            client = anthropic.Anthropic(api_key=api_key)

            logger.info(f"Sending Anthropic query with model {model}")

            # 发送请求
            start_time = asyncio.get_event_loop().time()
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": text}
                ]
            )
            elapsed_time = asyncio.get_event_loop().time() - start_time

            logger.info(f"Anthropic response received in {elapsed_time:.2f}s")

            # 提取响应文本
            reply = message.content[0].text
            return reply
        except Exception as e:
            logger.error(f"Anthropic query failed: {e}", exc_info=True)
            raise
