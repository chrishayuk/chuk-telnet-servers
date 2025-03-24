#!/usr/bin/env python3
"""
Character-Level Echo Telnet Server

A Telnet server that demonstrates minimal processing,
only acting when a full line is submitted.

Key Features:
- Minimal character-level processing
- Line submission handling
- Clean, straightforward interaction
"""

import asyncio
import logging
import sys

# Import the character-based protocol handler
from telnet_server.telnet_protocol_handlers import CharacterProtocolHandler

# Configure logging
logger = logging.getLogger('echo-telnet-server')

class EchoTelnetHandler(CharacterProtocolHandler):
    """
    Interactive Telnet handler that processes input only on line submission.
    
    Provides:
    - Minimal server-side character processing
    - Line-based interaction
    - Simple command handling
    """

    async def process_character(self, char: str) -> bool:
        """
        Process individual characters with minimal handling.
        
        Only acts on specific control characters:
        - Enter key for line submission
        - Ctrl-C for interrupt
        
        Args:
            char (str): Single character input
        
        Returns:
            bool: Whether to continue processing (False to exit)
        """
        # Handle line submission (Enter key)
        if char in {'\r', '\n'}:
            # Construct the line from input buffer
            line = ''.join(self.input_buffer)
            
            # Clear the input buffer
            self.input_buffer.clear()
            
            # Log the received message
            logger.info(f"Received from {self.addr}: {line}")
            
            # Process special commands
            if line.lower() in ['quit', 'exit', 'q']:
                await self.send_line("Goodbye!")
                return False
            
            # Echo the entire line back
            await self.send_line(line)
            
            # Provide new prompt
            await super().send_raw(b'> ')
        
        # Handle interrupt (Ctrl-C)
        elif char == '\x03':  # Ctrl-C
            await self.send_line("^C")
            self.input_buffer.clear()
            await super().send_raw(b'\r\n> ')
        
        # Accumulate input characters for line submission
        elif char in {'\x7f', '\b'}:  # Delete or Backspace
            if self.input_buffer:
                # Remove last character from buffer
                self.input_buffer.pop()
        
        # Regular character input (just accumulate)
        else:
            # Add character to input buffer
            self.input_buffer.append(char)
        
        return True

    async def handle_client(self) -> None:
        """
        Customize the client handling to provide a welcoming experience.
        
        Sends initial instructions and sets up the interactive environment.
        """
        # Log new connection
        logger.info(f"New connection from {self.addr}")
        
        # Send welcome and usage instructions
        await self.send_line("Welcome to the Character-Level Echo Server!")
        await self.send_line("- Type your message")
        await self.send_line("- Press Enter to submit")
        await self.send_line("- Type 'quit' to exit")
        await self.send_line("- Ctrl-C will clear your current input")
        await super().send_raw(b'\r\n> ')
        
        # Call the base class's handle_client 
        await super().handle_client()

# Optional: Direct server startup method (for local testing)
def main():
    """
    Provide a direct launch method for the echo server.
    
    Supports launching the server directly or through the server launcher.
    """
    try:
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Use the server launcher from the framework
        from telnet_server.server_launcher import main as server_launcher
        
        # Simulate command-line arguments to use this module's handler
        import sys
        sys.argv = [
            sys.argv[0], 
            f"{__name__}:EchoTelnetHandler",  # Dynamically get the handler path
            '--host', '0.0.0.0',
            '--port', '8023'
        ]
        
        # Run the server launcher
        server_launcher()
    
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt.")
    
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
    
    finally:
        logger.info("Server process exiting.")

if __name__ == "__main__":
    main()