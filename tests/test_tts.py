import unittest
import asyncio
import os

from backend.services.tts.base import TTSProvider

class TestTTS(unittest.TestCase):
    """TTS 服务测试"""

    def setUp(self):
        # 测试文本
        self.test_text = "这是一个测试文本，用于测试文本转语音功能。"

        # 加载环境变量
        from dotenv import load_dotenv
        load_dotenv()

    def test_openai_tts(self):
        """测试 OpenAI TTS"""
        # 检查 API 密钥
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("OPENAI_API_KEY not set")

        config = {
            "tts_provider": "openai",
            "tts_config": {
                "model": "gpt-4o-mini-tts",
                "voice": "alloy"
            }
        }

        async def run_test():
            provider = await TTSProvider.get_provider(config)
            result = await provider.synthesize(self.test_text, config)
            self.assertIsInstance(result, bytes)
            self.assertTrue(len(result) > 0)

            # 保存音频进行手动验证
            import pathlib
            output_dir = pathlib.Path(__file__).parent / "output"
            output_dir.mkdir(exist_ok=True)

            with open(output_dir / "openai_tts_output.mp3", "wb") as f:
                f.write(result)

        asyncio.run(run_test())

    def test_elevenlabs_tts(self):
        """测试 ElevenLabs TTS"""
        # 检查 API 密钥
        if not os.getenv("ELEVENLABS_API_KEY"):
            self.skipTest("ELEVENLABS_API_KEY not set")

        config = {
            "tts_provider": "elevenlabs",
            "tts_config": {
                "api_key": os.getenv("ELEVENLABS_API_KEY"),
                "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Josh 声音
                "model_id": "eleven_multilingual_v2"
            }
        }

        async def run_test():
            provider = await TTSProvider.get_provider(config)
            result = await provider.synthesize(self.test_text, config)
            self.assertIsInstance(result, bytes)
            self.assertTrue(len(result) > 0)

            # 保存音频进行手动验证
            import pathlib
            output_dir = pathlib.Path(__file__).parent / "output"
            output_dir.mkdir(exist_ok=True)

            with open(output_dir / "elevenlabs_tts_output.mp3", "wb") as f:
                f.write(result)

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
