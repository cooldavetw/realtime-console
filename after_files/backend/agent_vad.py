import os
import json
import base64
import asyncio
from io import BytesIO
import wave
import urllib3
import requests
import websockets
from websockets.server import serve
from websockets.exceptions import ConnectionClosedError
from openai import OpenAI

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------- CONFIG ----------
client = OpenAI()  # uses OPENAI_API_KEY from env
API_URL = os.getenv("API_URL")  # your RAG HTTP endpoint
AUDIO_INPUT_FORMAT = os.getenv("AUDIO_INPUT_FORMAT", "pcm16").lower()

# PCM capture parameters (from your original)
PCM_SAMPLE_RATE = int(os.getenv("PCM_SAMPLE_RATE", "16000"))
PCM_CHANNELS    = int(os.getenv("PCM_CHANNELS", "1"))
PCM_SAMPWIDTH   = 2  # 16-bit PCM

# Realtime model & endpoint
OPENAI_REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17")
OPENAI_REALTIME_URL = f"wss://api.openai.com/v1/realtime?model={OPENAI_REALTIME_MODEL}"
OPENAI_BETA_HEADER = "realtime=v1"  # required per docs

# If you want the exact label from your snippet, change to "transcription_session.update"
SESSION_UPDATE_EVENT_TYPE = os.getenv("SESSION_UPDATE_EVENT_TYPE", "session.update")

def query_backend(payload: dict):
    r = requests.post(API_URL, json=payload, verify=False, timeout=30)
    r.raise_for_status()
    return r.json()

def pcm_bytes_to_wav_bytes(pcm_bytes: bytes, sample_rate: int, channels: int, sampwidth: int) -> bytes:
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()

async def handle_audio(websocket):
    """
    - Bridges client <-> OpenAI Realtime (server VAD).
    - Client sends ONLY raw audio frames (bytes). No "DONE".
    - We forward frames to OpenAI via input_audio_buffer.append.
    - On transcription completion, we do RAG + TTS, then send base64 audio back to the client.
    """
    print("Client connected")

    # Open a WS session to OpenAI Realtime
    try:
        openai_ws = await websockets.connect(
            OPENAI_REALTIME_URL,
            extra_headers={
                "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                "OpenAI-Beta": OPENAI_BETA_HEADER,
            },
            max_size=10 * 1024 * 1024,
            ping_interval=20,
            ping_timeout=20,
        )
    except Exception as e:
        await websocket.send(f"ERROR: cannot connect to OpenAI Realtime: {e}")
        return

    # ----- Configure session: transcription + server VAD -----
    # Matches your provided structure (language/prompt are optional)
    session_update = {
        "type": SESSION_UPDATE_EVENT_TYPE,  # "session.update" (or "transcription_session.update" if your stack expects it)
        "session": {
            "input_audio_format": "pcm16",  # your snippet uses a simple string
            "input_audio_transcription": {
                "model": "gpt-4o-transcribe",
                "prompt": "",
                "language": ""
            },
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500,
                # Optional: keep the server from auto-answering;
                # we want to run our own RAG + TTS flow after transcription
                "create_response": False
            },
            # Ask server to include transcription logprobs if desired
            "include": ["item.input_audio_transcription.logprobs"],
        }
    }

    await openai_ws.send(json.dumps(session_update))

    # ---- State to track ordering (from committed events) ----
    last_committed_item_id = None

    async def openai_event_reader():
        """Read events from OpenAI; when a transcript completes, run RAG + TTS and ship audio back to the client."""
        nonlocal last_committed_item_id

        try:
            async for raw in openai_ws:
                try:
                    evt = json.loads(raw)
                except Exception:
                    # Some events may come as bytes (shouldn't); log and continue
                    print("Non-JSON event from OpenAI:", type(raw))
                    continue

                etype = evt.get("type", "")

                # Useful VAD signals (optional but nice for UX)
                if etype == "input_audio_buffer.speech_started":
                    print("[VAD] speech started")
                elif etype == "input_audio_buffer.speech_stopped":
                    print("[VAD] speech stopped")
                elif etype == "input_audio_buffer.committed":
                    last_committed_item_id = evt.get("item_id")
                    print(f"[VAD] buffer committed -> item_id={last_committed_item_id}, prev={evt.get('previous_item_id')}")

                # Completed transcription for a committed user item
                elif etype == "conversation.item.input_audio_transcription.completed":
                    # The transcript text can be in several shapes; common field:
                    # evt["transcript"] or evt["item"]["content"][0]["transcript"]["text"]
                    user_text = None
                    # Try common spots in case schema varies
                    user_text = (evt.get("transcript")
                                 or evt.get("text")
                                 or (evt.get("item", {}).get("content", [{}])[0].get("transcript", {}) or {}).get("text"))

                    if not user_text:
                        print("Transcription completed event, but text missing:", evt)
                        continue

                    print("USER SAID:", user_text)

                    # ---- RAG / BACKEND ----
                    try:
                        rag = query_backend({"question": user_text})
                        reply = (rag.get("text") or rag.get("answer") or str(rag)).strip()
                    except Exception as e:
                        err = f"ERROR: backend query failed: {e}"
                        print(err)
                        try:
                            await websocket.send(err)
                        except Exception:
                            pass
                        continue

                    print("REPLY:", reply)

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
                            # Send base64 PCM/WAV/MP3 — here you’ll get the model default (usually MP3).
                            # If you specifically want WAV, switch to .speech.with_streaming_response and set format,
                            # or post-process accordingly.
                            b64 = base64.b64encode(audio_bytes).decode("utf-8")
                            await websocket.send(b64)
                    except Exception as e:
                        try:
                            await websocket.send(f"ERROR: TTS failed: {e}")
                        except Exception:
                            pass

                elif etype == "error":
                    # Surface server errors
                    print("OpenAI server error:", evt)
                    try:
                        await websocket.send("ERROR from OpenAI Realtime: " + json.dumps(evt))
                    except Exception:
                        pass

        except ConnectionClosedError:
            print("OpenAI WS closed by server")
        except Exception as e:
            print("OpenAI event reader exception:", e)

    # Start background task to consume OpenAI events
    reader_task = asyncio.create_task(openai_event_reader())

    # ---- Main loop: forward client audio to OpenAI ----
    try:
        async for message in websocket:
            # We only need binary audio from the client now (no control "DONE").
            if isinstance(message, (bytes, bytearray, memoryview)):
                # If input is PCM16, you can send as-is; the Realtime API expects base64-encoded bytes
                # for append events.
                audio_chunk = bytes(message)

                # If your clients send raw PCM16, you can forward directly.
                # (If they send WEBM/OPUS, you can still forward as bytes; the server decodes formats too.)
                audio_b64 = base64.b64encode(audio_chunk).decode("utf-8")

                append_evt = {
                    "type": "input_audio_buffer.append",
                    "audio": audio_b64
                }
                await openai_ws.send(json.dumps(append_evt))

                # NOTE: In server_vad mode, the server commits automatically after end-of-speech.
                # You do NOT need to send input_audio_buffer.commit unless you want manual control.
            else:
                # Optional: accept text commands like "CLEAR" to reset the buffer if desired.
                text = str(message).strip().upper()
                if text == "CLEAR":
                    await openai_ws.send(json.dumps({"type": "input_audio_buffer.clear"}))
                # Ignore other strings (we no longer use DONE)
    except ConnectionClosedError as e:
        print(f"Client disconnected: {e}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            await websocket.send(f"ERROR: {e}")
        except Exception:
            pass
    finally:
        print("Connection closed")
        # Cleanup
        try:
            reader_task.cancel()
        except Exception:
            pass
        try:
            await openai_ws.close()
        except Exception:
            pass

async def main():
    async with serve(
            handle_audio,
            "0.0.0.0",
            8001,
            max_size=10 * 1024 * 1024,
            ping_interval=20,
            ping_timeout=20,
    ):
        print("WebSocket server listening on :8001")
        await asyncio.Future()

if __name__ == "__main__":
    # pip install --upgrade openai websockets requests
    asyncio.run(main())
