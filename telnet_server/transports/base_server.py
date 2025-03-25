#!/usr/bin/env python3
# telnet_server/transports/base_server.py
"""
Base Server Interface

This module defines the abstract base class that all server implementations
must inherit from to work with the telnet server framework. It provides common
functionality and enforces a consistent interface across different transports.
"""
import asyncio
import logging
import signal
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Set, Type, List

# Import base handler
from telnet_server.handlers.base_handler import BaseHandler

# Configure logging
logger = logging.getLogger('base-server')

class BaseServer(ABC):
    """
    Abstract base class for server implementations.
    
    This class defines the common interface and functionality that all
    server implementations must provide, ensuring consistency across
    different transport protocols.
    """
    
    def __init__(self, host: str = '0.0.0.0', port: int = 8023,
                 handler_class: Type[BaseHandler] = None):
        """
        Initialize the server with host, port, and handler class.
        
        Args:
            host: Host address to bind to
            port: Port number to listen on
            handler_class: Handler class to use for client connections
        """
        self.host = host
        self.port = port
        self.handler_class = handler_class
        self.server = None
        self.active_connections = set()
        self.running = True
    
    @abstractmethod
    async def start_server(self) -> None:
        """
        Start the server.
        
        This method should start the server listening for connections
        on the specified host and port, and set up any necessary
        signal handlers for graceful shutdown.
        
        Raises:
            ValueError: If no handler class was provided
            Exception: If an error occurs while starting the server
        """
        # Validate handler class is provided
        if not self.handler_class:
            raise ValueError("Handler class must be provided")
        
        # Set up signal handlers (implementation specific)
        await self._setup_signal_handlers()
    
    @abstractmethod
    async def shutdown(self) -> None:
        """
        Gracefully shut down the server.
        
        This method should stop accepting new connections, notify all
        clients of the shutdown, and close all active connections.
        """
        logger.info(f"Shutting down {self.__class__.__name__}...")
        
        # Signal all connections to stop
        self.running = False
        
        # Send shutdown message
        await self.send_global_message("\nServer is shutting down. Goodbye!")
        
        # Wait for connections to close (with timeout)
        await self._wait_for_connections_to_close()
    
    @abstractmethod
    async def send_global_message(self, message: str) -> None:
        """
        Send a message to all connected clients.
        
        Args:
            message: The message to send
        """
        pass
    
    async def _setup_signal_handlers(self) -> None:
        """
        Set up signal handlers for graceful shutdown.
        
        This method registers SIGINT and SIGTERM handlers to allow
        for graceful shutdown when the server is terminated.
        """
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(
                    sig,
                    lambda: asyncio.create_task(self.shutdown())
                )
            logger.debug("Signal handlers registered for graceful shutdown")
        except (NotImplementedError, AttributeError):
            logger.warning("Could not set up signal handlers, platform may not support them")
    
    async def _wait_for_connections_to_close(self, timeout: int = 5) -> None:
        """
        Wait for active connections to close.
        
        Args:
            timeout: Maximum time to wait in seconds
        """
        for i in range(timeout):
            if not self.active_connections:
                break
            logger.info(f"Waiting for connections to close: {len(self.active_connections)} remaining ({timeout-i}s)")
            await asyncio.sleep(1)
        
        # Force close any remaining connections
        if self.active_connections:
            logger.warning(f"Forcing closure of {len(self.active_connections)} remaining connections")
            await self._force_close_connections()
    
    @abstractmethod
    async def _force_close_connections(self) -> None:
        """
        Force close all remaining connections.
        
        This method should forcibly close any connections that didn't
        close gracefully during shutdown.
        """
        pass
    
    def get_connection_count(self) -> int:
        """
        Get the number of active connections.
        
        Returns:
            The number of active connections
        """
        return len(self.active_connections)
    
    def get_server_info(self) -> Dict[str, Any]:
        """
        Get information about the server.
        
        Returns:
            A dictionary containing server information
        """
        return {
            'type': self.__class__.__name__,
            'host': self.host,
            'port': self.port,
            'connections': self.get_connection_count(),
            'running': self.running
        }