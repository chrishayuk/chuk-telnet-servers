#!/usr/bin/env python3
"""
Echo Telnet Server Example
A simple telnet server that echoes back what the client sends
"""
import asyncio
import logging
import sys
from typing import Optional

# Import the base classes
from telnet_server.protocol_handler import TelnetProtocolHandler

# Configure logging
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

    async def cleanup(self) -> None:
        """Optional cleanup method"""
        logger.info(f"Cleaning up connection for {self.addr}")
        
# Optional: Direct server startup method (for local testing)
def main():
    """Main function for direct server startup"""
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