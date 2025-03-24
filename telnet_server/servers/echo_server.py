#!/usr/bin/env python3
"""
Echo Telnet Server

A Telnet server that uses TelnetProtocolHandler to manage Telnet negotiation and control sequences.
This echo server overrides the on_command_submitted() hook to echo submitted commands.
"""

import logging
import sys

from telnet_server.protocol_handlers.telnet_protocol_handler import TelnetProtocolHandler

logger = logging.getLogger('echo-telnet-server')

class EchoTelnetHandler(TelnetProtocolHandler):
    """
    Echo Telnet Handler that inherits all Telnet-specific processing from TelnetProtocolHandler.
    
    It only overrides the on_command_submitted() hook to echo back submitted commands.
    """
    async def on_command_submitted(self, command: str) -> None:
        """
        Echo the submitted command back to the client.
        Terminates the session if the command is 'quit', 'exit', or 'q'.
        """
        logger.info(f"Received command from {self.addr}: {command}")
        if command.lower() in ['quit', 'exit', 'q']:
            await self.send_line("Goodbye!")
            self.running = False
        else:
            await self.send_line(f"Echo: {command}")

def main():
    """
    Direct launch method for the echo server.
    
    Uses the server launcher infrastructure to run the Telnet server with EchoTelnetHandler.
    """
    try:
        from telnet_server.server_launcher import main as server_launcher

        sys.argv = [
            sys.argv[0],
            "telnet_server.echo_server:EchoTelnetHandler",  # Handler path
            "--host", "0.0.0.0",
            "--port", "8023"
        ]
        server_launcher()
    except KeyboardInterrupt:
        logger.info("Server shutdown initiated by user.")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
    finally:
        logger.info("Server process exiting.")

if __name__ == "__main__":
    main()
