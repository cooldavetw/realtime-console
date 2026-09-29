import json
import logging
import base64
import wave
from io import BytesIO
from typing import Dict, Any

logger = logging.getLogger(__name__)

def generate_id(prefix: str = "") -> str:
    """生成唯一ID"""
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:10]}"

async def send_event(websocket, event_type: str, data: Dict[str, Any] = None) -> None:
    """发送事件到客户端"""
    if data is None:
        data = {}

    payload = {
        "type": event_type,
        **data
    }

    # 日志记录 - 对大型音频数据做特殊处理
    log_payload = payload.copy()
    if event_type == "response.audio.delta" and "delta" in log_payload:
        audio_length = len(log_payload["delta"])
        log_payload["delta"] = f"[audio bytes: {audio_length}]"
    elif "data" in log_payload and isinstance(log_payload["data"], str) and len(log_payload["data"]) > 100:
        log_payload["data"] = f"[audio data: {len(log_payload['data'])} chars]"
    elif "audio_bytes" in log_payload:
        audio_length = len(log_payload["audio_bytes"])
        log_payload["audio_bytes"] = f"[audio bytes: {audio_length}]"
    elif "item" in log_payload and isinstance(log_payload["item"], dict):
        item = log_payload["item"].copy()
        if "content" in item and isinstance(item["content"], list):
            for i, content in enumerate(item["content"]):
                if isinstance(content, dict) and content.get("type") == "audio" and "audio_bytes" in content:
                    audio_length = len(content["audio_bytes"])
                    item["content"][i]["audio_bytes"] = f"[audio bytes: {audio_length}]"
        log_payload["item"] = item

    logger.debug(f"Sending event: {event_type} - {json.dumps(log_payload, default=str)}")

    try:
        await websocket.send_text(json.dumps(payload))
    except Exception as e:
        logger.error(f"Error sending event: {e}")

def pcm_bytes_to_wav_bytes(pcm_bytes: bytes, sample_rate: int, channels: int, sampwidth: int) -> bytes:
    """将原始PCM数据转换为WAV格式"""
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()

def extract_transcript_from_event(event: Dict[str, Any]) -> str:
    """从事件中提取转录文本"""
    # 尝试从不同位置获取文本
    transcript = (
            event.get("transcript") or
            event.get("text") or
            (event.get("item", {})
             .get("content", [{}])[0]
             .get("transcript", {}) or {})
            .get("text")
    )

    return transcript or ""
