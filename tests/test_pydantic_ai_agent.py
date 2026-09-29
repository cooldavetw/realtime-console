"""Exercise the real agent with deterministic models and no network calls."""
import asyncio
from unittest.mock import AsyncMock

import pytest
from pydantic_ai import Agent, models
from pydantic_ai.messages import ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel

from backend.config import settings
from backend.core.conversation_store import ConversationStore
from backend.core.session import SessionManager
from backend.services.query.base import QueryProvider
from backend.services.query.pydantic_ai_agent import PydanticAIQueryProvider


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)
    monkeypatch.setattr(settings, "CONFIG", {})


def prompts(messages):
    return [part.content for message in messages for part in message.parts
            if isinstance(part, UserPromptPart)]


def echo_history(messages, info):
    return ModelResponse(parts=[TextPart(" | ".join(prompts(messages)))])


def config(function=echo_history):
    return {"query_config": {"model": FunctionModel(function)}}


@pytest.mark.asyncio
async def test_history_and_isolation():
    first = PydanticAIQueryProvider()
    second = PydanticAIQueryProvider()
    assert await first.query("My name is Ada", config()) == "My name is Ada"
    assert await first.query("What is my name?", config()) == "My name is Ada | What is my name?"
    assert await second.query("Hello", config()) == "Hello"


@pytest.mark.asyncio
async def test_failed_and_timed_out_turns_do_not_enter_history():
    provider = PydanticAIQueryProvider()
    await provider.query("First", config())
    before = list(provider.history)

    async def fail(messages, info):
        raise RuntimeError("Model failed")

    with pytest.raises(RuntimeError, match="Model failed"):
        await provider.query("Failed", config(fail))
    assert provider.history == before

    async def slow(messages, info):
        await asyncio.sleep(1)
        return ModelResponse(parts=[TextPart("Late")])

    options = config(slow)
    options["query_config"]["timeout"] = 0.01
    with pytest.raises(asyncio.TimeoutError):
        await provider.query("Timed out", options)
    assert provider.history == before
    assert await provider.query("Next", config()) == "First | Next"


@pytest.mark.asyncio
async def test_concurrent_turns_keep_history_order():
    provider = PydanticAIQueryProvider()
    results = await asyncio.gather(
        provider.query("One", config()), provider.query("Two", config())
    )
    assert results == ["One", "One | Two"]


@pytest.fixture
def manager(tmp_path, monkeypatch):
    from backend.core import session
    monkeypatch.setattr(session, "ConversationStore", lambda: ConversationStore(tmp_path / "test.db"))
    return SessionManager()


@pytest.mark.asyncio
async def test_session_provider_lifecycle_and_flowise_fallback(manager, monkeypatch):
    # Override construction only to supply a local model; exercise Agent.run itself.
    from backend.services.query import pydantic_ai_agent
    agent = Agent(output_type=str)
    monkeypatch.setattr(pydantic_ai_agent, "Agent", lambda **kwargs: agent)
    session_id = manager.create_session()
    assert manager.get_session(session_id)["config"]["query_provider"] == "pydantic_ai"
    with agent.override(model=FunctionModel(echo_history)):
        assert await manager.query("One", session_id) == "One"
        assert await manager.query("Two", session_id) == "One | Two"
        manager.update_session(session_id, {"mode": "push_to_talk"})
        assert await manager.query("Three", session_id) == "One | Two | Three"
        manager.update_session(session_id, {"query_config": {"system_prompt": "New instructions"}})
        assert await manager.query("Fresh", session_id) == "Fresh"
        other = manager.create_session()
        assert await manager.query("Separate", other) == "Separate"
    manager.delete_session(session_id)
    assert manager.get_session(session_id) is None
    assert manager.conversation_store.get_conversation_items(session_id) == []

    from backend.services.query.flowise import FlowiseQueryProvider
    flowise = AsyncMock(return_value="Flowise reply")
    monkeypatch.setattr(FlowiseQueryProvider, "query", flowise)
    manager.update_session(other, {"query_provider": "flowise"})
    assert await manager.query("Fallback", other) == "Flowise reply"
    flowise.assert_awaited_once()
    manager.delete_session(other)


@pytest.mark.asyncio
async def test_agent_configuration_and_default_factory():
    assert isinstance(await QueryProvider.get_provider({}), PydanticAIQueryProvider)
    seen = []

    def inspect_instructions(messages, info):
        seen.append(info.instructions)
        return ModelResponse(parts=[TextPart("Configured")])

    options = config(inspect_instructions)
    options["query_config"]["system_prompt"] = "Answer in Traditional Chinese."
    assert await PydanticAIQueryProvider().query("Hello", options) == "Configured"
    assert seen == ["Answer in Traditional Chinese."]


def test_websocket_text_and_speech_share_agent_history(manager, monkeypatch, tmp_path):
    import base64
    import main
    from fastapi.testclient import TestClient
    from backend.services.query import pydantic_ai_agent
    from backend.services.stt.openai_stt import OpenAISTTProvider
    from backend.services.tts.openai_tts import OpenAITTSProvider

    agent = Agent(output_type=str)
    monkeypatch.setattr(pydantic_ai_agent, "Agent", lambda **kwargs: agent)
    monkeypatch.setattr(main, "init_config", lambda: None)
    monkeypatch.setattr(main, "setup_logging", lambda: None)
    synthesize = AsyncMock(return_value=b"test speech")
    monkeypatch.setattr(OpenAITTSProvider, "synthesize", synthesize)
    monkeypatch.setattr(OpenAISTTProvider, "transcribe", AsyncMock(return_value="Spoken turn"))
    app = main.create_app(tmp_path / "missing")

    def receive_response(ws):
        while True:
            event = ws.receive_json()
            assert event["type"] != "error", event
            if event["type"] == "response.created":
                return event

    with agent.override(model=FunctionModel(echo_history)):
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as ws:
                assert ws.receive_json()["config"]["query_provider"] == "pydantic_ai"
                ws.send_json({"type": "query.custom", "text": "Typed turn"})
                assert receive_response(ws)["text"] == "Typed turn"
                ws.send_json({"type": "audio.chunk", "data": base64.b64encode(b'\x00\x00' * 100).decode()})
                ws.send_json({"type": "response.create"})
                reply = receive_response(ws)
                assert reply["text"] == "Typed turn | Spoken turn"
                assert base64.b64decode(reply["audio"]) == b"test speech"
    assert synthesize.await_count == 2
    assert app.state.websocket_handler.session_manager.sessions == {}
