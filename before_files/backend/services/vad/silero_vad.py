import logging
import numpy as np
from typing import Dict, Any, Callable, Awaitable

from services.vad.base import VADProvider

logger = logging.getLogger(__name__)

class SileroVADProvider:
    """Silero VAD 提供商"""

    @staticmethod
    async def setup(config: Dict[str, Any],
                    on_speech_start: Callable[[], Awaitable[None]],
                    on_speech_stop: Callable[[], Awaitable[None]],
                    on_transcription: Callable[[str], Awaitable[None]]) -> Any:
        """
        设置 VAD 服务，返回会话对象
        包括 Silero 模型加载和相关配置
        """
        try:
            # 需要安装 torch 和 silero-vad
            # pip install torch silero-vad
            import torch

            # 从配置提取参数
            vad_config = config.get("vad_config", {})
            threshold = vad_config.get("threshold", 0.5)
            sampling_rate = vad_config.get("sampling_rate", 16000)
            silence_duration_ms = vad_config.get("silence_duration_ms", 500)

            # 加载 Silero VAD 模型与工具函数
            logger.info("Loading Silero VAD model...")
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False
            )

            (get_speech_timestamps, save_audio, read_audio,
             VADIterator, collect_chunks) = utils

            # 创建 VAD 迭代器对象
            vad_iterator = VADIterator(model, threshold=threshold, sampling_rate=sampling_rate)

            # 初始化会话状态
            session = {
                "vad_iterator": vad_iterator,
                "speech_detected": False,
                "buffer": [],
                "silence_samples": int(silence_duration_ms * sampling_rate / 1000),
                "silent_samples_count": 0,
                "on_speech_start": on_speech_start,
                "on_speech_stop": on_speech_stop,
                "on_transcription": on_transcription,
                "sampling_rate": sampling_rate,
            }

            logger.info("Silero VAD setup completed.")
            return session

        except Exception as e:
            logger.error(f"Failed to setup Silero VAD: {e}", exc_info=True)
            raise

    @staticmethod
    async def process_audio(session: Any, audio_data: bytes) -> None:
        """
        处理音频数据，通过 VAD 检测语音活动
        """
        try:
            if not session:
                raise ValueError("Invalid VAD session")

            # 将 byte 数据转成整型数组
            audio_int16 = np.frombuffer(audio_data, dtype=np.int16)

            # 转换为浮点数并归一化
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            # 从会话对象中获取当前状态
            vad_iterator = session["vad_iterator"]
            speech_detected = session["speech_detected"]
            buffer = session["buffer"]
            silence_samples = session["silence_samples"]
            silent_samples_count = session["silent_samples_count"]

            # 分块处理音频数据
            for chunk in np.array_split(audio_float32, max(1, len(audio_float32) // 512)):
                # 添加音频块到缓冲区
                buffer.append(chunk)

                # 检查语音概率
                speech_prob = vad_iterator(chunk)

                if speech_prob > 0.5 and not speech_detected:
                    # 检测到语音开始
                    speech_detected = True
                    silent_samples_count = 0
                    await session["on_speech_start"]()
                    logger.info("Speech detected: START")

                elif speech_prob <= 0.5 and speech_detected:
                    # 静音期间累积计数
                    silent_samples_count += len(chunk)

                    if silent_samples_count >= silence_samples:
                        # 检测到语音结束
                        speech_detected = False
                        silent_samples_count = 0
                        await session["on_speech_stop"]()
                        logger.info("Speech detected: STOP")

                        # 处理缓冲区中的音频（模拟转录）
                        full_audio = np.concatenate(buffer)
                        await session["on_transcription"]("(Silero VAD detected speech)")
                        buffer.clear()

                else:
                    # 如果没有语音，重置静音计数
                    silent_samples_count = 0

            # 更新会话状态
            session["speech_detected"] = speech_detected
            session["buffer"] = buffer
            session["silent_samples_count"] = silent_samples_count

        except Exception as e:
            logger.error(f"Error processing audio with Silero VAD: {e}", exc_info=True)
            raise

    @staticmethod
    async def close(session: Any) -> None:
        """
        释放 VAD 会话相关资源
        """
        try:
            if session and "vad_iterator" in session:
                # 重置 VAD 迭代器
                session["vad_iterator"].reset_states()
                logger.info("Silero VAD session closed.")
        except Exception as e:
            logger.error(f"Error closing Silero VAD session: {e}", exc_info=True)
