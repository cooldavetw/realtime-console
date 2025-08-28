import asyncio
import logging
from websockets.server import serve

from config.settings import get_config
from handlers.websocket_handler import WebSocketHandler

logger = logging.getLogger(__name__)

async def start_server():
    """启动 WebSocket 服务器"""
    handler = WebSocketHandler()

    try:
        host = get_config("HOST", "0.0.0.0")
        port = get_config("PORT", 8000)
        max_size = get_config("MAX_MESSAGE_SIZE", 10 * 1024 * 1024)
        ping_interval = get_config("PING_INTERVAL", 20)
        ping_timeout = get_config("PING_TIMEOUT", 20)

        logger.info(f"Starting WebSocket server on {host}:{port}...")

        async with serve(
                handler.handle_client,
                host,
                port,
                max_size=max_size,
                ping_interval=ping_interval,
                ping_timeout=ping_timeout,
        ):
            logger.info(f"WebSocket server listening on {host}:{port}")
            await asyncio.Future()  # 无限运行
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        raise
