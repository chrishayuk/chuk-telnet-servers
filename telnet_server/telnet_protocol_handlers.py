#!/usr/bin/env python3
# telnet_server/telnet_protocol_handlers.py
"""
Telnet Protocol Handlers

Provides base protocol handlers for different communication styles:
- Line-based communication
- Character-based communication

Designed to be flexible, extensible, and easy to use across different 
types of Telnet server implementations.
"""

import asyncio
import logging
from typing import Optional, List

# Import base handler
from telnet_server.connection_handler import ConnectionHandler

# Configure loggers
line_logger = logging.getLogger('line-protocol')
char_logger = logging.getLogger('character-protocol')

class BaseProtocolHandler(ConnectionHandler):
    """
    Base protocol handler providing common functionality 
    for all communication protocols.
    
    Serves as an abstract base class for more specific protocol implementations.
    """
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Initialize the base protocol handler.
        
        Args:
            reader (asyncio.StreamReader): Input stream for reading data
            writer (asyncio.StreamWriter): Output stream for writing data
        """
        super().__init__(reader, writer)
        
        # Input management
        self.input_buffer: List[str] = []
        self.command_history: List[str] = []
        self.history_index: Optional[int] = None

    async def send_line(self, message: str) -> None:
        """
        Send a line of text to the client with carriage return and line feed.
        
        Provides a standard method for sending complete messages.
        
        Args:
            message (str): Message to send
        """
        try:
            await self.write_raw(f"{message}\r\n".encode('utf-8'))
        except Exception as e:
            line_logger.error(f"Error sending line to {self.addr}: {e}")
            raise

    async def send_raw(self, data: bytes) -> None:
        """
        Send raw bytes to the client.
        
        Args:
            data (bytes): Raw data to send
        """
        try:
            self.writer.write(data)
            await self.writer.drain()
        except Exception as e:
            line_logger.error(f"Error sending raw data to {self.addr}: {e}")
            raise

    async def cleanup(self) -> None:
        """
        Perform standard cleanup operations when the connection is closed.
        
        Ensures proper resource release and logging.
        """
        try:
            # Close the writer
            self.writer.close()
            await self.writer.wait_closed()
        except Exception as e:
            line_logger.error(f"Error during connection cleanup: {e}")
        
        line_logger.info(f"Connection closed for {self.addr}")


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
            timeout (float): Maximum time to wait for a line (default: 5 minutes)
        
        Returns:
            Optional[str]: The read line, or None if connection is closed
        """
        try:
            # Wait for a complete line with timeout
            data = await asyncio.wait_for(self.reader.readline(), timeout=timeout)
            
            # Check for connection closure
            if not data:
                return None
            
            # Decode and clean the line
            return data.decode('utf-8', errors='ignore').strip()
        
        except asyncio.TimeoutError:
            # Reraise timeout to allow caller-specific handling
            raise
        
        except Exception as e:
            line_logger.error(f"Error reading line from {self.addr}: {e}")
            return None

    async def handle_client(self) -> None:
        """
        Default implementation for line-based client handling.
        
        Provides a basic template for line-oriented communication.
        Subclasses should override with specific protocol logic.
        """
        try:
            # Send initial welcome message
            await self.send_line("Welcome to the Line-Based Telnet Server")

            # Main processing loop
            while self.running:
                try:
                    # Read a line with timeout
                    line = await self.read_line()
                    
                    # Handle connection closure
                    if line is None:
                        break
                    
                    # Process the line (to be implemented by subclasses)
                    await self.process_line(line)
                
                except asyncio.TimeoutError:
                    # Handle potential timeout (optional)
                    continue
                
                except Exception as e:
                    line_logger.error(f"Error in client handler: {e}")
                    break
        
        finally:
            # Ensure cleanup
            await self.cleanup()

    async def process_line(self, line: str) -> None:
        """
        Process a single line of input.
        
        This is a placeholder method that should be overridden by subclasses
        to provide specific line processing logic.
        
        Args:
            line (str): The line of text to process
        """
        raise NotImplementedError(
            "Subclasses must implement specific line processing logic"
        )


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
            timeout (Optional[float]): Maximum time to wait for a character
        
        Returns:
            Optional[str]: The read character, or None if connection is closed
        """
        try:
            # Read a single byte
            char_bytes = await asyncio.wait_for(self.reader.read(1), timeout=timeout)
            
            # Check for end of transmission
            if not char_bytes:
                return None
            
            # Convert to character, handling potential encoding issues
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
        Subclasses should override with specific protocol logic and welcome message.
        """
        try:
            # Main processing loop
            while self.running:
                try:
                    # Read a single character
                    char = await self.read_character()
                    
                    # Handle connection closure
                    if char is None:
                        break
                    
                    # Process the character (to be implemented by subclasses)
                    should_continue = await self.process_character(char)
                    
                    # Break if processing indicates termination
                    if not should_continue:
                        break
                
                except Exception as e:
                    char_logger.error(f"Error in character processing: {e}")
                    break
        
        finally:
            # Ensure cleanup
            await self.cleanup()

    async def process_character(self, char: str) -> bool:
        """
        Process a single character.
        
        This is a placeholder method that should be overridden by subclasses
        to provide specific character processing logic.
        
        Args:
            char (str): The character to process
        
        Returns:
            bool: Whether to continue processing (False to terminate)
        """
        raise NotImplementedError(
            "Subclasses must implement specific character processing logic"
        )