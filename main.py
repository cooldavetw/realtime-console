"""Serve the realtime console and its WebSocket API from one process."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse

from backend.config.settings import PROJECT_ROOT, get_config, init_config
from backend.config.logging_config import setup_logging
from backend.handlers.websocket_handler import WebSocketHandler


def create_app(frontend_dir: Path = None) -> FastAPI:
    build_dir = Path(frontend_dir) if frontend_dir is not None else PROJECT_ROOT / "frontend" / "build"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_config()
        setup_logging()
        app.state.websocket_handler = WebSocketHandler()
        yield
        manager = app.state.websocket_handler.session_manager
        for session_id in list(manager.sessions):
            manager.delete_session(session_id)

    app = FastAPI(title="Segma Realtime Console", lifespan=lifespan)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        await app.state.websocket_handler.handle_client(websocket)

    if (build_dir / "index.html").is_file():
        app.frontend("/", directory=build_dir, fallback="index.html")
    else:
        @app.get("/")
        async def frontend_missing():
            return JSONResponse(
                status_code=503,
                content={"detail": "Frontend not built. Run npm install and npm run build in frontend/, then restart the server."},
            )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    init_config()
    uvicorn.run(
        app,
        host=get_config("HOST"),
        port=get_config("PORT"),
        ws_max_size=get_config("MAX_MESSAGE_SIZE"),
        ws_ping_interval=get_config("PING_INTERVAL"),
        ws_ping_timeout=get_config("PING_TIMEOUT"),
    )
