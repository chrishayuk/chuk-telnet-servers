#!/usr/bin/env python3
# telnet_server/handlers/telnet_handler.py
"""
Telnet Protocol Handler

This module provides a handler for the Telnet protocol, which combines
the character and line handlers with telnet-specific protocol handling.
"""
import asyncio
import logging
from typing import Optional, Tuple, List, Dict, Union

# imports
from telnet_server.handlers.line_handler import LineHandler
from telnet_server.protocols.telnet.constants import (
    IAC, DO, DONT, WILL, WONT, SB, SE,
    OPT_ECHO, OPT_SGA, OPT_TERMINAL, OPT_NAWS, OPT_LINEMODE,
    get_command_name, get_option_name
)
from telnet_server.protocols.telnet.options import OptionManager
from telnet_server.protocols.telnet.terminal import TerminalInfo
from telnet_server.protocols.telnet.negotiation import (
    send_command, send_subnegotiation, request_terminal_type, 
    send_initial_negotiations, process_negotiation
)
from telnet_server.utils.terminal_codes import CRLF, CR, LF

# Create logger for this module
logger = logging.getLogger('telnet-protocol')

class TelnetHandler(LineHandler):
    """
    Telnet protocol handler that combines character and line handling
    with telnet-specific protocol features.
    
    This class extends the LineHandler to add support for the Telnet protocol,
    including option negotiation, terminal handling, and proper control character
    processing. It automatically detects and adapts to the client's capabilities.
    """
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Initialize the telnet handler.
        
        Args:
            reader: The stream reader for reading from the client
            writer: The stream writer for writing to the client
        """
        super().__init__(reader, writer)
        
        # Telnet-specific state
        self.line_mode = False  # Start in character mode
        
        # Initialize telnet components
        self.options = OptionManager()
        self.options.initialize_options([
            OPT_ECHO, OPT_SGA, OPT_TERMINAL, OPT_NAWS, OPT_LINEMODE
        ])
        
        self.terminal = TerminalInfo()
        
        # Buffer for accumulating partial telnet commands
        self.iac_buffer = bytearray()
    
    async def handle_client(self) -> None:
        """
        Main client handling loop for telnet.
        
        This method handles telnet protocol negotiation and then
        delegates to the appropriate handling mode based on the
        negotiated options.
        """
        try:
            await self.on_connect()
            
            # Negotiate terminal settings
            await self._send_initial_negotiations()
            
            # Send welcome message
            await self.send_welcome()
            
            # Main processing loop
            should_continue = True
            while self.running and should_continue:
                try:
                    if self.line_mode:
                        # Line mode processing
                        line = await self._read_line_with_telnet()
                        if line is None:
                            logger.debug(f"Client {self.addr} disconnected")
                            break
                        
                        should_continue = await self.process_line(line)
                    else:
                        # Character mode processing
                        data = await self._read_mixed_mode()
                        if data is None:
                            logger.debug(f"Client {self.addr} disconnected")
                            break
                        
                        if data:  # Only process if we got data
                            for char in data:
                                should_continue = await self.default_process_character(char)
                                if not should_continue:
                                    break
                            
                            if not should_continue:
                                break
                except asyncio.CancelledError:
                    # The task was cancelled - exit gracefully
                    logger.debug(f"Client handling task for {self.addr} was cancelled")
                    break
                except Exception as e:
                    # Handle other exceptions
                    await self.on_error(e)
                    # Decide whether to continue or break based on the error
                    if "Connection reset" in str(e) or "Broken pipe" in str(e):
                        break
                    # For other errors, wait a bit to avoid spamming logs
                    await asyncio.sleep(1)
        finally:
            # Clean up
            await self.on_disconnect()
            await self.cleanup()
    
    async def _send_initial_negotiations(self) -> None:
        """
        Send initial telnet option negotiations.
        
        This sets up the client terminal mode appropriately.
        """
        await send_initial_negotiations(self.writer)
    
    async def _read_mixed_mode(self, timeout: float = 300) -> Optional[str]:
        """
        Read in mixed mode, handling both telnet commands and regular data.
        
        This method handles the complexities of telnet protocol interleaved
        with regular character data, processing telnet commands and
        returning only the actual character data for the application.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            The processed character data, None if connection closed,
            or an empty string on timeout
        """
        try:
            # Read a chunk of data with timeout
            raw_data = await asyncio.wait_for(self.reader.read(1024), timeout=timeout)
            if not raw_data:
                return None  # Connection closed
            
            logger.debug(f"Raw data received: {[b for b in raw_data]}")
            
            # Process the data to handle telnet commands and CR/LF combinations
            processed_chars = ""
            i = 0
            while i < len(raw_data):
                byte = raw_data[i]
                
                # Check for IAC (telnet command)
                if byte == IAC:
                    i += 1
                    if i >= len(raw_data):
                        # IAC at end of buffer - wait for more data
                        self.iac_buffer.append(IAC)
                        break
                    
                    cmd = raw_data[i]
                    if cmd in (DO, DONT, WILL, WONT):
                        # These commands have one option byte
                        i += 1
                        if i < len(raw_data):
                            option = raw_data[i]
                            await process_negotiation(
                                self.reader, self.writer, cmd, option, self.options
                            )
                            # Update line mode flag based on LINEMODE option
                            if option == OPT_LINEMODE:
                                self.line_mode = (
                                    self.options.is_local_enabled(OPT_LINEMODE) or
                                    self.options.is_remote_enabled(OPT_LINEMODE)
                                )
                        else:
                            # Incomplete command - save in buffer
                            self.iac_buffer.extend([IAC, cmd])
                            break
                    elif cmd == SB:
                        # Subnegotiation - read until IAC SE
                        sub_data = bytearray()
                        i += 1
                        found_se = False
                        while i < len(raw_data) - 1:
                            if raw_data[i] == IAC and raw_data[i+1] == SE:
                                i += 1  # Skip to SE
                                found_se = True
                                break
                            sub_data.append(raw_data[i])
                            i += 1
                        
                        if found_se:
                            # Process the complete subnegotiation
                            self._process_subnegotiation(sub_data)
                        else:
                            # Incomplete subnegotiation - save in buffer
                            self.iac_buffer.extend([IAC, SB])
                            self.iac_buffer.extend(sub_data)
                            break
                    # IAC IAC means literal 255
                    elif cmd == IAC:
                        processed_chars += chr(IAC)
                    
                    i += 1
                    continue
                
                # Check for CR+LF or CR+NUL combinations
                if byte == CR:
                    if i+1 < len(raw_data):
                        next_byte = raw_data[i+1]
                        if next_byte == LF:
                            # CR+LF combo - treat as a single newline
                            processed_chars += "\n"
                            i += 2
                            continue
                        elif next_byte == 0:  # NUL
                            # CR+NUL combo - treat as a single CR
                            processed_chars += "\r"
                            i += 2
                            continue
                    
                    # Standalone CR
                    processed_chars += "\r"
                    i += 1
                    continue
                
                # Regular character - make sure it's in printable ASCII range or control codes we care about
                if (32 <= byte <= 126) or byte in (8, 10, 13, 3, 127):
                    processed_chars += chr(byte)
                
                i += 1
            
            logger.debug(f"Processed data: {repr(processed_chars)}")
            return processed_chars
        
        except asyncio.TimeoutError:
            return ""  # Timeout - return empty string
        except Exception as e:
            logger.error(f"Error in _read_mixed_mode: {e}")
            return None  # Error - treat as connection closed
    
    def _process_subnegotiation(self, data: bytearray) -> None:
        """
        Process telnet subnegotiation data.
        
        This handles extended option data like terminal type and window size.
        
        Args:
            data: The subnegotiation data (without IAC SB and IAC SE)
        """
        logger.debug(f"Processing subnegotiation data: {list(data)}")
        
        if not data:
            return
        
        option = data[0]
        
        if option == OPT_TERMINAL and len(data) > 1:
            if data[1] == 0:  # IS
                self.terminal.process_terminal_type_data(data[1:])
        
        elif option == OPT_NAWS and len(data) >= 5:
            self.terminal.process_window_size_data(data[1:])
    
    async def _read_line_with_telnet(self, timeout: float = 300) -> Optional[str]:
        """
        Read a complete line in line mode, handling telnet commands.
        
        This method works when the client has negotiated line mode.
        
        Args:
            timeout: Maximum time to wait in seconds
            
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
                if data[i] == IAC:
                    i += 1
                    if i < len(data):
                        if data[i] == IAC:  # Literal IAC
                            line_bytes.append(IAC)
                        # Skip other telnet sequences
                        elif data[i] in (DO, DONT, WILL, WONT):
                            i += 1  # Skip option byte
                    i += 1
                    continue
                
                # Skip CR/LF at the end
                if data[i] in (CR, LF) and i >= len(data) - 2:
                    i += 1
                    continue
                
                # Regular character
                line_bytes.append(data[i])
                i += 1
            
            line_str = line_bytes.decode('utf-8', errors='ignore')
            logger.debug(f"Line-mode read => {repr(line_str)}")
            return line_str
            
        except asyncio.TimeoutError:
            logger.debug("Timeout reading line")
            return None
        except Exception as e:
            logger.error(f"Error in _read_line_with_telnet: {e}")
            return None
    
    async def send_welcome(self) -> None:
        """
        Send a welcome message to the client.
        
        This is a hook method that can be overridden by subclasses to
        send a custom welcome message.
        """
        await self.send_line("Welcome! This server can handle line or character mode.")
        await self.show_prompt()
    
    async def process_line(self, line: str) -> bool:
        """
        Process a complete line in line mode.
        
        Args:
            line: The line to process
            
        Returns:
            True to continue processing, False to terminate the connection
        """
        logger.debug(f"process_line => {repr(line)}")
        
        if line.lower() in ['quit', 'exit', 'q']:
            await self.send_line("Goodbye (line mode)!")
            return False
        
        # This hook allows subclasses to provide custom command handling
        await self.on_command_submitted(line)
        
        # Only show prompt if we're continuing
        await self.show_prompt()
        return True
    
    async def on_command_submitted(self, command: str) -> None:
        """
        Hook method that processes a submitted command.
        
        This should be overridden by subclasses to implement custom command handling.
        The default implementation simply echoes the command back.
        
        Args:
            command: The command that was submitted
        """
        await self.send_line(f"[Echo] {command}")