#!/usr/bin/env python3
# telnet_server/server_config.py
"""
Server Configuration Module

Helps initialize servers with specific configurations.
This module provides utilities for loading and validating
server configurations from YAML files.
"""
import os
import yaml
import logging
from typing import Dict, Any, Type, Optional, List, Union

# Import the default Telnet server and base handler
from telnet_server.server import TelnetServer
from telnet_server.handlers.base_handler import BaseHandler

# Define transport types
TRANSPORT_TELNET = "telnet"
TRANSPORT_TCP = "tcp"
TRANSPORT_WEBSOCKET = "websocket"
TRANSPORT_WS_TELNET = "ws_telnet"
SUPPORTED_TRANSPORTS = [TRANSPORT_TELNET, TRANSPORT_TCP, TRANSPORT_WEBSOCKET, TRANSPORT_WS_TELNET]

logger = logging.getLogger('server-config')

class ServerConfig:
    """
    Manages server configuration from YAML files.
    
    Provides static methods for loading, validating, and creating server
    instances based on configuration.
    """
    
    @staticmethod
    def load_config(config_file: str) -> Dict[str, Any]:
        """
        Load configuration from a YAML file.
        
        If the top-level contains 'servers', that mapping is included.
        """
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Config file not found: {config_file}")
        
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            if not isinstance(config, dict):
                raise ValueError("Configuration must be a dictionary")
            
            # Multi-server support: if "servers" exists, validate each one.
            if "servers" in config:
                servers_config = config["servers"]
                if not isinstance(servers_config, dict):
                    raise ValueError("The 'servers' key must contain a dictionary of server configurations")
                for name, server_conf in servers_config.items():
                    missing = [field for field in ['handler_class'] if field not in server_conf]
                    if missing:
                        raise ValueError(f"Missing required config fields for server '{name}': {', '.join(missing)}")
            else:
                # Single-server config requires 'handler_class'
                required_fields = ['handler_class']
                missing = [field for field in required_fields if field not in config]
                if missing:
                    raise ValueError(f"Missing required config fields: {', '.join(missing)}")
            
            # Set common default values (these can be overridden per server)
            if 'host' not in config:
                config['host'] = '0.0.0.0'
                logger.info("Using default host: 0.0.0.0")
            if 'port' not in config:
                config['port'] = 8023
                logger.info("Using default port: 8023")
            if 'transport' not in config:
                config['transport'] = TRANSPORT_TELNET
                logger.info(f"Using default transport: {TRANSPORT_TELNET}")
            elif config['transport'] not in SUPPORTED_TRANSPORTS:
                raise ValueError(f"Unsupported transport: {config['transport']}. Supported transports: {', '.join(SUPPORTED_TRANSPORTS)}")
            
            # Validate port range at the top level
            port = config.get('port', 8023)
            if not isinstance(port, int) or port < 1 or port > 65535:
                raise ValueError(f"Invalid port number: {port}. Must be between 1 and 65535.")
            
            return config
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing config file: {e}")
    
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> None:
        """
        Validate a configuration dictionary.
        """
        def _validate_server_conf(server_conf: Dict[str, Any], server_name: Optional[str] = None):
            handler_class = server_conf.get('handler_class', '')
            if not isinstance(handler_class, str) or ':' not in handler_class:
                name_info = f" for server '{server_name}'" if server_name else ""
                raise ValueError(f"Invalid handler_class format{name_info}: {handler_class}. Expected format: 'module.path:ClassName'")
            # Validate numeric fields
            for numeric_field in ['max_connections', 'connection_timeout']:
                if numeric_field in server_conf:
                    value = server_conf[numeric_field]
                    if not isinstance(value, (int, float)) or value <= 0:
                        raise ValueError(f"{numeric_field} must be a positive number")
            # Validate transport type
            transport = server_conf.get('transport', TRANSPORT_TELNET)
            if transport not in SUPPORTED_TRANSPORTS:
                raise ValueError(f"Unsupported transport: {transport}. Supported transports: {', '.join(SUPPORTED_TRANSPORTS)}")
            # Validate WebSocket-specific settings if needed
            if transport in [TRANSPORT_WEBSOCKET, TRANSPORT_WS_TELNET]:
                if 'ws_path' not in server_conf:
                    logger.warning("No WebSocket path specified, using default: '/telnet'")
                    server_conf['ws_path'] = '/telnet'
                if server_conf.get('use_ssl', False):
                    required_ssl_fields = ['ssl_cert', 'ssl_key']
                    missing = [field for field in required_ssl_fields if field not in server_conf]
                    if missing:
                        raise ValueError(f"SSL is enabled but missing required fields: {', '.join(missing)}")
        
        if "servers" in config:
            for name, server_conf in config["servers"].items():
                _validate_server_conf(server_conf, server_name=name)
        else:
            _validate_server_conf(config)
    
    @staticmethod
    def create_server_from_config(
        config: Dict[str, Any], 
        handler_class: Type[BaseHandler]
    ) -> Union[TelnetServer, Any]:
        """
        Create a server instance from the configuration.
        """
        host = config.get('host', '0.0.0.0')
        port = config.get('port', 8023)
        transport = config.get('transport', TRANSPORT_TELNET)
        
        if transport == TRANSPORT_TELNET:
            server = TelnetServer(host, port, handler_class)
        elif transport == "tcp":
            try:
                from telnet_server.transports.tcp.tcp_server import TCPServer
                server = TCPServer(host, port, handler_class)
            except ImportError as e:
                raise ImportError(f"Could not create TCP server: {e}.")
        elif transport == TRANSPORT_WEBSOCKET:
            try:
                from telnet_server.transports.websocket.ws_server import WebSocketServer
                ws_path = config.get('ws_path', '/telnet')
                use_ssl = config.get('use_ssl', False)
                ssl_cert = config.get('ssl_cert', None)
                ssl_key = config.get('ssl_key', None)
                ping_interval = config.get('ping_interval', 30)
                ping_timeout = config.get('ping_timeout', 10)
                allow_origins = config.get('allow_origins', ['*'])
                server = WebSocketServer(
                    host=host, 
                    port=port, 
                    handler_class=handler_class,
                    path=ws_path,
                    ssl_cert=ssl_cert if use_ssl else None,
                    ssl_key=ssl_key if use_ssl else None,
                    ping_interval=ping_interval,
                    ping_timeout=ping_timeout,
                    allow_origins=allow_origins
                )
            except ImportError as e:
                raise ImportError(
                    f"Could not create WebSocket server: {e}. "
                    "WebSocket transport requires the 'websockets' package. Install it with: pip install websockets"
                )
        elif transport == "ws_telnet":
            try:
                from telnet_server.transports.websocket.ws_telnet_server import WSTelnetServer
                ws_path = config.get('ws_path', '/telnet')
                use_ssl = config.get('use_ssl', False)
                ssl_cert = config.get('ssl_cert', None)
                ssl_key = config.get('ssl_key', None)
                ping_interval = config.get('ping_interval', 30)
                ping_timeout = config.get('ping_timeout', 10)
                allow_origins = config.get('allow_origins', ['*'])
                server = WSTelnetServer(
                    host=host,
                    port=port,
                    handler_class=handler_class,
                    path=ws_path,
                    ssl_cert=ssl_cert if use_ssl else None,
                    ssl_key=ssl_key if use_ssl else None,
                    ping_interval=ping_interval,
                    ping_timeout=ping_timeout,
                    allow_origins=allow_origins
                )
            except ImportError as e:
                raise ImportError(f"Could not create WebSocket Telnet server: {e}.")
        else:
            raise ValueError(f"Unsupported transport: {transport}")
        
        # Apply additional configuration (skip transport-specific keys)
        excluded_keys = {'host', 'port', 'handler_class', 'transport', 
                         'ws_path', 'use_ssl', 'ssl_cert', 'ssl_key',
                         'ping_interval', 'ping_timeout', 'allow_origins'}
        for key, value in config.items():
            if key not in excluded_keys:
                try:
                    setattr(server, key, value)
                    logger.debug(f"Set server attribute {key} = {value}")
                except AttributeError:
                    logger.warning(f"Could not set server attribute '{key}'")
        
        return server
    
    @staticmethod
    def save_config(config: Dict[str, Any], filename: str) -> None:
        """
        Save configuration to a YAML file.
        """
        try:
            with open(filename, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            logger.info(f"Configuration saved to {filename}")
        except IOError as e:
            logger.error(f"Error saving configuration to {filename}: {e}")
            raise
    
    @staticmethod
    def create_default_config(handler_class: str, transport: str = TRANSPORT_TELNET) -> Dict[str, Any]:
        """
        Create a default configuration dictionary.
        """
        if transport not in SUPPORTED_TRANSPORTS:
            raise ValueError(f"Unsupported transport: {transport}")
        
        config = {
            'host': '0.0.0.0',
            'port': 8023,
            'handler_class': handler_class,
            'transport': transport,
            'max_connections': 100,
            'connection_timeout': 300,
            'welcome_message': "Welcome to the Server!"
        }
        
        if transport == TRANSPORT_WEBSOCKET or transport == "ws_telnet":
            config.update({
                'ws_path': '/telnet',
                'use_ssl': False,
                'ssl_cert': '',
                'ssl_key': '',
                'allow_origins': ['*'],
                'ping_interval': 30,
                'ping_timeout': 10
            })
            if transport == TRANSPORT_WEBSOCKET:
                config['welcome_message'] = "Welcome to the WebSocket Server!"
            else:
                config['welcome_message'] = "Welcome to the WebSocket Telnet Server!"
        
        return config