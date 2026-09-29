import logging
import numpy as np
from typing import Dict, Any, Callable, Awaitable

from backend.services.vad.base import VADProvider

logger = logging.getLogger(__name__)

class LocalVADProvider:
    """本地 VAD 提供商 (使用 Silero VAD)"""

    @staticmethod
    async def setup(config: Dict[str, Any],
                    on_speech_start: Callable[[], Awaitable[None]],
                    on_speech_stop: Callable[[], Awaitable[None]],
                    on_transcription: Callable[[str], Awaitable[None]]) -> Any:
        """设置 VAD 服务，返回连接或会话对象"""
        try:
            # 这需要 torch 和 silero-vad 包
            # pip install torch
            # 然后根据 https://github.com/snakers4/silero-vad 安装 silero-vad
            import torch

            # 获取配置
            vad_config = config.get("vad_config", {})
            threshold = vad_config.get("threshold", 0.5)
            sampling_rate = vad_config.get("sampling_rate", 16000)
            silence_duration_ms = vad_config.get("silence_duration_ms", 500)

            # 加载模型
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False
            )

            # 获取工具函数
            (get_speech_timestamps, save_audio, read_audio,
             VADIterator, collect_chunks) = utils

            # 创建 VAD 迭代器
            vad_iterator = VADIterator(model, threshold=threshold, sampling_rate=sampling_rate)

            # 返回会话对象
            return {
                "vad_iterator": vad_iterator,
                "speech_detected": False,
                "buffer": [],
                "silence_samples": int(silence_duration_ms * sampling_rate / 1000),
                "silent_samples_count": 0,
                "on_speech_start": on_speech_start,
                "on_speech_stop": on_speech_stop,
                "on_transcription": on_transcription,
                "sampling_rate": sampling_rate
            }

        except Exception as e:
            logger.error(f"Failed to setup local VAD: {e}", exc_info=True)
            raise

    @staticmethod
    async def process_audio(session: Any, audio_data: bytes) -> None:
        """处理音频数据"""
        try:
            if not session:
                raise ValueError("Invalid VAD session")

            # 将字节转换为整数数组
            import numpy as np
            audio_int16 = np.frombuffer(audio_data, dtype=np.int16)

            # 转换为浮点数并归一化
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            # 获取会话状态
            vad_iterator = session["vad_iterator"]
            speech_detected = session["speech_detected"]
            buffer = session["buffer"]
            silence_samples = session["silence_samples"]
            silent_samples_count = session["silent_samples_count"]

            # 处理音频
            for chunk in np.array_split(audio_float32, max(1, len(audio_float32) // 512)):
                # 将音频添加到缓冲区
                buffer.append(chunk)

                # 检查 VAD
                speech_prob = vad_iterator(chunk)

                if speech_prob > 0.5 and not speech_detected:
                    # 检测到语音开始
                    speech_detected = True
                    silent_samples_count = 0
                    await session["on_speech_start"]()

                elif speech_prob <= 0.5 and speech_detected:
                    # 静音增加
                    silent_samples_count += len(chunk)

                    if silent_samples_count >= silence_samples:
                        # 检测到语音结束
                        speech_detected = False
                        silent_samples_count = 0

                        # 调用语音结束回调
                        await session["on_speech_stop"]()

                        # 处理缓冲区中的音频进行转录
                        all_audio = np.concatenate(buffer)

                        # 在实际使用中，这里会调用 STT 服务
                        # 这里只是一个模拟
                        await session["on_transcription"]("(本地 VAD 检测到语音)")

                        # 清空缓冲区
                        buffer.clear()

                else:
                    # 重置静音计数
                    silent_samples_count = 0

            # 更新会话状态
            session["speech_detected"] = speech_detected
            session["buffer"] = buffer
            session["silent_samples_count"] = silent_samples_count

        except Exception as e:
            logger.error(f"Error processing audio in local VAD: {e}", exc_info=True)
            raise

    @staticmethod
    async def close(session: Any) -> None:
        """关闭 VAD 会话"""
        try:
            if session and "vad_iterator" in session:
                # 释放 VAD 迭代器
                session["vad_iterator"].reset_states()

        except Exception as e:
            logger.error(f"Error closing local VAD session: {e}", exc_info=True)
