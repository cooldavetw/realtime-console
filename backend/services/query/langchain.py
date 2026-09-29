import os
import logging
from typing import Dict, Any
import asyncio

from backend.services.query.base import QueryProvider

logger = logging.getLogger(__name__)

class LangChainQueryProvider:
    """LangChain 查询提供商"""

    @staticmethod
    async def query(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用 LangChain 查询"""
        try:
            # 这需要 langchain 包
            # pip install langchain langchain-openai
            from langchain.chains import LLMChain
            from langchain.prompts import PromptTemplate
            from langchain_openai import ChatOpenAI

            # 获取配置
            query_config = config.get("query_config", {})
            api_key = query_config.get("api_key", os.getenv("OPENAI_API_KEY"))
            model_name = query_config.get("model", "gpt-4")
            template = query_config.get("template", "你是一个有帮助的助手。问题: {question}\n回答:")
            temperature = query_config.get("temperature", 0.7)

            if not api_key:
                raise ValueError("LangChain with OpenAI requires api_key")

            # 创建 LLM
            llm = ChatOpenAI(
                model=model_name,
                openai_api_key=api_key,
                temperature=temperature
            )

            # 创建提示模板
            prompt = PromptTemplate(
                input_variables=["question"],
                template=template
            )

            # 创建链
            chain = LLMChain(llm=llm, prompt=prompt)

            logger.info(f"Sending LangChain query with model {model_name}")

            # 运行链
            start_time = asyncio.get_event_loop().time()
            result = await chain.ainvoke({"question": text})
            elapsed_time = asyncio.get_event_loop().time() - start_time

            logger.info(f"LangChain response received in {elapsed_time:.2f}s")

            # 提取响应文本
            reply = result.get("text", "")
            return reply
        except Exception as e:
            logger.error(f"LangChain query failed: {e}", exc_info=True)
            raise
