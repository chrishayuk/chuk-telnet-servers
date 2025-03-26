# sample_servers/jump_server/config.py
import logging

logger = logging.getLogger(__name__)

# A global set for tracking active handlers
# This needs to be in the shared module that both the handler and commands can access
ACTIVE_HANDLERS = set()

# Available worlds
WORLDS = {
    "CodersDen": {
        "description": "AI coding Q&A world",
        "address": ("192.168.1.10", 8024)
    },
    "StoryVerse": {
        "description": "Narrative realm for text adventures",
        "address": ("192.168.1.11", 8025)
    },
    "DataDoctor": {
        "description": "Data science & analytics realm",
        "address": ("192.168.1.12", 8026)
    }
}

def register_handler(handler):
    """
    Register a handler to the global ACTIVE_HANDLERS set.
    Returns True if added, False if already exists.
    """
    logger.debug(f"Registering handler: {handler}")
    if handler not in ACTIVE_HANDLERS:
        ACTIVE_HANDLERS.add(handler)
        logger.debug(f"ACTIVE_HANDLERS size after add: {len(ACTIVE_HANDLERS)}")
        return True
    return False

def unregister_handler(handler):
    """
    Remove a handler from the global ACTIVE_HANDLERS set.
    Returns True if removed, False if not found.
    """
    logger.debug(f"Unregistering handler: {handler}")
    if handler in ACTIVE_HANDLERS:
        ACTIVE_HANDLERS.remove(handler)
        logger.debug(f"ACTIVE_HANDLERS size after remove: {len(ACTIVE_HANDLERS)}")
        return True
    return False

def get_all_handlers():
    """
    Return a copy of the ACTIVE_HANDLERS set.
    """
    return ACTIVE_HANDLERS.copy()