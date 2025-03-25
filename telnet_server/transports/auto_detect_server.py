#!/usr/bin/env python3
# telnet_server/transports/auto_detect_server.py
"""
Auto-Detecting Multi-Protocol Server

This module provides a server implementation that automatically detects
the protocol being used by the client and routes the connection to
the appropriate protocol handler. This allows a single server to handle
multiple protocols (e.g., Telnet, WebSocket) on the same port.
"""
import asyncio
import logging
import ssl
import re
import base64
import hashlib
from typing import Dict, Any, List, Type

# Import base classes
from telnet_server.handlers.base_handler import BaseHandler
from telnet_server.transports.base_server import BaseServer

# Import specific protocol implementations
from telnet_server.server import TelnetServer

# Try to import websockets
try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    from websockets.exceptions import ConnectionClosed
    from telnet_server.transports.websocket.ws_adapter import WebSocketAdapter
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WEBSOCKETS_ERROR = (
        "WebSocket support requires the 'websockets' package. "
        "Install with: pip install websockets"
    )

logger = logging.getLogger('auto-detect-server')


class AutoDetectServer(BaseServer):
    """
    Server that automatically detects and handles multiple protocols.
    
    This server examines the initial bytes of each connection to determine
    the protocol being used by the client, then routes the connection to
    the appropriate handler.
    """
    def __init__(
        self,
        host: str = '0.0.0.0',
        port: int = 8023,
        handler_class: Type[BaseHandler] = None,
        ws_path: str = '/telnet',
        ssl_cert: str = None,
        ssl_key: str = None,
        ping_interval: int = 30,
        ping_timeout: int = 10,
        allow_origins: List[str] = None
    ):
        super().__init__(host, port, handler_class)
        
        self.ws_path = ws_path
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.allow_origins = allow_origins or ['*']
        
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        self.ssl_context = None
        if ssl_cert and ssl_key:
            self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.ssl_context.load_cert_chain(ssl_cert, ssl_key)
            logger.info(f"SSL enabled with cert: {ssl_cert}")
        
        # Track active connections by protocol (for optional broadcast)
        self.connections_by_protocol = {
            'telnet': set(),
            'websocket': set()
        }
    
    async def start_server(self) -> None:
        await super().start_server()
        try:
            self.server = await asyncio.start_server(
                self.handle_new_connection,
                self.host,
                self.port,
                ssl=self.ssl_context
            )
            scheme = "wss/telnets" if self.ssl_context else "ws/telnet"
            logger.info(f"Auto-detect server running on {scheme}://{self.host}:{self.port}")
            
            async with self.server:
                await self.server.serve_forever()
        except Exception as e:
            logger.error(f"Error starting auto-detect server: {e}")
            raise
    
    async def handle_new_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        addr = writer.get_extra_info('peername')
        logger.debug(f"New connection from {addr}")
        
        try:
            # Read a small chunk to detect "GET " (WebSocket) vs. Telnet IAC (0xFF) vs. default
            initial_data = await reader.readexactly(4)
        except asyncio.IncompleteReadError:
            # If we didn't even get 4 bytes, treat as Telnet or close
            initial_data = b''
        
        if not initial_data:
            logger.warning(f"Empty initial data from {addr}, closing connection")
            writer.close()
            return
        
        protocol = self.detect_protocol(initial_data)
        logger.info(f"Detected protocol '{protocol}' from {addr}")
        
        if protocol == 'websocket':
            # Handle WebSocket handshake manually
            await self.handle_websocket_connection(initial_data, reader, writer)
        else:
            # Put the 4 bytes back into the existing reader buffer so
            # all subsequent data remains in the same StreamReader.
            self.reinject_data(reader, initial_data)
            
            # Now handle as Telnet using the *same* reader
            await self.handle_telnet_connection(reader, writer)
    
    def detect_protocol(self, initial_data: bytes) -> str:
        if initial_data.startswith(b'GET '):
            return 'websocket'
        if initial_data and initial_data[0] == 0xFF:
            return 'telnet'
        return 'telnet'
    
    def reinject_data(self, reader: asyncio.StreamReader, data: bytes) -> None:
        """
        Put 'data' back into 'reader' so the telnet handler sees it.
        """
        leftover = reader._buffer  # already-read leftover in the original reader
        # Combine them
        combined = bytearray(data)
        combined.extend(leftover)
        leftover.clear()
        
        # Now feed back into the original reader buffer
        reader._buffer.extend(combined)
    
    async def handle_telnet_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:
        addr = writer.get_extra_info('peername')
        handler = self.handler_class(reader, writer)
        handler.server = self
        
        self.active_connections.add(handler)
        self.connections_by_protocol['telnet'].add(handler)
        
        try:
            await handler.handle_client()
        except Exception as e:
            logger.error(f"Error handling telnet client {addr}: {e}")
        finally:
            try:
                if hasattr(handler, 'cleanup'):
                    await handler.cleanup()
                writer.close()
                try:
                    await asyncio.wait_for(writer.wait_closed(), 5.0)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Error cleaning up telnet connection: {e}")
            
            self.active_connections.discard(handler)
            self.connections_by_protocol['telnet'].discard(handler)
    
    async def handle_websocket_connection(
        self,
        initial_data: bytes,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:
        addr = writer.get_extra_info('peername')
        
        if not WEBSOCKETS_AVAILABLE:
            logger.warning(f"WebSocket connection from {addr} rejected: {WEBSOCKETS_ERROR}")
            error_body = f"Server Error: {WEBSOCKETS_ERROR}".encode('utf-8')
            response = (
                b"HTTP/1.1 400 Bad Request\r\n"
                b"Content-Type: text/plain\r\n"
                b"Connection: close\r\n"
                b"\r\n"
            ) + error_body
            writer.write(response)
            await writer.drain()
            writer.close()
            return
        
        # Combine initial_data + anything in the reader buffer to parse the HTTP request
        full_request = bytearray(initial_data)
        full_request.extend(reader._buffer)
        reader._buffer.clear()
        
        lines = full_request.split(b'\n')
        if not lines:
            writer.close()
            return
        
        request_line = lines[0].decode('utf-8', errors='replace').strip()
        match = re.match(r'GET\s+(\S+)\s+HTTP', request_line)
        if not match:
            logger.warning(f"Invalid WebSocket request line from {addr}")
            writer.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
            await writer.drain()
            writer.close()
            return
        
        path = match.group(1)
        
        # Parse headers
        headers = {}
        for line in lines[1:]:
            line = line.strip()
            if not line:
                break
            try:
                k, v = line.decode('utf-8', errors='ignore').split(':', 1)
                headers[k.lower().strip()] = v.strip()
            except ValueError:
                pass
        
        # Basic checks
        if 'upgrade' not in headers or 'sec-websocket-key' not in headers:
            logger.warning(f"Invalid WebSocket request from {addr}")
            writer.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
            await writer.drain()
            writer.close()
            return
        
        if headers['upgrade'].lower() != 'websocket':
            logger.warning(f"Missing 'Upgrade: websocket' from {addr}")
            writer.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
            await writer.drain()
            writer.close()
            return
        
        if path != self.ws_path:
            logger.warning(f"WebSocket request for incorrect path: {path}")
            writer.write(b"HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n")
            await writer.drain()
            writer.close()
            return
        
        # CORS check
        origin = headers.get('origin', '')
        if self.allow_origins and '*' not in self.allow_origins and origin not in self.allow_origins:
            logger.warning(f"WebSocket origin {origin} not allowed")
            writer.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
            await writer.drain()
            writer.close()
            return
        
        # Perform handshake
        ws_key = headers['sec-websocket-key']
        ws_accept = base64.b64encode(
            hashlib.sha1((ws_key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode()
        
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {ws_accept}\r\n"
            "\r\n"
        )
        writer.write(response.encode('utf-8'))
        await writer.drain()
        
        # Let websockets take over
        sock = writer.get_extra_info('socket')
        protocol = await websockets.basic_auth_protocol_factory(
            process_request=None,
            ping_interval=self.ping_interval,
            ping_timeout=self.ping_timeout,
        )(sock, host=self.host)
        
        adapter = WebSocketAdapter(protocol, self.handler_class)
        adapter.server = self
        
        self.active_connections.add(adapter)
        self.connections_by_protocol['websocket'].add(adapter)
        
        try:
            await adapter.handle_client()
        except Exception as e:
            logger.error(f"Error handling WebSocket client {addr}: {e}")
        finally:
            self.active_connections.discard(adapter)
            self.connections_by_protocol['websocket'].discard(adapter)
    
    async def send_global_message(self, message: str) -> None:
        tasks = []
        for handler in self.connections_by_protocol['telnet']:
            try:
                if hasattr(handler, 'send_line'):
                    tasks.append(asyncio.create_task(handler.send_line(message)))
            except Exception as e:
                logger.error(f"Error sending msg to telnet: {e}")
        for adapter in self.connections_by_protocol['websocket']:
            try:
                tasks.append(asyncio.create_task(adapter.send_line(message)))
            except Exception as e:
                logger.error(f"Error sending msg to websocket: {e}")
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def shutdown(self) -> None:
        logger.info("Shutting down auto-detect server...")
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        await super().shutdown()
        logger.info("Auto-detect server has shut down.")
    
    async def _force_close_connections(self) -> None:
        for handler in list(self.connections_by_protocol['telnet']):
            try:
                if hasattr(handler, 'writer'):
                    handler.writer.close()
                self.active_connections.discard(handler)
                self.connections_by_protocol['telnet'].discard(handler)
            except Exception as e:
                logger.error(f"Error force closing telnet connection: {e}")
        
        for adapter in list(self.connections_by_protocol['websocket']):
            try:
                await adapter.close()
                self.active_connections.discard(adapter)
                self.connections_by_protocol['websocket'].discard(adapter)
            except Exception as e:
                logger.error(f"Error force closing websocket connection: {e}")
