#!/usr/bin/env python3
# telnet_server/protocol_handlers/telnet_protocol_handler.py
"""
Robust Telnet Protocol Handler

This handler properly negotiates terminal settings with telnet clients and
supports both line mode and character mode. It handles telnet option negotiation,
control characters, and provides proper visual feedback for terminal operations.

Features:
- Automatic detection of line mode vs. character mode capabilities
- Proper handling of CR/LF sequences and other control characters
- Detailed logging of telnet negotiations for troubleshooting
- Clean separation between protocol handling and application logic
- Robust error handling for unexpected client behaviors
"""

import asyncio
import logging
from typing import Optional, Dict, Set, Tuple

from telnet_server.protocol_handlers.character_protocol_handler import CharacterProtocolHandler

telnet_logger = logging.getLogger('telnet-protocol')

class TelnetProtocolHandler(CharacterProtocolHandler):
    """
    A robust Telnet protocol handler that:
    - Properly negotiates terminal settings with telnet clients
    - Supports both line mode and character mode
    - Handles control characters and provides visual feedback
    - Logs all telnet negotiations for troubleshooting
    """

    # Telnet command codes
    IAC  = 255  # Interpret As Command
    DONT = 254
    DO   = 253
    WONT = 252
    WILL = 251
    SB   = 250  # Subnegotiation Begin
    SE   = 240  # Subnegotiation End
    
    # Telnet control codes
    NUL = 0     # NULL
    LF  = 10    # Line Feed
    CR  = 13    # Carriage Return
    BS  = 8     # Backspace
    DEL = 127   # Delete
    CTRL_C = 3  # Ctrl+C
    
    # Common option codes
    OPT_ECHO = 1        # Echo
    OPT_SGA = 3         # Suppress Go Ahead
    OPT_TERMINAL = 24   # Terminal Type
    OPT_NAWS = 31       # Window Size
    OPT_LINEMODE = 34   # Line Mode
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Initialize the telnet protocol handler with default settings."""
        super().__init__(reader, writer)
        self.addr = writer.get_extra_info('peername')
        self.line_mode = False
        self.current_command = ""
        
        # Terminal capabilities
        self.terminal_type = "UNKNOWN"
        self.window_size = (80, 24)  # Default terminal size (columns, rows)
        
        # Track negotiated options
        self.local_options: Dict[int, bool] = {}    # Options we (server) have enabled
        self.remote_options: Dict[int, bool] = {}   # Options client has enabled
        
        # Buffer for handling IAC sequences
        self.iac_buffer = bytearray()
        
        # Initialize with default settings
        self._initialize_options()
    
    def _initialize_options(self):
        """Initialize default option states."""
        # By default, we don't enable any options
        for opt in [self.OPT_ECHO, self.OPT_SGA, self.OPT_LINEMODE]:
            self.local_options[opt] = False
            self.remote_options[opt] = False
    
    async def handle_client(self) -> None:
        """
        Main client handling loop. Negotiates terminal settings,
        then reads and processes input based on the negotiated mode.
        """
        telnet_logger.debug(f"New client connected: {self.addr}")
        
        # Send initial terminal negotiations
        await self._send_initial_negotiations()
        
        # Send welcome message
        await self.send_line("Welcome! This server can handle line or character mode.")
        await self.show_prompt()
        
        try:
            should_continue = True
            while self.running and should_continue:
                if self.line_mode:
                    # Process in line mode
                    line = await self._read_line()
                    if line is None:
                        telnet_logger.debug("Client disconnected (line mode).")
                        break
                    
                    # Process the line
                    should_continue = await self.process_line(line)
                else:
                    # Process in character mode
                    data = await self._read_mixed_mode()
                    if data is None:
                        telnet_logger.debug("Client disconnected (mixed mode).")
                        break
                    
                    if data:  # Only process if we got actual data
                        # Process each character in the data
                        for char in data:
                            should_continue = await self.process_character(char)
                            if not should_continue:
                                break
                        
                        if not should_continue:
                            break
                
        except Exception as e:
            telnet_logger.error(f"Error handling client {self.addr}: {e}")
        finally:
            telnet_logger.debug(f"Cleaning up client {self.addr}")
            await self.cleanup()
    
    async def _send_initial_negotiations(self):
        """
        Send initial telnet option negotiations to establish proper terminal handling.
        This is key to getting the client into the right mode.
        """
        telnet_logger.debug("Sending initial negotiations")
        
        # WILL ECHO - We'll echo characters back to the client
        await self._send_command(self.WILL, self.OPT_ECHO)
        
        # WILL SGA - Suppress Go Ahead (modern telnet)
        await self._send_command(self.WILL, self.OPT_SGA)
        
        # DO SGA - Ask client to suppress Go Ahead
        await self._send_command(self.DO, self.OPT_SGA)
        
        # DO TERMINAL TYPE - Request terminal type info
        await self._send_command(self.DO, self.OPT_TERMINAL)
        
        # DO NAWS - Request window size
        await self._send_command(self.DO, self.OPT_NAWS)
        
        # Line mode negotiation - prefer character mode
        await self._send_command(self.WONT, self.OPT_LINEMODE)
        
        telnet_logger.debug("Initial negotiations sent")
    
    async def _send_command(self, command: int, option: int):
        """Send a telnet command with the given option."""
        self.writer.write(bytes([self.IAC, command, option]))
        await self.writer.drain()
        
        # Update our local tracking of options
        if command == self.WILL:
            self.local_options[option] = True
        elif command == self.WONT:
            self.local_options[option] = False
    
    async def _read_mixed_mode(self, timeout: float = 300) -> Optional[str]:
        """
        Read data in mixed mode, handling both regular characters and telnet commands.
        This method is responsible for:
        1. Distinguishing between telnet commands and regular data
        2. Processing CR/LF/NUL combinations correctly
        3. Returning a clean string of characters for the application to process
        
        Args:
            timeout: Maximum time to wait for data in seconds
        
        Returns:
            A string of processed characters, None if connection closed, or empty string on timeout
        """
        try:
            # Read a chunk of data with timeout
            raw_data = await asyncio.wait_for(self.reader.read(1024), timeout=timeout)
            if not raw_data:
                return None  # Connection closed
            
            telnet_logger.debug(f"Raw data received: {[b for b in raw_data]}")
            
            # Process the data to handle telnet commands and CR/LF combinations
            processed_chars = ""
            i = 0
            while i < len(raw_data):
                byte = raw_data[i]
                
                # Check for IAC (telnet command)
                if byte == self.IAC:
                    i += 1
                    if i >= len(raw_data):
                        # IAC at end of buffer - wait for more data
                        break
                    
                    cmd = raw_data[i]
                    if cmd in (self.DO, self.DONT, self.WILL, self.WONT):
                        # These commands have one option byte
                        i += 1
                        if i < len(raw_data):
                            option = raw_data[i]
                            self._process_telnet_command(cmd, option)
                    elif cmd == self.SB:
                        # Subnegotiation - read until IAC SE
                        sb_data = bytearray()
                        i += 1
                        while i < len(raw_data) - 1:
                            if raw_data[i] == self.IAC and raw_data[i+1] == self.SE:
                                i += 1  # Skip to SE
                                break
                            sb_data.append(raw_data[i])
                            i += 1
                        
                        # Process the subnegotiation data
                        if sb_data:
                            self._process_subnegotiation(sb_data)
                    # IAC IAC means literal 255
                    elif cmd == self.IAC:
                        processed_chars += chr(self.IAC)
                    
                    i += 1
                    continue
                
                # Check for CR+LF or CR+NUL combinations
                if byte == self.CR:
                    if i+1 < len(raw_data):
                        next_byte = raw_data[i+1]
                        if next_byte == self.LF:
                            # CR+LF combo - treat as a single newline
                            processed_chars += "\n"
                            i += 2
                            continue
                        elif next_byte == self.NUL:
                            # CR+NUL combo - treat as a single CR
                            processed_chars += "\r"
                            i += 2
                            continue
                    
                    # Standalone CR
                    processed_chars += "\r"
                    i += 1
                    continue
                
                # Regular character - make sure it's in printable ASCII range or control codes we care about
                if (byte >= 32 and byte <= 126) or byte in (self.BS, self.LF, self.CR, self.CTRL_C, self.DEL):
                    processed_chars += chr(byte)
                
                i += 1
            
            telnet_logger.debug(f"Processed data: {repr(processed_chars)}")
            return processed_chars
        
        except asyncio.TimeoutError:
            return ""  # Timeout - return empty string
        except Exception as e:
            telnet_logger.error(f"Error in _read_mixed_mode: {e}")
            return None  # Error - treat as connection closed
    
    def _process_telnet_command(self, cmd: int, option: int):
        """
        Process a telnet command and respond appropriately.
        This handles the core of the telnet protocol negotiation.
        
        Args:
            cmd: The telnet command (DO, DONT, WILL, WONT)
            option: The option code being negotiated
        """
        telnet_logger.debug(f"Processing telnet command: {cmd}, option: {option}")
        
        if option == self.OPT_LINEMODE:
            if cmd == self.DO:
                # Client says DO LINEMODE
                telnet_logger.debug("Client requests DO LINEMODE => respond WILL LINEMODE")
                self.line_mode = True
                self.writer.write(bytes([self.IAC, self.WILL, self.OPT_LINEMODE]))
                self.local_options[option] = True
            elif cmd == self.WILL:
                # Client says WILL LINEMODE
                telnet_logger.debug("Client says WILL LINEMODE => respond DO LINEMODE")
                self.line_mode = True
                self.writer.write(bytes([self.IAC, self.DO, self.OPT_LINEMODE]))
                self.remote_options[option] = True
            elif cmd == self.DONT:
                telnet_logger.debug("Client says DONT LINEMODE => stay in char mode")
                self.line_mode = False
                self.local_options[option] = False
            elif cmd == self.WONT:
                telnet_logger.debug("Client says WONT LINEMODE => stay in char mode")
                self.line_mode = False
                self.remote_options[option] = False
        
        elif option == self.OPT_ECHO:
            if cmd == self.DO:
                # Client wants us to ECHO - we agree
                telnet_logger.debug("Client says DO ECHO - we agree")
                self.writer.write(bytes([self.IAC, self.WILL, self.OPT_ECHO]))
                self.local_options[option] = True
            elif cmd == self.DONT:
                # Client says don't echo - we comply
                telnet_logger.debug("Client says DONT ECHO - we comply")
                self.writer.write(bytes([self.IAC, self.WONT, self.OPT_ECHO]))
                self.local_options[option] = False
            elif cmd == self.WILL:
                # Client wants to echo - we prefer to handle it
                telnet_logger.debug("Client says WILL ECHO - we refuse")
                self.writer.write(bytes([self.IAC, self.DONT, self.OPT_ECHO]))
                self.remote_options[option] = False
            elif cmd == self.WONT:
                # Client won't echo - good, we'll do it
                telnet_logger.debug("Client says WONT ECHO - that's fine")
                self.remote_options[option] = False
        
        elif option == self.OPT_SGA:
            if cmd == self.DO:
                # Client wants us to suppress GA - we agree
                telnet_logger.debug("Client says DO SGA - we agree")
                self.writer.write(bytes([self.IAC, self.WILL, self.OPT_SGA]))
                self.local_options[option] = True
            elif cmd == self.WILL:
                # Client will suppress GA - good
                telnet_logger.debug("Client says WILL SGA - good")
                self.remote_options[option] = True
        
        elif option == self.OPT_TERMINAL:
            if cmd == self.WILL:
                # Client will send terminal type - request it
                telnet_logger.debug("Client says WILL TERMINAL - requesting type")
                self.remote_options[option] = True
                # Send subnegotiation to request terminal type
                self.writer.write(bytes([self.IAC, self.SB, self.OPT_TERMINAL, 1, self.IAC, self.SE]))
        
        elif option == self.OPT_NAWS:
            if cmd == self.WILL:
                # Client will send window size - good
                telnet_logger.debug("Client says WILL NAWS - good")
                self.remote_options[option] = True
        
        else:
            # For other options, just refuse
            telnet_logger.debug(f"Refusing unknown option: {option}")
            if cmd == self.DO:
                self.writer.write(bytes([self.IAC, self.WONT, option]))
            elif cmd == self.WILL:
                self.writer.write(bytes([self.IAC, self.DONT, option]))
    
    def _process_subnegotiation(self, data: bytearray):
        """
        Process telnet subnegotiation data.
        This handles extended option data like terminal type and window size.
        
        Args:
            data: The subnegotiation data (without IAC SB and IAC SE)
        """
        telnet_logger.debug(f"Processing subnegotiation data: {list(data)}")
        
        if not data:
            return
        
        option = data[0]
        
        if option == self.OPT_TERMINAL and len(data) > 1:
            if data[1] == 0:  # Terminal type response
                term_type = bytes(data[2:]).decode('ascii', errors='ignore')
                telnet_logger.debug(f"Terminal type: {term_type}")
                self.terminal_type = term_type
        
        elif option == self.OPT_NAWS and len(data) >= 5:
            # Window size is sent as 2-byte values for width, then height
            width = (data[1] << 8) + data[2]
            height = (data[3] << 8) + data[4]
            telnet_logger.debug(f"Window size: {width}x{height}")
            self.window_size = (width, height)
    
    async def _read_line(self, timeout: float = 300) -> Optional[str]:
        """
        Read a complete line in line mode.
        This method works when the client has negotiated line mode.
        
        Args:
            timeout: Maximum time to wait for a line in seconds
        
        Returns:
            The read line, or None if connection closed or error
        """
        try:
            data = await asyncio.wait_for(self.reader.readline(), timeout=timeout)
            if not data:
                return None  # Connection closed
            
            # Process the line - strip CR/LF and handle telnet sequences
            line_bytes = bytearray()
            i = 0
            while i < len(data):
                # Check for IAC
                if data[i] == self.IAC:
                    i += 1
                    if i < len(data):
                        if data[i] == self.IAC:  # Literal IAC
                            line_bytes.append(self.IAC)
                        # Skip other telnet sequences
                        elif data[i] in (self.DO, self.DONT, self.WILL, self.WONT):
                            i += 1  # Skip option byte
                    i += 1
                    continue
                
                # Skip CR/LF at the end
                if data[i] in (self.CR, self.LF) and i >= len(data) - 2:
                    i += 1
                    continue
                
                # Regular character
                line_bytes.append(data[i])
                i += 1
            
            line_str = line_bytes.decode('utf-8', errors='ignore')
            telnet_logger.debug(f"Line-mode read => {repr(line_str)}")
            return line_str
            
        except asyncio.TimeoutError:
            telnet_logger.debug("Timeout reading line")
            return None
        except Exception as e:
            telnet_logger.error(f"Error in _read_line: {e}")
            return None
    
    async def process_line(self, line: str) -> bool:
        """
        Process a complete line in line mode.
        This is called after a complete line has been read.
        
        Args:
            line: The line to process
        
        Returns:
            True to continue processing, False to terminate the connection
        """
        telnet_logger.debug(f"process_line => {repr(line)}")
        
        if line.lower() in ['quit', 'exit', 'q']:
            await self.send_line("Goodbye (line mode)!")
            return False
        
        # This hook allows subclasses to provide custom command handling
        await self.on_command_submitted(line)
        
        # Only show prompt if we're continuing
        await self.show_prompt()
        return True
    
    async def process_character(self, char: str) -> bool:
        """
        Process a single character in character mode.
        This handles control characters and accumulates a command buffer.
        
        Args:
            char: The character to process
        
        Returns:
            True to continue processing, False to terminate the connection
        """
        telnet_logger.debug(f"process_character => received: {repr(char)}")
        
        # Check for Ctrl+C
        if char == "\x03":
            await self.send_line("\n^C - Closing connection.")
            return False
        
        # Handle carriage return or newline (Enter key)
        if char in ("\r", "\n"):
            # Echo the newline visually
            await self.send_raw(b"\r\n")
            
            cmd = self.current_command.strip()
            self.current_command = ""
            
            if cmd.lower() in ["quit", "exit", "q"]:
                await self.send_line("Goodbye (char mode)!")
                return False
            
            if cmd:
                # Process command through the hook method
                await self.on_command_submitted(cmd)
            
            # Only show prompt if we're continuing
            await self.show_prompt()
            return True
        
        # Handle backspace or delete
        if char in ("\b", "\x7f"):
            if self.current_command:
                # Echo the backspace visually (back, space, back)
                await self.send_raw(b"\b \b")
                self.current_command = self.current_command[:-1]
            return True
        
        # Echo the character as it's typed (for visual feedback)
        try:
            await self.send_raw(char.encode('utf-8'))
        except UnicodeEncodeError:
            # Handle any non-encodable characters
            telnet_logger.warning(f"Could not encode character: {repr(char)}")
        
        # Accumulate normal chars
        self.current_command += char
        return True
    
    async def send_line(self, message: str) -> None:
        """
        Send a line of text with proper CR+LF line ending.
        
        Args:
            message: The message to send
        """
        try:
            # Always use CR+LF for proper terminal handling
            await self.send_raw(f"{message}\r\n".encode('utf-8'))
        except Exception as e:
            telnet_logger.error(f"Error sending line to {self.addr}: {e}")
            raise
    
    async def send_raw(self, data: bytes) -> None:
        """
        Send raw bytes to the client.
        
        Args:
            data: The raw data to send
        """
        try:
            self.writer.write(data)
            await self.writer.drain()
        except Exception as e:
            telnet_logger.error(f"Error sending raw data to {self.addr}: {e}")
            raise
    
    async def show_prompt(self) -> None:
        """
        Display a command prompt to the user.
        This can be overridden to customize the prompt appearance.
        """
        telnet_logger.debug("Sending prompt '>'")
        await self.send_raw(b"> ")
    
    async def on_command_submitted(self, command: str) -> None:
        """
        Hook method that processes a submitted command.
        This should be overridden by subclasses to implement custom command handling.
        The default implementation simply echoes the command back.
        
        Args:
            command: The command that was submitted
        """
        await self.send_line(f"[Echo] {command}")
    
    async def cleanup(self) -> None:
        """
        Clean up resources when the connection is closed.
        """
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception as e:
            telnet_logger.error(f"Error during cleanup for {self.addr}: {e}")