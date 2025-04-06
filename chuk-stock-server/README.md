# Stock Feed Server

A real-time stock price server built on the chuk-protocol-server framework. This server provides stock price updates through various protocols, including Telnet, TCP, WebSocket, and WebSocket-Telnet.

## Features

- **Multi-Protocol Support**: Connect via Telnet, TCP, WebSocket, and WebSocket-Telnet
- **Real-Time Stock Data**: Live stock price information using yfinance
- **Intelligent Caching**: Prevents excessive API requests with a thread-safe cache
- **Interactive Terminal Interface**: Proper terminal handling for telnet clients
- **Multiple Connection Methods**: Access from traditional terminal clients or modern web interfaces
- **Configurable Server Options**: Detailed configuration via YAML or command line
- **Graceful Shutdown Handling**: Clean connection termination on server shutdown
- **Thread-Safe Connection Management**: Robust handling of concurrent connections

## Prerequisites

- Python 3.11+
- `uv` package manager (recommended)

## Installation

### Using uv

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create a virtual environment and install the package
uv venv
uv pip install -e .
```

### Alternative: Using pip

```bash
# Create a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

# Install the package
pip install -e .
```

## Quick Start

### Start the server

```bash
# Basic stock server on default port 8023
uv run server-launcher

# With specific configuration file
uv run server-launcher -c config.yaml

# With specific protocol and port (command-line override)
uv run server-launcher --port 8025 --protocol websocket --ws-path /ws
```

### Connect to the server

```bash
# Connect with telnet (default port 8023)
telnet localhost 8023
```

## Configuration Options

### Command Line Arguments

```bash
uv run server-launcher --help
```

Available options:

- `--host`: Server host (default: 0.0.0.0)
- `--port`: Server port (default: 8023)
- `--protocol`: Server protocol (choices: telnet, tcp, websocket, ws_telnet, default: telnet)
- `--ws-path`: WebSocket path (default: /ws)
- `--use-ssl`: Use SSL for WebSocket connections
- `--ssl-cert`: Path to SSL certificate for WebSocket server
- `--ssl-key`: Path to SSL key for WebSocket server
- `--allow-origins`: Allowed origins for WebSocket connections (default: all)
- `--max-connections`: Maximum number of connections (default: 100)
- `--connection-timeout`: Connection timeout in seconds (default: 300)
- `--cache-ttl`: Cache time-to-live in seconds (default: 5)
- `--log-level`: Logging level (choices: DEBUG, INFO, WARNING, ERROR, default: INFO)

### YAML Configuration

A sample `config.yaml` file is included in the repository. To start with the configuration:

```bash
uv run server-launcher -c config.yaml
```

## Client Examples

### Terminal Clients

#### Using telnet
```bash
telnet localhost 8023
```

#### Using netcat
```bash
nc localhost 8023
```

#### Using PuTTY (Windows)
1. Open PuTTY
2. Set Host Name to `localhost`
3. Set Port to `8023`
4. Connection type: `Telnet`
5. Click "Open"

### WebSocket Clients

#### Using wscat (Command-line WebSocket client)
```bash
# Install wscat
npm install -g wscat

# Connect to the WebSocket server
wscat -c ws://localhost:8025/ws
```

#### Browser-based WebSocket Console
```javascript
// In your browser's developer console
const ws = new WebSocket('ws://localhost:8025/ws');
ws.onmessage = function(event) {
  console.log(event.data);
};
ws.onopen = function() {
  console.log('Connection opened');
  ws.send('stock AAPL\r\n'); // Start Apple stock feed
};
```

### Web Client - xterm-web

For a ready-to-use web terminal client, you can use [xterm-web](https://github.com/chrishayuk/xterm-web), which provides:

- Browser-based terminal connecting to remote servers via a WebSocket proxy
- Terminal emulation with xterm.js
- Command history and local echo toggle
- Responsive design

To connect xterm-web to your stock server:

1. Set the WebSocket URL to `ws://your-server:8025/ws`
2. Configure terminal emulation for proper command handling

## Stock Server Commands

Once connected to the server, you can use these commands:

- `stock <ticker>` - Start a price feed for the given stock ticker (e.g., `stock AAPL`)
- `stop` - Stop the current price feed
- `help` - Show available commands
- `quit` - Disconnect from the server

Example session:
```
Welcome to the Stock Feed Server!
-------------------------------
Type 'stock <ticker>' to start a price feed (e.g., stock AAPL)
Type 'help' for available commands
Type 'quit' to disconnect
> stock AAPL
Starting price feed for AAPL...
Press Ctrl+C or type 'stop' to stop the feed
[2025-04-05 12:34:56] AAPL: 198.45
[2025-04-05 12:35:01] AAPL: 198.50
> stop
Feed stopped.
> quit
Goodbye!
```

## Docker Support

You can run the stock server in Docker:

```dockerfile
FROM python:3.11-alpine

WORKDIR /app

COPY . .
RUN pip install -e .

EXPOSE 8023 8024 8025 8026

CMD ["uv", "run", "server-launcher", "--host", "0.0.0.0", "--port", "8023", "--protocol", "telnet", "--log-level", "INFO"]
```

Build and run:

```bash
docker build -t stock-server .
docker run -p 8023:8023 -p 8025:8025 stock-server
```

## Advanced Usage

### SSL Configuration

For secure WebSocket connections:

```bash
uv run server-launcher --protocol websocket --use-ssl --ssl-cert /path/to/cert.pem --ssl-key /path/to/key.pem
```

### Multiple Server Types

Run multiple server types simultaneously using a YAML configuration (as shown in the config.yaml example).

### Monitoring

For WebSocket servers, you can enable monitoring at the `/monitor` endpoint:

```yaml
websocket:
  # Other config...
  enable_monitoring: true
  monitor_path: "/monitor"
```

## Troubleshooting

### Connection issues

1. Check that the server is running: `telnet localhost 8023`
2. Verify yfinance is working correctly by testing a ticker lookup
3. Check logs with increased verbosity: `uv run server-launcher --log-level DEBUG`
4. Verify WebSocket path is correct for WS connections

### Common errors

- **Connection refused**: The server is not running or the port is blocked
- **Stock data not updating**: Check yfinance API status or network connectivity
- **WebSocket handshake failed**: Check WebSocket protocol and allowed origins

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Credits

This stock server is built on top of the chuk-protocol-server framework.