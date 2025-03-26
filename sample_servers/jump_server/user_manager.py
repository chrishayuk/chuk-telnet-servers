# sample_servers/jump_server/user_manager.py
"""
Centralized user management module for the Jump Point server.
This implementation is robust against None values for addresses or connection info.
"""
import logging
from typing import Dict, Any, Optional, Tuple, Set

logger = logging.getLogger(__name__)

# The global registry for connected handlers
_active_handlers: Set[Any] = set()

# Track user info separately for better reliability
# Use handler ID as key (since it's guaranteed to be unique)
_users: Dict[int, Dict[str, Any]] = {}

def register_user(handler: Any, username: Optional[str] = None, addr: Optional[Tuple[str, int]] = None) -> bool:
    """
    Register a user handler and associated metadata.
    
    Args:
        handler: The handler object
        username: Optional username
        addr: Optional address tuple (host, port)
        
    Returns:
        bool: True if registered, False if already exists
    """
    global _active_handlers, _users
    
    # Generate a unique ID for this handler
    handler_id = id(handler)
    
    # Store in the active handlers set
    if handler not in _active_handlers:
        _active_handlers.add(handler)
        
        # Update user info
        _users[handler_id] = {
            'handler': handler,
            'username': username,
            'addr': addr or ('unknown', 0)
        }
        
        logger.debug(f"Registered user: {username or addr or 'unknown'}, handler_id={handler_id}")
        logger.debug(f"Active handlers: {len(_active_handlers)}, Users: {len(_users)}")
        return True
    
    # If handler exists but data changed, update it
    if handler_id in _users:
        if username and _users[handler_id]['username'] != username:
            _users[handler_id]['username'] = username
            logger.debug(f"Updated username for handler_id={handler_id}: {username}")
        if addr and _users[handler_id]['addr'] != addr:
            _users[handler_id]['addr'] = addr
            logger.debug(f"Updated address for handler_id={handler_id}: {addr}")
    
    return False

def unregister_user(handler: Any) -> bool:
    """
    Unregister a user handler.
    
    Args:
        handler: The handler object
        
    Returns:
        bool: True if unregistered, False if not found
    """
    global _active_handlers, _users
    
    handler_id = id(handler)
    removed = False
    
    # Remove from users dict
    if handler_id in _users:
        user_info = _users.pop(handler_id)
        logger.debug(f"Unregistered user: {user_info.get('username') or user_info.get('addr') or 'unknown'}, handler_id={handler_id}")
        removed = True
    
    # Remove from active handlers set
    if handler in _active_handlers:
        _active_handlers.remove(handler)
        logger.debug(f"Active handlers: {len(_active_handlers)}, Users: {len(_users)}")
        removed = True
    
    return removed

def update_username(handler: Any, username: str) -> bool:
    """
    Update the username for a handler.
    
    Args:
        handler: The handler object
        username: The new username
        
    Returns:
        bool: True if updated, False if handler not found
    """
    handler_id = id(handler)
    
    if handler_id in _users:
        old_username = _users[handler_id].get('username')
        _users[handler_id]['username'] = username
        logger.debug(f"Updated username: {old_username} -> {username}, handler_id={handler_id}")
        return True
    
    # If the user isn't registered yet, register them now
    register_user(handler, username=username)
    return True

def get_all_users() -> Dict[int, Dict[str, Any]]:
    """
    Get all registered users.
    
    Returns:
        Dict: Dictionary of user information
    """
    return _users.copy()

def get_all_handlers() -> Set[Any]:
    """
    Get all registered handlers.
    
    Returns:
        Set: Set of handler objects
    """
    return _active_handlers.copy()

def get_user_count() -> int:
    """
    Get the count of registered users.
    
    Returns:
        int: Number of users
    """
    return len(_users)

def handler_exists(handler: Any) -> bool:
    """
    Check if a handler is registered.
    
    Args:
        handler: The handler object
        
    Returns:
        bool: True if registered, False otherwise
    """
    return handler in _active_handlers