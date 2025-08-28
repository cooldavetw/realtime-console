"""
事件协议定义，定义了客户端和服务器之间交换的事件格式。
这里提供了事件的结构说明，作为文档和代码参考。
"""

CLIENT_EVENTS = {
    "session.create": {
        "description": "创建会话并设置配置",
        "parameters": {
            "config": {
                "type": "object",
                "description": "会话配置",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["push_to_talk", "vad"],
                        "description": "会话模式"
                    },
                    "stt_provider": {
                        "type": "string",
                        "enum": ["openai", "azure", "assemblyai", "groq", "localai"],
                        "description": "STT 提供商"
                    },
                    "stt_config": {
                        "type": "object",
                        "description": "STT 配置"
                    },
                    "tts_provider": {
                        "type": "string",
                        "enum": ["openai", "azure", "elevenlabs", "localai"],
                        "description": "TTS 提供商"
                    },
                    "tts_config": {
                        "type": "object",
                        "description": "TTS 配置"
                    },
                    "query_provider": {
                        "type": "string",
                        "enum": ["flowise", "openai", "anthropic", "azure_openai", "langchain", "huggingface", "localai", "ollama", "google_ai", "custom_api"],
                        "description": "查询提供商"
                    },
                    "query_config": {
                        "type": "object",
                        "description": "查询配置"
                    },
                    "vad_config": {
                        "type": "object",
                        "description": "VAD 配置"
                    }
                }
            }
        }
    },
    "session.update": {
        "description": "更新配置",
        "parameters": {
            "config": {
                "type": "object",
                "description": "会话配置",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["push_to_talk", "vad"],
                        "description": "会话模式"
                    },
                    "stt_provider": {
                        "type": "string",
                        "enum": ["openai", "azure", "assemblyai", "groq", "localai"],
                        "description": "STT 提供商"
                    },
                    "stt_config": {
                        "type": "object",
                        "description": "STT 配置"
                    },
                    "tts_provider": {
                        "type": "string",
                        "enum": ["openai", "azure", "elevenlabs", "localai"],
                        "description": "TTS 提供商"
                    },
                    "tts_config": {
                        "type": "object",
                        "description": "TTS 配置"
                    },
                    "query_provider": {
                        "type": "string",
                        "enum": ["flowise", "openai", "anthropic", "azure_openai", "langchain", "huggingface", "localai", "ollama", "google_ai", "custom_api"],
                        "description": "查询提供商"
                    },
                    "query_config": {
                        "type": "object",
                        "description": "查询配置"
                    },
                    "vad_config": {
                        "type": "object",
                        "description": "VAD 配置"
                    }
                }
            }
        }
    },
    "audio.chunk": {
        "description": "发送音频数据片段",
        "parameters": {
            "format": {
                "type": "string",
                "enum": ["pcm16", "webm"],
                "description": "音频格式"
            },
            "data": {
                "type": "string",
                "description": "base64编码的音频数据"
            }
        }
    },
    "audio.done": {
        "description": "标记音频输入结束（Push-to-talk 模式）",
        "parameters": {}
    },
    "audio.clear": {
        "description": "清除当前音频缓冲区",
        "parameters": {}
    },
    "query.custom": {
        "description": "发送自定义文本查询（跳过语音处理）",
        "parameters": {
            "text": {
                "type": "string",
                "description": "查询文本"
            }
        }
    },
    "response.create": {
        "description": "完成正在进行的响应",
        "parameters": {}
    },
    "response.cancel": {
        "description": "取消正在进行的响应",
        "parameters": {}
    }
}

SERVER_EVENTS = {
    "session.created": {
        "description": "会话创建成功",
        "parameters": {
            "session_id": {
                "type": "string",
                "description": "会话ID"
            },
            "config": {
                "type": "object",
                "description": "会话配置"
            }
        }
    },
    "vad.speech_started": {
        "description": "VAD 模式检测到语音开始",
        "parameters": {}
    },
    "vad.speech_stopped": {
        "description": "VAD 模式检测到语音结束",
        "parameters": {}
    },
    "audio.committed": {
        "description": "音频已提交处理",
        "parameters": {
            "audio_id": {
                "type": "string",
                "description": "音频ID"
            }
        }
    },
    "transcript.created": {
        "description": "语音转文字完成",
        "parameters": {
            "session_id": {
                "type": "string",
                "description": "会话ID"
            },
            "transcription_id": {
                "type": "string",
                "description": "轉文字ID"
            },
            "audio_id": {
                "type": "string",
                "description": "音频ID"
            },
            "text": {
                "type": "string",
                "description": "转录文本"
            }
        }
    },
    "query.sent": {
        "description": "查询已发送至后端",
        "parameters": {
            "query_id": {
                "type": "string",
                "description": "查询ID"
            },
            "text": {
                "type": "string",
                "description": "查询文本"
            }
        }
    },
    "response.created": {
        "description": "收到后端响应",
        "parameters": {
            "response_id": {
                "type": "string",
                "description": "响应ID"
            },
            "text": {
                "type": "string",
                "description": "响应文本"
            }
        }
    },
    "audio.started": {
        "description": "TTS开始处理",
        "parameters": {
            "response_id": {
                "type": "string",
                "description": "响应ID"
            }
        }
    },
    "audio.chunk": {
        "description": "TTS音频数据片段",
        "parameters": {
            "response_id": {
                "type": "string",
                "description": "响应ID"
            },
            "format": {
                "type": "string",
                "enum": ["mp3", "wav"],
                "description": "音频格式"
            },
            "data": {
                "type": "string",
                "description": "base64编码的音频数据"
            }
        }
    },
    "response.cancelled": {
        "description": "响应已取消",
        "parameters": {
            "response_id": {
                "type": "string",
                "description": "响应ID"
            }
        }
    },
    "conversation.updated": {
        "description": "对话项已更新",
        "parameters": {
            "session_id": {
                "type": "string",
                "description": "会话ID"
            },
            "item": {
                "type": "object",
                "description": "对话项内容",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "对话项ID"
                    },
                    "role": {
                        "type": "string",
                        "enum": ["user", "assistant"],
                        "description": "角色"
                    },
                    "type": {
                        "type": "string",
                        "description": "对话项类型"
                    },
                    "content": {
                        "type": "object",
                        "description": "对话内容"
                    }
                }
            },
            "delta": {
                "type": "object",
                "description": "增量更新内容"
            }
        }
    },
    "conversation.interrupted": {
        "description": "对话已中断",
        "parameters": {
            "session_id": {
                "type": "string",
                "description": "会话ID"
            },
            "response_id": {
                "type": "string",
                "description": "被中断的响应ID"
            }
        }
    },
    "error": {
        "description": "错误信息",
        "parameters": {
            "code": {
                "type": "string",
                "description": "错误代码"
            },
            "message": {
                "type": "string",
                "description": "错误描述"
            }
        }
    }
}
