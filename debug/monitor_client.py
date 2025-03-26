#!/usr/bin/env python3
"""
WebSocket Session Monitoring Client Example

This script demonstrates how to connect to the monitoring endpoint
and observe active sessions in real-time.
"""

import asyncio
import json
import logging
import sys
import websockets
import argparse
import signal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('monitor-client')

class SessionMonitorClient:
    """A client for monitoring WebSocket sessions."""
    
    def __init__(self, url: str):
        """
        Initialize the session monitor client.
        
        Args:
            url: The WebSocket URL to connect to
        """
        self.url = url
        self.websocket = None
        self.running = True
        self.active_sessions = {}
    
    async def connect(self):
        """Connect to the monitoring endpoint."""
        try:
            self.websocket = await websockets.connect(self.url)
            logger.info(f"Connected to monitoring endpoint: {self.url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {self.url}: {e}")
            return False
    
    async def start_monitoring(self):
        """Start monitoring sessions."""
        if not self.websocket:
            if not await self.connect():
                return
        
        try:
            # Process incoming messages
            async for message in self.websocket:
                if not self.running:
                    break
                
                try:
                    data = json.loads(message)
                    await self.handle_event(data)
                except json.JSONDecodeError:
                    logger.warning(f"Received invalid JSON: {message}")
                    continue
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection to monitoring server closed")
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
        finally:
            if self.websocket:
                # Use a try-except block to handle the close
                try:
                    await self.websocket.close()
                except:
                    pass
    
    async def watch_session(self, session_id: str):
        """
        Start watching a specific session.
        
        Args:
            session_id: The ID of the session to watch
        """
        if not self.websocket:
            logger.error("Not connected to monitoring server")
            return
        
        try:
            command = {
                'type': 'watch_session',
                'session_id': session_id
            }
            await self.websocket.send(json.dumps(command))
            logger.info(f"Requested to watch session: {session_id}")
        except Exception as e:
            logger.error(f"Failed to send watch request: {e}")
    
    async def stop_watching(self, session_id: str):
        """
        Stop watching a specific session.
        
        Args:
            session_id: The ID of the session to stop watching
        """
        if not self.websocket:
            logger.error("Not connected to monitoring server")
            return
        
        try:
            command = {
                'type': 'stop_watching',
                'session_id': session_id
            }
            await self.websocket.send(json.dumps(command))
            logger.info(f"Requested to stop watching session: {session_id}")
        except Exception as e:
            logger.error(f"Failed to send stop watching request: {e}")
    
    async def handle_event(self, event: dict):
        """
        Handle a monitoring event.
        
        Args:
            event: The event to handle
        """
        event_type = event.get('type')
        
        if event_type == 'active_sessions':
            # Received list of active sessions
            sessions = event.get('sessions', [])
            self.active_sessions = {s['id']: s for s in sessions}
            
            if sessions:
                logger.info(f"Active sessions ({len(sessions)}):")
                for i, session in enumerate(sessions):
                    logger.info(f"  {i+1}. Session ID: {session['id']} - {session['client']['remote_addr']}")
                
                # Find the newest session if available
                newest_session_id = None
                for session in sessions:
                    if session.get('is_newest', False):
                        newest_session_id = session['id']
                        break
                
                # Watch the newest session or the first one if no newest flag
                if newest_session_id:
                    await self.watch_session(newest_session_id)
                elif sessions:
                    await self.watch_session(sessions[0]['id'])
            else:
                logger.info("No active sessions")
        
        elif event_type == 'session_started':
            # New session started
            session = event.get('session', {})
            session_id = session.get('id')
            
            if session_id:
                self.active_sessions[session_id] = session
                logger.info(f"New session started: {session_id} - {session.get('client', {}).get('remote_addr')}")
                
                # Automatically watch new sessions
                await self.watch_session(session_id)
        
        elif event_type == 'session_ended':
            # Session ended
            session = event.get('session', {})
            session_id = session.get('id')
            
            if session_id and session_id in self.active_sessions:
                self.active_sessions.pop(session_id)
                logger.info(f"Session ended: {session_id}")
        
        elif event_type == 'client_input':
            # Client input received
            session_id = event.get('session_id')
            data = event.get('data', {})
            text = data.get('text', '')
            
            if session_id in self.active_sessions:
                logger.info(f"[Client {session_id}] {text.strip()}")
        
        elif event_type == 'server_message':
            # Server message sent to client
            session_id = event.get('session_id')
            data = event.get('data', {})
            text = data.get('text', '')
            
            if session_id in self.active_sessions:
                logger.info(f"[Server → {session_id}] {text.strip()}")
        
        elif event_type == 'watch_response':
            # Response to watch request
            session_id = event.get('session_id')
            status = event.get('status')
            
            if status == 'success':
                logger.info(f"Now watching session: {session_id}")
            elif status == 'stopped':
                logger.info(f"Stopped watching session: {session_id}")
            else:
                error = event.get('error', 'Unknown error')
                logger.error(f"Failed to watch session {session_id}: {error}")
    
    async def close(self):
        """Close the connection to the monitoring endpoint."""
        self.running = False
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("Disconnected from monitoring server")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")

async def main():
    """Main entry point for the monitoring client."""
    parser = argparse.ArgumentParser(description='WebSocket Session Monitoring Client')
    parser.add_argument('--url', type=str, default='ws://localhost:8025/monitor',
                      help='WebSocket URL for monitoring (default: ws://localhost:8025/monitor)')
    args = parser.parse_args()
    
    # Create the monitoring client
    client = SessionMonitorClient(args.url)
    
    # Set up signal handling for graceful shutdown
    loop = asyncio.get_running_loop()
    
    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(client.close())
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)
    
    try:
        # Start monitoring
        await client.start_monitoring()
    except KeyboardInterrupt:
        logger.info("Monitoring client stopped by user")
    finally:
        await client.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Client terminated by user")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)