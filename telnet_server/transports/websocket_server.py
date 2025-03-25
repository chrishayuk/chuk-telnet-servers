#!/usr/bin/env python3
# telnet_server/transports/websocket_server.py
"""
WebSocket Transport for Telnet Server

This module provides a WebSocket transport implementation that allows
browsers to connect directly to the telnet server without requiring
a proxy. It adapts the standard telnet protocol handler to work with
WebSocket connections.
"""
import asyncio
import logging
import ssl
import json
import websockets
from typing import Type, Dict, Any, Set, Optional, List
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

# Import base classes
from telnet_server.handlers.base_handler import BaseHandler
from telnet_server.transports.transport_adapter import WebSocketAdapter

# Configure logging
logger = logging.getLogger('websocket-server')

class WebSocketServer:
    """
    WebSocket server implementation for Telnet services.
    
    This class implements a WebSocket server that adapts WebSocket
    connections to work with the telnet handler classes, providing
    a bridge between browser clients and the telnet server.
    """
    
    def __init__(self, host: str = '0.0.0.0', port: int = 8023,
                 handler_class: Type[BaseHandler] = None,
                 path: str = '/telnet', ssl_cert: str = None,
                 ssl_key: str = None, ping_interval: int = 30,
                 ping_timeout: int = 10, allow_origins: List[str] = None):
        """
        Initialize the WebSocket server with host, port, and handler class.
        
        Args:
            host: Host address to bind to
            port: Port number to listen on
            handler_class: Handler class to use for client connections
            path: WebSocket endpoint path
            ssl_cert: SSL certificate file path (optional)
            ssl_key: SSL key file path (optional)
            ping_interval: WebSocket ping interval in seconds
            ping_timeout: WebSocket ping timeout in seconds
            allow_origins: List of allowed origins for CORS
        """
        self.host = host
        self.port = port
        self.handler_class = handler_class
        self.path = path
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.allow_origins = allow_origins or ['*']
        
        self.server = None
        self.active_connections: Set[WebSocketAdapter] = set()
        self.running = True
        
        # SSL context setup if SSL is enabled
        self.ssl_context = None
        if ssl_cert and ssl_key:
            self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.ssl_context.load_cert_chain(ssl_cert, ssl_key)
            logger.info(f"SSL enabled with cert: {ssl_cert}")
    
    async def start_server(self) -> None:
        """
        Start the WebSocket server.
        
        This method starts the server listening for connections
        on the specified host and port, and sets up signal handlers
        for graceful shutdown.
        
        Raises:
            ValueError: If no handler class was provided
            Exception: If an error occurs while starting the server
        """
        if not self.handler_class:
            raise ValueError("Handler class must be provided")
        
        try:
            # Define the WebSocket handler function
            async def websocket_handler(websocket: WebSocketServerProtocol, path: str):
                if path != self.path:
                    await websocket.close(1003, f"Endpoint {path} not found")
                    return
                
                # Create an adapter for this WebSocket
                adapter = WebSocketAdapter(websocket, self.handler_class)
                adapter.server = self  # Set reference to server
                
                # Add to active connections
                self.active_connections.add(adapter)
                
                try:
                    # Start the handler
                    await adapter.handle_client()
                except ConnectionClosed as e:
                    logger.info(f"WebSocket connection closed: {e}")
                except Exception as e:
                    logger.error(f"Error handling WebSocket client: {e}")
                finally:
                    # Clean up
                    if adapter in self.active_connections:
                        self.active_connections.remove(adapter)
            
            # Configure CORS and other WebSocket options
            extra_kwargs = {
                'ping_interval': self.ping_interval,
                'ping_timeout': self.ping_timeout,
                'process_request': self._process_request,
            }
            
            # Start the WebSocket server
            self.server = await websockets.serve(
                websocket_handler, 
                self.host, 
                self.port,
                ssl=self.ssl_context,
                **extra_kwargs
            )
            
            # Ensure the server starts correctly
            scheme = "wss" if self.ssl_context else "ws"
            logger.info(f"WebSocket server running on {scheme}://{self.host}:{self.port}{self.path}")
            
            # Set up signal handlers for graceful shutdown
            loop = asyncio.get_running_loop()
            for sig in ('SIGINT', 'SIGTERM'):
                try:
                    loop.add_signal_handler(
                        getattr(asyncio.signals, sig),
                        lambda: asyncio.create_task(self.shutdown())
                    )
                except (NotImplementedError, AttributeError):
                    # Windows doesn't support SIGINT/SIGTERM properly
                    logger.warning(f"Could not set up {sig} handler, OS may not support it")
            
            # Keep the server running until shutdown
            await self._keep_running()
            
        except Exception as e:
            logger.error(f"Error starting WebSocket server: {e}")
            raise
    
    async def _keep_running(self) -> None:
        """Keep the server running until shutdown is called."""
        while self.running:
            await asyncio.sleep(1)
    
    async def _process_request(self, path: str, headers: Dict[str, str]) -> Optional[tuple]:
        """
        Process WebSocket upgrade requests for CORS and other validations.
        
        Args:
            path: The requested path
            headers: The request headers
            
        Returns:
            None to accept the connection, or a tuple of (status_code, headers)
            to reject it
        """
        # Check path matches our endpoint
        if path != self.path:
            return (404, {}, b"Not Found")
        
        # CORS handling
        if self.allow_origins and 'Origin' in headers:
            origin = headers['Origin']
            if '*' in self.allow_origins or origin in self.allow_origins:
                # Return CORS headers for options requests or websocket upgrades
                cors_headers = {
                    'Access-Control-Allow-Origin': origin,
                    'Access-Control-Allow-Methods': 'GET',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                    'Access-Control-Max-Age': '86400',  # 24 hours
                }
                
                # For OPTIONS preflight requests
                if headers.get('Access-Control-Request-Method'):
                    return (200, cors_headers, b"")
            else:
                # Origin not allowed
                return (403, {}, b"Origin not allowed")
        
        # Accept the connection
        return None
    
    async def send_global_message(self, message: str) -> None:
        """
        Send a message to all connected clients.
        
        Args:
            message: The message to send
        """
        send_tasks = []
        for adapter in self.active_connections:
            try:
                send_tasks.append(asyncio.create_task(adapter.send_line(message)))
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
        logger.info("Shutting down WebSocket server...")
        
        # Signal all handlers to stop
        self.running = False
        
        # Send shutdown message to all clients
        await self.send_global_message("\nServer is shutting down. Goodbye!")
        
        # Wait for connections to close (with timeout)
        wait_time = 5  # seconds
        for i in range(wait_time):
            if not self.active_connections:
                break
            logger.info(f"Waiting for connections to close: {len(self.active_connections)} remaining ({wait_time-i}s)")
            await asyncio.sleep(1)
        
        # Force close any remaining connections
        for adapter in list(self.active_connections):
            try:
                await adapter.close()
                self.active_connections.remove(adapter)
            except Exception as e:
                logger.error(f"Error closing WebSocket connection: {e}")
        
        # Close the server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        logger.info("WebSocket server has shut down.")