# chuk_jump_server/commands/info_cmd.py
from chuk_protocol_server.handlers.telnet_handler import TelnetHandler

# imports
from chuk_jump_server.config import WORLDS

async def handle(handler: TelnetHandler, world_name: str = None):
    """
    Show more detailed info about a specific world.
    Usage: info <world_name>
    """
    if not world_name:
        await handler.send_line("Usage: info <world>")
        return

    world = WORLDS.get(world_name)
    if not world:
        await handler.send_line(f"No such world: {world_name}")
        return

    await handler.send_line(f"World: {world_name}")
    await handler.send_line(f"Description: {world.get('description', '')}")
    addr = world.get("address")
    if addr:
        await handler.send_line(f"Address: {addr[0]}:{addr[1]} (example usage)")
    else:
        await handler.send_line("No address info available.")
