#!/usr/bin/env python3
"""
WebSocket Session Monitoring Client Example

Modified to emulate a connected terminal rather than using debug/log messages.
"""

import asyncio
import json
import sys
import websockets
import argparse
import signal

class SessionMonitorClient:
    """A client for monitoring WebSocket sessions, emulating a raw terminal view."""
    
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
            print(f"Connected to {self.url}")
            return True
        except Exception as e:
            print(f"Failed to connect to {self.url}: {e}", file=sys.stderr)
            return False
    
    async def start_monitoring(self):
        """Start monitoring sessions."""
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
                    print(f"Received invalid JSON: {message}", file=sys.stderr)
                    continue
        except websockets.exceptions.ConnectionClosed:
            print("Connection to monitoring server closed.")
        except Exception as e:
            print(f"Error in monitoring loop: {e}", file=sys.stderr)
        finally:
            if self.websocket:
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
            print("Not connected to monitoring server.", file=sys.stderr)
            return
        
        try:
            command = {
                'type': 'watch_session',
                'session_id': session_id
            }
            await self.websocket.send(json.dumps(command))
        except Exception as e:
            print(f"Failed to send watch request: {e}", file=sys.stderr)
    
    async def stop_watching(self, session_id: str):
        """
        Stop watching a specific session.
        
        Args:
            session_id: The ID of the session to stop watching
        """
        if not self.websocket:
            print("Not connected to monitoring server.", file=sys.stderr)
            return
        
        try:
            command = {
                'type': 'stop_watching',
                'session_id': session_id
            }
            await self.websocket.send(json.dumps(command))
        except Exception as e:
            print(f"Failed to send stop watching request: {e}", file=sys.stderr)
    
    async def handle_event(self, event: dict):
        """
        Handle a monitoring event, printing relevant data to emulate a raw terminal.
        
        Args:
            event: The event to handle
        """
        event_type = event.get('type')
        
        if event_type == 'active_sessions':
            # Received list of active sessions
            sessions = event.get('sessions', [])
            self.active_sessions = {s['id']: s for s in sessions}
            
            # Automatically watch the newest session or the first one
            if sessions:
                newest_session_id = None
                for s in sessions:
                    if s.get('is_newest', False):
                        newest_session_id = s['id']
                        break
                session_to_watch = newest_session_id or sessions[0]['id']
                await self.watch_session(session_to_watch)
        
        elif event_type == 'session_started':
            # New session started
            session = event.get('session', {})
            session_id = session.get('id')
            if session_id:
                self.active_sessions[session_id] = session
                # Automatically watch new sessions
                await self.watch_session(session_id)
                print(f"\n--- Session started: {session_id} ---\n")
        
        elif event_type == 'session_ended':
            # Session ended
            session = event.get('session', {})
            session_id = session.get('id')
            if session_id and session_id in self.active_sessions:
                self.active_sessions.pop(session_id)
                print(f"\n--- Session ended: {session_id} ---\n")
        
        elif event_type == 'client_input':
            # Client input received
            session_id = event.get('session_id')
            data = event.get('data', {})
            text = data.get('text', '')
            if session_id in self.active_sessions:
                # Emulate user input on the terminal
                sys.stdout.write(text)
                sys.stdout.flush()
        
        elif event_type == 'server_message':
            # Server message sent to client
            session_id = event.get('session_id')
            data = event.get('data', {})
            text = data.get('text', '')
            if session_id in self.active_sessions:
                # Emulate server response on the terminal
                sys.stdout.write(text)
                sys.stdout.flush()
        
        elif event_type == 'watch_response':
            # Response to watch request
            session_id = event.get('session_id')
            status = event.get('status')
            if status == 'success':
                # Indicate that we are now "attached" to this session
                print(f"\n--- Now watching session: {session_id} ---\n")
            elif status == 'stopped':
                print(f"\n--- Stopped watching session: {session_id} ---\n")
            else:
                error = event.get('error', 'Unknown error')
                print(f"Failed to watch session {session_id}: {error}", file=sys.stderr)

    async def close(self):
        """Close the connection to the monitoring endpoint."""
        self.running = False
        if self.websocket:
            try:
                await self.websocket.close()
                print("Disconnected from monitoring server.")
            except Exception as e:
                print(f"Error closing connection: {e}", file=sys.stderr)

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
        print("Received shutdown signal.")
        asyncio.create_task(client.close())
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)
    
    try:
        # Start monitoring
        await client.start_monitoring()
    except KeyboardInterrupt:
        print("Monitoring client stopped by user.")
    finally:
        await client.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Client terminated by user.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
