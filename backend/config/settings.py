import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
from typing import Dict, Any

# 配置存储
CONFIG = {}

def init_config():
    """初始化配置"""
    # 从环境变量加载配置
    load_dotenv(PROJECT_ROOT / ".env")
    CONFIG.update({
        "QUERY_PROVIDER": os.getenv("QUERY_PROVIDER", "pydantic_ai"),
        "AGENT_MODEL": os.getenv("AGENT_MODEL", "openai:gpt-4o"),
        "AGENT_SYSTEM_PROMPT": os.getenv("AGENT_SYSTEM_PROMPT") or (
            "You are a helpful voice assistant. Reply in the user's language. "
            "Keep answers concise and natural when spoken aloud."
        ),
        "AGENT_TIMEOUT": float(os.getenv("AGENT_TIMEOUT", "60")),
        "FLOWISE_API_URL": os.getenv("FLOWISE_API_URL"),
        "FLOWISE_API_KEY": os.getenv("FLOWISE_API_KEY"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),

        # STT配置
        "STT_PROMPT": os.getenv("STT_PROMPT"),

        # 音频配置
        "PCM_SAMPLE_RATE": int(os.getenv("PCM_SAMPLE_RATE", "16000")),
        "PCM_CHANNELS": int(os.getenv("PCM_CHANNELS", "1")),
        "PCM_SAMPWIDTH": 2,  # 16-bit PCM

        # 服务器配置
        "HOST": os.getenv("HOST", "0.0.0.0"),
        "PORT": int(os.getenv("PORT", "8000")),
        "MAX_MESSAGE_SIZE": 10 * 1024 * 1024,
        "PING_INTERVAL": 20,
        "PING_TIMEOUT": 20,

        # OpenAI Realtime API 配置
        "OPENAI_REALTIME_MODEL": os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview-2024-10-01"),
        "OPENAI_BETA_HEADER": "realtime=v1"
    })

    # 构建 Realtime URL
    CONFIG["OPENAI_REALTIME_URL"] = f"wss://api.openai.com/v1/realtime?model={CONFIG['OPENAI_REALTIME_MODEL']}"

def get_config(key: str = None, default: Any = None) -> Any:
    """获取配置值"""
    if key is None:
        return CONFIG
    return CONFIG.get(key, default)
