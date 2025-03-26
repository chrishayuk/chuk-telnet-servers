# sample_servers/jump_server/handler.py
import logging
import importlib
from typing import Optional, Dict, Callable, Any

from telnet_server.handlers.telnet_handler import TelnetHandler

# Import from user manager and config
from sample_servers.jump_server.user_manager import (
    register_user, unregister_user, update_username, 
    get_all_users, get_all_handlers
)
from sample_servers.jump_server.config import WORLDS

logger = logging.getLogger('jump-point-handler')

class JumpPointTelnetHandler(TelnetHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.asking_username = False       # Flag for initial username prompt
        self.username = None               # The user's current name or None
        self.addr = None                   # Will store the client's address
        self.commands = self._load_commands()
        
        # Register with user manager immediately on creation
        # This ensures tracking even if peer info is unavailable
        register_user(self)
        logger.debug(f"Handler created and registered with user manager")

    def __del__(self):
        """
        Destructor to ensure handler is removed from tracking.
        """
        try:
            unregister_user(self)
            logger.debug(f"Handler destroyed and unregistered from user manager")
        except Exception as e:
            # This might fail during interpreter shutdown
            pass

    def _load_commands(self) -> Dict[str, Callable]:
        """
        Dynamically load command modules from the commands directory.
        Returns a dictionary mapping command names to handler functions.
        """
        command_modules = {
            'who': 'sample_servers.jump_server.commands.who_cmd',
            'username': 'sample_servers.jump_server.commands.set_username_cmd',
            'list': 'sample_servers.jump_server.commands.list_cmd',
            'help': 'sample_servers.jump_server.commands.help_cmd',
            'info': 'sample_servers.jump_server.commands.info_cmd',
            'jump': 'sample_servers.jump_server.commands.jump_cmd',
        }
        
        commands = {}
        for cmd_name, module_path in command_modules.items():
            try:
                module = importlib.import_module(module_path)
                if hasattr(module, 'handle'):
                    commands[cmd_name] = module.handle
                else:
                    logger.error(f"Command module {module_path} lacks a handle function")
            except ImportError as e:
                logger.error(f"Failed to import command module {module_path}: {e}")
        
        return commands

    async def on_connection_made(self) -> None:
        """
        Called when a client first connects. Store their IP/port.
        """
        try:
            peername = self.transport.get_extra_info('peername')
            if peername:
                self.addr = peername
                # Update the user record with the address if available
                register_user(self, addr=self.addr, username=self.username)
            else:
                self.addr = ('unknown', 0)
                logger.warning("Client connected but peername is None")
        except Exception as e:
            logger.error(f"Error getting peer info: {e}")
            self.addr = ('unknown', 0)

        logger.debug(f"Connection established from {self.addr}")
        await super().on_connection_made()

    async def on_connection_lost(self, exc: Optional[Exception]) -> None:
        """
        Called when a client disconnects.
        """
        logger.debug(f"Connection lost from {self.addr}, username={self.username}")
        
        # Unregister from user manager
        unregister_user(self)
            
        await super().on_connection_lost(exc)

    async def send_welcome(self) -> None:
        """
        Sends a welcome banner and prompts for a username.
        """
        welcome_lines = [
            "Welcome to the Jump Point!",
            "-------------------------",
            "(Type 'help' for commands, 'quit' to disconnect)"
        ]
        for line in welcome_lines:
            await self.send_line(line)

        await self.send_line("Please enter your desired username:")
        self.asking_username = True
        await self.show_prompt()

    async def readline(self) -> str:
        """
        Helper method to read a line from the user.
        """
        logger.warning("readline() method called but not fully implemented")
        return ""

    async def on_command_submitted(self, command: str) -> None:
        """
        Called each time the user presses Enter.
        """
        logger.info(f"Received command from {self.addr}: {command}")
        line = command.strip()

        # Handle initial username prompt
        if self.asking_username:
            self.asking_username = False
            self.username = line or "Anonymous"
            
            # Update username in the user manager
            update_username(self, self.username)
            
            await self.send_line(f"Hello, {self.username}!")
            await self.show_prompt()
            return

        # Parse command line
        parts = line.split()
        if not parts:
            await self.show_prompt()
            return

        cmd = parts[0].lower()
        args = parts[1:]

        # Handle built-in quit command
        if cmd == 'quit':
            await self.disconnect()
            return

        # Handle username command specially to ensure we update the user manager
        if cmd == 'username':
            if len(args) > 0:
                # If they provided a username with the command
                new_username = " ".join(args)
                self.username = new_username
                update_username(self, self.username)
                await self.send_line(f"Your username is now: {self.username}")
            else:
                # Otherwise we'll rely on the username_cmd module
                if 'username' in self.commands:
                    await self.commands['username'](self, *args)
                else:
                    await self.send_line("The username command is not available.")
            
            await self.show_prompt()
            return

        # Handle commands using the loaded command modules
        if cmd in self.commands:
            await self.commands[cmd](self, *args)
        else:
            # Fallback for unknown commands
            await self.send_line(f"Unknown command: {cmd}. Type 'help' for commands.")

        await self.show_prompt()