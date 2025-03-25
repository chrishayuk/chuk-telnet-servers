#!/usr/bin/env python3
# telnet_server/server_launcher.py
"""
Universal Server Launcher

This module provides a flexible, configuration-driven approach to launching 
servers with different transport protocols. It supports dynamic handler loading,
configuration file parsing, and provides a universal entry point for different
types of servers and transport protocols.

Key Features:
- Support for multiple transport protocols (Telnet, WebSocket, Auto-Detect)
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
from typing import Type, Dict, Any, Optional, Union

# Import base classes
from telnet_server.handlers.base_handler import BaseHandler

# Import transport constants
# These are explicitly defined here to avoid circular imports
TRANSPORT_TELNET = "telnet"
TRANSPORT_WEBSOCKET = "websocket"
TRANSPORT_AUTO_DETECT = "auto-detect"
SUPPORTED_TRANSPORTS = [TRANSPORT_TELNET, TRANSPORT_WEBSOCKET, TRANSPORT_AUTO_DETECT]

# Import server classes
from telnet_server.server import TelnetServer

def setup_logging(verbosity: int = 1) -> None:
    """
    Configure logging based on verbosity level.
    
    Logging levels:
    - 0: WARNING - Only show critical issues
    - 1: INFO - Standard operational information
    - 2: DEBUG - Detailed diagnostic information
    
    Args:
        verbosity: Logging verbosity level (0-2)
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

def load_handler_class(handler_path: str) -> Type[BaseHandler]:
    """
    Dynamically load a protocol handler class from a string path.
    
    The handler path follows the format: 'module.submodule:ClassName'
    
    Args:
        handler_path: Full path to the handler class
    
    Returns:
        The loaded handler class
    
    Raises:
        ValueError: If the handler cannot be loaded
        TypeError: If the loaded class is not a valid handler
    """
    try:
        # Split the path into module path and class name
        module_path, class_name = handler_path.split(':')
        
        # Dynamically import the module
        module = importlib.import_module(module_path)
        
        # Retrieve the handler class from the module
        handler_class = getattr(module, class_name)
        
        # Verify it's a proper handler
        if not issubclass(handler_class, BaseHandler):
            raise TypeError(f"{class_name} must be a subclass of BaseHandler")
        
        return handler_class
    
    except (ValueError, ImportError, AttributeError) as e:
        # Provide a detailed error message for troubleshooting
        raise ValueError(f"Could not load handler class '{handler_path}': {e}")

def create_server_instance(
    handler_class: Type[BaseHandler],
    config: Dict[str, Any]
) -> Union[TelnetServer, Any]:
    """
    Create a server instance based on the configuration.
    
    Args:
        handler_class: The handler class to use
        config: Server configuration including transport type
        
    Returns:
        A configured server instance
        
    Raises:
        ValueError: If the transport type is invalid or required modules are missing
    """
    # Get server configuration
    host = config.get('host', '0.0.0.0')
    port = config.get('port', 8023)
    transport = config.get('transport', TRANSPORT_TELNET)
    
    # Validate transport type
    if transport not in SUPPORTED_TRANSPORTS:
        raise ValueError(f"Unsupported transport: {transport}. "
                         f"Supported transports: {', '.join(SUPPORTED_TRANSPORTS)}")
    
    # Extract common WebSocket configuration for both WebSocket and Auto-Detect modes
    ws_path = config.get('ws_path', '/telnet')
    use_ssl = config.get('use_ssl', False)
    ssl_cert = config.get('ssl_cert')
    ssl_key = config.get('ssl_key')
    ping_interval = config.get('ping_interval', 30)
    ping_timeout = config.get('ping_timeout', 10)
    allow_origins = config.get('allow_origins', ['*'])
    
    # Create the server based on transport type
    if transport == TRANSPORT_TELNET:
        server = TelnetServer(host, port, handler_class)
        
    elif transport == TRANSPORT_WEBSOCKET:
        # Import WebSocketServer dynamically to avoid import errors
        # if the websockets package is not installed
        try:
            # First try importing from the transports package
            try:
                from telnet_server.transports.websocket import WebSocketServer
            except ImportError:
                # If that fails, try importing directly from the module
                from telnet_server.transports.websocket.ws_server import WebSocketServer
            
            # Create WebSocket server with SSL if configured
            if use_ssl and ssl_cert and ssl_key:
                server = WebSocketServer(
                    host, port, handler_class,
                    path=ws_path,
                    ssl_cert=ssl_cert,
                    ssl_key=ssl_key,
                    ping_interval=ping_interval,
                    ping_timeout=ping_timeout,
                    allow_origins=allow_origins
                )
            else:
                server = WebSocketServer(
                    host, port, handler_class,
                    path=ws_path,
                    ping_interval=ping_interval,
                    ping_timeout=ping_timeout,
                    allow_origins=allow_origins
                )
                
        except ImportError as e:
            raise ImportError(
                f"Could not create WebSocket server: {e}. "
                "WebSocket transport requires the 'websockets' package. "
                "Install it with: pip install websockets"
            )
            
    elif transport == TRANSPORT_AUTO_DETECT:
        # Import AutoDetectServer dynamically
        try:
            from telnet_server.transports.auto_detect_server import AutoDetectServer
            
            # Create auto-detect server with the appropriate settings
            if use_ssl and ssl_cert and ssl_key:
                server = AutoDetectServer(
                    host, port, handler_class,
                    ws_path=ws_path,
                    ssl_cert=ssl_cert,
                    ssl_key=ssl_key,
                    ping_interval=ping_interval,
                    ping_timeout=ping_timeout,
                    allow_origins=allow_origins
                )
            else:
                server = AutoDetectServer(
                    host, port, handler_class,
                    ws_path=ws_path,
                    ping_interval=ping_interval,
                    ping_timeout=ping_timeout,
                    allow_origins=allow_origins
                )
        
        except ImportError as e:
            raise ImportError(
                f"Could not create Auto-Detect server: {e}."
            )
    else:
        # This should never happen due to earlier validation
        raise ValueError(f"Unsupported transport: {transport}")
    
    # Apply any additional server attributes
    excluded_keys = {'host', 'port', 'handler_class', 'transport', 
                    'ws_path', 'use_ssl', 'ssl_cert', 'ssl_key',
                    'ping_interval', 'ping_timeout', 'allow_origins'}
    
    for key, value in config.items():
        if key not in excluded_keys:
            try:
                setattr(server, key, value)
                logging.debug(f"Set server attribute: {key} = {value}")
            except AttributeError:
                logging.warning(f"Could not set server attribute: {key}")
    
    return server

async def run_server(server: Union[TelnetServer, Any]) -> None:
    """
    Run a server instance.
    
    Args:
        server: The server instance to run
    """
    await server.start_server()

def main():
    """
    Main entry point for the server launcher.
    
    Handles:
    - Command-line argument parsing
    - Configuration loading
    - Server initialization
    - Error handling
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Create argument parser
    parser = argparse.ArgumentParser(
        description='Universal Server Launcher',
        epilog='Launch servers with different transport protocols'
    )
    
    # Mutually exclusive group for handler specification
    handler_group = parser.add_mutually_exclusive_group(required=True)
    handler_group.add_argument(
        'handler', 
        type=str, 
        nargs='?', 
        default=None,
        help='Handler class path (e.g., "telnet_server.handlers.telnet_handler:TelnetHandler")'
    )
    handler_group.add_argument(
        '--config', '-c', 
        type=str,
        help='Path to YAML configuration file'
    )
    
    # Server configuration options
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
        '--transport',
        type=str,
        choices=SUPPORTED_TRANSPORTS,
        default=TRANSPORT_TELNET,
        help=f'Transport protocol to use (default: {TRANSPORT_TELNET})'
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
            
            # Command-line args take precedence over config file
            if args.host != '0.0.0.0':
                config['host'] = args.host
            if args.port != 8023:
                config['port'] = args.port
            if args.transport != TRANSPORT_TELNET:
                config['transport'] = args.transport
            
            # Validate the configuration
            ServerConfig.validate_config(config)
        
        else:
            # Use command-line arguments
            handler_class = load_handler_class(args.handler)
            config = {
                'host': args.host,
                'port': args.port,
                'transport': args.transport
            }
        
        # Create the server instance
        server = create_server_instance(handler_class, config)
        
        # Log server startup details
        transport_name = config.get('transport', TRANSPORT_TELNET).upper()
        logger.info(f"Starting {transport_name} server with {handler_class.__name__} "
                  f"on {config.get('host', '0.0.0.0')}:{config.get('port', 8023)}")
        
        # Run the server
        asyncio.run(run_server(server))
    
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