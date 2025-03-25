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
from typing import Type, List, Optional, Any
from abc import abstractmethod

import websockets
from websockets.server import WebSocketServerProtocol

from telnet_server.handlers.base_handler import BaseHandler
from telnet_server.transports.base_server import BaseServer

logger = logging.getLogger('base-ws-server')

class BaseWebSocketServer(BaseServer):
    """
    Base class for WebSocket servers. Handles common WebSocket functionality.
    Subclasses must implement the _connection_handler method.
    """
    
    def __init__(
        self,
        host: str = '0.0.0.0',
        port: int = 8025,
        handler_class: Type[BaseHandler] = None,
        ping_interval: int = 30,
        ping_timeout: int = 10,
        allow_origins: Optional[List[str]] = None,
        ssl_cert: Optional[str] = None,
        ssl_key: Optional[str] = None
    ):
        """
        Initialize the WebSocket server.
        
        Args:
            host: Host address to bind to
            port: Port number to listen on
            handler_class: Handler class to use for client connections
            ping_interval: Interval between WebSocket ping frames
            ping_timeout: Timeout for WebSocket ping responses
            allow_origins: List of allowed origins for CORS
            ssl_cert: Path to SSL certificate file
            ssl_key: Path to SSL key file
        """
        super().__init__(host, port, handler_class)
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.allow_origins = allow_origins or ['*']
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        self.ssl_context = None
        
        # Set up SSL context if certificates provided
        if ssl_cert and ssl_key:
            self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.ssl_context.load_cert_chain(ssl_cert, ssl_key)
            logger.info(f"SSL enabled with cert: {ssl_cert}")

    async def start_server(self) -> None:
        """
        Start the WebSocket server.
        
        This method starts the server listening for connections
        on the specified host and port.
        
        Raises:
            ValueError: If no handler class was provided
            Exception: If an error occurs while starting the server
        """
        await super().start_server()
        try:
            self.server = await self._create_server()
            
            scheme = "wss" if self.ssl_context else "ws"
            logger.info(f"WebSocket server running on {scheme}://{self.host}:{self.port}")
            
            # Keep the server running
            await self._keep_running()
        except Exception as e:
            logger.error(f"Error starting WebSocket server: {e}")
            raise

    async def _create_server(self) -> Any:
        """
        Create the WebSocket server instance.
        
        Returns:
            The WebSocket server instance
        """
        return await websockets.serve(
            self._connection_handler,
            self.host,
            self.port,
            ssl=self.ssl_context,
            ping_interval=self.ping_interval,
            ping_timeout=self.ping_timeout,
            compression=None,
            close_timeout=10
        )

    async def _keep_running(self) -> None:
        """
        Keep the server running until shutdown is requested.
        """
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("WebSocket server task cancelled")
            await self.shutdown()

    async def _close_server(self) -> None:
        """
        Close the WebSocket server.
        """
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def _force_close_connections(self) -> None:
        """
        Force close all remaining WebSocket connections.
        """
        for adapter in list(self.active_connections):
            try:
                await adapter.close()
                self.active_connections.remove(adapter)
            except Exception as e:
                logger.error(f"Error force closing WebSocket connection: {e}")

    @abstractmethod
    async def _connection_handler(self, websocket: WebSocketServerProtocol) -> None:
        """
        Handle a new WebSocket connection.
        
        This method must be implemented by subclasses to handle
        WebSocket-specific connection setup and processing.
        
        Args:
            websocket: The WebSocket connection
        """
        pass