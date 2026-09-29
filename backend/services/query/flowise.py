import os
import json
import logging
import requests
from typing import Dict, Any

from backend.services.query.base import QueryProvider

logger = logging.getLogger(__name__)

class FlowiseQueryProvider:
    """Flowise 查询提供商"""

    @staticmethod
    async def query(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用 Flowise API 查询"""
        try:
            # 获取 API 配置
            query_config = config.get("query_config", {})
            api_url = query_config.get("api_url", os.getenv("FLOWISE_API_URL"))
            api_key = query_config.get("api_key", os.getenv("FLOWISE_API_KEY"))

            # 构建查询负载
            payload = {
                "question": text,
                "streaming": False
            }

            # 如果有会话ID，添加到请求中
            if session_id:
                payload["chatId"] = session_id

            # 添加可选配置
            override_config = query_config.get("override_config")
            if override_config:
                payload["overrideConfig"] = override_config

            # 构建请求头
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            # 记录请求
            logger.info(f"Sending Flowise query to {api_url}: {json.dumps(payload, indent=2)}")

            # 发送请求
            import time
            start_time = time.time()
            r = requests.post(api_url, json=payload, headers=headers, verify=False, timeout=30)
            elapsed_time = time.time() - start_time

            # 请求失败
            r.raise_for_status()

            # 解析响应
            response = r.json()

            # 记录响应
            log_response = response.copy()
            for key, value in log_response.items():
                if isinstance(value, str) and len(value) > 500:
                    log_response[key] = f"[content truncated, length: {len(value)}]"

            logger.info(f"Flowise response received in {elapsed_time:.2f}s: {json.dumps(log_response, indent=2)}")

            # 提取回复文本
            reply = (response.get("text") or response.get("answer") or str(response)).strip()
            return reply
        except Exception as e:
            logger.error(f"Flowise query failed: {e}", exc_info=True)
            raise
