#!/usr/bin/env python3
import asyncio
import sys
import logging
from config.settings import init_config
from config.logging_config import setup_logging
from core.server import start_server

logger = logging.getLogger(__name__)

async def main():
    """启动 WebSocket 服务器"""
    try:
        # 初始化配置
        init_config()

        # 设置日志
        setup_logging()

        # 启动服务器
        await start_server()
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
