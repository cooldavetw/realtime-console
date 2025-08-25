import asyncio
import websockets
from websockets.server import serve
from io import BytesIO
import base64
import requests
import urllib3
import os
import wave
import sys

from openai import OpenAI

# ---------------- CONFIG ----------------
# Make sure your real key is only in env, not in code.
#   export OPENAI_API_KEY="sk-..."
client = OpenAI()  # uses env

API_URL = os.getenv("API_URL")

#API_URL = "https://192.168.66.24/aibuilder/api/v1/prediction/7b9b4cad-35a2-45c6-8e5e-1b15c07a0b79"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Tell the server what we expect from the client.
# Options:
#   "pcm16" - raw 16-bit PCM mono stream (e.g., from a phone/PBX pipeline)
#   "webm"  - concatenated MediaRecorder chunks (audio/webm;codecs=opus)
AUDIO_INPUT_FORMAT = os.getenv("AUDIO_INPUT_FORMAT", "pcm16").lower()

# If using pcm16, define your capture params:
PCM_SAMPLE_RATE = int(os.getenv("PCM_SAMPLE_RATE", "16000"))  # 16 kHz is common
PCM_CHANNELS    = int(os.getenv("PCM_CHANNELS", "1"))         # mono
PCM_SAMPWIDTH   = 2  # bytes per sample for 16-bit

def query(payload: dict):
    r = requests.post(API_URL, json=payload, verify=False, timeout=30)
    r.raise_for_status()
    return r.json()

def pcm_bytes_to_wav_bytes(pcm_bytes: bytes, sample_rate: int, channels: int, sampwidth: int) -> bytes:
    """Wrap raw PCM into a valid WAV container."""
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()

async def handle_audio(websocket):
    print("Client connected")
    audio_buffer = bytearray()

    try:
        async for message in websocket:
            # Control messages (e.g., DONE)
            if isinstance(message, str):
                if message.strip().upper() == "DONE":
                    print("recive DONE")
                    if not audio_buffer:
                        await websocket.send("ERROR: no audio received before DONE")
                        continue

                    # ---- Build a real audio file ----
                    if AUDIO_INPUT_FORMAT == "pcm16":
                        # Wrap raw PCM into WAV
                        wav_bytes = pcm_bytes_to_wav_bytes(
                            bytes(audio_buffer),
                            sample_rate=PCM_SAMPLE_RATE,
                            channels=PCM_CHANNELS,
                            sampwidth=PCM_SAMPWIDTH,
                        )
                        audio_file = BytesIO(wav_bytes)
                        audio_file.name = "audio.wav"
                    elif AUDIO_INPUT_FORMAT == "webm":
                        # Assume the client sent concatenated MediaRecorder chunks
                        # (first chunk includes EBML header). Just pass through.
                        webm_bytes = bytes(audio_buffer)
                        audio_file = BytesIO(webm_bytes)
                        audio_file.name = "audio.webm"
                    else:
                        await websocket.send(f"ERROR: unsupported AUDIO_INPUT_FORMAT={AUDIO_INPUT_FORMAT}")
                        audio_buffer.clear()
                        continue

                    # ---- TRANSCRIBE ----
                    # Supported: "gpt-4o-transcribe" or "whisper-1"
                    # If you see format issues, try whisper-1 as a sanity check.
                    try:
                        tr = client.audio.transcriptions.create(
                            model="gpt-4o-transcribe",
                            file=audio_file,
                        )
                    except Exception as e:
                        # fallback to whisper-1 for quick format sanity
                        try:
                            audio_file.seek(0)
                            tr = client.audio.transcriptions.create(
                                model="whisper-1",
                                file=audio_file,
                            )
                        except Exception as e2:
                            # surface both errors
                            await websocket.send(f"ERROR: STT failed: {e}\nFallback whisper-1 also failed: {e2}")
                            audio_buffer.clear()
                            continue

                    user_text = getattr(tr, "text", tr)
                    if not user_text:
                        await websocket.send("ERROR: transcription returned empty text")
                        audio_buffer.clear()
                        continue
                    print("user said:", user_text)

                    # ---- RAG / BACKEND ----
                    try:
                        rag = query({"question": user_text})
                        reply = (rag.get("text") or rag.get("answer") or str(rag)).strip()
                    except Exception as e:
                        await websocket.send(f"ERROR: backend query failed: {e}")
                        audio_buffer.clear()
                        continue

                    print("reply:", reply)

                    # ---- TTS ----
                    try:
                        tts = client.audio.speech.create(
                            model="gpt-4o-mini-tts",
                            voice="alloy",
                            input=reply
                        )
                        audio_bytes = getattr(tts, "content", None)
                        if audio_bytes is None and hasattr(tts, "read"):
                            audio_bytes = tts.read()
                        if not audio_bytes:
                            await websocket.send("ERROR: TTS produced no audio")
                        else:
                            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                            await websocket.send(audio_b64)
                    except Exception as e:
                        await websocket.send(f"ERROR: TTS failed: {e}")

                    # Reset for next utterance
                    audio_buffer.clear()
                else:
                    # optional: handle other text commands
                    print("unhandld text commands")
                    pass

            # Binary audio chunk
            elif isinstance(message, (bytes, bytearray, memoryview)):
                print("receive pure audio data")
                audio_buffer.extend(message)
            else:
                print(f"Unknown message type: {type(message)}")

    except websockets.exceptions.ConnectionClosedError as e:
        print(f"Client disconnected (ConnectionClosedError): {e}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            await websocket.send(f"ERROR: {e}")
        except Exception:
            pass
    finally:
        print("Connection closed")

async def main():
    async with serve(
        handle_audio,
        "0.0.0.0",
        8000,
        max_size=10 * 1024 * 1024,
        ping_interval=20,
        ping_timeout=20,
    ):
        print("WebSocket server listening on :8000")
        await asyncio.Future()

if __name__ == "__main__":
    # It helps to be on a recent SDK:
    #   pip install --upgrade openai websockets
    asyncio.run(main())
    