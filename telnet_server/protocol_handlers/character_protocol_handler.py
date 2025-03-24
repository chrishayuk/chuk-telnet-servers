#!/usr/bin/env python3
# telnet_server/protocol_handlers/character_protocol_handler.py
"""
Character-based Protocol Handler Module

Provides a handler for interactive, real-time communication by reading 
and processing individual characters. This class inherits from BaseProtocolHandler.
"""
import asyncio
import logging
from typing import Optional

# imports
from telnet_server.protocol_handlers.base_protocol_handler import BaseProtocolHandler

# logger
char_logger = logging.getLogger('character-protocol')

class CharacterProtocolHandler(BaseProtocolHandler):
    """
    Character-based protocol handler for interactive, real-time communication.
    
    Provides methods for reading and processing individual characters,
    allowing for more nuanced and interactive communication styles.
    """

    async def read_character(self, timeout: Optional[float] = None) -> Optional[str]:
        """
        Read a single character from the input stream.
        
        Args:
            timeout (Optional[float]): Maximum time to wait for a character.
        
        Returns:
            Optional[str]: The read character, or None if connection is closed.
        """
        try:
            # Read a single byte
            char_bytes = await asyncio.wait_for(self.reader.read(1), timeout=timeout)
            if not char_bytes:
                return None  # Connection closed
            return char_bytes.decode('utf-8', errors='ignore')
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            char_logger.error(f"Error reading character from {self.addr}: {e}")
            return None

    async def handle_client(self) -> None:
        """
        Default implementation for character-based client handling.
        
        Provides a basic template for character-oriented communication.
        Subclasses should override process_character() to implement specific logic.
        """
        try:
            while self.running:
                try:
                    char = await self.read_character()
                    if char is None:  # Connection closed
                        break
                    # Process the character (subclasses implement process_character)
                    should_continue = await self.process_character(char)
                    if not should_continue:
                        break
                except Exception as e:
                    char_logger.error(f"Error in character processing: {e}")
                    break
        finally:
            await self.cleanup()

    async def process_character(self, char: str) -> bool:
        """
        Process a single character.
        
        This placeholder method should be overridden by subclasses to provide
        specific character processing logic.
        
        Args:
            char (str): The character to process.
        
        Returns:
            bool: True to continue processing; False to terminate.
        """
        raise NotImplementedError("Subclasses must implement specific character processing logic")
