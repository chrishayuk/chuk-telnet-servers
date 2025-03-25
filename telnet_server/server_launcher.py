#!/usr/bin/env python3
# telnet_server/server_launcher.py
"""
Universal Server Launcher

This module provides a flexible, configuration-driven approach to launching 
servers with different transport protocols. It supports dynamic handler loading,
YAML configuration parsing, and launching multiple servers concurrently.
"""

import asyncio
import argparse
import importlib
import logging
import sys
import os
from typing import Type, Dict, Any, Optional, Union, List

# imports
from telnet_server.handlers.base_handler import BaseHandler
from telnet_server.server import TelnetServer  # For fallback

# Define transport constants
TRANSPORT_TELNET = "telnet"
TRANSPORT_WEBSOCKET = "websocket"
TCP_TRANSPORT = "tcp"
WS_TELNET_TRANSPORT = "ws_telnet"
SUPPORTED_TRANSPORTS = [TRANSPORT_TELNET, TCP_TRANSPORT, TRANSPORT_WEBSOCKET, WS_TELNET_TRANSPORT]

def setup_logging(verbosity: int = 1) -> None:
    log_levels = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    level = log_levels.get(verbosity, logging.DEBUG)
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def load_handler_class(handler_path: str) -> Type[BaseHandler]:
    try:
        module_path, class_name = handler_path.split(':')
        module = importlib.import_module(module_path)
        handler_class = getattr(module, class_name)
        if not issubclass(handler_class, BaseHandler):
            raise TypeError(f"{class_name} must be a subclass of BaseHandler")
        return handler_class
    except (ValueError, ImportError, AttributeError) as e:
        raise ValueError(f"Could not load handler class '{handler_path}': {e}")

def create_server_instance(
    handler_class: Type[BaseHandler],
    config: Dict[str, Any]
) -> Union[TelnetServer, Any]:
    from telnet_server.server_config import ServerConfig
    return ServerConfig.create_server_from_config(config, handler_class)

async def run_server(server: Union[TelnetServer, Any]) -> None:
    await server.start_server()

async def run_multiple_servers(servers: List[Any]) -> None:
    await asyncio.gather(*(run_server(s) for s in servers))

def main():
    parser = argparse.ArgumentParser(
        description='Universal Server Launcher',
        epilog='Launch servers with different transport protocols'
    )
    
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
    
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8023, help='Port to listen on (default: 8023)')
    parser.add_argument('--transport', type=str, choices=SUPPORTED_TRANSPORTS, default=TRANSPORT_TELNET, help=f'Transport protocol (default: {TRANSPORT_TELNET})')
    parser.add_argument('-v', '--verbose', action='count', default=1, help='Increase verbosity (can be used multiple times)')
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    logger = logging.getLogger('server-launcher')
    
    try:
        if args.config:
            from telnet_server.server_config import ServerConfig
            config = ServerConfig.load_config(args.config)
            logger.info(f"Loaded configuration from {args.config}")
            server_configs = []
            if "servers" in config:
                for server_name, server_conf in config["servers"].items():
                    logger.info(f"Configuring server: {server_name}")
                    handler_class = load_handler_class(server_conf['handler_class'])
                    if args.host != '0.0.0.0':
                        server_conf['host'] = args.host
                    if args.port != 8023:
                        server_conf['port'] = args.port
                    if args.transport != TRANSPORT_TELNET:
                        server_conf['transport'] = args.transport
                    ServerConfig.validate_config(server_conf)
                    server_instance = create_server_instance(handler_class, server_conf)
                    server_configs.append(server_instance)
            else:
                handler_class = load_handler_class(config['handler_class'])
                if args.host != '0.0.0.0':
                    config['host'] = args.host
                if args.port != 8023:
                    config['port'] = args.port
                if args.transport != TRANSPORT_TELNET:
                    config['transport'] = args.transport
                ServerConfig.validate_config(config)
                server_configs.append(create_server_instance(handler_class, config))
        else:
            handler_class = load_handler_class(args.handler)
            config = {
                'host': args.host,
                'port': args.port,
                'transport': args.transport
            }
            server_configs = [create_server_instance(handler_class, config)]
        
        for srv in server_configs:
            transport_name = getattr(srv, 'transport', TRANSPORT_TELNET).upper()
            logger.info(f"Starting {transport_name} server with {handler_class.__name__} on {getattr(srv, 'host', '0.0.0.0')}:{getattr(srv, 'port', 8023)}")
        
        asyncio.run(run_multiple_servers(server_configs))
    
    except KeyboardInterrupt:
        logger.info("Server shutdown initiated by user.")
        return 0
    except Exception as e:
        logger.error(f"Error launching server: {e}")
        if args.verbose >= 2:
            import traceback
            traceback.print_exc()
        return 1
    finally:
        logger.info("Server process completed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
