# chuk_jump_server/commands/help_cmd.py
from chuk_protocol_server.handlers.telnet_handler import TelnetHandler

async def handle(handler: TelnetHandler, *args):
    """
    Display available Jump Point commands.
    """
    lines = [
        "Jump Point Commands:",
        "  username         - Set or update your username",
        "  list             - Show all known worlds",
        "  info <world>     - Show details about a specific world",
        "  jump <world>     - 'Travel' to that world (demo only)",
        "  who              - See who's currently connected",
        "  help             - Show this help message",
        "  quit             - Disconnect from server",
    ]

    # loop through each line
    for line in lines:
        # send the line from the handler
        await handler.send_line(line)
