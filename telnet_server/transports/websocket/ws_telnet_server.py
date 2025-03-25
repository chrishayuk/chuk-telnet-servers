#!/usr/bin/env python3
# telnet_server/transports/websocket/ws_telnet_server.py
"""
WebSocket Telnet Server

This server accepts WebSocket connections and performs Telnet negotiation
over the WebSocket transport. It adapts the WebSocket connection to behave
like a Telnet connection.
"""

import asyncio
import logging
import ssl
from typing import Type, List

import websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

from telnet_server.handlers.base_handler import BaseHandler
from telnet_server.transports.websocket.base_ws_server import BaseWebSocketServer
from telnet_server.transports.websocket.ws_adapter import WebSocketAdapter

logger = logging.getLogger('ws-telnet-server')

class WSTelnetServer(BaseWebSocketServer):
    """
    WebSocket Telnet server that performs Telnet negotiation over WebSocket.
    """
    def __init__(
        self,
        host: str = '0.0.0.0',
        port: int = 8026,
        handler_class: Type[BaseHandler] = None,
        path: str = '/ws_telnet',
        ssl_cert: str = None,
        ssl_key: str = None,
        ping_interval: int = 30,
        ping_timeout: int = 10,
        allow_origins: List[str] = None
    ):
        """
        Initialize the WebSocket Telnet server.

        Args:
            host: Host address to bind to.
            port: Port number to listen on.
            handler_class: The handler class to handle Telnet negotiation and data.
            path: The WebSocket path (default /ws_telnet).
            ssl_cert: Path to SSL certificate (optional).
            ssl_key: Path to SSL key (optional).
            ping_interval: Interval in seconds for WebSocket pings.
            ping_timeout: Timeout in seconds for WebSocket pings.
            allow_origins: List of allowed origins for CORS checks (default: ['*']).
        """
        super().__init__(host, port, handler_class, ping_interval, ping_timeout, allow_origins)
        self.path = path
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        self.transport = "ws_telnet"
        self.ssl_context = None
        if ssl_cert and ssl_key:
            import ssl
            self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.ssl_context.load_cert_chain(ssl_cert, ssl_key)
            logger.info(f"SSL enabled with cert: {ssl_cert}")

    async def _connection_handler(self, websocket: WebSocketServerProtocol):
        """
        Handle an incoming WebSocket connection for Telnet negotiation.
        
        This checks the requested path, optionally performs CORS checks,
        and then uses a WebSocketAdapter to invoke the Telnet handler logic.
        """
        # Validate the WebSocket path.
        try:
            raw_path = websocket.request.path
        except AttributeError:
            logger.error("WS Telnet: websocket.request.path not available")
            await websocket.close(code=1011, reason="Internal server error")
            return

        expected_path = self.path if self.path.startswith("/") else f"/{self.path}"
        logger.debug(f"WS Telnet: Received path: '{raw_path}', expected: '{expected_path}'")
        if raw_path != expected_path:
            logger.warning(f"WS Telnet: Rejected connection to invalid path: '{raw_path}'")
            await websocket.close(code=1003, reason=f"Endpoint {raw_path} not found")
            return

        # Optional CORS check.
        try:
            headers = getattr(websocket, "request_headers", {})
            origin = headers.get("Origin") or headers.get("origin") or headers.get("HTTP_ORIGIN", "")
            if origin and self.allow_origins and '*' not in self.allow_origins and origin not in self.allow_origins:
                logger.warning(f"WS Telnet: Origin '{origin}' not allowed")
                await websocket.close(code=403, reason="Origin not allowed")
                return
        except Exception as err:
            logger.error(f"WS Telnet: CORS check error: {err}")
            await websocket.close(code=1011, reason="Internal server error")
            return

        # Create a WebSocket adapter that defers to the Telnet handler.
        adapter = WebSocketAdapter(websocket, self.handler_class)
        adapter.server = self
        # In ws_telnet mode, do NOT set mode to 'simple'; let Telnet negotiation proceed.
        self.active_connections.add(adapter)
        try:
            await adapter.handle_client()
        except ConnectionClosed as e:
            logger.info(f"WS Telnet: Connection closed: {e}")
        except Exception as e:
            logger.error(f"WS Telnet: Error handling client: {e}")
        finally:
            self.active_connections.discard(adapter)
