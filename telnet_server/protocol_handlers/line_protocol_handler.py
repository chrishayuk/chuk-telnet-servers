#!/usr/bin/env python3
# telnet_server/protocol_handlers/line_protocol_handler.py
"""
Line-based Protocol Handler Module

Provides a handler for traditional line-oriented communication. This class
inherits from BaseProtocolHandler and includes methods for reading complete
lines and processing them.
"""
import asyncio
import logging
from typing import Optional

# imports
from telnet_server.protocol_handlers.base_protocol_handler import BaseProtocolHandler

line_logger = logging.getLogger('line-protocol')

class LineProtocolHandler(BaseProtocolHandler):
    """
    Line-based protocol handler for traditional line-oriented communication.
    
    Provides methods for reading and writing complete lines of text.
    Suitable for protocols where entire lines are processed at once.
    """

    async def read_line(self, timeout: float = 300) -> Optional[str]:
        """
        Read a complete line from the client with timeout and error handling.
        
        Args:
            timeout (float): Maximum time to wait for a line (default: 5 minutes).
        
        Returns:
            Optional[str]: The read line, or None if connection is closed.
        """
        try:
            data = await asyncio.wait_for(self.reader.readline(), timeout=timeout)
            if not data:
                return None  # Connection closed
            return data.decode('utf-8', errors='ignore').strip()
        except asyncio.TimeoutError:
            raise  # Let the caller handle timeouts if desired
        except Exception as e:
            line_logger.error(f"Error reading line from {self.addr}: {e}")
            return None

    async def handle_client(self) -> None:
        """
        Default implementation for line-based client handling.
        
        Provides a basic template for line-oriented communication.
        Subclasses should override process_line() to implement specific logic.
        """
        try:
            await self.send_line("Welcome to the Line-Based Telnet Server")
            while self.running:
                try:
                    line = await self.read_line()
                    if line is None:
                        break  # Connection closed
                    await self.process_line(line)
                except asyncio.TimeoutError:
                    continue  # Optionally handle timeouts
                except Exception as e:
                    line_logger.error(f"Error in client handler: {e}")
                    break
        finally:
            await self.cleanup()

    async def process_line(self, line: str) -> None:
        """
        Process a single line of input.
        
        This placeholder method should be overridden by subclasses to provide
        specific line processing logic.
        
        Args:
            line (str): The line of text to process.
        """
        raise NotImplementedError("Subclasses must implement specific line processing logic")
