#!/usr/bin/env python3
# telnet_server/server.py
"""
Telnet Server Module

Core telnet server implementation with connection management.
This module provides the foundation for hosting telnet services
with proper connection lifecycle management and graceful shutdown.
"""
import asyncio
import logging
from typing import Dict, Any, Optional, Set, List, Type

# Import the protocol handler and base server
from telnet_server.handlers.base_handler import BaseHandler
from telnet_server.transports.base_server import BaseServer

# Configure logging
logger = logging.getLogger('telnet-server')

class TelnetServer(BaseServer):
    """
    Telnet server with connection handling capabilities.
    
    This class manages the lifecycle of a telnet server, including
    starting and stopping the server, handling client connections,
    and providing utilities for server-wide operations.
    """
    
    def __init__(self, host: str = '0.0.0.0', port: int = 8023, 
                 handler_class: Type[BaseHandler] = None):
        """
        Initialize the telnet server with host, port, and handler class.
        
        Args:
            host: Host address to bind to
            port: Port number to listen on
            handler_class: Handler class to use for client connections
        """
        super().__init__(host, port, handler_class)
    
    async def start_server(self) -> None:
        """
        Start the telnet server.
        
        This method starts the server listening for connections
        on the specified host and port, and sets up signal handlers
        for graceful shutdown.
        
        Raises:
            ValueError: If no handler class was provided
            Exception: If an error occurs while starting the server
        """
        # Call the base implementation to validate handler class
        await super().start_server()
        
        try:
            self.server = await asyncio.start_server(
                self.handle_new_connection,
                self.host,
                self.port
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
        """
        Handle a new client connection.
        
        This method creates a handler instance for the new client,
        adds it to the active connections, and starts processing.
        
        Args:
            reader: The stream reader for the client
            writer: The stream writer for the client
        """
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
    
    async def handle_client(self, handler: BaseHandler) -> None:
        """
        Handle a client using the handler.
        
        This method delegates client handling to the handler's
        handle_client method.
        
        Args:
            handler: The handler for the client
            
        Raises:
            NotImplementedError: If the handler doesn't implement handle_client
        """
        if hasattr(handler, 'handle_client'):
            await handler.handle_client()
        else:
            raise NotImplementedError("Handler must implement handle_client method")
    
    async def cleanup_connection(self, handler: BaseHandler) -> None:
        """
        Clean up a connection.
        
        This method delegates connection cleanup to the handler's
        cleanup method.
        
        Args:
            handler: The handler for the client
        """
        if hasattr(handler, 'cleanup'):
            await handler.cleanup()
    
    async def send_global_message(self, message: str) -> None:
        """
        Send a message to all connected clients.
        
        This method sends a message to all active connections,
        which can be useful for broadcasts or server-wide notifications.
        
        Args:
            message: The message to send
        """
        send_tasks = []
        for handler in self.active_connections:
            try:
                if hasattr(handler, 'send_line'):
                    send_tasks.append(asyncio.create_task(handler.send_line(message)))
            except Exception as e:
                logger.error(f"Error preparing to send message to client: {e}")
        
        if send_tasks:
            await asyncio.gather(*send_tasks, return_exceptions=True)
    
    async def shutdown(self) -> None:
        """
        Gracefully shut down the server.
        
        This method stops accepting new connections, notifies all
        clients of the shutdown, and closes all active connections.
        """
        logger.info("Shutting down telnet server...")
        
        # Stop accepting new connections
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # Call base class implementation to handle common shutdown tasks
        await super().shutdown()
        
        logger.info("Telnet server has shut down.")
    
    async def _force_close_connections(self) -> None:
        """
        Force close all remaining connections.
        
        This method forcibly closes any connections that didn't
        close gracefully during shutdown.
        """
        for handler in list(self.active_connections):
            try:
                if hasattr(handler, 'writer'):
                    handler.writer.close()
                self.active_connections.remove(handler)
            except Exception as e:
                logger.error(f"Error force closing connection: {e}")