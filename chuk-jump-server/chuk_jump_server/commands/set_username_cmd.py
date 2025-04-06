# chuk_jump_server/commands/set_username_cmd.py
import logging
from chuk_protocol_server.handlers.telnet_handler import TelnetHandler

# Import user management functions
from chuk_jump_server.user_manager import update_username

# logger
logger = logging.getLogger(__name__)

async def handle(handler: TelnetHandler, *args):
    """
    Prompt for a new username, or let them pass it as an argument.
    Example usage:
      username
      username MyNick
    """
    if args:
        # If user typed: 'username MyNick'
        desired_name = " ".join(args).strip()
    else:
        # Otherwise, let's prompt them interactively
        await handler.send_line("Enter your desired username:")

        # In a real implementation, we would await input here
        # For now, use a placeholder approach
        try:
            desired_name = await handler.readline()
            desired_name = desired_name.strip()
        except Exception as e:
            logger.error(f"Error reading input: {e}")
            desired_name = ""

    # check if we got a name
    if not desired_name:
        # no name, set as anonymous
        desired_name = "Anonymous"

    # set the username on the handler
    handler.username = desired_name
    
    # Update the username in the user manager
    success = update_username(handler, desired_name)
    if success:
        logger.debug(f"Username updated in user manager: {desired_name}")
    else:
        logger.warning(f"Failed to update username in user manager: {desired_name}")

    # show the username
    await handler.send_line(f"Your username is now set to: {handler.username}")
