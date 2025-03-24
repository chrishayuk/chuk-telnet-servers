#!/usr/bin/env python3
# telnet_server/server_config.py
"""
Server Configuration Module
Helps initialize telnet servers with specific configurations
"""
import os
import yaml
import logging
from typing import Dict, Any, Type

# imports
from telnet_server.protocol_handlers.base_protocol_handler import BaseProtocolHandler
from telnet_server.server import TelnetServer

logger = logging.getLogger('server-config')

class ServerConfig:
    """Manages server configuration from YAML files"""
    
    @staticmethod
    def load_config(config_file: str) -> Dict[str, Any]:
        """Load a configuration from a YAML file"""
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Config file not found: {config_file}")
        
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            # Validate required fields
            required_fields = ['host', 'port', 'handler_class']
            missing = [field for field in required_fields if field not in config]
            if missing:
                raise ValueError(f"Missing required config fields: {', '.join(missing)}")
            
            return config
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing config file: {e}")
    
    @staticmethod
    def create_server_from_config(config: Dict[str, Any], handler_class: Type[BaseProtocolHandler]) -> TelnetServer:
        """Create a server instance from a configuration dict"""
        # Extract base server parameters
        host = config.get('host', '0.0.0.0')
        port = config.get('port', 8023)
        
        # Create the server
        server = TelnetServer(host, port, handler_class)
        
        # Set optional server attributes
        optional_attrs = {k: v for k, v in config.items() 
                         if k not in ('host', 'port', 'handler_class')}
        
        for attr, value in optional_attrs.items():
            try:
                setattr(server, attr, value)
                logger.debug(f"Set server attribute {attr} = {value}")
            except AttributeError:
                logger.warning(f"Could not set attribute {attr} on server")
        
        return server