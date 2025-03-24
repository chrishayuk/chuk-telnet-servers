#!/usr/bin/env python3
"""
Terminal Mode Control Telnet Server

This server explicitly negotiates with the telnet client to establish
proper terminal handling of control characters and line endings.
"""

import asyncio
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('terminal-mode-telnet')

class TerminalModeServer:
    # Telnet commands
    IAC = 255  # Interpret As Command
    DONT = 254
    DO = 253
    WONT = 252
    WILL = 251
    SB = 250   # Subnegotiation Begin
    SE = 240   # Subnegotiation End
    
    # Telnet options
    OPT_ECHO = 1        # Echo
    OPT_SGA = 3         # Suppress Go Ahead
    OPT_STATUS = 5      # Status
    OPT_TIMING = 6      # Timing Mark
    OPT_TERMINAL = 24   # Terminal Type
    OPT_NAWS = 31       # Window Size
    OPT_TSPEED = 32     # Terminal Speed
    OPT_LINEMODE = 34   # Line Mode
    OPT_ENVIRON = 36    # Environment Variables
    OPT_NEW_ENVIRON = 39  # New Environment Variables
    
    # Control characters
    NUL = 0
    CR = 13
    LF = 10
    
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
        """Handle a client connection with terminal mode control."""
        addr = writer.get_extra_info('peername')
        logger.info(f"New connection from {addr}")
        
        # Send initial telnet negotiations to set the terminal mode correctly
        await self.send_initial_negotiations(writer)
        
        # Send welcome message after negotiations
        writer.write(b"Welcome to Terminal Mode Control Server!\r\n")
        writer.write(b"Type something and press Enter to see proper handling.\r\n")
        writer.write(b"> ")
        await writer.drain()
        
        # Main loop
        buffer = ""
        try:
            while True:
                byte = await reader.read(1)
                if not byte:  # Connection closed
                    logger.info(f"Connection closed by client {addr}")
                    break
                
                # Print the byte in hex and decimal
                byte_val = byte[0]
                logger.debug(f"Received byte: 0x{byte_val:02X} ({byte_val})")
                
                # Handle IAC sequence
                if byte_val == self.IAC:
                    await self.handle_iac(reader, writer)
                    continue
                
                # Handle CR or LF - treat as end of line
                if byte_val == self.CR or byte_val == self.LF:
                    # Echo proper newline sequence for the terminal
                    writer.write(b"\r\n")
                    
                    # Process the completed line
                    cmd = buffer.strip()
                    buffer = ""
                    
                    if cmd.lower() in ['quit', 'exit', 'q']:
                        writer.write(b"Goodbye!\r\n")
                        await writer.drain()
                        break
                    
                    if cmd:
                        writer.write(f"You typed: {cmd}\r\n".encode('utf-8'))
                    
                    # Show prompt
                    writer.write(b"> ")
                    await writer.drain()
                    continue
                
                # Handle regular printable character
                if 32 <= byte_val <= 126:  # ASCII printable range
                    char = chr(byte_val)
                    buffer += char
                    # Echo the character back to the user
                    writer.write(byte)
                    await writer.drain()
                
                # Handle backspace and delete
                if byte_val in (8, 127):  # Backspace or Delete
                    if buffer:
                        buffer = buffer[:-1]
                        # Echo backspace sequence to erase the character
                        writer.write(b"\b \b")
                        await writer.drain()
                
                # Handle Ctrl+C
                if byte_val == 3:  # Ctrl+C
                    writer.write(b"^C\r\nClosing connection...\r\n")
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
    
    async def send_initial_negotiations(self, writer):
        """
        Send initial telnet negotiations to configure the client's terminal mode.
        """
        logger.debug("Sending initial negotiations")
        
        # WILL ECHO - We'll echo characters back to the client
        writer.write(bytes([self.IAC, self.WILL, self.OPT_ECHO]))
        
        # WILL SGA - Suppress Go Ahead (modern telnet)
        writer.write(bytes([self.IAC, self.WILL, self.OPT_SGA]))
        
        # DO SGA - Ask client to suppress Go Ahead
        writer.write(bytes([self.IAC, self.DO, self.OPT_SGA]))
        
        # WONT LINEMODE - We don't want to use linemode
        writer.write(bytes([self.IAC, self.WONT, self.OPT_LINEMODE]))
        
        # DO TERMINAL TYPE - Request terminal type info
        writer.write(bytes([self.IAC, self.DO, self.OPT_TERMINAL]))
        
        # DO NAWS - Request window size
        writer.write(bytes([self.IAC, self.DO, self.OPT_NAWS]))
        
        await writer.drain()
        logger.debug("Initial negotiations sent")
    
    async def handle_iac(self, reader, writer):
        """Handle IAC telnet command sequences."""
        try:
            cmd_byte = await reader.readexactly(1)
            cmd = cmd_byte[0]
            logger.debug(f"IAC command: {cmd}")
            
            if cmd in (self.DO, self.DONT, self.WILL, self.WONT):
                opt_byte = await reader.readexactly(1)
                opt = opt_byte[0]
                logger.debug(f"IAC {cmd} option: {opt}")
                
                # Handle responses for options we care about
                if cmd == self.DO:
                    if opt == self.OPT_ECHO:
                        # Client says DO ECHO - we'll do it
                        logger.debug("Client says DO ECHO - we agree")
                    elif opt == self.OPT_SGA:
                        # Client says DO SGA - we'll do it
                        logger.debug("Client says DO SGA - we agree")
                    else:
                        # Refuse options we don't support
                        logger.debug(f"Refusing option: {opt}")
                        writer.write(bytes([self.IAC, self.WONT, opt]))
                        await writer.drain()
                
                elif cmd == self.WILL:
                    if opt == self.OPT_TERMINAL:
                        # Client says WILL TERMINAL - great, we'll request it
                        logger.debug("Client says WILL TERMINAL - requesting info")
                        # Send subnegotiation to request terminal type
                        writer.write(bytes([self.IAC, self.SB, self.OPT_TERMINAL, 1, self.IAC, self.SE]))
                        await writer.drain()
                    elif opt == self.OPT_NAWS:
                        # Client says WILL NAWS - great
                        logger.debug("Client says WILL NAWS - we'll use window size info")
                    elif opt == self.OPT_ECHO:
                        # We don't want the client to echo, we'll do it
                        logger.debug("Client says WILL ECHO - we refuse")
                        writer.write(bytes([self.IAC, self.DONT, self.OPT_ECHO]))
                        await writer.drain()
                    else:
                        # Refuse options we don't support
                        logger.debug(f"Refusing option: {opt}")
                        writer.write(bytes([self.IAC, self.DONT, opt]))
                        await writer.drain()
            
            elif cmd == self.SB:
                # Subnegotiation - read until IAC SE
                sub_data = bytearray()
                while True:
                    sub_byte = await reader.readexactly(1)
                    if sub_byte[0] == self.IAC:
                        next_byte = await reader.readexactly(1)
                        if next_byte[0] == self.SE:
                            break
                        sub_data.extend(sub_byte)
                        sub_data.extend(next_byte)
                    else:
                        sub_data.extend(sub_byte)
                
                logger.debug(f"Subnegotiation data: {list(sub_data)}")
                
                # Parse the subnegotiation data
                if sub_data and sub_data[0] == self.OPT_TERMINAL and len(sub_data) > 1:
                    if sub_data[1] == 0:  # Terminal type response
                        term_type = sub_data[2:].decode('ascii', errors='ignore')
                        logger.debug(f"Terminal type: {term_type}")
                
                elif sub_data and sub_data[0] == self.OPT_NAWS and len(sub_data) >= 5:
                    width = (sub_data[1] << 8) + sub_data[2]
                    height = (sub_data[3] << 8) + sub_data[4]
                    logger.debug(f"Window size: {width}x{height}")
        
        except Exception as e:
            logger.error(f"Error handling IAC: {e}")

async def main():
    """Main entry point."""
    server = TerminalModeServer()
    await server.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutdown initiated by user")
        print("\nServer shutdown by user")