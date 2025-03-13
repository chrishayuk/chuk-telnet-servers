#!/usr/bin/env python3
"""
Robust Asyncio-based Stock Telnet Server
Handles concurrent connections and implements proper timeouts
"""
import asyncio
import logging
import signal
import time
from typing import Dict, Any, Optional, Set
import yfinance as yf

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('stock-telnet-server')

# Globals
active_connections: Set[asyncio.StreamWriter] = set()
server_running = True

class StockCache:
    """Cache stock data to avoid excessive API requests"""
    def __init__(self, cache_ttl: int = 5):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = cache_ttl  # Time to live in seconds
    
    async def get_stock_price(self, ticker_symbol: str) -> tuple:
        """Get stock price for the given ticker symbol using cache if possible"""
        # Sanitize ticker symbol
        ticker_symbol = ticker_symbol.strip().upper()
        
        current_time = time.time()
        
        # Check cache
        if ticker_symbol in self.cache:
            cached_data = self.cache[ticker_symbol]
            if current_time - cached_data['timestamp'] < self.ttl:
                return cached_data['price'], cached_data['timestamp']
        
        # Fetch new data
        try:
            # Execute in a separate thread pool to avoid blocking
            price = await asyncio.get_event_loop().run_in_executor(
                None, self._fetch_stock_price, ticker_symbol
            )
            
            # Update cache
            self.cache[ticker_symbol] = {
                'price': price,
                'timestamp': current_time
            }
            
            return price, current_time
        except Exception as e:
            logger.error(f"Error fetching stock price for {ticker_symbol}: {e}")
            return "Error", current_time
    
    def _fetch_stock_price(self, ticker_symbol: str) -> str:
        """Actual API call to fetch stock price - runs in thread pool"""
        try:
            ticker = yf.Ticker(ticker_symbol)
            # Simpler approach that's less likely to fail
            ticker_data = ticker.history(period="1d")
            if ticker_data.empty:
                return "N/A"
            
            # Get the last closing price
            last_price = ticker_data['Close'].iloc[-1]
            return str(round(last_price, 2))
        except Exception as e:
            logger.error(f"Error in yfinance API call for {ticker_symbol}: {e}")
            return "Error"

# Initialize the stock cache
stock_cache = StockCache()

async def handle_feed_command(
    writer: asyncio.StreamWriter,
    reader: asyncio.StreamReader,
    ticker_symbol: str
) -> None:
    """Handle a stock feed command with proper timeout and interruption handling"""
    feed_active = True
    current_ticker = ticker_symbol.strip().upper()  # Sanitize ticker
    
    # Notify the client
    writer.write(f"Starting feed for {current_ticker}.\n".encode('utf-8'))
    writer.write(b"Press 'q' (or type a new 'stock <ticker>' command) then Enter to change the feed or stop it.\n")
    await writer.drain()
    
    while feed_active and server_running:
        try:
            # Get stock price from cache
            price, timestamp = await stock_cache.get_stock_price(current_ticker)
            
            # Format timestamp
            formatted_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
            
            # Send the price update
            message = f"[{formatted_time}] {current_ticker}: {price}\n"
            writer.write(message.encode('utf-8'))
            await writer.drain()
            
            # Wait for input with timeout
            try:
                # Set up a task to read with a timeout
                read_task = asyncio.create_task(reader.readline())
                
                # Wait for input with timeout
                done, pending = await asyncio.wait(
                    [read_task], 
                    timeout=5,
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # If we got input
                if read_task in done:
                    try:
                        data = await read_task
                        incoming = data.strip().decode('utf-8')
                        
                        if incoming.lower() == 'q':
                            writer.write(b"Feed stopped.\n")
                            await writer.drain()
                            feed_active = False
                        elif incoming.lower().startswith('stock'):
                            parts = incoming.split()
                            if len(parts) >= 2:
                                new_ticker = parts[1].strip().upper()
                                writer.write(f"Switching feed to {new_ticker}...\n".encode('utf-8'))
                                await writer.drain()
                                current_ticker = new_ticker
                        else:
                            writer.write(b"Unknown input. Type 'q' to stop or 'stock <ticker>' to switch.\n")
                            await writer.drain()
                    except Exception as e:
                        logger.error(f"Error processing client input: {e}")
                        feed_active = False
                else:
                    # Timeout occurred - cancel the read task
                    for task in pending:
                        task.cancel()
                
            except asyncio.CancelledError:
                # The task was canceled - we can continue with the loop
                continue
            except Exception as e:
                logger.error(f"Error during feed input handling: {e}")
                if "Connection reset" in str(e) or "Broken pipe" in str(e):
                    logger.info("Client disconnected during feed")
                    feed_active = False
                
        except Exception as e:
            logger.error(f"Error during feed loop: {e}")
            if "Connection reset" in str(e) or "Broken pipe" in str(e):
                logger.info("Client disconnected during feed")
                feed_active = False
            else:
                # For other errors, wait a bit before retrying
                await asyncio.sleep(1)

async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter
) -> None:
    """Handle a client connection"""
    # Get client info
    addr = writer.get_extra_info('peername')
    logger.info(f"New connection from {addr}")
    
    # Add to active connections
    active_connections.add(writer)
    
    try:
        # Send welcome message
        welcome = (
            "Welcome to the Stock Feed Server!\n"
            "You can request a stock feed by typing:\n"
            "  stock <ticker>   (e.g., stock AAPL for Apple Inc.)\n"
            "Type 'quit' to disconnect.\n"
        )
        writer.write(welcome.encode('utf-8'))
        await writer.drain()
        
        # Display menu
        await display_menu(writer)
        
        while server_running:
            try:
                # Prompt for command
                writer.write(b"\n> ")
                await writer.drain()
                
                # Read command with timeout
                try:
                    line = await asyncio.wait_for(reader.readline(), timeout=300)  # 5 minute timeout
                    
                    if not line:
                        logger.info(f"Client {addr} closed connection")
                        break  # Connection closed
                    
                    command = line.strip().decode('utf-8')
                    logger.debug(f"Received command from {addr}: {command}")
                    
                    if command.lower() == 'quit':
                        writer.write(b"Goodbye!\n")
                        await writer.drain()
                        break
                    
                    elif command.lower().startswith('stock'):
                        parts = command.split(maxsplit=1)  # Split only at the first space
                        if len(parts) < 2 or not parts[1].strip():
                            writer.write(b"Error: Provide a ticker symbol, e.g., 'stock AAPL'\n")
                            await writer.drain()
                            continue
                        
                        ticker_symbol = parts[1].strip().upper()
                        await handle_feed_command(writer, reader, ticker_symbol)
                        await display_menu(writer)
                    
                    else:
                        writer.write(b"Unknown command.\n")
                        await writer.drain()
                        await display_menu(writer)
                
                except asyncio.TimeoutError:
                    # Timeout waiting for command - check if server is still running
                    if not server_running:
                        break
                    # Else just continue the loop
                
                except Exception as e:
                    logger.error(f"Error handling client command from {addr}: {e}")
                    if "Connection reset" in str(e) or "Broken pipe" in str(e):
                        logger.info(f"Client {addr} disconnected")
                        break
                    else:
                        # For unexpected errors, wait a bit to avoid spamming logs
                        await asyncio.sleep(1)
            
            except Exception as e:
                logger.error(f"Error in client command loop for {addr}: {e}")
                if "Connection reset" in str(e) or "Broken pipe" in str(e):
                    break
                else:
                    # For unexpected errors, wait a bit to avoid spamming logs
                    await asyncio.sleep(1)
    
    except Exception as e:
        logger.error(f"Error in main client handler for {addr}: {e}")
    
    finally:
        # Clean up
        logger.info(f"Closing connection from {addr}")
        
        try:
            # Remove from active connections set first to avoid concurrent modification
            if writer in active_connections:
                active_connections.remove(writer)
            
            # Then close the connection
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=5.0)
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(f"Error or timeout waiting for connection to close: {e}")
        except Exception as e:
            logger.error(f"Error during connection cleanup for {addr}: {e}")

async def display_menu(writer: asyncio.StreamWriter) -> None:
    """Display the server menu"""
    try:
        menu = (
            "\n--- Menu ---\n"
            "stock <ticker> : Start (or switch to) a stock price feed for the specified ticker (e.g., stock AAPL)\n"
            "quit           : Disconnect from the server\n"
            "--------------\n"
        )
        writer.write(menu.encode('utf-8'))
        await writer.drain()
    except Exception as e:
        logger.error(f"Error displaying menu: {e}")
        # Don't re-raise - let the caller handle it

async def shutdown(server: asyncio.AbstractServer) -> None:
    """Gracefully shut down the server"""
    global server_running
    logger.info("Shutting down server...")
    
    # Stop accepting new connections
    server.close()
    await server.wait_closed()
    
    # Signal to all client handlers that the server is shutting down
    server_running = False
    
    # Give active connections a chance to close gracefully
    if active_connections:
        logger.info(f"Closing {len(active_connections)} active connections...")
        
        # Send a goodbye message to all clients
        for writer in list(active_connections):
            try:
                writer.write(b"\nServer is shutting down. Goodbye!\n")
                await writer.drain()
                writer.close()
            except Exception as e:
                logger.warning(f"Error sending shutdown message: {e}")
        
        # Wait for all connections to close (with timeout)
        wait_time = 5  # seconds
        for i in range(wait_time):
            if not active_connections:
                break
            logger.info(f"Waiting for connections to close: {len(active_connections)} remaining ({wait_time-i}s)")
            await asyncio.sleep(1)
        
        # Force close any remaining connections
        for writer in list(active_connections):
            try:
                writer.close()
                active_connections.remove(writer)
            except Exception as e:
                logger.warning(f"Error force-closing connection: {e}")

async def main():
    """Main function to start the server"""
    # Start the server
    host, port = '0.0.0.0', 8023
    
    try:
        server = await asyncio.start_server(
            handle_client,
            host,
            port
        )
        
        # Set up signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig, 
                lambda: asyncio.create_task(shutdown(server))
            )
        
        async with server:
            addr = server.sockets[0].getsockname()
            logger.info(f"Server running on {addr[0]}:{addr[1]}")
            
            # Keep the server running
            await server.serve_forever()
    except Exception as e:
        logger.error(f"Error starting server: {e}")
    finally:
        logger.info("Server has shut down.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt.")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
    finally:
        logger.info("Server process exiting.")