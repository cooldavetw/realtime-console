import unittest
import asyncio
import os
from pathlib import Path

from backend.services.stt.base import STTProvider

class TestSTT(unittest.TestCase):
    """STT 服务测试"""

    def setUp(self):
        # 加载测试音频
        test_audio_path = Path(__file__).parent / "resources" / "test_audio.wav"
        if not test_audio_path.exists():
            self.skipTest("Test audio file not found")

        with open(test_audio_path, "rb") as f:
            self.test_audio = f.read()

        # 加载环境变量
        from dotenv import load_dotenv
        load_dotenv()

    def test_openai_stt(self):
        """测试 OpenAI STT"""
        # 检查 API 密钥
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("OPENAI_API_KEY not set")

        config = {
            "stt_provider": "openai",
            "stt_config": {
                "model": "whisper-1"
            }
        }

        async def run_test():
            provider = await STTProvider.get_provider(config)
            result = await provider.transcribe(self.test_audio, config)
            self.assertIsInstance(result, str)
            self.assertTrue(len(result) > 0)

        asyncio.run(run_test())

    def test_azure_stt(self):
        """测试 Azure STT"""
        # 检查 API 密钥
        if not os.getenv("AZURE_SUBSCRIPTION_KEY") or not os.getenv("AZURE_SERVICE_REGION"):
            self.skipTest("Azure credentials not set")

        config = {
            "stt_provider": "azure",
            "stt_config": {
                "subscription_key": os.getenv("AZURE_SUBSCRIPTION_KEY"),
                "service_region": os.getenv("AZURE_SERVICE_REGION"),
                "language": "en-US"
            }
        }

        async def run_test():
            provider = await STTProvider.get_provider(config)
            result = await provider.transcribe(self.test_audio, config)
            self.assertIsInstance(result, str)
            self.assertTrue(len(result) > 0)

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
