import unittest
import asyncio
import os

from services.query.base import QueryProvider

class TestQuery(unittest.TestCase):
    """查询服务测试"""

    def setUp(self):
        # 测试查询
        self.test_query = "请给我介绍一下人工智能的发展历史。"

        # 加载环境变量
        from dotenv import load_dotenv
        load_dotenv()

    def test_flowise_query(self):
        """测试 Flowise 查询"""
        # 检查 API 配置
        if not os.getenv("FLOWISE_API_URL") or not os.getenv("FLOWISE_API_KEY"):
            self.skipTest("Flowise API configuration not set")

        config = {
            "query_provider": "flowise",
            "query_config": {
                "api_url": os.getenv("FLOWISE_API_URL"),
                "api_key": os.getenv("FLOWISE_API_KEY"),
            }
        }

        async def run_test():
            provider = await QueryProvider.get_provider(config)
            result = await provider.query(self.test_query, config, "test_session")
            self.assertIsInstance(result, str)
            self.assertTrue(len(result) > 0)
            print(f"Flowise response: {result[:100]}...")

        asyncio.run(run_test())

    def test_openai_query(self):
        """测试 OpenAI 查询"""
        # 检查 API 密钥
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("OPENAI_API_KEY not set")

        config = {
            "query_provider": "openai",
            "query_config": {
                "model": "gpt-4o",
                "system_prompt": "你是一个有帮助的AI助手。",
                "temperature": 0.7
            }
        }

        async def run_test():
            provider = await QueryProvider.get_provider(config)
            result = await provider.query(self.test_query, config)
            self.assertIsInstance(result, str)
            self.assertTrue(len(result) > 0)
            print(f"OpenAI response: {result[:100]}...")

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
