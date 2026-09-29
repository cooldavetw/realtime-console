import os
import logging
import requests
from typing import Dict, Any
import asyncio

from backend.services.query.base import QueryProvider

logger = logging.getLogger(__name__)

class HuggingFaceQueryProvider:
    """Hugging Face 查询提供商"""

    @staticmethod
    async def query(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用 Hugging Face API 查询"""
        try:
            # 获取配置
            query_config = config.get("query_config", {})
            api_key = query_config.get("api_key", os.getenv("HF_API_KEY"))
            model_id = query_config.get("model_id", "meta-llama/Llama-2-70b-chat-hf")

            if not api_key:
                raise ValueError("Hugging Face query requires api_key")

            # 构建 API URL
            api_url = f"https://api-inference.huggingface.co/models/{model_id}"

            # 构建请求头
            headers = {"Authorization": f"Bearer {api_key}"}

            # 构建请求体
            payload = {"inputs": text}

            logger.info(f"Sending Hugging Face query to model {model_id}")

            # 发送请求
            start_time = asyncio.get_event_loop().time()
            response = requests.post(api_url, headers=headers, json=payload)
            elapsed_time = asyncio.get_event_loop().time() - start_time

            # 请求失败
            response.raise_for_status()

            logger.info(f"Hugging Face response received in {elapsed_time:.2f}s")

            # 解析响应
            result = response.json()

            # Hugging Face 根据模型返回不同格式
            if isinstance(result, list) and result:
                if isinstance(result[0], dict) and "generated_text" in result[0]:
                    return result[0]["generated_text"]
                elif isinstance(result[0], str):
                    return result[0]

            # 如果无法解析，返回原始响应
            return str(result)
        except Exception as e:
            logger.error(f"Hugging Face query failed: {e}", exc_info=True)
            raise
