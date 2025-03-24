#!/usr/bin/env python3
"""
Stock Feed Telnet Server

A telnet-based server that provides real-time stock price information.
Uses the modular telnet server framework with proper terminal handling.

Features:
- Real-time stock price feeds with yfinance
- Proper terminal handling for telnet clients
- Caching to prevent excessive API requests
- Graceful shutdown handling
- Thread-safe connection management
"""

import asyncio
import logging
import signal
import time
from typing import Dict, Any, Set, Optional
import yfinance as yf

# Import from our modular architecture
from telnet_server.handlers.telnet_handler import TelnetHandler
from telnet_server.server import TelnetServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('stock-telnet-server')

# Global state
server_running = True

class StockCache:
    """
    Cache for stock price data to avoid excessive API requests.
    Thread-safe implementation for use in async environment.
    """
    def __init__(self, cache_ttl: int = 5):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = cache_ttl  # Time to live in seconds
        self.lock = asyncio.Lock()  # For thread safety
    
    async def get_stock_price(self, ticker_symbol: str) -> tuple:
        """
        Get stock price for the given ticker symbol using cache if possible.
        
        Args:
            ticker_symbol: The stock ticker symbol
        
        Returns:
            A tuple of (price, timestamp)
        """
        # Sanitize ticker symbol
        ticker_symbol = ticker_symbol.strip().upper()
        
        current_time = time.time()
        
        # Check cache with lock to ensure thread safety
        async with self.lock:
            # Check if we have a valid cached entry
            if ticker_symbol in self.cache:
                cached_data = self.cache[ticker_symbol]
                if current_time - cached_data['timestamp'] < self.ttl:
                    return cached_data['price'], cached_data['timestamp']
        
        # Not in cache or expired, fetch new data
        try:
            # Execute in a separate thread pool to avoid blocking
            price = await asyncio.get_event_loop().run_in_executor(
                None, self._fetch_stock_price, ticker_symbol
            )
            
            # Update cache with lock
            async with self.lock:
                self.cache[ticker_symbol] = {
                    'price': price,
                    'timestamp': current_time
                }
            
            return price, current_time
        except Exception as e:
            logger.error(f"Error fetching stock price for {ticker_symbol}: {e}")
            return "Error", current_time
    
    def _fetch_stock_price(self, ticker_symbol: str) -> str:
        """
        Actual API call to fetch stock price - runs in thread pool.
        
        Args:
            ticker_symbol: The stock ticker symbol
        
        Returns:
            The stock price as a string, or an error message
        """
        try:
            ticker = yf.Ticker(ticker_symbol)
            # Get the most recent history (more reliable than real-time data)
            ticker_data = ticker.history(period="1d")
            if ticker_data.empty:
                return "N/A"
            
            # Get the last closing price
            last_price = ticker_data['Close'].iloc[-1]
            return str(round(last_price, 2))
        except Exception as e:
            logger.error(f"Error in yfinance API call for {ticker_symbol}: {e}")
            return "Error"


class StockFeedHandler(TelnetHandler):
    """
    Custom telnet handler for the stock feed application.
    Inherits from our modular TelnetHandler for proper terminal handling.
    """
    # Class-level stock cache shared by all instances
    stock_cache = StockCache()
    
    # To track all active handlers for server shutdown
    active_handlers: Set['StockFeedHandler'] = set()
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Initialize the stock feed handler."""
        super().__init__(reader, writer)
        
        # Stock feed specific state
        self.current_feed: Optional[str] = None
        self.feed_task = None
        
        # Add to active handlers
        StockFeedHandler.active_handlers.add(self)
    
    async def handle_client(self) -> None:
        """
        Override the handle_client method to provide stock-specific welcome message.
        """
        logger.info(f"New connection from {self.addr}")
        
        try:
            # Let the parent class handle the initial setup and input processing loop
            await super().handle_client()
        except Exception as e:
            logger.error(f"Error in stock feed client handler: {e}")
        finally:
            # Stop any running feed task
            await self._stop_feed()
            # Remove from active handlers
            StockFeedHandler.active_handlers.discard(self)
    
    async def on_command_submitted(self, command: str) -> None:
        """
        Process commands for the stock feed server.
        
        Args:
            command: The command submitted by the user
        """
        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""
        
        if cmd == "stock" and len(parts) > 1:
            # Stock feed command - extract ticker symbol
            ticker = parts[1].strip().upper()
            await self._start_feed(ticker)
        elif cmd == "stop":
            # Stop the current feed
            await self._stop_feed()
            await self.send_line("Feed stopped.")
        elif cmd == "help":
            # Show help
            await self._show_help()
        else:
            # Unknown command
            await self.send_line(f"Unknown command: {command}")
            await self.send_line("Type 'help' for available commands")
    
    async def _start_feed(self, ticker: str) -> None:
        """
        Start a stock price feed for the given ticker.
        Stops any existing feed first.
        
        Args:
            ticker: The stock ticker symbol
        """
        # Stop any existing feed
        await self._stop_feed()
        
        # Set the current feed
        self.current_feed = ticker
        
        # Start a new feed task
        await self.send_line(f"Starting price feed for {ticker}...")
        await self.send_line("Press Ctrl+C or type 'stop' to stop the feed")
        
        self.feed_task = asyncio.create_task(self._run_feed(ticker))
    
    async def _stop_feed(self) -> None:
        """Stop the current stock feed if one is running."""
        if self.feed_task and not self.feed_task.done():
            self.feed_task.cancel()
            try:
                await self.feed_task
            except asyncio.CancelledError:
                pass  # Task cancellation is expected
            
        self.current_feed = None
        self.feed_task = None
    
    async def _run_feed(self, ticker: str) -> None:
        """
        Run the stock price feed for the given ticker.
        Fetches prices regularly and displays them to the user.
        
        Args:
            ticker: The stock ticker symbol
        """
        try:
            # Initial fetch to check if the ticker is valid
            price, timestamp = await self.stock_cache.get_stock_price(ticker)
            if price == "Error" or price == "N/A":
                await self.send_line(f"Could not fetch price for {ticker}. Please check the ticker symbol.")
                self.current_feed = None
                return
            
            # Display the initial price
            formatted_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
            await self.send_line(f"[{formatted_time}] {ticker}: {price}")
            
            # Loop to provide regular updates
            while server_running and self.running and self.current_feed == ticker:
                try:
                    # Wait a bit between updates
                    await asyncio.sleep(5)
                    
                    # Check if we should still be running
                    if not (server_running and self.running and self.current_feed == ticker):
                        break
                    
                    # Fetch current price
                    price, timestamp = await self.stock_cache.get_stock_price(ticker)
                    formatted_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
                    
                    # Display the update
                    await self.send_line(f"[{formatted_time}] {ticker}: {price}")
                    
                except asyncio.CancelledError:
                    # Feed was cancelled
                    raise
                except Exception as e:
                    logger.error(f"Error in feed loop for {ticker}: {e}")
                    await asyncio.sleep(1)  # Brief pause on error
        
        except asyncio.CancelledError:
            # Task cancellation is expected behavior
            logger.debug(f"Feed for {ticker} was cancelled")
        except Exception as e:
            logger.error(f"Error running feed for {ticker}: {e}")
            await self.send_line(f"Error in feed: {e}")
        finally:
            # Make sure we clean up properly
            self.current_feed = None
    
    async def _show_help(self) -> None:
        """Display help information to the user."""
        help_text = [
            "Available commands:",
            "  stock <ticker>  - Start a price feed for the given stock ticker",
            "  stop            - Stop the current price feed",
            "  help            - Show this help message",
            "  quit            - Disconnect from the server",
            "",
            "Examples:",
            "  stock AAPL      - Get Apple stock prices",
            "  stock MSFT      - Get Microsoft stock prices",
            "  stock GOOGL     - Get Google stock prices"
        ]
        
        for line in help_text:
            await self.send_line(line)
    
    async def process_character(self, char: str) -> bool:
        """
        Override to handle Ctrl+C specially for the stock feed.
        We'll stop the current feed rather than disconnecting.
        
        Args:
            char: The character to process
        
        Returns:
            True to continue, False to disconnect
        """
        # Check for Ctrl+C specifically
        if char == "\x03":
            if self.current_feed:
                # If we have an active feed, stop it instead of disconnecting
                await self.send_line("\n^C - Stopping current feed.")
                await self._stop_feed()
                await self.show_prompt()
                return True
            else:
                # No feed running, so exit as normal
                await self.send_line("\n^C - Closing connection.")
                return False
        
        # For all other characters, use the parent implementation
        return await super().process_character(char)

    async def send_welcome(self) -> None:
        """Send a customized welcome message."""
        welcome_text = [
            "Welcome to the Stock Feed Server!",
            "-------------------------------",
            "Type 'stock <ticker>' to start a price feed (e.g., stock AAPL)",
            "Type 'help' for available commands",
            "Type 'quit' to disconnect"
        ]
        
        for line in welcome_text:
            await self.send_line(line)
        
        await self.show_prompt()


async def shutdown_handlers():
    """Gracefully shut down all active handlers."""
    if StockFeedHandler.active_handlers:
        logger.info(f"Shutting down {len(StockFeedHandler.active_handlers)} active connections...")
        
        # Send a goodbye message to all clients
        shutdown_tasks = []
        for handler in list(StockFeedHandler.active_handlers):
            try:
                # Stop any active feeds
                if handler.current_feed:
                    await handler.send_line("\nServer is shutting down. Stopping feed...")
                    await handler._stop_feed()
                
                # Send goodbye message
                await handler.send_line("\nServer is shutting down. Goodbye!")
                
                # Close the connection
                handler.writer.close()
                shutdown_tasks.append(handler.writer.wait_closed())
            except Exception as e:
                logger.warning(f"Error sending shutdown message: {e}")
        
        # Wait for all connections to close (with timeout)
        if shutdown_tasks:
            try:
                done, pending = await asyncio.wait(shutdown_tasks, timeout=5)
                if pending:
                    logger.warning(f"{len(pending)} connections did not close gracefully")
            except Exception as e:
                logger.error(f"Error waiting for connections to close: {e}")
        
        # Clear the set
        StockFeedHandler.active_handlers.clear()


# Main function to run the server directly
async def main():
    """
    Main entry point for the stock feed server.
    Sets up the server and signal handlers for graceful shutdown.
    """
    # Start the server
    host, port = '0.0.0.0', 8023
    
    try:
        # Create and start the server
        server = TelnetServer(host, port, StockFeedHandler)
        
        # Set up signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig, 
                lambda: asyncio.create_task(server.shutdown())
            )
        
        logger.info(f"Stock Feed Server running on {host}:{port}")
        await server.start_server()
    
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