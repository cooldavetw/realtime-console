import os
import logging
import json
import requests
from typing import Dict, Any
import asyncio

from services.query.base import QueryProvider

logger = logging.getLogger(__name__)

class CustomAPIQueryProvider:
    """自定义 API 查询提供商"""

    @staticmethod
    async def query(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用自定义 API 查询"""
        try:
            # 获取配置
            query_config = config.get("query_config", {})
            api_url = query_config.get("api_url")
            method = query_config.get("method", "POST")
            headers = query_config.get("headers", {})
            auth_token = query_config.get("auth_token")

            if not api_url:
                raise ValueError("Custom API query requires api_url")

            if auth_token and "Authorization" not in headers:
                headers["Authorization"] = f"Bearer {auth_token}"

            # 获取请求体模板和响应解析路径
            body_template = query_config.get("body_template", '{"query": "${query}"}')
            response_path = query_config.get("response_path", "")

            # 替换模板中的查询
            body = body_template.replace("${query}", text)
            if body.startswith("{"):
                try:
                    body = json.loads(body)
                    headers["Content-Type"] = "application/json"
                except:
                    pass

            logger.info(f"Sending custom API query to {api_url}")

            # 发送请求
            start_time = asyncio.get_event_loop().time()
            if method.upper() == "POST":
                if isinstance(body, dict):
                    response = requests.post(api_url, json=body, headers=headers)
                else:
                    response = requests.post(api_url, data=body, headers=headers)
            elif method.upper() == "GET":
                response = requests.get(api_url, params={"query": text}, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            elapsed_time = asyncio.get_event_loop().time() - start_time

            # 请求失败
            response.raise_for_status()

            logger.info(f"Custom API response received in {elapsed_time:.2f}s")

            # 解析响应
            if response.headers.get("Content-Type", "").startswith("application/json"):
                result = response.json()

                # 如果指定了响应路径，尝试提取
                if response_path:
                    paths = response_path.split(".")
                    for path in paths:
                        if isinstance(result, dict) and path in result:
                            result = result[path]
                        else:
                            break

                if isinstance(result, (dict, list)):
                    return json.dumps(result)
                else:
                    return str(result)
            else:
                return response.text
        except Exception as e:
            logger.error(f"Custom API query failed: {e}", exc_info=True)
            raise
