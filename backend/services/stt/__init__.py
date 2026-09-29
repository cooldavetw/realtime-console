from backend.services.stt.base import STTProvider
from backend.services.stt.openai_stt import OpenAISTTProvider
from backend.services.stt.azure_stt import AzureSTTProvider
from backend.services.stt.assemblyai_stt import AssemblyAISTTProvider
from backend.services.stt.groq_stt import GroqSTTProvider
from backend.services.stt.localai_stt import LocalAISTTProvider

__all__ = [
    'STTProvider', 'OpenAISTTProvider', 'AzureSTTProvider',
    'AssemblyAISTTProvider', 'GroqSTTProvider', 'LocalAISTTProvider'
]
