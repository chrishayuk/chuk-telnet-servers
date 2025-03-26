# sample_servers/jump_server/commands/jump_cmd.py
from telnet_server.handlers.telnet_handler import TelnetHandler

# imports
from sample_servers.jump_server.config import WORLDS

async def handle(handler: TelnetHandler, world_name: str = None):
    """
    Demonstrate 'jumping' to another world. In a real system, you'd proxy or reconnect.
    """
    if not world_name:
        await handler.send_line("Usage: jump <world>")
        return

    world = WORLDS.get(world_name)
    if not world:
        await handler.send_line(f"No such world: {world_name}")
        return
    
    await handler.send_line(f"You jump to {world_name}!")
    addr = world.get("address")
    if addr:
        await handler.send_line(f"(In a real scenario, you'd connect to {addr[0]}:{addr[1]})")
