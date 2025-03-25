#!/usr/bin/env python3
# telnet_server/transports/auto_detect_server.py
"""
Auto-Detecting Multi-Protocol Server

This server listens on a single port and:
 - If the first 4 bytes are 'GET ', it performs a WebSocket handshake,
   then attempts Telnet negotiation over the WebSocket (Telnet IAC codes
   in binary frames). If the client doesn't respond with Telnet codes,
   it falls back to a simple line-echo mode.
 - Otherwise, it immediately recognizes Telnet, reinjects any leftover bytes,
   and hands off to your normal Telnet handler (handler_class).
 
Requires:
 - telnet_server/server.py (your existing TelnetServer)
 - websockets >= 9 (if you have the older constructor requiring ws_handler/ws_server).
"""

import asyncio
import logging
import ssl
import re
import base64
import hashlib
from typing import Dict, Any, List, Type

from telnet_server.server import TelnetServer  # your normal Telnet server
from telnet_server.transports.base_server import BaseServer
from telnet_server.handlers.base_handler import BaseHandler

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    from websockets.exceptions import ConnectionClosed
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WEBSOCKETS_ERROR = "Missing websockets package. Install with: pip install websockets"

logger = logging.getLogger("auto-detect-server")

# For older websockets (including v15) that require ws_server.register():
class DummyWSServer:
    def register(self, protocol):
        pass

##############################################################################
# Telnet Over WebSocket Handler
##############################################################################

IAC  = 255
WILL = 251
WONT = 252
DO   = 253
DONT = 254
ECHO = 1
SGA  = 3

class TelnetOverWebSocketHandler(BaseHandler):
    """
    A single handler that attempts Telnet negotiation (IAC WILL ECHO, etc.)
    inside a WebSocket. If the client doesn't respond with IAC codes, it
    falls back to line-based echo.
    """
    def __init__(self, websocket):
        super().__init__(None, None)
        self.websocket = websocket
        self.negotiation_timeout = 2.0
        self.is_telnet = False
        self.fallback_mode = False

    async def handle_client(self) -> None:
        try:
            logger.debug("Sending IAC WILL ECHO/SGA for Telnet over WebSocket.")
            await self.send_telnet_command(IAC, WILL, ECHO)
            await self.send_telnet_command(IAC, WILL, SGA)

            responded = await self.wait_for_telnet_response()
            if responded:
                logger.info("Client responded with IAC => continuing Telnet over WS.")
                self.is_telnet = True
                await self.send_line("Telnet negotiation successful! Type 'quit' to exit.\r\n")
            else:
                logger.info("No Telnet codes => fallback mode.")
                self.fallback_mode = True
                await self.send_line("Fallback mode (no Telnet negotiation). Type 'quit' to exit.\r\n")

            while True:
                data = await self.websocket.recv()
                if data is None:
                    logger.debug("WebSocket closed (None).")
                    break

                # Convert text frames to bytes
                if isinstance(data, str):
                    data = data.encode("utf-8", errors="replace")

                if self.fallback_mode:
                    # Just a line-based echo
                    line = data.decode("utf-8", errors="replace").strip()
                    if line.lower() in ("quit", "exit"):
                        await self.send_line("Goodbye (fallback).")
                        break
                    else:
                        await self.send_line(f"Echo(fallback): {line}")
                else:
                    # Telnet mode
                    if b"quit" in data.lower():
                        await self.send_line("Goodbye from Telnet-over-WS!")
                        break
                    # If you want to parse IAC fully, do so here. We'll just echo:
                    line = data.decode("utf-8", errors="replace").strip()
                    await self.send_line(f"TelnetEcho: {line}")

        except ConnectionClosed:
            logger.debug("WebSocket connection closed.")
        except Exception as e:
            logger.error(f"TelnetOverWebSocketHandler error: {e}", exc_info=True)

    async def wait_for_telnet_response(self) -> bool:
        try:
            frame = await asyncio.wait_for(self.websocket.recv(), timeout=self.negotiation_timeout)
            if not frame:
                return False
            if isinstance(frame, str):
                frame = frame.encode("utf-8", errors="replace")
            if IAC in frame:
                logger.debug(f"Detected IAC in initial WS frame: {frame}")
                return True
            else:
                logger.debug("No IAC => fallback.")
                await self.send_line(f"Echo(fallback-first): {frame.decode('utf-8','replace')}")
                return False
        except asyncio.TimeoutError:
            logger.debug("Timeout => fallback.")
            return False
        except ConnectionClosed:
            logger.debug("ConnectionClosed => fallback.")
            return False

    async def send_telnet_command(self, *bytes_seq):
        data = bytes(bytes_seq)
        await self.websocket.send(data)

    async def send_line(self, text: str):
        data = (text + "\r\n").encode("utf-8")
        await self.websocket.send(data)

##############################################################################
# Minimal Adapter for TelnetOverWebSocketHandler
##############################################################################

class TelnetOverWSAdapter:
    def __init__(self, protocol: WebSocketServerProtocol):
        self.protocol = protocol
        self.handler = None

    async def handle_client(self):
        self.handler = TelnetOverWebSocketHandler(self.protocol)
        await self.handler.handle_client()

##############################################################################
# The AutoDetectServer
##############################################################################

class AutoDetectServer(BaseServer):
    """
    Auto-detect server:
     - If first 4 bytes == 'GET ', do a manual WebSocket handshake,
       then run TelnetOverWebSocketHandler.
     - Otherwise, treat as Telnet with your normal `handler_class`.
    """
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8023,
        handler_class: Type[BaseHandler] = None,
        ws_path: str = "/telnet",
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
        self.allow_origins = allow_origins or ["*"]

        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        self.ssl_context = None
        if ssl_cert and ssl_key:
            self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.ssl_context.load_cert_chain(ssl_cert, ssl_key)
            logger.info(f"SSL enabled with cert: {ssl_cert}")

        self.connections_by_protocol = {
            "telnet": set(),
            "websocket": set(),
        }

    async def start_server(self) -> None:
        await super().start_server()
        try:
            self.server = await asyncio.start_server(
                self.handle_new_connection,
                self.host,
                self.port,
                ssl=self.ssl_context,
            )
            scheme = "wss/telnets" if self.ssl_context else "ws/telnet"
            logger.info(f"Auto-detect server running on {scheme}://{self.host}:{self.port}")

            async with self.server:
                await self.server.serve_forever()
        except Exception as e:
            logger.error(f"Error starting auto-detect server: {e}")
            raise

    async def handle_new_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        addr = writer.get_extra_info("peername")
        logger.debug(f"New connection from {addr}")

        try:
            # Attempt to read 4 bytes to detect "GET "
            initial_data = await reader.readexactly(4)
        except asyncio.IncompleteReadError:
            initial_data = b""

        if not initial_data:
            logger.warning(f"Empty initial data from {addr}, closing.")
            writer.close()
            return

        # Check if it's "GET "
        if initial_data.startswith(b"GET "):
            await self.handle_websocket_connection(initial_data, reader, writer)
        else:
            # Not GET => Telnet
            leftover = reader._buffer
            combined = bytearray(initial_data)
            combined.extend(leftover)
            leftover.clear()
            reader._buffer.extend(combined)

            await self.handle_telnet_connection(reader, writer)

    async def handle_telnet_connection(self, reader, writer):
        addr = writer.get_extra_info("peername")
        handler = self.handler_class(reader, writer)
        handler.server = self

        self.active_connections.add(handler)
        self.connections_by_protocol["telnet"].add(handler)

        try:
            await handler.handle_client()
        except Exception as e:
            logger.error(f"Telnet error from {addr}: {e}")
        finally:
            try:
                if hasattr(handler, "cleanup"):
                    await handler.cleanup()
                writer.close()
                await asyncio.wait_for(writer.wait_closed(), 3.0)
            except:
                pass
            self.active_connections.discard(handler)
            self.connections_by_protocol["telnet"].discard(handler)

    async def handle_websocket_connection(self, initial_data, reader, writer):
        if not WEBSOCKETS_AVAILABLE:
            logger.warning(f"WebSocket from {writer.get_extra_info('peername')} rejected: {WEBSOCKETS_ERROR}")
            writer.close()
            return

        addr = writer.get_extra_info("peername")

        # Rebuild the HTTP request
        full_req = bytearray(initial_data)
        full_req.extend(reader._buffer)
        reader._buffer.clear()

        lines = full_req.split(b"\n")
        if not lines:
            writer.close()
            return

        req_line = lines[0].decode("utf-8", errors="replace").strip()
        match = re.match(r"GET\s+(\S+)\s+HTTP", req_line)
        if not match:
            writer.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
            await writer.drain()
            writer.close()
            return

        path = match.group(1)
        # parse headers
        headers = {}
        for line in lines[1:]:
            line = line.strip()
            if not line:
                break
            try:
                k, v = line.decode("utf-8", errors="ignore").split(":", 1)
                headers[k.lower().strip()] = v.strip()
            except:
                pass

        if "upgrade" not in headers or "sec-websocket-key" not in headers:
            writer.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
            await writer.drain()
            writer.close()
            return

        if headers["upgrade"].lower() != "websocket":
            writer.write(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
            await writer.drain()
            writer.close()
            return

        if path != self.ws_path:
            writer.write(b"HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n")
            await writer.drain()
            writer.close()
            return

        origin = headers.get("origin", "")
        if self.allow_origins and "*" not in self.allow_origins and origin not in self.allow_origins:
            writer.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
            await writer.drain()
            writer.close()
            return

        # Build accept key
        ws_key = headers["sec-websocket-key"]
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
        writer.write(response.encode("utf-8"))
        await writer.drain()

        # let websockets take over
        sock = writer.get_extra_info("socket")
        loop = asyncio.get_running_loop()

        # For websockets 15, we need a dummy server
        class DummyWSServer:
            def register(self, proto):
                pass

        dummy = DummyWSServer()
        protocol = WebSocketServerProtocol(
            None,
            dummy,
            ping_interval=self.ping_interval,
            ping_timeout=self.ping_timeout,
        )
        transport, _ = await loop.connect_accepted_socket(lambda: protocol, sock)
        protocol.connection_open()

        # Now create an adapter that uses TelnetOverWebSocketHandler
        adapter = TelnetOverWSAdapter(protocol)
        self.active_connections.add(adapter)
        self.connections_by_protocol["websocket"].add(adapter)

        try:
            await adapter.handle_client()
        except Exception as e:
            logger.error(f"Error in WebSocket connection from {addr}: {e}")
        finally:
            self.active_connections.discard(adapter)
            self.connections_by_protocol["websocket"].discard(adapter)

    async def shutdown(self) -> None:
        logger.info("Shutting down auto-detect server...")
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        await super().shutdown()
        logger.info("Auto-detect server shut down.")

    async def _force_close_connections(self) -> None:
        # forcibly close leftover connections if needed
        pass

    async def send_global_message(self, message: str) -> None:
        """
        Broadcast a message to all Telnet or WebSocket connections.
        This method is required by BaseServer, so we provide at least a stub.
        """
        # If you want an actual broadcast:
        tasks = []
        # Broadcast to telnet connections
        for h in self.connections_by_protocol["telnet"]:
            if hasattr(h, "send_line"):
                tasks.append(asyncio.create_task(h.send_line(message)))
        # Broadcast to WS connections (TelnetOverWSAdapter)
        for a in self.connections_by_protocol["websocket"]:
            if hasattr(a, "handler") and a.handler:
                await a.handler.send_line(message)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
