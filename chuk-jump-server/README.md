# Jump Point Server

A multi-world telnet server that provides an interactive jumping point between different server realms.

## Features

- **Multi-World Connectivity**: Jump between different themed servers
- **User Management**: Track and manage connected users
- **Flexible Command System**: Extensible command architecture
- **Telnet Support**: Connect via traditional terminal clients
- **Configurable Worlds**: Easily add or modify server destinations
- **Interactive User Experience**: Username customization and world exploration
- **Robust Handler Management**: Thread-safe connection tracking

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
# Basic Jump Point server on default port 8023
uv run jump-point-server

# With specific configuration file
uv run jump-point-server -c config.yaml

# With custom host and port
uv run jump-point-server --host 0.0.0.0 --port 8024
```

### Connect to the server

```bash
# Connect with telnet
telnet localhost 8023
```

## Configuration Options

### Command Line Arguments

```bash
uv run jump-point-server --help
```

Available options:

- `--host`: Server host (default: 0.0.0.0)
- `--port`: Server port (default: 8023)
- `--log-level`: Logging level (choices: DEBUG, INFO, WARNING, ERROR, default: INFO)

## Worlds

The Jump Point server currently supports these worlds:

- **CodersDen**: AI coding Q&A world
- **StoryVerse**: Narrative realm for text adventures
- **DataDoctor**: Data science & analytics realm

## Server Commands

Once connected to the Jump Point server, you can use these commands:

- `username` - Set or update your username
- `list` - Show all known worlds
- `info <world>` - Show details about a specific world
- `jump <world>` - 'Travel' to that world (demo only)
- `who` - See who's currently connected
- `help` - Show help message
- `quit` - Disconnect from server

Example session:
```
Welcome to the Jump Point!
-------------------------
(Type 'help' for commands, 'quit' to disconnect)
Please enter your desired username:
> Alice
Hello, Alice!
> list
Available Worlds:
  CodersDen - AI coding Q&A world
  StoryVerse - Narrative realm for text adventures
  DataDoctor - Data science & analytics realm
> info CodersDen
World: CodersDen
Description: AI coding Q&A world
Address: 192.168.1.10:8024 (example usage)
> jump CodersDen
You jump to CodersDen!
(In a real scenario, you'd connect to 192.168.1.10:8024)
> quit
Goodbye!
```

## Docker Support

You can run the Jump Point server in Docker:

```dockerfile
FROM python:3.11-alpine

WORKDIR /app

COPY . .
RUN pip install -e .

EXPOSE 8023

CMD ["uv", "run", "jump-point-server", "--host", "0.0.0.0", "--port", "8023", "--log-level", "INFO"]
```

Build and run:

```bash
docker build -t jump-point-server .
docker run -p 8023:8023 jump-point-server
```

## Troubleshooting

### Connection Issues

1. Check that the server is running: `telnet localhost 8023`
2. Verify the correct host and port
3. Check logs with increased verbosity: `uv run jump-point-server --log-level DEBUG`

### Common Errors

- **Connection refused**: The server is not running or the port is blocked
- **Username not setting**: Ensure the user manager is working correctly
- **World connection failures**: Verify world configuration in `config.py`

## Extending the Server

- Add new worlds in `config.py`
- Create new command modules in the `commands/` directory
- Customize the user management in `user_manager.py`

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Credits

A multi-world telnet server built with Python's asyncio and custom protocol handling.