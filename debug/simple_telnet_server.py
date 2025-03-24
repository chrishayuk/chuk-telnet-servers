#!/usr/bin/env python3
"""
Minimal Raw Telnet Server

This server does the absolute minimum to handle telnet connections:
1. It prints every byte received in both decimal and hex
2. It echoes exactly what it receives, byte for byte
3. It handles raw input without any assumptions about telnet protocols
"""

import asyncio
import logging
import sys

# Configure logging with raw byte values
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('raw-telnet')

class MinimalTelnetServer:
    def __init__(self, host='0.0.0.0', port=8023):
        self.host = host
        self.port = port
        
    async def start(self):
        """Start the telnet server."""
        server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        
        addr = server.sockets[0].getsockname()
        logger.info(f'Serving on {addr}')
        
        async with server:
            await server.serve_forever()
    
    async def handle_client(self, reader, writer):
        """Handle a client connection with absolute minimal processing."""
        addr = writer.get_extra_info('peername')
        logger.info(f"New connection from {addr}")
        
        # Send welcome message
        welcome = b"Welcome to Raw Telnet Server!\r\n> "
        writer.write(welcome)
        await writer.drain()
        
        # Minimal buffer for inspection
        buffer = b""
        
        try:
            while True:
                # Read raw data
                data = await reader.read(1024)
                if not data:  # Connection closed
                    logger.info(f"Connection closed by client {addr}")
                    break
                
                # Log every byte for detailed inspection
                byte_log = " ".join([f"{b:02X}({b})" for b in data])
                logger.debug(f"Raw bytes: {byte_log}")
                
                # Echo everything back, byte for byte
                writer.write(data)
                await writer.drain()
                
                # Check for CR to add prompt
                if b'\r' in data or b'\n' in data:
                    writer.write(b"\r\n> ")
                    await writer.drain()
                
                # Add to buffer for inspection
                buffer += data
                # Keep buffer manageable
                buffer = buffer[-1024:]
                
                # Simple check for quit commands
                if b'quit' in buffer.lower() or b'exit' in buffer.lower():
                    writer.write(b"\r\nGoodbye!\r\n")
                    await writer.drain()
                    break
                
        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass
            logger.info(f"Connection closed for {addr}")
            # Log the final buffer state for debugging
            logger.debug(f"Final buffer: {buffer}")

async def main():
    """Main entry point."""
    server = MinimalTelnetServer()
    await server.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutdown initiated by user")
        print("\nServer shutdown by user")