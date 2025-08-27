import asyncio
import json
import base64
import os
import uuid
import logging
from typing import Dict, Any, Optional, Callable, List, Union
from io import BytesIO
import wave
import websockets
from websockets.server import serve
import requests
import urllib3
from openai import OpenAI

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("agent")

# 禁用不安全请求警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ----------------- 配置 -----------------
# 从环境变量获取配置
API_URL = os.getenv("API_URL")

# PCM 音频配置
PCM_SAMPLE_RATE = int(os.getenv("PCM_SAMPLE_RATE", "16000"))
PCM_CHANNELS = int(os.getenv("PCM_CHANNELS", "1"))
PCM_SAMPWIDTH = 2  # 16-bit PCM

# OpenAI Realtime API 配置
OPENAI_REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17")
OPENAI_REALTIME_URL = f"wss://api.openai.com/v1/realtime?model={OPENAI_REALTIME_MODEL}"
OPENAI_BETA_HEADER = "realtime=v1"

# 创建 OpenAI 客户端
client = OpenAI()  # 使用环境变量中的 OPENAI_API_KEY

# ----------------- 工具函数 -----------------

def generate_id(prefix: str = "") -> str:
    """生成唯一ID"""
    return f"{prefix}_{uuid.uuid4().hex[:10]}"

def pcm_bytes_to_wav_bytes(pcm_bytes: bytes, sample_rate: int, channels: int, sampwidth: int) -> bytes:
    """将原始PCM数据转换为WAV格式"""
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()

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
    if "data" in log_payload and isinstance(log_payload["data"], str) and len(log_payload["data"]) > 100:
        log_payload["data"] = f"[audio data: {len(log_payload['data'])} chars]"

    logger.info(f"Sending event: {event_type} - {json.dumps(log_payload, default=str)}")

    try:
        await websocket.send(json.dumps(payload))
    except Exception as e:
        logger.error(f"Error sending event: {e}")

# ----------------- 服务提供商适配器 -----------------

class STTProvider:
    """语音转文本提供商接口"""

    @staticmethod
    async def transcribe(audio_bytes: bytes, config: Dict[str, Any]) -> str:
        """将音频转换为文本"""
        provider = config.get("stt_provider", "openai")

        audio_file = BytesIO(audio_bytes)
        audio_file.name = "audio.wav"

        if provider == "openai":
            try:
                model = config.get("stt_config", {}).get("model", "whisper-1")
                language = config.get("stt_config", {}).get("language", "")
                prompt = config.get("stt_config", {}).get("prompt", "")

                tr = client.audio.transcriptions.create(
                    model=model,
                    file=audio_file,
                    language=language if language else None,
                    prompt=prompt if prompt else None
                )
                return getattr(tr, "text", "")
            except Exception as e:
                logger.error(f"OpenAI STT error: {e}")
                # 尝试回退到 whisper-1
                try:
                    audio_file.seek(0)
                    tr = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file
                    )
                    return getattr(tr, "text", "")
                except Exception as e2:
                    logger.error(f"Fallback whisper-1 also failed: {e2}")
                    raise Exception(f"STT failed: {e}\nFallback whisper-1 also failed: {e2}")

        elif provider == "azure":
            # 实现 Azure 语音服务
            raise NotImplementedError("Azure STT not implemented yet")

        elif provider == "assemblyai":
            # 实现 AssemblyAI 服务
            raise NotImplementedError("AssemblyAI STT not implemented yet")

        elif provider == "groq":
            # 实现 Groq 服务
            raise NotImplementedError("Groq STT not implemented yet")

        elif provider == "localai":
            # 实现 LocalAI 服务
            raise NotImplementedError("LocalAI STT not implemented yet")

        else:
            raise ValueError(f"Unknown STT provider: {provider}")

class TTSProvider:
    """文本转语音提供商接口"""

    @staticmethod
    async def synthesize(text: str, config: Dict[str, Any]) -> bytes:
        """将文本转换为语音"""
        provider = config.get("tts_provider", "openai")

        if provider == "openai":
            try:
                model = config.get("tts_config", {}).get("model", "gpt-4o-mini-tts")
                voice = config.get("tts_config", {}).get("voice", "alloy")
                speed = config.get("tts_config", {}).get("speed", 1.0)

                tts = client.audio.speech.create(
                    model=model,
                    voice=voice,
                    input=text,
                    speed=speed
                )

                audio_bytes = getattr(tts, "content", None)
                if audio_bytes is None and hasattr(tts, "read"):
                    audio_bytes = tts.read()

                if not audio_bytes:
                    raise Exception("TTS produced no audio")

                return audio_bytes
            except Exception as e:
                logger.error(f"OpenAI TTS error: {e}")
                raise

        elif provider == "azure":
            # 实现 Azure 语音服务
            raise NotImplementedError("Azure TTS not implemented yet")

        elif provider == "elevenlabs":
            # 实现 ElevenLabs 服务
            raise NotImplementedError("ElevenLabs TTS not implemented yet")

        elif provider == "localai":
            # 实现 LocalAI 服务
            raise NotImplementedError("LocalAI TTS not implemented yet")

        else:
            raise ValueError(f"Unknown TTS provider: {provider}")

class QueryProvider:
    """查询提供商接口"""

    @staticmethod
    async def query(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """发送查询到后端服务获取回答"""
        provider = config.get("query_provider", "flowise")

        if provider == "flowise":
            return await QueryProvider._query_flowise(text, config, session_id)
        elif provider == "openai":
            return await QueryProvider._query_openai(text, config, session_id)
        elif provider == "anthropic":
            return await QueryProvider._query_anthropic(text, config, session_id)
        elif provider == "azure_openai":
            return await QueryProvider._query_azure_openai(text, config, session_id)
        elif provider == "langchain":
            return await QueryProvider._query_langchain(text, config, session_id)
        elif provider == "huggingface":
            return await QueryProvider._query_huggingface(text, config, session_id)
        elif provider == "localai":
            return await QueryProvider._query_localai(text, config, session_id)
        elif provider == "ollama":
            return await QueryProvider._query_ollama(text, config, session_id)
        elif provider == "google_ai":
            return await QueryProvider._query_google_ai(text, config, session_id)
        elif provider == "custom_api":
            return await QueryProvider._query_custom_api(text, config, session_id)
        else:
            raise ValueError(f"Unknown query provider: {provider}")

    @staticmethod
    async def _query_flowise(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用 Flowise API 查询"""
        try:
            # 获取 API 配置
            api_url = config.get("query_config", {}).get("api_url", os.getenv("API_URL"))
            api_key = config.get("query_config", {}).get("api_key", os.getenv("FLOWISE_API_KEY"))
            chatflow_id = config.get("query_config", {}).get("chatflow_id")

            # 构建查询负载
            payload = {
                "question": text,
                "streaming": False
            }

            # 如果有会话ID，添加到请求中
            if session_id:
                payload["chatId"] = session_id

            # 添加可选配置
            override_config = config.get("query_config", {}).get("override_config")
            if override_config:
                payload["overrideConfig"] = override_config

            # 构建URL
            url = api_url
            if chatflow_id:
                if not url.endswith("/"):
                    url += "/"
                if "prediction" not in url:
                    url += "api/v1/prediction/"
                url += chatflow_id

            # 构建请求头
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            # 记录请求
            logger.info(f"Sending Flowise query to {url}: {json.dumps(payload, indent=2)}")

            # 发送请求
            start_time = asyncio.get_event_loop().time()
            r = requests.post(url, json=payload, headers=headers, verify=False, timeout=30)
            elapsed_time = asyncio.get_event_loop().time() - start_time

            # 请求失败
            r.raise_for_status()

            # 解析响应
            response = r.json()

            # 记录响应
            log_response = response.copy()
            for key, value in log_response.items():
                if isinstance(value, str) and len(value) > 500:
                    log_response[key] = f"[content truncated, length: {len(value)}]"

            logger.info(f"Flowise response received in {elapsed_time:.2f}s: {json.dumps(log_response, indent=2)}")

            # 提取回复文本
            reply = (response.get("text") or response.get("answer") or str(response)).strip()
            return reply
        except Exception as e:
            logger.error(f"Flowise query failed: {e}")
            raise

    @staticmethod
    async def _query_openai(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用 OpenAI API 查询"""
        try:
            # 获取配置
            model = config.get("query_config", {}).get("model", "gpt-4o")
            system_prompt = config.get("query_config", {}).get("system_prompt", "你是一个有帮助的助手。")
            temperature = config.get("query_config", {}).get("temperature", 0.7)
            max_tokens = config.get("query_config", {}).get("max_tokens")
            api_key = config.get("query_config", {}).get("api_key", os.getenv("OPENAI_API_KEY"))

            # 创建 OpenAI 客户端
            openai_client = OpenAI(api_key=api_key)

            # 构建消息
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]

            # 创建参数
            params = {
                "model": model,
                "messages": messages,
                "temperature": temperature
            }

            if max_tokens:
                params["max_tokens"] = max_tokens

            logger.info(f"Sending OpenAI query with model {model}")

            # 发送请求
            start_time = asyncio.get_event_loop().time()
            response = openai_client.chat.completions.create(**params)
            elapsed_time = asyncio.get_event_loop().time() - start_time

            logger.info(f"OpenAI response received in {elapsed_time:.2f}s")

            # 提取响应文本
            reply = response.choices[0].message.content
            return reply
        except Exception as e:
            logger.error(f"OpenAI query failed: {e}")
            raise

    @staticmethod
    async def _query_anthropic(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用 Anthropic API 查询"""
        try:
            # 这需要 anthropic 包
            # pip install anthropic
            import anthropic

            # 获取配置
            model = config.get("query_config", {}).get("model", "claude-3-opus-20240229")
            system_prompt = config.get("query_config", {}).get("system_prompt", "你是 Claude，一个有帮助的 AI 助手。")
            max_tokens = config.get("query_config", {}).get("max_tokens", 1024)
            temperature = config.get("query_config", {}).get("temperature", 0.7)
            api_key = config.get("query_config", {}).get("api_key", os.getenv("ANTHROPIC_API_KEY"))

            # 创建 Anthropic 客户端
            client = anthropic.Anthropic(api_key=api_key)

            logger.info(f"Sending Anthropic query with model {model}")

            # 发送请求
            start_time = asyncio.get_event_loop().time()
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": text}
                ]
            )
            elapsed_time = asyncio.get_event_loop().time() - start_time

            logger.info(f"Anthropic response received in {elapsed_time:.2f}s")

            # 提取响应文本
            reply = message.content[0].text
            return reply
        except Exception as e:
            logger.error(f"Anthropic query failed: {e}")
            raise

    @staticmethod
    async def _query_azure_openai(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用 Azure OpenAI API 查询"""
        try:
            # 获取配置
            api_key = config.get("query_config", {}).get("api_key", os.getenv("AZURE_OPENAI_API_KEY"))
            endpoint = config.get("query_config", {}).get("endpoint", os.getenv("AZURE_OPENAI_ENDPOINT"))
            deployment = config.get("query_config", {}).get("deployment")
            model = config.get("query_config", {}).get("model", "gpt-4")
            system_prompt = config.get("query_config", {}).get("system_prompt", "你是一个有帮助的助手。")
            temperature = config.get("query_config", {}).get("temperature", 0.7)

            # 创建 Azure OpenAI 客户端
            from openai import AzureOpenAI

            client = AzureOpenAI(
                api_key=api_key,
                azure_endpoint=endpoint,
                api_version="2023-05-15"
            )

            logger.info(f"Sending Azure OpenAI query with deployment {deployment}")

            # 发送请求
            start_time = asyncio.get_event_loop().time()
            response = client.chat.completions.create(
                model=deployment or model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=temperature
            )
            elapsed_time = asyncio.get_event_loop().time() - start_time

            logger.info(f"Azure OpenAI response received in {elapsed_time:.2f}s")

            # 提取响应文本
            reply = response.choices[0].message.content
            return reply
        except Exception as e:
            logger.error(f"Azure OpenAI query failed: {e}")
            raise

    @staticmethod
    async def _query_langchain(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用 LangChain 查询"""
        try:
            # 这需要 langchain 包
            # pip install langchain
            from langchain.chains import LLMChain
            from langchain.prompts import PromptTemplate
            from langchain_openai import ChatOpenAI

            # 获取配置
            api_key = config.get("query_config", {}).get("api_key", os.getenv("OPENAI_API_KEY"))
            model_name = config.get("query_config", {}).get("model", "gpt-4")
            template = config.get("query_config", {}).get("template", "你是一个有帮助的助手。问题: {question}\n回答:")
            temperature = config.get("query_config", {}).get("temperature", 0.7)

            # 创建 LLM
            llm = ChatOpenAI(
                model=model_name,
                openai_api_key=api_key,
                temperature=temperature
            )

            # 创建提示模板
            prompt = PromptTemplate(
                input_variables=["question"],
                template=template
            )

            # 创建链
            chain = LLMChain(llm=llm, prompt=prompt)

            logger.info(f"Sending LangChain query with model {model_name}")

            # 运行链
            start_time = asyncio.get_event_loop().time()
            result = chain.invoke({"question": text})
            elapsed_time = asyncio.get_event_loop().time() - start_time

            logger.info(f"LangChain response received in {elapsed_time:.2f}s")

            # 提取响应文本
            reply = result.get("text", "")
            return reply
        except Exception as e:
            logger.error(f"LangChain query failed: {e}")
            raise

    @staticmethod
    async def _query_huggingface(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用 Hugging Face API 查询"""
        try:
            # 获取配置
            api_key = config.get("query_config", {}).get("api_key", os.getenv("HF_API_KEY"))
            model_id = config.get("query_config", {}).get("model_id", "meta-llama/Llama-2-70b-chat-hf")
            api_url = f"https://api-inference.huggingface.co/models/{model_id}"

            # 构建请求头
            headers = {"Authorization": f"Bearer {api_key}"}

            # 构建请求体
            payload = {"inputs": text}

            logger.info(f"Sending Hugging Face query to model {model_id}")

            # 发送请求
            start_time = asyncio.get_event_loop().time()
            response = requests.post(api_url, headers=headers, json=payload)
            elapsed_time = asyncio.get_event_loop().time() - start_time

            # 请求失败
            response.raise_for_status()

            logger.info(f"Hugging Face response received in {elapsed_time:.2f}s")

            # 解析响应
            result = response.json()

            # Hugging Face 根据模型返回不同格式
            if isinstance(result, list) and result:
                if isinstance(result[0], dict) and "generated_text" in result[0]:
                    return result[0]["generated_text"]
                elif isinstance(result[0], str):
                    return result[0]

            # 如果无法解析，返回原始响应
            return str(result)
        except Exception as e:
            logger.error(f"Hugging Face query failed: {e}")
            raise

    @staticmethod
    async def _query_localai(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用 LocalAI 查询"""
        try:
            # 获取配置
            base_url = config.get("query_config", {}).get("base_url", "http://localhost:8080/v1")
            model = config.get("query_config", {}).get("model", "gpt-3.5-turbo")
            system_prompt = config.get("query_config", {}).get("system_prompt", "你是一个有帮助的助手。")
            temperature = config.get("query_config", {}).get("temperature", 0.7)
            api_key = config.get("query_config", {}).get("api_key", "sk-no-key-required")

            # 创建 OpenAI 客户端指向 LocalAI
            from openai import OpenAI

            client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )

            logger.info(f"Sending LocalAI query with model {model}")

            # 发送请求
            start_time = asyncio.get_event_loop().time()
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=temperature
            )
            elapsed_time = asyncio.get_event_loop().time() - start_time

            logger.info(f"LocalAI response received in {elapsed_time:.2f}s")

            # 提取响应文本
            reply = response.choices[0].message.content
            return reply
        except Exception as e:
            logger.error(f"LocalAI query failed: {e}")
            raise

    @staticmethod
    async def _query_ollama(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用 Ollama API 查询"""
        try:
            # 获取配置
            base_url = config.get("query_config", {}).get("base_url", "http://localhost:11434")
            model = config.get("query_config", {}).get("model", "llama2")
            system = config.get("query_config", {}).get("system", "你是一个有帮助的助手。")

            # API 端点
            api_url = f"{base_url}/api/generate"

            # 构建请求体
            payload = {
                "model": model,
                "prompt": text,
                "system": system,
                "stream": False
            }

            logger.info(f"Sending Ollama query to model {model}")

            # 发送请求
            start_time = asyncio.get_event_loop().time()
            response = requests.post(api_url, json=payload)
            elapsed_time = asyncio.get_event_loop().time() - start_time

            # 请求失败
            response.raise_for_status()

            # 解析响应
            result = response.json()

            logger.info(f"Ollama response received in {elapsed_time:.2f}s")

            # 提取响应文本
            reply = result.get("response", "")
            return reply
        except Exception as e:
            logger.error(f"Ollama query failed: {e}")
            raise

    @staticmethod
    async def _query_google_ai(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用 Google AI API 查询"""
        try:
            # 这需要 google-generativeai 包
            # pip install google-generativeai
            import google.generativeai as genai

            # 获取配置
            api_key = config.get("query_config", {}).get("api_key", os.getenv("GOOGLE_API_KEY"))
            model_name = config.get("query_config", {}).get("model", "gemini-pro")
            temperature = config.get("query_config", {}).get("temperature", 0.7)

            # 配置 API
            genai.configure(api_key=api_key)

            # 获取模型
            model = genai.GenerativeModel(model_name=model_name)

            logger.info(f"Sending Google AI query with model {model_name}")

            # 发送请求
            start_time = asyncio.get_event_loop().time()
            response = model.generate_content(
                text,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature
                )
            )
            elapsed_time = asyncio.get_event_loop().time() - start_time

            logger.info(f"Google AI response received in {elapsed_time:.2f}s")

            # 提取响应文本
            reply = response.text
            return reply
        except Exception as e:
            logger.error(f"Google AI query failed: {e}")
            raise

    @staticmethod
    async def _query_custom_api(text: str, config: Dict[str, Any], session_id: str = None) -> str:
        """使用自定义 API 查询"""
        try:
            # 获取配置
            api_url = config.get("query_config", {}).get("api_url")
            method = config.get("query_config", {}).get("method", "POST")
            headers = config.get("query_config", {}).get("headers", {})
            auth_token = config.get("query_config", {}).get("auth_token")

            if auth_token and "Authorization" not in headers:
                headers["Authorization"] = f"Bearer {auth_token}"

            # 获取请求体模板和响应解析路径
            body_template = config.get("query_config", {}).get("body_template", '{"query": "${query}"}')
            response_path = config.get("query_config", {}).get("response_path", "")

            # 替换模板中的查询
            body = body_template.replace("${query}", text)
            if body.startswith("{"):
                try:
                    body = json.loads(body)
                    headers["Content-Type"] = "application/json"
                except:
                    pass

            logger.info(f"Sending custom API query to {api_url}")

            # 发送请求
            start_time = asyncio.get_event_loop().time()
            if method.upper() == "POST":
                if isinstance(body, dict):
                    response = requests.post(api_url, json=body, headers=headers)
                else:
                    response = requests.post(api_url, data=body, headers=headers)
            elif method.upper() == "GET":
                response = requests.get(api_url, params={"query": text}, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            elapsed_time = asyncio.get_event_loop().time() - start_time

            # 请求失败
            response.raise_for_status()

            logger.info(f"Custom API response received in {elapsed_time:.2f}s")

            # 解析响应
            if response.headers.get("Content-Type", "").startswith("application/json"):
                result = response.json()

                # 如果指定了响应路径，尝试提取
                if response_path:
                    paths = response_path.split(".")
                    for path in paths:
                        if isinstance(result, dict) and path in result:
                            result = result[path]
                        else:
                            break

                if isinstance(result, (dict, list)):
                    return json.dumps(result)
                else:
                    return str(result)
            else:
                return response.text
        except Exception as e:
            logger.error(f"Custom API query failed: {e}")
            raise

# ----------------- 会话状态管理 -----------------

class SessionManager:
    """管理用户会话状态"""

    def __init__(self):
        self.sessions = {}

    def create_session(self, config: Dict[str, Any] = None) -> str:
        """创建新会话"""
        session_id = generate_id("sess")

        # 设置默认配置
        default_config = {
            "mode": "push_to_talk",
            "stt_provider": "openai",
            "stt_config": {
                "model": "gpt-4o-transcribe"
            },
            "tts_provider": "openai",
            "tts_config": {
                "model": "gpt-4o-mini-tts",
                "voice": "alloy"
            },
            "vad_config": {
                "threshold": 0.5,
                "silence_duration_ms": 500,
                "prefix_padding_ms": 300
            }
        }

        # 合并用户配置
        if config:
            self._merge_config(default_config, config)

        # 创建会话状态
        self.sessions[session_id] = {
            "config": default_config,
            "audio_buffer": bytearray(),
            "active_response": None,
            "openai_ws": None,
            "openai_task": None
        }

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话状态"""
        return self.sessions.get(session_id)

    def update_session(self, session_id: str, config: Dict[str, Any]) -> bool:
        """更新会话配置"""
        session = self.get_session(session_id)
        if not session:
            return False

        self._merge_config(session["config"], config)
        return True

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self.sessions:
            # 清理资源
            session = self.sessions[session_id]
            if session.get("openai_task"):
                session["openai_task"].cancel()
            if session.get("openai_ws"):
                asyncio.create_task(session["openai_ws"].close())

            del self.sessions[session_id]
            return True
        return False

    def _merge_config(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """递归合并配置"""
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._merge_config(target[key], value)
            else:
                target[key] = value

# ----------------- WebSocket 处理器 -----------------

class WebSocketHandler:
    """处理 WebSocket 连接和事件"""

    def __init__(self):
        self.session_manager = SessionManager()

    async def handle_client(self, websocket):
        """处理客户端 WebSocket 连接"""
        logger.info("Client connected")

        # 创建默认会话
        session_id = self.session_manager.create_session()
        session = self.session_manager.get_session(session_id)

        # 发送会话创建事件
        await send_event(websocket, "session.created", {
            "session_id": session_id,
            "config": session["config"]
        })

        # 如果是 VAD 模式，连接到 OpenAI Realtime API
        if session["config"]["mode"] == "vad":
            await self._setup_vad_mode(websocket, session_id, session)

        try:
            async for message in websocket:
                # 处理文本消息（JSON 事件）
                if isinstance(message, str):
                    try:
                        event = json.loads(message)
                        await self._process_event(websocket, event, session_id)
                    except json.JSONDecodeError:
                        await send_event(websocket, "error", {
                            "code": "invalid_json",
                            "message": "Invalid JSON format"
                        })

                # 处理二进制消息（音频数据）
                elif isinstance(message, bytes):
                    # 将二进制音频转换为 audio.chunk 事件
                    await self._process_binary_audio(websocket, message, session_id)

                else:
                    await send_event(websocket, "error", {
                        "code": "invalid_message_type",
                        "message": f"Unsupported message type: {type(message)}"
                    })

        except websockets.exceptions.ConnectionClosedError as e:
            logger.info(f"Client disconnected: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            try:
                await send_event(websocket, "error", {
                    "code": "server_error",
                    "message": f"Unexpected error: {str(e)}"
                })
            except Exception:
                pass
        finally:
            # 清理会话
            self.session_manager.delete_session(session_id)
            logger.info("Connection closed")

    async def _process_event(self, websocket, event, session_id):
        """处理客户端事件"""
        event_type = event.get("type")

        if not event_type:
            await send_event(websocket, "error", {
                "code": "missing_event_type",
                "message": "Missing event type"
            })
            return

        logger.info(f"Received event: {event_type}")
        session = self.session_manager.get_session(session_id)

        if not session:
            await send_event(websocket, "error", {
                "code": "session_not_found",
                "message": "Session not found"
            })
            return

        # 事件处理
        if event_type == "session.create":
            # 更新会话配置
            config = event.get("config", {})
            old_mode = session["config"]["mode"]

            # 更新配置
            self.session_manager.update_session(session_id, config)
            new_mode = session["config"]["mode"]

            # 如果模式发生变化，需要重新设置连接
            if old_mode != new_mode and new_mode == "vad":
                await self._setup_vad_mode(websocket, session_id, session)
            elif old_mode != new_mode and new_mode == "push_to_talk":
                # 关闭 VAD 连接
                if session.get("openai_task"):
                    session["openai_task"].cancel()
                if session.get("openai_ws"):
                    await session["openai_ws"].close()
                    session["openai_ws"] = None

            # 发送会话创建事件
            await send_event(websocket, "session.created", {
                "session_id": session_id,
                "config": session["config"]
            })

        elif event_type == "audio.chunk":
            # 处理音频块
            format_type = event.get("format", "pcm16")
            audio_data_b64 = event.get("data")

            if not audio_data_b64:
                await send_event(websocket, "error", {
                    "code": "missing_audio_data",
                    "message": "Missing audio data"
                })
                return

            try:
                # 解码 base64 音频数据
                audio_data = base64.b64decode(audio_data_b64)

                # 根据模式处理音频
                if session["config"]["mode"] == "push_to_talk":
                    # Push-to-talk 模式：累积音频数据
                    session["audio_buffer"].extend(audio_data)

                elif session["config"]["mode"] == "vad":
                    # VAD 模式：转发到 OpenAI Realtime API
                    if session.get("openai_ws"):
                        # 重新编码为 base64
                        audio_b64 = base64.b64encode(audio_data).decode("utf-8")

                        # 发送到 OpenAI
                        append_evt = {
                            "type": "input_audio_buffer.append",
                            "audio": audio_b64
                        }
                        await session["openai_ws"].send(json.dumps(append_evt))
                    else:
                        await send_event(websocket, "error", {
                            "code": "vad_not_connected",
                            "message": "VAD mode is not properly connected"
                        })
            except Exception as e:
                await send_event(websocket, "error", {
                    "code": "audio_processing_error",
                    "message": f"Error processing audio: {e}"
                })

        elif event_type == "audio.done":
            # 仅在 Push-to-talk 模式处理
            if session["config"]["mode"] == "push_to_talk":
                if not session["audio_buffer"]:
                    await send_event(websocket, "error", {
                        "code": "empty_audio",
                        "message": "No audio received before done"
                    })
                    return

                # 处理完整音频
                audio_id = generate_id("audio")

                # 发送音频已提交事件
                await send_event(websocket, "audio.committed", {
                    "audio_id": audio_id
                })

                # 处理音频数据
                audio_data = bytes(session["audio_buffer"])

                # 创建 WAV
                wav_bytes = pcm_bytes_to_wav_bytes(
                    audio_data,
                    sample_rate=PCM_SAMPLE_RATE,
                    channels=PCM_CHANNELS,
                    sampwidth=PCM_SAMPWIDTH,
                )

                try:
                    # 转录音频
                    text = await STTProvider.transcribe(wav_bytes, session["config"])

                    # 发送转录结果
                    await send_event(websocket, "transcript.created", {
                        "audio_id": audio_id,
                        "text": text
                    })

                    # 查询后端
                    await self._process_query(websocket, text, session_id)

                    # 清空音频缓冲区
                    session["audio_buffer"].clear()

                except Exception as e:
                    await send_event(websocket, "error", {
                        "code": "processing_error",
                        "message": f"Error processing audio: {e}"
                    })
                    session["audio_buffer"].clear()

        elif event_type == "audio.clear":
            # 清除音频缓冲区
            session["audio_buffer"].clear()

            # VAD 模式：发送清除命令到 OpenAI
            if session["config"]["mode"] == "vad" and session.get("openai_ws"):
                clear_evt = {
                    "type": "input_audio_buffer.clear"
                }
                await session["openai_ws"].send(json.dumps(clear_evt))

            await send_event(websocket, "audio.cleared", {})

        elif event_type == "query.custom":
            # 直接查询
            text = event.get("text")
            if not text:
                await send_event(websocket, "error", {
                    "code": "missing_text",
                    "message": "Missing query text"
                })
                return

            await self._process_query(websocket, text, session_id)

        elif event_type == "response.cancel":
            # 取消响应
            if session["active_response"]:
                response_id = session["active_response"].get("id")

                await send_event(websocket, "response.cancelled", {
                    "response_id": response_id
                })

                session["active_response"] = None
            else:
                await send_event(websocket, "error", {
                    "code": "no_active_response",
                    "message": "No active response to cancel"
                })

        else:
            await send_event(websocket, "error", {
                "code": "unknown_event",
                "message": f"Unknown event type: {event_type}"
            })

    async def _process_binary_audio(self, websocket, audio_data, session_id):
        """处理二进制音频数据"""
        session = self.session_manager.get_session(session_id)

        if session["config"]["mode"] == "push_to_talk":
            # Push-to-talk 模式：累积音频数据
            session["audio_buffer"].extend(audio_data)

        elif session["config"]["mode"] == "vad":
            # VAD 模式：转发到 OpenAI Realtime API
            if session.get("openai_ws"):
                # 重新编码为 base64
                audio_b64 = base64.b64encode(audio_data).decode("utf-8")

                # 发送到 OpenAI
                append_evt = {
                    "type": "input_audio_buffer.append",
                    "audio": audio_b64
                }
                await session["openai_ws"].send(json.dumps(append_evt))
            else:
                await send_event(websocket, "error", {
                    "code": "vad_not_connected",
                    "message": "VAD mode is not properly connected"
                })

    async def _process_query(self, websocket, text, session_id):
        """处理查询流程"""
        # 创建查询 ID
        query_id = generate_id("query")

        # 获取会话
        session = self.session_manager.get_session(session_id)


        # 发送查询已发送事件
        await send_event(websocket, "query.sent", {
            "query_id": query_id,
            "text": text
        })

        try:
            # 查询后端，传递会话配置
            reply = await QueryProvider.query(text, session["config"], session_id)


            # 创建响应 ID
            response_id = generate_id("resp")

            # 跟踪活动响应
            session["active_response"] = {
                "id": response_id,
                "text": reply
            }

            # 发送响应已创建事件
            await send_event(websocket, "response.created", {
                "response_id": response_id,
                "text": reply
            })

            # 生成语音
            await send_event(websocket, "audio.started", {
                "response_id": response_id
            })

            try:
                # 生成语音
                audio_bytes = await TTSProvider.synthesize(reply, session["config"])

                # 发送音频到客户端
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                await send_event(websocket, "audio.chunk", {
                    "response_id": response_id,
                    "format": "mp3",  # 或根据实际格式调整
                    "data": audio_b64
                })

                # 发送完成事件
                await send_event(websocket, "audio.completed", {
                    "response_id": response_id
                })

                # 清除活动响应
                session["active_response"] = None

            except Exception as e:
                await send_event(websocket, "error", {
                    "code": "tts_error",
                    "message": f"TTS failed: {e}"
                })

                # 即使失败也清除活动响应
                session["active_response"] = None

        except Exception as e:
            await send_event(websocket, "error", {
                "code": "query_error",
                "message": f"Query failed: {e}"
            })

    async def _setup_vad_mode(self, websocket, session_id, session):
        """设置 VAD 模式连接到 OpenAI Realtime API"""
        # 关闭现有连接
        if session.get("openai_task"):
            session["openai_task"].cancel()
        if session.get("openai_ws"):
            await session["openai_ws"].close()

        # 连接到 OpenAI Realtime API
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

            session["openai_ws"] = openai_ws

            # 配置 VAD
            vad_config = session["config"]["vad_config"]

            session_update = {
                "type": "session.update",
                "session": {
                    "input_audio_format": "pcm16",
                    "input_audio_transcription": {
                        "model": session["config"]["stt_config"].get("model", "gpt-4o-transcribe"),
                        "prompt": session["config"]["stt_config"].get("prompt", ""),
                        "language": session["config"]["stt_config"].get("language", "")
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": vad_config.get("threshold", 0.5),
                        "prefix_padding_ms": vad_config.get("prefix_padding_ms", 300),
                        "silence_duration_ms": vad_config.get("silence_duration_ms", 500),
                        "create_response": False  # 不自动生成响应
                    },
                    "include": ["item.input_audio_transcription.logprobs"],
                }
            }

            await openai_ws.send(json.dumps(session_update))

            # 启动事件处理任务
            session["openai_task"] = asyncio.create_task(
                self._handle_openai_events(websocket, session_id, session)
            )

            logger.info("VAD mode connected to OpenAI Realtime API")

        except Exception as e:
            logger.error(f"Failed to connect to OpenAI Realtime API: {e}")
            await send_event(websocket, "error", {
                "code": "vad_connection_error",
                "message": f"Cannot connect to OpenAI Realtime API: {e}"
            })

    async def _handle_openai_events(self, websocket, session_id, session):
        """处理来自 OpenAI Realtime API 的事件"""
        try:
            openai_ws = session["openai_ws"]

            async for raw in openai_ws:
                try:
                    evt = json.loads(raw)
                except Exception:
                    logger.warning(f"Non-JSON event from OpenAI: {type(raw)}")
                    continue

                event_type = evt.get("type", "")

                # VAD 事件
                if event_type == "input_audio_buffer.speech_started":
                    logger.info("Speech started detected by VAD")
                    await send_event(websocket, "vad.speech_started", {})

                elif event_type == "input_audio_buffer.speech_stopped":
                    logger.info("Speech stopped detected by VAD")
                    await send_event(websocket, "vad.speech_stopped", {})

                elif event_type == "input_audio_buffer.committed":
                    audio_id = evt.get("item_id")
                    logger.info(f"Audio buffer committed by VAD: {audio_id}")
                    await send_event(websocket, "audio.committed", {
                        "audio_id": audio_id
                    })

                # 转录完成
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    # 提取转录文本
                    user_text = None

                    # 尝试从不同位置获取文本
                    user_text = (evt.get("transcript")
                                 or evt.get("text")
                                 or (evt.get("item", {}).get("content", [{}])[0].get("transcript", {}) or {}).get("text"))

                    if not user_text:
                        logger.warning("Transcription event without text")
                        continue

                    audio_id = evt.get("item", {}).get("id")

                    logger.info(f"Transcription completed: {user_text}")

                    # 发送转录结果
                    await send_event(websocket, "transcript.created", {
                        "audio_id": audio_id,
                        "text": user_text
                    })

                    # 查询后端
                    await self._process_query(websocket, user_text, session_id)

                # 错误处理
                elif event_type == "error":
                    logger.error(f"OpenAI Realtime API error: {evt}")
                    await send_event(websocket, "error", {
                        "code": "openai_error",
                        "message": f"OpenAI Realtime API error: {json.dumps(evt)}"
                    })

        except websockets.exceptions.ConnectionClosedError:
            logger.info("OpenAI Realtime API connection closed")
        except Exception as e:
            logger.error(f"Error handling OpenAI events: {e}", exc_info=True)
        finally:
            # 清理
            session["openai_task"] = None
            session["openai_ws"] = None

# ----------------- 主程序 -----------------

async def main():
    """启动 WebSocket 服务器"""
    handler = WebSocketHandler()

    try:
        logger.info("Starting WebSocket server...")
        async with serve(
                handler.handle_client,
                "0.0.0.0",
                8000,
                max_size=10 * 1024 * 1024,
                ping_interval=20,
                ping_timeout=20,
        ):
            logger.info("WebSocket server listening on :8000")
            await asyncio.Future()  # 无限运行
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
