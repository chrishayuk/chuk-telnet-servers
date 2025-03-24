#!/usr/bin/env python3
# telnetserver/protocol_handler.py
"""
Telnet Protocol Handler Module
Extends the ConnectionHandler with telnet-specific functionality
"""
import asyncio
import logging
from typing import Optional

# Import base handler
from telnet_server.connection_handler import ConnectionHandler

# Configure logger
logger = logging.getLogger('telnet-protocol')

class TelnetProtocolHandler(ConnectionHandler):
    """Handler for telnet protocol connections"""
    
    async def send_line(self, message: str) -> None:
        """Send a line to the client with error handling"""
        try:
            await self.write_raw(f"{message}\n".encode('utf-8'))
        except Exception as e:
            logger.error(f"Error sending line to {self.addr}: {e}")
            raise
    
    async def read_line(self, timeout: float = 300) -> Optional[str]:
        """Read a line from the client with timeout and error handling"""
        try:
            data = await asyncio.wait_for(self.reader.readline(), timeout=timeout)
            if not data:  # Connection closed
                return None
            return data.decode('utf-8', errors='ignore').strip()
        except asyncio.TimeoutError:
            raise  # Let the caller handle timeouts
        except Exception as e:
            logger.error(f"Error reading line from {self.addr}: {e}")
            return None