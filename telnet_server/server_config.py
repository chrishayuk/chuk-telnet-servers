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
SUPPORTED_TRANSPORTS = [TRANSPORT_TELNET, TRANSPORT_WEBSOCKET]

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
        if transport == TRANSPORT_WEBSOCKET:
            # WebSocket-specific validation
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
        # Use the ServerFactory to create the server
        from telnet_server.server_factory import ServerFactory
        
        # Create the server
        server = ServerFactory.create_server(config, handler_class)
        
        # Apply additional configuration
        ServerFactory.apply_config_to_server(server, config)
        
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
            transport: The transport type to use (telnet or websocket)
            
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
            'welcome_message': "Welcome to the Telnet Server!"
        }
        
        # Add transport-specific defaults
        if transport == TRANSPORT_WEBSOCKET:
            config.update({
                'ws_path': '/telnet',
                'use_ssl': False,
                'ssl_cert': '',
                'ssl_key': '',
                'allow_origins': ['*'],  # CORS settings
                'ping_interval': 30,  # WebSocket keepalive in seconds
                'ping_timeout': 10
            })
        
        return config