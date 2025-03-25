#!/usr/bin/env python3
# telnet_server/transports/tcp/tcp_server.py
"""
TCP Server Module

This module implements a pure TCP server that uses simple linefeed processing.
It bypasses any Telnet negotiation, immediately setting the handler to "simple" mode.
"""

import asyncio
import logging
from typing import Type

from telnet_server.handlers.base_handler import BaseHandler
from telnet_server.transports.base_server import BaseServer

logger = logging.getLogger('tcp-server')

class TCPServer(BaseServer):
    """
    TCP server that provides basic linefeed-based communication.
    
    This server does not attempt Telnet negotiation; it immediately creates
    a handler, sets the mode to "simple", and processes input as plain text.
    """
    
    def __init__(self, host: str = '0.0.0.0', port: int = 8024, handler_class: Type[BaseHandler] = None):
        super().__init__(host, port, handler_class)
        self.transport = "tcp"  # Explicitly mark transport as TCP.
    
    async def start_server(self) -> None:
        await super().start_server()
        try:
            self.server = await self._create_server()
            addr = self.server.sockets[0].getsockname()
            logger.info(f"TCP server running on {addr[0]}:{addr[1]}")
            async with self.server:
                await self.server.serve_forever()
        except Exception as e:
            logger.error(f"Error starting TCP server: {e}")
            raise
    
    async def _create_server(self) -> asyncio.Server:
        """
        Create the asyncio server instance.
        
        Returns:
            The asyncio server instance
        """
        return await asyncio.start_server(
            self.handle_new_connection,
            self.host,
            self.port
        )
    
    def create_handler(self, reader, writer) -> BaseHandler:
        """
        Create a handler instance with mode set to "simple".
        
        Args:
            reader: The stream reader for the client
            writer: The stream writer for the client
            
        Returns:
            The created handler instance
        """
        handler = super().create_handler(reader, writer)
        handler.mode = "simple"  # Set mode to simple, bypassing negotiation
        handler.initial_data = b""
        return handler