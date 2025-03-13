#!/usr/bin/env python3
# src/servers/stock_server.py
"""
Stock Telnet Server Implementation
Uses the telnet server framework to provide stock quotes
"""
import asyncio
import logging
import time
import re
from typing import Dict, Any, Optional, Set, List

import yfinance as yf
from telnet_server import TelnetServer, TelnetProtocolHandler

# Configure logging
logger = logging.getLogger('stock-telnet-server')

class StockCache:
    """Cache stock data to avoid excessive API requests"""
    def __init__(self, cache_ttl: int = 5):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = cache_ttl  # Time to live in seconds
    
    async def get_stock_price(self, ticker_symbol: str) -> tuple:
        """Get stock price for the given ticker symbol using cache if possible"""
        # Sanitize ticker symbol - remove all non-alphanumeric characters except dots and hyphens
        ticker_symbol = re.sub(r'[^\w\.-]', '', ticker_symbol).upper()
        
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
            # Additional validation to prevent API errors
            if not ticker_symbol or len(ticker_symbol) < 1 or len(ticker_symbol) > 10:
                logger.warning(f"Invalid ticker symbol: '{ticker_symbol}'")
                return "Invalid ticker"
            
            ticker = yf.Ticker(ticker_symbol)
            ticker_data = ticker.history(period="1d")
            if ticker_data.empty:
                return "N/A"
            
            # Get the last closing price
            last_price = ticker_data['Close'].iloc[-1]
            return str(round(last_price, 2))
        except Exception as e:
            logger.error(f"Error in yfinance API call for {ticker_symbol}: {e}")
            return "Error"


class StockTelnetHandler(TelnetProtocolHandler):
    """Handler for stock telnet sessions"""
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Initialize with reader/writer streams and cache"""
        super().__init__(reader, writer)
        self.current_ticker = None
        self.feed_active = False
    
    async def handle_client(self) -> None:
        """Handle a client connection"""
        logger.info(f"New connection from {self.addr}")
        
        # Send welcome message
        await self.send_line("Welcome to the Stock Feed Server!")
        await self.send_line("You can request a stock feed by typing:")
        await self.send_line("  stock <ticker>   (e.g., stock AAPL for Apple Inc.)")
        await self.send_line("Type 'quit' to disconnect.")
        
        # Display menu
        await self.display_menu()
        
        while self.running:
            try:
                # Prompt for command
                await self.send_line("\n> ")
                
                # Read command with timeout
                command = await self.read_line(timeout=300)  # 5 minute timeout
                if command is None:
                    logger.info(f"Client {self.addr} closed connection")
                    break
                
                logger.info(f"Received command from {self.addr}: {command}")
                
                if command.lower() == 'quit':
                    await self.send_line("Goodbye!")
                    break
                
                elif command.lower().startswith('stock'):
                    # Use regex to extract the ticker symbol safely
                    match = re.search(r'stock\s+([^\s]+)', command.lower())
                    if match:
                        raw_ticker = match.group(1)
                        # Sanitize the ticker
                        ticker_symbol = re.sub(r'[^\w\.-]', '', raw_ticker).upper()
                        
                        if ticker_symbol:
                            logger.info(f"Extracted ticker symbol: '{ticker_symbol}'")
                            await self.handle_feed_command(ticker_symbol)
                            await self.display_menu()
                        else:
                            await self.send_line("Error: Invalid ticker symbol")
                    else:
                        await self.send_line("Error: Provide a ticker symbol, e.g., 'stock AAPL'")
                
                else:
                    await self.send_line("Unknown command.")
                    await self.display_menu()
            
            except asyncio.TimeoutError:
                # Timeout waiting for command - check if server is still running
                if not self.running:
                    break
                # Else just continue the loop
            
            except Exception as e:
                logger.error(f"Error in client command loop for {self.addr}: {e}")
                if "Connection reset" in str(e) or "Broken pipe" in str(e):
                    break
                else:
                    # For unexpected errors, wait a bit to avoid spamming logs
                    await asyncio.sleep(1)
    
    async def display_menu(self) -> None:
        """Display the server menu"""
        await self.send_line("\n--- Menu ---")
        await self.send_line("stock <ticker> : Start (or switch to) a stock price feed for the specified ticker (e.g., stock AAPL)")
        await self.send_line("quit           : Disconnect from the server")
        await self.send_line("--------------")
    
    async def handle_feed_command(self, ticker_symbol: str) -> None:
        """Handle a stock feed command with proper timeout and interruption handling"""
        # Critical sanitization of ticker symbol
        ticker_symbol = re.sub(r'[^\w\.-]', '', ticker_symbol).upper()
        
        if not ticker_symbol:
            await self.send_line("Error: Invalid ticker symbol")
            return
        
        self.feed_active = True
        self.current_ticker = ticker_symbol
        
        # Notify the client
        await self.send_line(f"Starting feed for {self.current_ticker}.")
        await self.send_line("Press 'q' (or type a new 'stock <ticker>' command) then Enter to change the feed or stop it.")
        
        # Get the cache from the server
        cache = self.server.stock_cache
        
        while self.feed_active and self.running:
            try:
                # Get stock price from cache
                price, timestamp = await cache.get_stock_price(self.current_ticker)
                
                # Format timestamp
                formatted_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
                
                # Send the price update
                await self.send_line(f"[{formatted_time}] {self.current_ticker}: {price}")
                
                # Wait for input with timeout
                try:
                    # Set up a task to read with a timeout
                    read_task = asyncio.create_task(self.reader.readline())
                    
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
                            # Critical: handle empty data (connection closed)
                            if not data:
                                logger.info("Connection closed during feed")
                                self.feed_active = False
                                break
                                
                            incoming = data.decode('utf-8', errors='ignore').strip()
                            
                            if incoming.lower() == 'q':
                                await self.send_line("Feed stopped.")
                                self.feed_active = False
                            elif incoming.lower().startswith('stock'):
                                # Extract ticker symbol safely
                                match = re.search(r'stock\s+([^\s]+)', incoming.lower())
                                if match:
                                    raw_ticker = match.group(1)
                                    # Sanitize the ticker symbol
                                    new_ticker = re.sub(r'[^\w\.-]', '', raw_ticker).upper()
                                    
                                    if new_ticker:
                                        await self.send_line(f"Switching feed to {new_ticker}...")
                                        self.current_ticker = new_ticker
                                    else:
                                        await self.send_line("Error: Invalid ticker symbol")
                                else:
                                    await self.send_line("Error: Invalid command format. Use 'stock SYMBOL'")
                            else:
                                await self.send_line("Unknown input. Type 'q' to stop or 'stock <ticker>' to switch.")
                        except Exception as e:
                            logger.error(f"Error processing client input: {e}")
                            self.feed_active = False
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
                        self.feed_active = False
                    
            except Exception as e:
                logger.error(f"Error during feed loop: {e}")
                if "Connection reset" in str(e) or "Broken pipe" in str(e):
                    logger.info("Client disconnected during feed")
                    self.feed_active = False
                else:
                    # For other errors, wait a bit before retrying
                    await asyncio.sleep(1)
        
        self.feed_active = False
        self.current_ticker = None


class StockTelnetServer(TelnetServer):
    """Telnet server providing stock information"""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 8023):
        """Initialize with stock cache"""
        super().__init__(host, port, self.create_handler)
        self.stock_cache = StockCache()
    
    def create_handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> StockTelnetHandler:
        """Create a new handler for a client connection"""
        handler = StockTelnetHandler(reader, writer)
        # Give the handler access to the server
        handler.server = self
        return handler


def main():
    """Main function"""
    try:
        # Create server
        server = StockTelnetServer()
        # Start server
        asyncio.run(server.start_server())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt.")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
    finally:
        logger.info("Server process exiting.")


if __name__ == "__main__":
    main()