#!/usr/bin/env python3
# telnet_server/base_protocol_handler.py
"""
Base Protocol Handler Module

Provides the BaseProtocolHandler class with common functionality for all
Telnet protocol handlers, such as sending messages and cleanup.
This class is kept minimal and does not include command history.
"""

import asyncio
import logging
from typing import List

# Adjust the import path as needed for your project structure.
from telnet_server.protocol_handlers.connection_handler import ConnectionHandler

logger = logging.getLogger('base-protocol')

class BaseProtocolHandler(ConnectionHandler):
    """
    Base protocol handler providing common functionality for all communication protocols.
    """

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Initialize the base protocol handler.

        Args:
            reader (asyncio.StreamReader): Input stream for reading data.
            writer (asyncio.StreamWriter): Output stream for writing data.
        """
        super().__init__(reader, writer)
        self.input_buffer: List[str] = []  # Basic input management (without history)

    async def send_line(self, message: str) -> None:
        """
        Send a line of text to the client with carriage return and line feed.

        Args:
            message (str): Message to send.
        """
        try:
            await self.write_raw(f"{message}\r\n".encode('utf-8'))
        except Exception as e:
            logger.error(f"Error sending line to {self.addr}: {e}")
            raise

    async def send_raw(self, data: bytes) -> None:
        """
        Send raw bytes to the client.

        Args:
            data (bytes): Raw data to send.
        """
        try:
            self.writer.write(data)
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Error sending raw data to {self.addr}: {e}")
            raise

    async def cleanup(self) -> None:
        """
        Perform cleanup operations when the connection is closed.
        """
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception as e:
            logger.error(f"Error during cleanup for {self.addr}: {e}")
        logger.info(f"Connection closed for {self.addr}")
