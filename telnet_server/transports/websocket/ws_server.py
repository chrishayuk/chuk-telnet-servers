#!/usr/bin/env python3
# telnet_server/transports/websocket/ws_server.py
"""
WebSocket Transport Server

This module provides a WebSocket server implementation that adapts
browser connections to the telnet server framework, allowing browsers
to connect directly without requiring a proxy.
"""

import asyncio
import logging
import ssl
from typing import Type, List
import websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

# websockets are available
WEBSOCKETS_AVAILABLE = True

# Import base handler, base server, and adapter
from telnet_server.handlers.base_handler import BaseHandler
from telnet_server.transports.base_server import BaseServer
from telnet_server.transports.websocket.ws_adapter import WebSocketAdapter

logger = logging.getLogger('websocket-server')


class WebSocketServer(BaseServer):
    """
    WebSocket server implementation for Telnet services.
    """

    def __init__(
        self,
        host: str = '0.0.0.0',
        port: int = 8023,
        handler_class: Type[BaseHandler] = None,
        path: str = '/telnet',
        ssl_cert: str = None,
        ssl_key: str = None,
        ping_interval: int = 30,
        ping_timeout: int = 10,
        allow_origins: List[str] = None
    ):
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError(
                "WebSocket server requires the 'websockets' package. "
                "Install it with: pip install websockets"
            )

        super().__init__(host, port, handler_class)

        self.path = path
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.allow_origins = allow_origins or ['*']
        self.ssl_context = None

        if ssl_cert and ssl_key:
            self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.ssl_context.load_cert_chain(ssl_cert, ssl_key)
            logger.info(f"SSL enabled with cert: {ssl_cert}")

    async def start_server(self) -> None:
        await super().start_server()

        try:
            async def websocket_handler(websocket: WebSocketServerProtocol):
                """
                Handle an incoming WebSocket connection.
                """
                try:
                    # WebSocketServerProtocol in websockets 11+ uses `request` object
                    raw_path = websocket.request.path
                except AttributeError:
                    logger.error("websocket.request.path not available — upgrade websockets or adjust handler")
                    await websocket.close(code=1011, reason="Internal server error")
                    return

                expected_path = self.path if self.path.startswith("/") else f"/{self.path}"
                logger.debug(f"Received connection path: '{raw_path}', Expected path: '{expected_path}'")

                if raw_path != expected_path:
                    logger.warning(f"Rejected connection to invalid path: '{raw_path}'")
                    await websocket.close(code=1003, reason=f"Endpoint {raw_path} not found")
                    return

                try:
                    headers = getattr(websocket, 'request_headers', {})
                    origin = (
                        headers.get('Origin')
                        or headers.get('origin')
                        or headers.get('HTTP_ORIGIN', '')
                    )

                    if (
                        origin
                        and self.allow_origins
                        and '*' not in self.allow_origins
                        and origin not in self.allow_origins
                    ):
                        logger.warning(f"WebSocket origin {origin} not allowed")
                        await websocket.close(code=403, reason="Origin not allowed")
                        return
                except Exception as cors_err:
                    logger.error(f"Error during CORS check: {cors_err}")
                    await websocket.close(code=1011, reason="Internal server error")
                    return

                adapter = WebSocketAdapter(websocket, self.handler_class)
                adapter.server = self

                self.active_connections.add(adapter)
                try:
                    await adapter.handle_client()
                except ConnectionClosed as e:
                    logger.info(f"WebSocket connection closed: {e}")
                except Exception as e:
                    logger.error(f"Error handling WebSocket client: {e}")
                finally:
                    self.active_connections.discard(adapter)

            self.server = await websockets.serve(
                websocket_handler,
                self.host,
                self.port,
                ssl=self.ssl_context,
                ping_interval=self.ping_interval,
                ping_timeout=self.ping_timeout,
                compression=None,
                close_timeout=10,
            )

            scheme = "wss" if self.ssl_context else "ws"
            logger.info(f"WebSocket server running on {scheme}://{self.host}:{self.port}{self.path}")

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
                logger.error(f"Error preparing to send message to client: {e}")
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
                logger.error(f"Error force closing WebSocket connection: {e}")
