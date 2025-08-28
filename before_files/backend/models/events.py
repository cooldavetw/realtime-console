from enum import Enum
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field

class EventType(str, Enum):
    # 客户端事件
    SESSION_CREATE = "session.create"
    AUDIO_CHUNK = "audio.chunk"
    AUDIO_DONE = "audio.done"
    AUDIO_CLEAR = "audio.clear"
    QUERY_CUSTOM = "query.custom"
    RESPONSE_CANCEL = "response.cancel"

    # 服务器事件
    SESSION_CREATED = "session.created"
    VAD_SPEECH_STARTED = "vad.speech_started"
    VAD_SPEECH_STOPPED = "vad.speech_stopped"
    AUDIO_COMMITTED = "audio.committed"
    TRANSCRIPT_CREATED = "transcript.created"
    QUERY_SENT = "query.sent"
    RESPONSE_CREATED = "response.created"
    AUDIO_STARTED = "audio.started"
    AUDIO_CHUNK_RESPONSE = "audio.chunk"
    AUDIO_COMPLETED = "audio.completed"
    ERROR = "error"
    AUDIO_CLEARED = "audio.cleared"
    RESPONSE_CANCELLED = "response.cancelled"

class AudioContent(BaseModel):
    type: str = "audio"
    audio_bytes: bytes

class TextContent(BaseModel):
    type: str = "text"
    text: str

class AudioChunkEvent(BaseModel):
    type: str = EventType.AUDIO_CHUNK
    format: str = "pcm16"
    data: str  # base64 encoded audio data

class SessionCreateEvent(BaseModel):
    type: str = EventType.SESSION_CREATE
    config: Dict[str, Any]

class AudioDoneEvent(BaseModel):
    type: str = EventType.AUDIO_DONE

class AudioClearEvent(BaseModel):
    type: str = EventType.AUDIO_CLEAR

class QueryCustomEvent(BaseModel):
    type: str = EventType.QUERY_CUSTOM
    text: str

class ResponseCancelEvent(BaseModel):
    type: str = EventType.RESPONSE_CANCEL

class SessionCreatedEvent(BaseModel):
    type: str = EventType.SESSION_CREATED
    session_id: str
    config: Dict[str, Any]

class VADSpeechStartedEvent(BaseModel):
    type: str = EventType.VAD_SPEECH_STARTED

class VADSpeechStoppedEvent(BaseModel):
    type: str = EventType.VAD_SPEECH_STOPPED

class AudioCommittedEvent(BaseModel):
    type: str = EventType.AUDIO_COMMITTED
    audio_id: str

class TranscriptCreatedEvent(BaseModel):
    type: str = EventType.TRANSCRIPT_CREATED
    audio_id: str
    text: str

class QuerySentEvent(BaseModel):
    type: str = EventType.QUERY_SENT
    query_id: str
    text: str

class ResponseCreatedEvent(BaseModel):
    type: str = EventType.RESPONSE_CREATED
    response_id: str
    text: str

class AudioStartedEvent(BaseModel):
    type: str = EventType.AUDIO_STARTED
    response_id: str

class AudioChunkResponseEvent(BaseModel):
    type: str = EventType.AUDIO_CHUNK_RESPONSE
    response_id: str
    format: str
    data: str  # base64 encoded audio data

class AudioCompletedEvent(BaseModel):
    type: str = EventType.AUDIO_COMPLETED
    response_id: str

class ErrorEvent(BaseModel):
    type: str = EventType.ERROR
    code: str
    message: str

class AudioClearedEvent(BaseModel):
    type: str = EventType.AUDIO_CLEARED

class ResponseCancelledEvent(BaseModel):
    type: str = EventType.RESPONSE_CANCELLED
    response_id: str

# 合并所有客户端事件类型
ClientEvent = Union[
    SessionCreateEvent,
    AudioChunkEvent,
    AudioDoneEvent,
    AudioClearEvent,
    QueryCustomEvent,
    ResponseCancelEvent
]

# 合并所有服务器事件类型
ServerEvent = Union[
    SessionCreatedEvent,
    VADSpeechStartedEvent,
    VADSpeechStoppedEvent,
    AudioCommittedEvent,
    TranscriptCreatedEvent,
    QuerySentEvent,
    ResponseCreatedEvent,
    AudioStartedEvent,
    AudioChunkResponseEvent,
    AudioCompletedEvent,
    ErrorEvent,
    AudioClearedEvent,
    ResponseCancelledEvent
]
