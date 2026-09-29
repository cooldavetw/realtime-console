"""In-process conversational agent, owned by a single WebSocket session."""
import asyncio
from typing import Any, Dict

from pydantic_ai import Agent

from backend.config.settings import get_config

DEFAULT_MODEL = "openai:gpt-4o"
DEFAULT_INSTRUCTIONS = (
    "You are a helpful voice assistant. Reply in the user's language. "
    "Keep answers concise and natural when spoken aloud."
)


class PydanticAIQueryProvider:
    def __init__(self, agent=None):
        # Defer model resolution until a query, so startup needs no credentials.
        self.agent = agent if agent is not None else Agent(output_type=str)
        self.history = []
        self._lock = asyncio.Lock()

    async def query(self, text: str, config: Dict[str, Any], session_id: str = None) -> str:
        options = config.get("query_config", {})
        model = options.get("model") or get_config("AGENT_MODEL", DEFAULT_MODEL)
        instructions = options.get("system_prompt") or get_config(
            "AGENT_SYSTEM_PROMPT", DEFAULT_INSTRUCTIONS
        )
        timeout = float(options.get("timeout", get_config("AGENT_TIMEOUT", 60)))
        if timeout <= 0:
            raise ValueError("Agent timeout must be positive")

        # Serialize overlapping turns and only retain successfully completed runs.
        async with self._lock:
            result = await asyncio.wait_for(
                self.agent.run(
                    text,
                    model=model,
                    instructions=instructions,
                    message_history=list(self.history),
                ),
                timeout=timeout,
            )
            self.history = result.all_messages()
            return result.output
