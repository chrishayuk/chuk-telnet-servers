# Robust Telnet Server Framework

A comprehensive framework for building reliable telnet-based applications with proper terminal handling. This framework solves common telnet protocol issues and provides a solid foundation for interactive command-line applications.

## Overview

This framework provides a layered approach to telnet server implementation, with carefully designed components that handle different aspects of the telnet protocol and terminal interactions. The architecture prioritizes robustness, proper terminal handling, and extensibility.

### Key Features

- **Proper Telnet Protocol Implementation**: Full support for telnet option negotiation and subnegotiation
- **Dual-Mode Operation**: Supports both line mode and character mode terminal handling
- **Clean Architecture**: Clear separation between protocol handling and application logic
- **Robust Error Handling**: Graceful handling of connection issues and unexpected client behavior
- **Detailed Logging**: Comprehensive logging for troubleshooting and debugging
- **Customizable Handlers**: Easy extension for different application types
- **Example Applications**: Stock price feed server implementation and simple echo server

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/telnet-server.git
   cd telnet-server
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the echo server:
   ```bash
   python telnet_server/server_launcher.py -c config/echo_server.yaml
   ```

## Architecture

The framework is built on a layered architecture:

1. **Connection Handler Layer**: Basic socket I/O and connection management
2. **Character Protocol Layer**: Character-by-character reading and processing
3. **Telnet Protocol Layer**: Telnet-specific protocol handling and negotiation
4. **Application Logic Layer**: Custom application behavior

### Core Components

- **ConnectionHandler**: Handles basic socket I/O and lifecycle
- **CharacterProtocolHandler**: Provides character-by-character processing
- **TelnetProtocolHandler**: Implements telnet protocol with proper terminal handling
- **EchoTelnetHandler / StockFeedHandler**: Application-specific handlers

## Usage

### Basic Usage

To create a simple echo server:

```python
from telnet_server.protocol_handlers.telnet_protocol_handler import TelnetProtocolHandler

class EchoTelnetHandler(TelnetProtocolHandler):
    async def on_command_submitted(self, command: str) -> None:
        await self.send_line(f"Echo: {command}")
```

### Server Launcher

The framework includes a flexible server launcher for easy testing and deployment:

```bash
# Run with a specific handler
python telnet_server/server_launcher.py your_module.your_handler:YourHandlerClass

# Run with configuration file
python telnet_server/server_launcher.py -c config/your_config.yaml
```

### Stock Feed Server Example

A complete stock price feed server is included to demonstrate advanced functionality:

```bash
# Run the stock feed server
python stock_feed_server.py
```

## Terminal Handling

The framework includes sophisticated terminal handling that correctly negotiates capabilities with telnet clients:

1. **Initial Negotiation**: Establishes proper terminal settings at connection time
2. **Visual Feedback**: Echoes characters and provides appropriate visual feedback
3. **Control Character Handling**: Properly processes CR, LF, backspace, and other control characters
4. **Window Size**: Adapts to client terminal dimensions when available
5. **Terminal Type**: Detects client terminal type for specialized behavior

## Customization

### Creating Custom Handlers

1. Inherit from `TelnetProtocolHandler` for most applications:

```python
class MyCustomHandler(TelnetProtocolHandler):
    async def on_command_submitted(self, command: str) -> None:
        # Process commands here
        if command.startswith("hello"):
            await self.send_line("Hello to you too!")
        else:
            await self.send_line(f"Unknown command: {command}")
```

2. For more advanced customization, override additional methods:

```python
class AdvancedHandler(TelnetProtocolHandler):
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

### Configuration Files

Configure servers with YAML configuration files:

```yaml
# config/my_server.yaml
host: 0.0.0.0
port: 8023
handler_class: my_module.my_handler:MyCustomHandler
max_connections: 100
```

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
- `base-protocol`: Base protocol operations
- `character-protocol`: Character processing events
- `telnet-server`: Server lifecycle events

## Advanced Topics

### Telnet Option Negotiation

The framework handles telnet option negotiation according to RFC 854 and related standards. Key options supported include:

- **ECHO (option 1)**: Controls character echo
- **SGA (option 3)**: Suppresses Go Ahead signals for full-duplex operation
- **TERMINAL TYPE (option 24)**: Identifies client terminal type
- **NAWS (option 31)**: Negotiates window size
- **LINEMODE (option 34)**: Controls line-by-line versus character-by-character input

### Terminal Control Sequences

The framework properly handles terminal control sequences:

- Backspace: Sends `\b \b` to visually erase characters
- Newline: Sends `\r\n` for proper line breaks
- Control characters: Properly processes Ctrl+C and other control characters

## Performance Considerations

- The server uses asyncio for efficient handling of multiple connections
- Character-by-character processing is more CPU-intensive than line mode
- Connection cleanup is handled carefully to prevent resource leaks

## Troubleshooting

Common issues and solutions:

- **^M characters visible**: Check that proper terminal negotiations are being sent
- **No character echo**: Verify ECHO option negotiation
- **Slow performance**: Reduce logging level in production environments
- **Connection resets**: Ensure proper error handling in custom handlers

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgements

- Telnet protocol specifications (RFCs 854, 855, 856, etc.)
- The asyncio library for elegant async/await support
- The Python community for inspiration and feedback