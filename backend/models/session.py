from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class STTConfig(BaseModel):
    model: str = "gpt-4o-transcribe"
    language: Optional[str] = None
    prompt: Optional[str] = None

class TTSConfig(BaseModel):
    model: str = "gpt-4o-mini-tts"
    voice: str = "alloy"
    speed: float = 1.0

class QueryConfig(BaseModel):
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    override_config: Optional[Dict[str, Any]] = None

class VADConfig(BaseModel):
    threshold: float = 0.5
    silence_duration_ms: int = 500
    prefix_padding_ms: int = 300

class SessionConfig(BaseModel):
    mode: str = "push_to_talk"
    stt_provider: str = "openai"
    stt_config: STTConfig = Field(default_factory=STTConfig)
    tts_provider: str = "openai"
    tts_config: TTSConfig = Field(default_factory=TTSConfig)
    query_provider: str = "flowise"
    query_config: QueryConfig = Field(default_factory=QueryConfig)
    vad_config: VADConfig = Field(default_factory=VADConfig)

class SessionState(BaseModel):
    config: SessionConfig
    audio_buffer: bytes = b""
    active_response: Optional[Dict[str, Any]] = None
    openai_ws: Optional[Any] = None
    openai_task: Optional[Any] = None
