# Multi-Protocol Server Framework

A modern Python framework for building server applications that work across multiple transport protocols: Telnet, TCP, and WebSocket. Create a server once and make it accessible from traditional terminal clients, command-line tools, and web browsers.

## Features

- **Multiple Transport Protocols**: Run your server on Telnet, TCP, and WebSocket simultaneously
- **Unified Handler Interface**: Write your application logic once, deploy everywhere
- **Configurable**: YAML-based configuration with transport-specific options
- **Graceful Shutdown**: Proper connection handling and clean termination
- **Protocol Detection**: Automatic Telnet negotiation detection with fallback
- **Session Management**: Connection limits, timeouts, and custom welcome messages
- **Async Architecture**: Built on Python's asyncio for efficient handling of concurrent connections
- **Proper Telnet Protocol Implementation**: Full support for telnet option negotiation and subnegotiation
- **Dual-Mode Operation**: Supports both line mode and character mode terminal handling
- **Robust Error Handling**: Graceful handling of connection issues and unexpected client behavior

## Requirements

- Python 3.7+
- Dependencies:
  - websockets
  - pyyaml
  - asyncio

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/multi-protocol-server.git
cd multi-protocol-server

# Install dependencies
pip install -r requirements.txt

# Optional: Install development dependencies
pip install -r requirements-dev.txt
```

## Quick Start

1. Create a handler class that inherits from one of the base handlers
2. Configure your server with a YAML file
3. Launch your server using the server launcher

```bash
python -m telnet_server.server_launcher -c config/echo_server.yaml
```

## Client Connections

Your server will be accessible from multiple client types:

### Telnet Client

Connect to the Telnet transport using a traditional Telnet client:

```bash
telnet localhost 8023
```

The server will negotiate Telnet options and provide a full-featured terminal experience.

### TCP Client (netcat)

Connect to the TCP transport using netcat or similar tools:

```bash
nc localhost 8024
```

This provides a simple line-based interface without Telnet negotiation.

### WebSocket Client

Connect to the WebSocket transport using any WebSocket client:

#### Command-line with websocat

```bash
# Install websocat if needed (https://github.com/vi/websocat)
websocat --exit-on-eof ws://localhost:8025/ws
```

#### Browser JavaScript

```javascript
const ws = new WebSocket('ws://localhost:8025/ws');
ws.onmessage = function(event) { console.log('Received:', event.data); };
ws.onopen = function() { console.log('Connected!'); };
ws.onclose = function() { console.log('Disconnected'); };

// Send a message
ws.send('hello');
```

## Configuration

The framework uses YAML configuration files for server setup:

```yaml
# Single server configuration
host: 0.0.0.0
port: 8023
handler_class: sample_servers.echo_server:EchoTelnetHandler

# OR 

# Multi-transport configuration
servers:
  telnet:
    host: "0.0.0.0"
    port: 8023
    transport: "telnet"
    handler_class: "sample_servers.echo_server:EchoTelnetHandler"
    max_connections: 100
    connection_timeout: 300
    welcome_message: "Welcome to the Telnet Server!"

  tcp:
    host: "0.0.0.0"
    port: 8024
    transport: "tcp"
    handler_class: "sample_servers.echo_server:EchoTelnetHandler"
    max_connections: 100
    connection_timeout: 300
    welcome_message: "Welcome to the TCP Server!"

  websocket:
    host: "0.0.0.0"
    port: 8025
    transport: "websocket"
    ws_path: "/ws"
    handler_class: "sample_servers.echo_server:EchoTelnetHandler"
    use_ssl: false
    allow_origins:
      - "*"
    max_connections: 100
    connection_timeout: 300
    welcome_message: "Welcome to the WebSocket Server!"
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| host | Bind address | 0.0.0.0 |
| port | Listen port | 8023 |
| transport | Protocol type (telnet, tcp, websocket, ws_telnet) | telnet |
| handler_class | Handler class path (module:ClassName) | Required |
| max_connections | Maximum concurrent connections | 100 |
| connection_timeout | Session timeout in seconds | 300 |
| welcome_message | Message displayed on connection | None |
| ws_path | Path for WebSocket endpoint | /ws |
| allow_origins | CORS allowed origins | ["*"] |
| use_ssl | Enable SSL/TLS (WebSocket) | false |
| ssl_cert | Path to SSL certificate | None |
| ssl_key | Path to SSL key | None |
| ping_interval | WebSocket ping interval in seconds | 30 |
| ping_timeout | WebSocket ping timeout in seconds | 10 |

## Creating Handlers

Handlers define your server's behavior. Extend one of the base handler classes:

```python
#!/usr/bin/env python3
from telnet_server.handlers.telnet_handler import TelnetHandler

class EchoTelnetHandler(TelnetHandler):
    async def on_command_submitted(self, command: str) -> None:
        if command.lower() == 'help':
            await self.send_line("Available commands: help, info, quit")
        else:
            await self.send_line(f"Echo: {command}")

    async def process_line(self, line: str) -> bool:
        if line.lower() in ['quit', 'exit', 'q']:
            await self.end_session("Goodbye!")
            return False
        await self.on_command_submitted(line)
        return True
```

For more advanced customization, override additional methods:

```python
class AdvancedHandler(TelnetHandler):
    def __init__(self, reader, writer):
        super().__init__(reader, writer)
        self.custom_state = {}

    async def show_prompt(self) -> None:
        # Customize the prompt
        await self.send_raw(b"my-app> ")

    async def process_character(self, char: str) -> bool:
        # Custom character processing
        # Return False to terminate the connection
        return await super().process_character(char)
```

## Architecture

The framework is built on a layered architecture:

1. **Servers**: Handle transport-specific connection management (Telnet, TCP, WebSocket)
2. **Handlers**: Process client input and generate responses
3. **Adapters**: Bridge between different transport types and handlers

This modular design allows for:

- **Transport Layer**: Manages network protocols and connections
- **Character Protocol Layer**: Character-by-character reading and processing
- **Telnet Protocol Layer**: Telnet-specific protocol handling and negotiation
- **Application Logic Layer**: Custom application behavior

## Running the Server

Launch your server with the server launcher module:

```bash
# With a configuration file
python -m telnet_server.server_launcher -c config/my_server.yaml

# Direct handler specification
python -m telnet_server.server_launcher my_package.handlers:MyHandler --port 8000

# Verbose logging
python -m telnet_server.server_launcher -c config/my_server.yaml -vv
```

## Example Servers

Several example servers are provided to demonstrate the framework:

- **Echo Server**: Simple echo server that responds to commands
- **Stock Server**: Mock stock ticker server with real-time updates
- **Guess Who Server**: Text-based implementation of the Guess Who game

Run them from the examples directory:

```bash
python -m telnet_server.server_launcher -c config/echo_server.yaml
```

## Terminal Handling

The framework includes sophisticated terminal handling that correctly negotiates capabilities with telnet clients:

1. **Initial Negotiation**: Establishes proper terminal settings at connection time
2. **Visual Feedback**: Echoes characters and provides appropriate visual feedback
3. **Control Character Handling**: Properly processes CR, LF, backspace, and other control characters
4. **Window Size**: Adapts to client terminal dimensions when available
5. **Terminal Type**: Detects client terminal type for specialized behavior

## Telnet Option Negotiation

The framework handles telnet option negotiation according to RFC 854 and related standards. Key options supported include:

- **ECHO (option 1)**: Controls character echo
- **SGA (option 3)**: Suppresses Go Ahead signals for full-duplex operation
- **TERMINAL TYPE (option 24)**: Identifies client terminal type
- **NAWS (option 31)**: Negotiates window size
- **LINEMODE (option 34)**: Controls line-by-line versus character-by-character input

## Terminal Control Sequences

The framework properly handles terminal control sequences:

- **Backspace**: Sends `\b \b` to visually erase characters
- **Newline**: Sends `\r\n` for proper line breaks
- **Control characters**: Properly processes Ctrl+C and other control characters

## Extending the Framework

### Adding a New Transport

1. Create a new server class extending `BaseServer`
2. Implement required methods for your transport
3. Add the transport type to the server launcher

### Creating Custom Handlers

1. Extend one of the base handler classes (BaseHandler, CharacterHandler, LineHandler, TelnetHandler)
2. Implement your application logic
3. Configure the server to use your handler

## Logging

The framework includes comprehensive logging to assist with debugging:

```python
# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

Different components use different loggers:
- `telnet-protocol`: Telnet protocol events and negotiations
- `base-server`: Server lifecycle events
- `character-handler`: Character processing events
- `websocket-adapter`: WebSocket connection events
- `ws-plain-server`: WebSocket server events

## Performance Considerations

- The server uses asyncio for efficient handling of multiple connections
- Character-by-character processing is more CPU-intensive than line mode
- Connection cleanup is handled carefully to prevent resource leaks
- WebSocket connections include ping/pong frames to detect disconnects

## Troubleshooting

Common issues and solutions:

- **^M characters visible**: Check that proper terminal negotiations are being sent
- **No character echo**: Verify ECHO option negotiation
- **Slow performance**: Reduce logging level in production environments
- **Connection resets**: Ensure proper error handling in custom handlers
- **WebSocket client doesn't exit**: Use the `--exit-on-eof` flag with websocat

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgements

- Telnet protocol specifications (RFCs 854, 855, 856, etc.)
- The asyncio library for elegant async/await support
- The websockets library for WebSocket protocol support
- The Python community for inspiration and feedback