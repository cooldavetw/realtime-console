import os
import logging
from typing import Dict, Any
import asyncio

from backend.services.query.base import QueryProvider

logger = logging.getLogger(__name__)

class GoogleAIQueryProvider:
    """Google AI 查询提供商"""

    @staticmethod
    async def query(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用 Google AI API 查询"""
        try:
            # 这需要 google-generativeai 包
            # pip install google-generativeai
            import google.generativeai as genai

            # 获取配置
            query_config = config.get("query_config", {})
            api_key = query_config.get("api_key", os.getenv("GOOGLE_API_KEY"))
            model_name = query_config.get("model", "gemini-pro")
            temperature = query_config.get("temperature", 0.7)

            if not api_key:
                raise ValueError("Google AI query requires api_key")

            # 配置 API
            genai.configure(api_key=api_key)

            # 获取模型
            model = genai.GenerativeModel(model_name=model_name)

            logger.info(f"Sending Google AI query with model {model_name}")

            # 发送请求
            start_time = asyncio.get_event_loop().time()
            response = model.generate_content(
                text,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature
                )
            )
            elapsed_time = asyncio.get_event_loop().time() - start_time

            logger.info(f"Google AI response received in {elapsed_time:.2f}s")

            # 提取响应文本
            reply = response.text
            return reply
        except Exception as e:
            logger.error(f"Google AI query failed: {e}", exc_info=True)
            raise
