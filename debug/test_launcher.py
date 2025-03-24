#!/usr/bin/env python3
"""
Test Telnet Server Launcher

This script launches a test telnet server with the updated TelnetProtocolHandler.
"""

import asyncio
import logging
import sys
import os

# Add the parent directory to the Python path so we can import the telnet_server modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Set up logging first
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Create a logger for this module
logger = logging.getLogger('test-server')

# Import server classes
from telnet_server.server import TelnetServer
from telnet_server.protocols.telnet_protocol_handler import TelnetProtocolHandler

class TestEchoHandler(TelnetProtocolHandler):
    """A simple echo handler for testing."""
    
    async def on_command_submitted(self, command):
        """Override to provide custom echo behavior."""
        await self.send_line(f"You typed: {command}")

async def run_server(host="0.0.0.0", port=8023):
    """Run the telnet server."""
    # Create the server with our handler
    server = TelnetServer(host, port, TestEchoHandler)
    
    # Start the server
    logger.info(f"Starting test server on {host}:{port}")
    await server.start_server()

def main():
    """Main entry point."""
    try:
        # Run the server
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server shutdown initiated by user")
    except Exception as e:
        logger.error(f"Error running server: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())