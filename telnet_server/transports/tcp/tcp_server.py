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
            self.server = await asyncio.start_server(
                self.handle_new_connection,
                self.host,
                self.port
            )
            addr = self.server.sockets[0].getsockname()
            logger.info(f"TCP server running on {addr[0]}:{addr[1]}")
            async with self.server:
                await self.server.serve_forever()
        except Exception as e:
            logger.error(f"Error starting TCP server: {e}")
            raise
    
    async def handle_new_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        # Directly create the handler without reading any initial data.
        handler = self.handler_class(reader, writer)
        handler.server = self
        handler.mode = "simple"          # Set mode to simple, bypassing negotiation.
        handler.initial_data = b""
        self.active_connections.add(handler)
        
        try:
            await self.handle_client(handler)
        except Exception as e:
            addr = getattr(handler, 'addr', 'unknown')
            logger.error(f"Error handling TCP client {addr}: {e}")
        finally:
            try:
                await self.cleanup_connection(handler)
                writer.close()
                try:
                    await asyncio.wait_for(writer.wait_closed(), timeout=5.0)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Error cleaning up TCP client connection: {e}")
            if handler in self.active_connections:
                self.active_connections.remove(handler)
    
    async def handle_client(self, handler: BaseHandler) -> None:
        if hasattr(handler, 'handle_client'):
            await handler.handle_client()
        else:
            raise NotImplementedError("Handler must implement handle_client method")
    
    async def cleanup_connection(self, handler: BaseHandler) -> None:
        if hasattr(handler, 'cleanup'):
            await handler.cleanup()
    
    async def send_global_message(self, message: str) -> None:
        send_tasks = []
        for handler in self.active_connections:
            try:
                if hasattr(handler, 'send_line'):
                    send_tasks.append(asyncio.create_task(handler.send_line(message)))
            except Exception as e:
                logger.error(f"Error preparing to send message to TCP client: {e}")
        if send_tasks:
            await asyncio.gather(*send_tasks, return_exceptions=True)
    
    async def shutdown(self) -> None:
        logger.info("Shutting down TCP server...")
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        await super().shutdown()
        logger.info("TCP server has shut down.")
    
    async def _force_close_connections(self) -> None:
        for handler in list(self.active_connections):
            try:
                if hasattr(handler, 'writer'):
                    handler.writer.close()
                self.active_connections.remove(handler)
            except Exception as e:
                logger.error(f"Error force closing TCP connection: {e}")