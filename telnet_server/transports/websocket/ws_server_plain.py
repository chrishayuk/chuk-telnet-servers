#!/usr/bin/env python3
# telnet_server/transports/websocket/ws_server_plain.py
"""
Plain WebSocket Server

Accepts WebSocket connections as plain text, skipping Telnet negotiation.
"""

import asyncio
import logging
from typing import Type, Optional, List

import websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

from telnet_server.handlers.base_handler import BaseHandler
from telnet_server.transports.websocket.base_ws_server import BaseWebSocketServer
from telnet_server.transports.websocket.ws_adapter import WebSocketAdapter

logger = logging.getLogger('ws-plain-server')

class PlainWebSocketServer(BaseWebSocketServer):
    """
    Plain WebSocket server that processes incoming messages as plain text
    (no Telnet negotiation), with optional TLS if ssl_cert and ssl_key are given.
    """
    
    def __init__(
        self,
        host: str = '0.0.0.0',
        port: int = 8023,
        handler_class: Type[BaseHandler] = None,
        path: str = '/ws',
        ping_interval: int = 30,
        ping_timeout: int = 10,
        allow_origins: Optional[List[str]] = None,
        ssl_cert: Optional[str] = None,
        ssl_key: Optional[str] = None,
    ):
        super().__init__(
            host=host,
            port=port,
            handler_class=handler_class,
            ping_interval=ping_interval,
            ping_timeout=ping_timeout,
            allow_origins=allow_origins,
            ssl_cert=ssl_cert,
            ssl_key=ssl_key
        )
        self.path = path
        self.transport = "websocket"

    async def _connection_handler(self, websocket: WebSocketServerProtocol):
        """
        Handle a WebSocket connection in plain text mode.
        """
        # Validate request path
        try:
            raw_path = websocket.request.path
        except AttributeError:
            logger.error("Plain WS: websocket.request.path not available")
            await websocket.close(code=1011, reason="Internal server error")
            return

        expected_path = self.path if self.path.startswith("/") else f"/{self.path}"
        logger.debug(f"Plain WS: path='{raw_path}', expected='{expected_path}'")
        if raw_path != expected_path:
            logger.warning(f"Plain WS: Rejected connection: invalid path '{raw_path}'")
            await websocket.close(code=1003, reason=f"Invalid path {raw_path}")
            return

        # Optional CORS check
        try:
            headers = getattr(websocket, 'request_headers', {})
            origin = headers.get('Origin') or headers.get('origin') or headers.get('HTTP_ORIGIN', '')
            if origin and self.allow_origins and ('*' not in self.allow_origins) and (origin not in self.allow_origins):
                logger.warning(f"Plain WS: Origin '{origin}' not allowed")
                await websocket.close(code=403, reason="Origin not allowed")
                return
        except Exception as err:
            logger.error(f"Plain WS: CORS error: {err}")
            await websocket.close(code=1011, reason="CORS error")
            return

        # Create an adapter in "simple" mode to skip Telnet negotiation
        adapter = WebSocketAdapter(websocket, self.handler_class)
        adapter.server = self
        adapter.mode = "simple"
        self.active_connections.add(adapter)
        try:
            await adapter.handle_client()
        except ConnectionClosed as e:
            logger.info(f"Plain WS: Connection closed: {e}")
        except Exception as e:
            logger.error(f"Plain WS: Error handling client: {e}")
        finally:
            self.active_connections.discard(adapter)
