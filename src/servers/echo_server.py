#!/usr/bin/env python3
# src/servers/echo_server.py
"""
Echo Telnet Server Example
A simple telnet server that echoes back what the client sends
"""
import asyncio
import logging
import os
import sys
from typing import List, Dict, Any

# imports
from telnet_server import TelnetServer, TelnetProtocolHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# setup the loggers
logger = logging.getLogger('echo-telnet-server')

class EchoTelnetHandler(TelnetProtocolHandler):
    """Handler for echo telnet sessions"""

    async def handle_client(self) -> None:
        """Handle a client connection"""
        logger.info(f"New connection from {self.addr}")
        
        # Send welcome message
        await self.send_line("Welcome to the Echo Server!")
        await self.send_line("Type any message and I'll echo it back.")
        await self.send_line("Type 'quit' to disconnect.")
        
        await self.send_line("\n> ")
        
        # Main loop
        while self.running:
            try:
                # Read a line from the client
                message = await self.read_line(timeout=300)
                
                # Handle disconnection
                if message is None:
                    logger.info(f"Client {self.addr} closed connection")
                    break
                
                # Log the message
                logger.info(f"Received from {self.addr}: {message}")
                
                # Check for quit command
                if message.lower() == 'quit':
                    await self.send_line("Goodbye!")
                    break
                
                # Echo the message back
                await self.send_line(f"Echo: {message}")
                
                # Prompt for the next message
                await self.send_line("\n> ")
                
            except asyncio.TimeoutError:
                # Check if we're still running
                if not self.running:
                    break
            
            except Exception as e:
                logger.error(f"Error in echo loop for {self.addr}: {e}")
                if "Connection reset" in str(e) or "Broken pipe" in str(e):
                    break
                else:
                    await asyncio.sleep(1)


class EchoTelnetServer(TelnetServer):
    """Simple echo telnet server"""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 8023):
        """Initialize the echo server"""
        super().__init__(host, port, EchoTelnetHandler)


def main():
    """Main function"""
    try:
        # Create and start the echo server
        server = EchoTelnetServer()
        asyncio.run(server.start_server())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt.")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
    finally:
        logger.info("Server process exiting.")


if __name__ == "__main__":
    # call main
    main()