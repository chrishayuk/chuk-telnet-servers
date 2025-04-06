# sample_servers/jump_point_server/server.py
import asyncio
import logging

# imports
from chuk_protocol_server.servers.telnet_server import TelnetServer
from chuk_jump_server.handler import JumpPointTelnetHandler

# logger
logger = logging.getLogger('jump-point-server')

async def main():
    """
    Entry point to start the Jump Point server.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # set the host and port
    host, port = '0.0.0.0', 8023
    logger.info(f"Starting Jump Point on {host}:{port}")

    # Instantiate the server with our custom JumpPointTelnetHandler
    server = TelnetServer(host, port, JumpPointTelnetHandler)

    try:
        await server.start_server()
    except KeyboardInterrupt:
        logger.info("Server shutdown initiated by user.")
    except Exception as e:
        logger.error(f"Error running server: {e}")
    finally:
        logger.info("Jump Point has shut down.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt.")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
