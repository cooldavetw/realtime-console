import unittest
import asyncio
import websockets
import json
import base64
import os
from pathlib import Path

class TestServer(unittest.TestCase):
    """WebSocket 服务器集成测试"""

    def setUp(self):
        # 加载环境变量
        from dotenv import load_dotenv
        load_dotenv()

        # 测试音频
        test_audio_path = Path(__file__).parent / "resources" / "test_audio.wav"
        if test_audio_path.exists():
            with open(test_audio_path, "rb") as f:
                self.test_audio = f.read()
        else:
            self.test_audio = None

        # 服务器 URL
        self.server_url = "ws://localhost:8000"

    async def connect_and_test(self):
        """连接到服务器并进行测试"""
        if not self.test_audio:
            self.skipTest("Test audio file not found")

        try:
            # 连接到服务器
            async with websockets.connect(self.server_url) as websocket:
                # 等待会话创建事件
                response = await websocket.recv()
                data = json.loads(response)
                self.assertEqual(data["type"], "session.created")

                # 创建推送对讲模式会话
                await websocket.send(json.dumps({
                    "type": "session.create",
                    "config": {
                        "mode": "push_to_talk",
                        "stt_provider": "openai",
                        "tts_provider": "openai"
                    }
                }))

                # 接收会话创建响应
                response = await websocket.recv()
                data = json.loads(response)
                self.assertEqual(data["type"], "session.created")

                # 发送音频块
                audio_b64 = base64.b64encode(self.test_audio).decode("utf-8")
                await websocket.send(json.dumps({
                    "type": "audio.chunk",
                    "format": "wav",
                    "data": audio_b64
                }))

                # 发送音频完成
                await websocket.send(json.dumps({
                    "type": "audio.done"
                }))

                # 接收音频提交事件
                response = await websocket.recv()
                data = json.loads(response)
                self.assertEqual(data["type"], "audio.committed")

                # 接收转录事件
                response = await websocket.recv()
                data = json.loads(response)
                self.assertEqual(data["type"], "transcript.created")

                # 接收查询发送事件
                response = await websocket.recv()
                data = json.loads(response)
                self.assertEqual(data["type"], "query.sent")

                # 接收响应创建事件
                response = await websocket.recv()
                data = json.loads(response)
                self.assertEqual(data["type"], "response.created")

                # 接收音频开始事件
                response = await websocket.recv()
                data = json.loads(response)
                self.assertEqual(data["type"], "audio.started")

                # 接收音频块事件
                response = await websocket.recv()
                data = json.loads(response)
                self.assertEqual(data["type"], "audio.chunk")

                # 接收音频完成事件
                response = await websocket.recv()
                data = json.loads(response)
                self.assertEqual(data["type"], "audio.completed")

        except (ConnectionRefusedError, websockets.exceptions.WebSocketException):
            self.skipTest("Server not running")

    def test_server_integration(self):
        """测试服务器集成"""
        asyncio.run(self.connect_and_test())

if __name__ == "__main__":
    unittest.main()
