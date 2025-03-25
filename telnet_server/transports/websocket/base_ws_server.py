#!/usr/bin/env python3
# telnet_server/transports/websocket/base_ws_server.py
"""
Base WebSocket Server

Provides a base class for WebSocket servers that run over the 'websockets' package.
Implements common functionality: starting the server, keeping it running,
sending global messages, and graceful shutdown. Subclasses override _connection_handler().
"""

import asyncio
import logging
import ssl
from typing import Type, List

import websockets
from websockets.server import WebSocketServerProtocol

from telnet_server.handlers.base_handler import BaseHandler
from telnet_server.transports.base_server import BaseServer

logger = logging.getLogger('base-ws-server')

# telnet_server/transports/websocket/base_ws_server.py

class BaseWebSocketServer(BaseServer):
    def __init__(
        self,
        host: str = '0.0.0.0',
        port: int = 8023,
        handler_class: Type[BaseHandler] = None,
        ping_interval: int = 30,
        ping_timeout: int = 10,
        allow_origins: List[str] = None,
        ssl_cert: str = None,
        ssl_key: str = None
    ):
        super().__init__(host, port, handler_class)
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.allow_origins = allow_origins or ['*']
        self.ssl_context = None
        self.server = None

        if ssl_cert and ssl_key:
            import ssl
            self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.ssl_context.load_cert_chain(ssl_cert, ssl_key)
            logger.info(f"SSL enabled with cert: {ssl_cert}")


    async def start_server(self) -> None:
        await super().start_server()
        try:
            self.server = await websockets.serve(
                self._connection_handler,
                self.host,
                self.port,
                ssl=self.ssl_context,
                ping_interval=self.ping_interval,
                ping_timeout=self.ping_timeout,
                compression=None,
                close_timeout=10,
            )
            scheme = "wss" if self.ssl_context else "ws"
            logger.info(f"WebSocket server running on {scheme}://{self.host}:{self.port}")
            await self._keep_running()
        except Exception as e:
            logger.error(f"Error starting WebSocket server: {e}")
            raise

    async def _keep_running(self) -> None:
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Server task cancelled")
            await self.shutdown()

    async def send_global_message(self, message: str) -> None:
        send_tasks = []
        for adapter in self.active_connections:
            try:
                send_tasks.append(asyncio.create_task(adapter.send_line(message)))
            except Exception as e:
                logger.error(f"Error preparing to send message: {e}")
        if send_tasks:
            await asyncio.gather(*send_tasks, return_exceptions=True)

    async def shutdown(self) -> None:
        if not self.running:
            return
        logger.info("Shutting down WebSocket server...")
        await super().shutdown()
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        logger.info("WebSocket server has shut down.")

    async def _force_close_connections(self) -> None:
        for adapter in list(self.active_connections):
            try:
                await adapter.close()
                self.active_connections.remove(adapter)
            except Exception as e:
                logger.error(f"Error force closing connection: {e}")

    async def _connection_handler(self, websocket: WebSocketServerProtocol):
        """
        Abstract connection handler.
        Subclasses must implement _connection_handler().
        """
        raise NotImplementedError("Subclasses must implement _connection_handler")
