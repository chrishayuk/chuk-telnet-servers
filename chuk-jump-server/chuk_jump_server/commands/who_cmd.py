# chuk_jump_server/commands/who_cmd.py
import logging
from chuk_protocol_server.handlers.telnet_handler import TelnetHandler

# Import user management functions
from chuk_jump_server.user_manager import get_all_users, get_user_count

logger = logging.getLogger(__name__)

async def handle(handler: TelnetHandler, *args):
    """
    List all connected users with usernames using the user manager.
    Filters out unnamed/unknown handlers.
    """
    # Get user info from the user manager
    users = get_all_users()
    user_count = get_user_count()
    
    # Debug logging
    logger.debug(f"[who_cmd] User count: {user_count}")
    logger.debug(f"[who_cmd] Current handler ID: {id(handler)}")
    
    # Build user list for debug logging
    user_list = []
    for user_id, user_data in users.items():
        username = user_data.get('username')
        addr = user_data.get('addr')
        user_list.append(f"{username or str(addr or 'unknown')}")
    
    logger.debug(f"[who_cmd] Users: {user_list}")
    
    # Display header
    await handler.send_line("Currently connected users:")
    
    # Get the ID of the current handler for marking "you"
    current_handler_id = id(handler)
    
    # Track if we've displayed any users
    displayed_users = 0
    shown_current_user = False
    
    # Display each user that has a username set
    for user_id, user_data in users.items():
        try:
            # Extract user info
            user_handler = user_data.get('handler')
            username = user_data.get('username')
            
            # Skip handlers without usernames set
            if not username or username == "Anonymous":
                continue
                
            # Determine if this is the current user
            is_current_user = (user_handler is handler or user_id == current_handler_id)
            
            # Display the user
            if is_current_user:
                await handler.send_line(f"  - {username} (you)")
                shown_current_user = True
            else:
                await handler.send_line(f"  - {username}")
                
            displayed_users += 1
        except Exception as e:
            logger.error(f"Error displaying user info: {e}")
    
    # If we didn't show the current user and they have a username, show them at the end
    if not shown_current_user and handler.username and handler.username != "Anonymous":
        await handler.send_line(f"  - {handler.username} (you)")
        displayed_users += 1
    
    # If no users were displayed, show a message
    if displayed_users == 0:
        await handler.send_line("  (No named users connected)")