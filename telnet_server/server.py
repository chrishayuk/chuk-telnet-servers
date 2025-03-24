#!/usr/bin/env python3
# telnet_server/server.py
"""
Telnet Server Module
Core telnet server implementation with connection management
"""
import asyncio
import logging
import signal
from typing import Dict, Any, Optional, Set, List, Callable, Awaitable, Type

# Import the protocol handler
from telnet_server.telnet_protocol_handlers import BaseProtocolHandler

# Configure logging
logger = logging.getLogger('telnet-server')

class TelnetServer:
    """Telnet server with connection handling capabilities"""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 8023, 
                 handler_class: Type[BaseProtocolHandler] = None):
        """Initialize with host, port, and handler class"""
        self.host = host
        self.port = port
        self.handler_class = handler_class
        self.server = None
        self.active_connections: Set[BaseProtocolHandler] = set()
        self.running = True
    
    async def start_server(self) -> None:
        """Start the telnet server"""
        if not self.handler_class:
            raise ValueError("Handler class must be provided")
        
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
            logger.info(f"Telnet server running on {addr[0]}:{addr[1]}")
            
            async with self.server:
                await self.server.serve_forever()
        except Exception as e:
            logger.error(f"Error starting telnet server: {e}")
            raise
    
    async def handle_new_connection(self, reader: asyncio.StreamReader, 
                                   writer: asyncio.StreamWriter) -> None:
        """Handle a new client connection"""
        # Create handler
        handler = self.handler_class(reader, writer)
        handler.server = self  # Set reference to server
        
        # Add to active connections
        self.active_connections.add(handler)
        
        try:
            # Handle client
            await self.handle_client(handler)
        except Exception as e:
            logger.error(f"Error handling client {handler.addr if hasattr(handler, 'addr') else 'unknown'}: {e}")
        finally:
            # Clean up
            try:
                await self.cleanup_connection(handler)
                writer.close()
                try:
                    await asyncio.wait_for(writer.wait_closed(), timeout=5.0)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Error cleaning up client connection: {e}")
            
            # Remove from active connections
            if handler in self.active_connections:
                self.active_connections.remove(handler)
    
    async def handle_client(self, handler) -> None:
        """
        Handle a client using the handler
        Override this method in subclasses if needed
        """
        if hasattr(handler, 'handle_client'):
            await handler.handle_client()
        else:
            raise NotImplementedError("Handler must implement handle_client method")
    
    async def cleanup_connection(self, handler) -> None:
        """
        Clean up a connection
        Override this method in subclasses if needed
        """
        if hasattr(handler, 'cleanup'):
            await handler.cleanup()
    
    async def send_global_message(self, message: str) -> None:
        """Send a message to all connected clients"""
        send_tasks = []
        for handler in self.active_connections:
            try:
                send_tasks.append(asyncio.create_task(handler.send_line(message)))
            except Exception as e:
                logger.error(f"Error preparing to send message to client: {e}")
        
        if send_tasks:
            await asyncio.gather(*send_tasks, return_exceptions=True)
    
    async def shutdown(self) -> None:
        """Gracefully shut down the server"""
        logger.info("Shutting down telnet server...")
        
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
                if hasattr(handler, 'send_line'):
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
                if hasattr(handler, 'writer'):
                    handler.writer.close()
                self.active_connections.remove(handler)
            except Exception:
                pass
        
        logger.info("Telnet server has shut down.")