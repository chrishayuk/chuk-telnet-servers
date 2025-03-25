#!/usr/bin/env python3
# telnet_server/server_config.py
"""
Server Configuration Module

Helps initialize telnet servers with specific configurations.
This module provides utilities for loading and validating
server configurations from YAML files.
"""
import os
import yaml
import logging
from typing import Dict, Any, Type, Optional, List, Union

# Import the server and base handler
from telnet_server.server import TelnetServer
from telnet_server.handlers.base_handler import BaseHandler

# Define transport types
TRANSPORT_TELNET = "telnet"
TRANSPORT_WEBSOCKET = "websocket" 
TRANSPORT_AUTO_DETECT = "auto-detect"
SUPPORTED_TRANSPORTS = [TRANSPORT_TELNET, TRANSPORT_WEBSOCKET, TRANSPORT_AUTO_DETECT]

logger = logging.getLogger('server-config')

class ServerConfig:
    """
    Manages server configuration from YAML files.
    
    This class provides static methods for loading configurations
    from YAML files, validating them, and creating server instances
    based on those configurations.
    """
    
    @staticmethod
    def load_config(config_file: str) -> Dict[str, Any]:
        """
        Load a configuration from a YAML file.
        
        Args:
            config_file: Path to the YAML configuration file
            
        Returns:
            The loaded configuration as a dictionary
            
        Raises:
            FileNotFoundError: If the configuration file doesn't exist
            ValueError: If the configuration is invalid or can't be parsed
        """
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Config file not found: {config_file}")
        
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            if not isinstance(config, dict):
                raise ValueError("Configuration must be a dictionary")
            
            # Validate required fields
            required_fields = ['handler_class']
            missing = [field for field in required_fields if field not in config]
            if missing:
                raise ValueError(f"Missing required config fields: {', '.join(missing)}")
            
            # Set default values if not provided
            if 'host' not in config:
                config['host'] = '0.0.0.0'
                logger.info("Using default host: 0.0.0.0")
                
            if 'port' not in config:
                config['port'] = 8023
                logger.info("Using default port: 8023")
                
            # Set default transport if not provided
            if 'transport' not in config:
                config['transport'] = TRANSPORT_TELNET
                logger.info(f"Using default transport: {TRANSPORT_TELNET}")
            elif config['transport'] not in SUPPORTED_TRANSPORTS:
                raise ValueError(f"Unsupported transport: {config['transport']}. "
                                f"Supported transports: {', '.join(SUPPORTED_TRANSPORTS)}")
            
            # Validate port range
            port = config['port']
            if not isinstance(port, int) or port < 1 or port > 65535:
                raise ValueError(f"Invalid port number: {port}. Must be between 1 and 65535.")
            
            return config
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing config file: {e}")
    
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> None:
        """
        Validate a configuration dictionary.
        
        Args:
            config: The configuration dictionary to validate
            
        Raises:
            ValueError: If the configuration is invalid
        """
        # Check handler_class format
        handler_class = config.get('handler_class', '')
        if not isinstance(handler_class, str) or ':' not in handler_class:
            raise ValueError(
                f"Invalid handler_class format: {handler_class}. "
                "Expected format: 'module.path:ClassName'"
            )
        
        # Check numeric values are valid
        for numeric_field in ['max_connections', 'connection_timeout']:
            if numeric_field in config:
                value = config[numeric_field]
                if not isinstance(value, (int, float)) or value <= 0:
                    raise ValueError(f"{numeric_field} must be a positive number")
        
        # Validate transport
        transport = config.get('transport', TRANSPORT_TELNET)
        if transport not in SUPPORTED_TRANSPORTS:
            raise ValueError(
                f"Unsupported transport: {transport}. "
                f"Supported transports: {', '.join(SUPPORTED_TRANSPORTS)}"
            )
        
        # Validate transport-specific settings
        if transport in [TRANSPORT_WEBSOCKET, TRANSPORT_AUTO_DETECT]:
            # WebSocket-specific validation (also applies to auto-detect)
            if 'ws_path' not in config:
                logger.warning("No WebSocket path specified, using default: '/telnet'")
                config['ws_path'] = '/telnet'
                
            # Check if SSL/TLS is configured
            if config.get('use_ssl', False):
                required_ssl_fields = ['ssl_cert', 'ssl_key']
                missing = [field for field in required_ssl_fields if field not in config]
                if missing:
                    raise ValueError(
                        f"SSL is enabled but missing required fields: {', '.join(missing)}"
                    )
    
    @staticmethod
    def create_server_from_config(
        config: Dict[str, Any], 
        handler_class: Type[BaseHandler]
    ) -> Union[TelnetServer, Any]:
        """
        Create a server instance from a configuration dictionary.
        
        Args:
            config: The configuration dictionary
            handler_class: The handler class to use
            
        Returns:
            A configured server instance based on the selected transport
            
        Raises:
            ImportError: If the required transport-specific module can't be imported
            ValueError: If the transport is invalid
        """
        # Extract base server parameters
        host = config.get('host', '0.0.0.0')
        port = config.get('port', 8023)
        transport = config.get('transport', TRANSPORT_TELNET)
        
        # Create the server based on transport type
        if transport == TRANSPORT_TELNET:
            # Create standard TelnetServer
            server = TelnetServer(host, port, handler_class)
            
        elif transport == TRANSPORT_WEBSOCKET:
            # Import the WebSocketServer at runtime
            try:
                from telnet_server.transports.websocket.ws_server import WebSocketServer
                
                # Extract WebSocket-specific settings
                ws_path = config.get('ws_path', '/telnet')
                use_ssl = config.get('use_ssl', False)
                ssl_cert = config.get('ssl_cert', None)
                ssl_key = config.get('ssl_key', None)
                ping_interval = config.get('ping_interval', 30)
                ping_timeout = config.get('ping_timeout', 10)
                allow_origins = config.get('allow_origins', ['*'])
                
                # Create WebSocket server
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
                    "WebSocket transport requires the 'websockets' package. "
                    "Install it with: pip install websockets"
                )
        
        elif transport == TRANSPORT_AUTO_DETECT:
            # Import the AutoDetectServer at runtime
            try:
                from telnet_server.transports.auto_detect_server import AutoDetectServer
                
                # Extract WebSocket-specific settings (used by auto-detect)
                ws_path = config.get('ws_path', '/telnet')
                use_ssl = config.get('use_ssl', False)
                ssl_cert = config.get('ssl_cert', None)
                ssl_key = config.get('ssl_key', None)
                ping_interval = config.get('ping_interval', 30)
                ping_timeout = config.get('ping_timeout', 10)
                allow_origins = config.get('allow_origins', ['*'])
                
                # Create AutoDetect server
                server = AutoDetectServer(
                    host=host, 
                    port=port, 
                    handler_class=handler_class,
                    ws_path=ws_path,
                    ssl_cert=ssl_cert if use_ssl else None,
                    ssl_key=ssl_key if use_ssl else None,
                    ping_interval=ping_interval,
                    ping_timeout=ping_timeout,
                    allow_origins=allow_origins
                )
            except ImportError as e:
                raise ImportError(
                    f"Could not create Auto-Detect server: {e}."
                )
        
        else:
            raise ValueError(f"Unsupported transport: {transport}")
        
        # Apply additional configuration
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
        Save a configuration dictionary to a YAML file.
        
        Args:
            config: The configuration dictionary to save
            filename: The file to save the configuration to
            
        Raises:
            IOError: If the file cannot be written
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
        
        Args:
            handler_class: The handler class path string
            transport: The transport type to use (telnet, websocket, or auto-detect)
            
        Returns:
            A default configuration dictionary
            
        Raises:
            ValueError: If the transport is invalid
        """
        if transport not in SUPPORTED_TRANSPORTS:
            raise ValueError(f"Unsupported transport: {transport}")
        
        # Base configuration common to all transports
        config = {
            'host': '0.0.0.0',
            'port': 8023,
            'handler_class': handler_class,
            'transport': transport,
            'max_connections': 100,
            'connection_timeout': 300,
            'welcome_message': "Welcome to the Server!"
        }
        
        # Add transport-specific defaults
        if transport in [TRANSPORT_WEBSOCKET, TRANSPORT_AUTO_DETECT]:
            config.update({
                'ws_path': '/telnet',
                'use_ssl': False,
                'ssl_cert': '',
                'ssl_key': '',
                'allow_origins': ['*'],  # CORS settings
                'ping_interval': 30,  # WebSocket keepalive in seconds
                'ping_timeout': 10
            })
            
            if transport == TRANSPORT_AUTO_DETECT:
                config['welcome_message'] = "Welcome to the Auto-Detect Server! Supporting both Telnet and WebSocket clients."
            else:
                config['welcome_message'] = "Welcome to the WebSocket Server!"
        
        return config