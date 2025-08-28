import os
import logging
from typing import Dict, Any
import asyncio

from services.query.base import QueryProvider

logger = logging.getLogger(__name__)

class AzureOpenAIQueryProvider:
    """Azure OpenAI 查询提供商"""

    @staticmethod
    async def query(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用 Azure OpenAI API 查询"""
        try:
            # 获取配置
            query_config = config.get("query_config", {})
            api_key = query_config.get("api_key", os.getenv("AZURE_OPENAI_API_KEY"))
            endpoint = query_config.get("endpoint", os.getenv("AZURE_OPENAI_ENDPOINT"))
            deployment = query_config.get("deployment")
            model = query_config.get("model", "gpt-4")
            system_prompt = query_config.get("system_prompt", "你是一个有帮助的助手。")
            temperature = query_config.get("temperature", 0.7)

            if not api_key or not endpoint:
                raise ValueError("Azure OpenAI requires api_key and endpoint")

            # 创建 Azure OpenAI 客户端
            from openai import AzureOpenAI

            client = AzureOpenAI(
                api_key=api_key,
                azure_endpoint=endpoint,
                api_version="2023-05-15"
            )

            logger.info(f"Sending Azure OpenAI query with deployment {deployment or model}")

            # 发送请求
            start_time = asyncio.get_event_loop().time()
            response = client.chat.completions.create(
                model=deployment or model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=temperature
            )
            elapsed_time = asyncio.get_event_loop().time() - start_time

            logger.info(f"Azure OpenAI response received in {elapsed_time:.2f}s")

            # 提取响应文本
            reply = response.choices[0].message.content
            return reply
        except Exception as e:
            logger.error(f"Azure OpenAI query failed: {e}", exc_info=True)
            raise
