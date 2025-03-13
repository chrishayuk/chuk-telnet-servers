#!/usr/bin/env python3
"""
Reusable Telnet Server Framework
Provides a base telnet server that can be extended for different applications
"""
import asyncio
import logging
import signal
from typing import Dict, Any, Optional, Set, List, Callable, Awaitable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# logger
logger = logging.getLogger('telnet-server')

class TelnetProtocolHandler:
    """Base class for implementing telnet protocol handlers"""
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Initialize with reader/writer streams"""
        self.reader = reader
        self.writer = writer
        self.addr = writer.get_extra_info('peername')
        self.running = True
    
    async def send_line(self, message: str) -> None:
        """Send a line to the client with error handling"""
        try:
            self.writer.write(f"{message}\n".encode('utf-8'))
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Error sending data to {self.addr}: {e}")
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
            logger.error(f"Error reading from {self.addr}: {e}")
            return None
    
    async def handle_client(self) -> None:
        """Handle the client connection - override this in subclasses"""
        raise NotImplementedError("Subclasses must implement handle_client")
    
    async def cleanup(self) -> None:
        """Perform cleanup actions - override as needed"""
        pass


class TelnetServer:
    """Base class for reusable telnet servers"""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 8023, 
                 protocol_factory: Callable[..., TelnetProtocolHandler] = None):
        """Initialize with host, port, and protocol factory"""
        self.host = host
        self.port = port
        self.protocol_factory = protocol_factory
        self.server = None
        self.active_connections: Set[TelnetProtocolHandler] = set()
        self.running = True
    
    async def start_server(self) -> None:
        """Start the telnet server"""
        if not self.protocol_factory:
            raise ValueError("Protocol factory must be provided")
        
        try:
            self.server = await asyncio.start_server(
                self.handle_new_connection,
                self.host,
                self.port
            )
            
            # Set up signal handlers for graceful shutdown
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(
                    sig, 
                    lambda: asyncio.create_task(self.shutdown())
                )
            
            addr = self.server.sockets[0].getsockname()
            logger.info(f"Server running on {addr[0]}:{addr[1]}")
            
            async with self.server:
                await self.server.serve_forever()
        except Exception as e:
            logger.error(f"Error starting server: {e}")
            raise
    
    async def handle_new_connection(self, reader: asyncio.StreamReader, 
                                   writer: asyncio.StreamWriter) -> None:
        """Handle a new client connection"""
        # Create protocol handler
        handler = self.protocol_factory(reader, writer)
        
        # Add to active connections
        self.active_connections.add(handler)
        
        try:
            # Handle client
            await handler.handle_client()
        except Exception as e:
            logger.error(f"Error handling client {handler.addr}: {e}")
        finally:
            # Clean up
            try:
                await handler.cleanup()
                writer.close()
                try:
                    await asyncio.wait_for(writer.wait_closed(), timeout=5.0)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Error cleaning up client {handler.addr}: {e}")
            
            # Remove from active connections
            if handler in self.active_connections:
                self.active_connections.remove(handler)
    
    async def shutdown(self) -> None:
        """Gracefully shut down the server"""
        logger.info("Shutting down server...")
        
        # Stop accepting new connections
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # Signal all handlers to stop
        self.running = False
        
        # Send shutdown message to all clients
        shutdown_tasks = []
        for handler in list(self.active_connections):
            try:
                handler.running = False
                shutdown_tasks.append(asyncio.create_task(
                    handler.send_line("\nServer is shutting down. Goodbye!")
                ))
            except Exception:
                pass
        
        # Wait for shutdown messages to be sent
        if shutdown_tasks:
            await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        
        # Wait for connections to close (with timeout)
        wait_time = 5  # seconds
        for i in range(wait_time):
            if not self.active_connections:
                break
            logger.info(f"Waiting for connections to close: {len(self.active_connections)} remaining ({wait_time-i}s)")
            await asyncio.sleep(1)
        
        # Force close any remaining connections
        for handler in list(self.active_connections):
            try:
                handler.writer.close()
                self.active_connections.remove(handler)
            except Exception:
                pass
        
        logger.info("Server has shut down.")