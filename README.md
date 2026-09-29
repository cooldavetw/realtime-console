# Segma Realtime Console

A React voice console with a Python FastAPI backend for streaming audio,
transcription, and AI conversations. FastAPI serves the compiled frontend and
WebSocket API together on one port. Docker is not required.

## Layout

```text
main.py             FastAPI application and startup entry point
backend/            Configuration, sessions, event handlers, and AI providers
frontend/           React source and production build
tests/             Backend and application tests
requirements.txt    Python dependencies
.env.example        Example runtime configuration
data/               SQLite database (created automatically)
logs/               Application logs (created automatically)
```

## Install and run

Use Python 3.10+ and Node.js 22 with npm. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your `OPENAI_API_KEY`. The example includes only this required
credential; add optional overrides below when needed. You can also add
`STT_PROMPT` to guide transcription.
The default pipeline uses OpenAI for transcription and speech synthesis, with
an in-process PydanticAI agent for queries. No Flowise service is required.

### Agent configuration

- `QUERY_PROVIDER=pydantic_ai` selects the local agent (the default).
- `AGENT_MODEL=openai:gpt-4o` selects its model.
- `AGENT_SYSTEM_PROMPT` sets the assistant's instructions.
- `AGENT_TIMEOUT=60` sets the query timeout in seconds.

Agent orchestration runs inside FastAPI; the default model still calls OpenAI.
The installed PydanticAI extra includes OpenAI support. Other model providers
require their corresponding PydanticAI extras and credentials.

Each WebSocket session owns its agent and message history. Typed input and
transcribed speech share that history. History is held in memory, removed on
disconnect, and reset when `query_provider` or `query_config` is updated.
Failed or timed-out runs do not add turns to history. Responses remain complete
text replies followed by speech synthesis, using the existing browser protocol.

The implementation is in `backend/services/query/pydantic_ai_agent.py`.
Register Python tools on its `Agent` to extend it. Existing Flowise tools,
retrieval sources, and workflow branches are not imported automatically;
this repository does not contain the original chatflow definition.

To use the existing Flowise integration instead, set `QUERY_PROVIDER=flowise`,
`FLOWISE_API_URL` to the chatflow prediction URL, and `FLOWISE_API_KEY` if
required, then restart the server. Other providers remain under
`backend/services/`.

The implementation follows PydanticAI's [message history](https://ai.pydantic.dev/message-history/)
and [testing](https://ai.pydantic.dev/testing/) APIs.

Build the frontend and start the application:

```bash
cd frontend
npm install
npm run build
cd ..
python main.py
```

Open http://localhost:8000. `HOST` and `PORT` in `.env` control the Python
entry point. Node is only needed for frontend builds and development.
Rebuild the frontend and restart the backend after frontend source changes.

You can also start from the repository root with:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Uvicorn's command-line flags control its host and port. Application credentials
are loaded from the root `.env` with either startup method. Use one worker;
active sessions are held in memory. For persistent operation, run this command
through a process manager such as systemd with the repository as its working
directory and the virtual environment's Uvicorn executable.

The browser connects to `/ws` on the same host, selecting `wss` automatically
for HTTPS. Remote microphone access requires HTTPS; localhost supports local
development. An HTTPS reverse proxy must forward WebSocket upgrades to `/ws`.
`GET /health` returns application health. Before the frontend is built, `/`
returns a 503 response with build instructions.

SQLite data and logs resolve relative to the repository rather than the shell's
working directory. Conversation records are deleted when a session disconnects,
preserving the existing session lifecycle.

## Development

Run the backend with automatic reload:

```bash
uvicorn main:app --reload --port 8000
```

For React hot reload, use another terminal:

```bash
cd frontend
REACT_APP_WS_URL=ws://localhost:8000/ws npm start
```

Open http://localhost:3000. `REACT_APP_WS_URL` is an optional frontend build-time
override; production builds normally use the same host as the page.

## Tests

```bash
python -m pytesttests/test_app.py
```

The other tests exercise external providers and require the corresponding API
credentials; speech transcription tests also require
`tests/resources/test_audio.wav`.
