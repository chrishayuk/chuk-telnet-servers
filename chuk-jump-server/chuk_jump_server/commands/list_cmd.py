# chuk_jump_server/commands/list_cmd.py
from chuk_protocol_server.handlers.telnet_handler import TelnetHandler

# imports
from chuk_jump_server.config import WORLDS

async def handle(handler: TelnetHandler, *args):
    """
    Show the list of available worlds from config.WORLDS.
    """
    await handler.send_line("Available Worlds:")
    for world_name, data in WORLDS.items():
        desc = data.get("description", "(no description)")
        await handler.send_line(f"  {world_name} - {desc}")
