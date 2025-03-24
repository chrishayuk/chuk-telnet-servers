#!/usr/bin/env python3
# telnet_server/server_launcher.py
"""
Generic Telnet Server Launcher

This module provides a flexible, configuration-driven approach to launching 
Telnet servers. It supports dynamic handler loading, configuration file parsing,
and provides a universal entry point for different types of Telnet servers.

Key Features:
- Dynamic handler class loading
- YAML configuration support
- Configurable logging levels
- Command-line argument parsing
- Graceful error handling
"""

import asyncio
import argparse
import importlib
import logging
import sys
import os
from typing import Type, Dict, Any, Optional

# Core server and protocol handler imports
from telnet_server.server import TelnetServer
from telnet_server.telnet_protocol_handlers import BaseProtocolHandler

def setup_logging(verbosity: int = 1) -> None:
    """
    Configure logging based on verbosity level.
    
    Logging levels:
    - 0: WARNING - Only show critical issues
    - 1: INFO - Standard operational information
    - 2: DEBUG - Detailed diagnostic information
    
    Args:
        verbosity (int): Logging verbosity level (0-2)
    """
    # Map verbosity levels to logging levels
    log_levels = {
        0: logging.WARNING,  # Minimal logging, only critical issues
        1: logging.INFO,     # Standard operational information
        2: logging.DEBUG     # Comprehensive diagnostic details
    }
    
    # Select the appropriate logging level
    level = log_levels.get(verbosity, logging.DEBUG)
    
    # Configure logging with a detailed format
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def load_handler_class(handler_path: str) -> Type[BaseProtocolHandler]:
    """
    Dynamically load a Telnet protocol handler class from a string path.
    
    The handler path follows the format: 'module.submodule:ClassName'
    
    Args:
        handler_path (str): Full path to the handler class
    
    Returns:
        Type[TelnetProtocolHandler]: The loaded handler class
    
    Raises:
        ValueError: If the handler cannot be loaded
        TypeError: If the loaded class is not a valid protocol handler
    """
    try:
        # Split the path into module path and class name
        module_path, class_name = handler_path.split(':')
        
        # Dynamically import the module
        module = importlib.import_module(module_path)
        
        # Retrieve the handler class from the module
        handler_class = getattr(module, class_name)
        
        # Verify it's a proper Telnet protocol handler
        if not issubclass(handler_class, BaseProtocolHandler):
            raise TypeError(f"{class_name} must be a subclass of TelnetProtocolHandler")
        
        return handler_class
    
    except (ValueError, ImportError, AttributeError) as e:
        # Provide a detailed error message for troubleshooting
        raise ValueError(f"Could not load handler class '{handler_path}': {e}")

def prepare_server_kwargs(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare additional server configuration parameters.
    
    Filters out standard configuration keys to allow custom server attributes.
    
    Args:
        config (Dict[str, Any]): Full configuration dictionary
    
    Returns:
        Dict[str, Any]: Additional server configuration parameters
    """
    # Remove standard keys to allow custom server configuration
    standard_keys = {'host', 'port', 'handler_class'}
    return {k: v for k, v in config.items() if k not in standard_keys}

async def run_server(
    handler_class: Type[BaseProtocolHandler], 
    host: str, 
    port: int, 
    server_kwargs: Optional[Dict[str, Any]] = None
) -> None:
    """
    Create and run a Telnet server with the specified handler.
    
    This function sets up the server, applies any additional configuration,
    and starts the server asynchronously.
    
    Args:
        handler_class (Type[TelnetProtocolHandler]): Handler class to use
        host (str): Host address to bind to
        port (int): Port number to listen on
        server_kwargs (Optional[Dict[str, Any]]): Additional server configuration
    """
    # Default to empty dictionary if no kwargs provided
    server_kwargs = server_kwargs or {}
    
    # Create the server instance
    server = TelnetServer(host, port, handler_class)
    
    # Apply any additional server attributes from configuration
    for key, value in server_kwargs.items():
        try:
            setattr(server, key, value)
        except AttributeError:
            logging.warning(f"Could not set server attribute {key}")
    
    # Start the server
    await server.start_server()

def main():
    """
    Main entry point for the Telnet server launcher.
    
    Handles:
    - Command-line argument parsing
    - Configuration loading
    - Server initialization
    - Error handling
    
    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    # Create argument parser
    parser = argparse.ArgumentParser(
        description='Flexible Telnet Server Launcher',
        epilog='Launch Telnet servers with ease!'
    )
    
    # Mutually exclusive group for handler specification
    handler_group = parser.add_mutually_exclusive_group(required=True)
    handler_group.add_argument(
        'handler', 
        type=str, 
        nargs='?', 
        default=None,
        help='Handler class path (e.g., "servers.echo_server:EchoTelnetHandler")'
    )
    handler_group.add_argument(
        '--config', '-c', 
        type=str,
        help='Path to YAML configuration file'
    )
    
    # Additional server configuration options
    parser.add_argument(
        '--host', 
        type=str, 
        default='0.0.0.0', 
        help='Host address to bind to (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--port', 
        type=int, 
        default=8023, 
        help='Port to listen on (default: 8023)'
    )
    parser.add_argument(
        '-v', '--verbose', 
        action='count', 
        default=1,
        help='Increase verbosity (can be used multiple times)'
    )
    
    # Parse command-line arguments
    args = parser.parse_args()
    
    # Setup logging based on verbosity
    setup_logging(args.verbose)
    
    # Create logger for this module
    logger = logging.getLogger('server-launcher')
    
    try:
        # Determine server configuration
        if args.config:
            # Import ServerConfig here to avoid circular imports
            from telnet_server.server_config import ServerConfig
            
            # Load configuration from file
            config = ServerConfig.load_config(args.config)
            logger.info(f"Loaded configuration from {args.config}")
            
            # Get handler class from configuration
            handler_class = load_handler_class(config['handler_class'])
            
            # Determine host and port, with command-line args taking precedence
            host = args.host if args.host != '0.0.0.0' else config.get('host', '0.0.0.0')
            port = args.port if args.port != 8023 else config.get('port', 8023)
            
            # Prepare additional server configuration
            server_kwargs = prepare_server_kwargs(config)
        
        else:
            # Load handler class from command line
            handler_class = load_handler_class(args.handler)
            host = args.host
            port = args.port
            server_kwargs = {}
        
        # Log server startup details
        logger.info(f"Starting server with {handler_class.__name__} on {host}:{port}")
        
        # Run the server
        asyncio.run(run_server(handler_class, host, port, server_kwargs))
    
    except KeyboardInterrupt:
        # Graceful handling of Ctrl-C
        logger.info("Server shutdown initiated by user.")
        return 0
    
    except Exception as e:
        # Comprehensive error handling
        logger.error(f"Error launching server: {e}")
        
        # Additional debug information for verbose mode
        if args.verbose >= 2:
            import traceback
            traceback.print_exc()
        
        return 1
    
    finally:
        logger.info("Server process completed.")
    
    return 0

# Entry point for script execution
if __name__ == "__main__":
    sys.exit(main())