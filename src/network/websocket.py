import asyncio
import json
import websockets
from typing import Optional, Callable, Dict
from src.config.settings import CONFIG
from datetime import datetime

class WebSocketClient:
    def __init__(self):
        self.uri = CONFIG['WEBSOCKET_SERVER']
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.message_handler: Optional[Callable] = None
        self.status_handler: Optional[Callable] = None
        self.reconnect_interval = 5
        self.metrics_task = None
        self.should_reconnect = False  # Add this flag

    async def connect(self):
        """Connect to WebSocket server"""
        self.should_reconnect = True  # Set reconnect flag
        
        while self.should_reconnect:
            try:
                if not self.connected:
                    self.websocket = await websockets.connect(self.uri)
                    self.connected = True
                    print(f"Connected to WebSocket server at {self.uri}")
                    
                    # Notify status handler of connection status change
                    if self.status_handler:
                        asyncio.get_running_loop().call_soon_threadsafe(self.status_handler, self.connected)
                    
                    # Send initial connection message
                    await self.send_message({
                        'type': 'connect',
                        'user_id': CONFIG['DISCORD_USER_ID']
                    })
                    
                    # Start metrics update task
                    if self.metrics_task is None:
                        self.metrics_task = asyncio.create_task(self.request_metrics_updates())
                    
                    # Start listening for messages
                    await self._listen()
                    
            except Exception as e:
                print(f"WebSocket connection error: {e}")
                self.connected = False
                
                # Notify status handler of connection status change
                if self.status_handler:
                    asyncio.get_running_loop().call_soon_threadsafe(self.status_handler, self.connected)

                if self.metrics_task:
                    self.metrics_task.cancel()
                    self.metrics_task = None
                if self.message_handler:
                    # Send empty metrics to reset counters
                    await self.message_handler({
                        'type': 'metrics_update',
                        'metrics': {}
                    })
                
                if self.should_reconnect:
                    print(f"Reconnecting in {self.reconnect_interval} seconds...")
                    await asyncio.sleep(self.reconnect_interval)
                else:
                    break  # Exit the loop if reconnection is disabled

    async def disconnect(self):
        """Disconnect from WebSocket server"""
        self.should_reconnect = False  # Disable reconnection
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            print("Disconnected from WebSocket server")

            # Notify status handler of connection status change
            if self.status_handler:
                asyncio.get_running_loop().call_soon_threadsafe(self.status_handler, self.connected)

    async def request_metrics_updates(self):
        """Periodically request metrics updates"""
        while self.should_reconnect:  # Use the same flag here
            try:
                if self.connected:
                    await self.send_message({'type': 'request_metrics'})
                await asyncio.sleep(5)  # Update every 5 seconds
            except Exception as e:
                print(f"Error requesting metrics: {e}")
                if self.message_handler:
                    # Send empty metrics on error
                    await self.message_handler({
                        'type': 'metrics_update',
                        'metrics': {}
                    })
                await asyncio.sleep(1)

    async def _listen(self):
        """Listen for messages from the server"""
        try:
            while True:
                if self.websocket:
                    message = await self.websocket.recv()
                    if self.message_handler:
                        await self.message_handler(json.loads(message))
        except websockets.ConnectionClosed:
            print("WebSocket connection closed")
            self.connected = False
        except Exception as e:
            print(f"Error in WebSocket listener: {e}")
            self.connected = False

    async def send_message(self, message: Dict):
        """Send message to WebSocket server"""
        if self.websocket and self.connected:
            try:
                await self.websocket.send(json.dumps(message))
            except Exception as e:
                print(f"Error sending message: {e}")
                self.connected = False

    def set_message_handler(self, handler: Callable):
        """Set handler for incoming messages"""
        self.message_handler = handler

    async def send_transcript(self, transcript: Dict, preferred_name: str):
        """Send transcription result to server"""
        timestamp = datetime.now().isoformat()
        message = {
            'type': 'transcript',
            'username': preferred_name,
            'content': transcript['text'],
            'timestamp': timestamp
        }
        await self.send_message(message)

    async def send_action(self, action: Dict):
        """Send action request to server"""
        message = {
            'type': action['type'],
            'timestamp': action['timestamp']
        }
        await self.send_message(message)

    def set_message_handler(self, handler: Callable):
        """Set handler for incoming messages"""
        self.message_handler = handler

    def set_status_handler(self, handler: Callable):
        """Set handler for connection status updates"""
        self.status_handler = handler

async def test_websocket():
    """Test WebSocket functionality with hotkey manager"""
    from src.audio.processor import AudioProcessor
    from src.audio.capture import AudioCapture
    from src.input.hotkey import HotkeyManager

    async def on_server_message(message):
        print(f"\nReceived from server: {message}")

    async def on_transcription(result):
        print("\nTranscription result:")
        print(f"Text: {result['text']}")
        # Send to WebSocket server
        await ws_client.send_transcript(result)

    try:
        processor = AudioProcessor()
        capture = AudioCapture()
        hotkey = HotkeyManager(processor, capture)
        ws_client = WebSocketClient()

        # Set up handlers
        hotkey.set_transcription_callback(on_transcription)
        ws_client.set_message_handler(on_server_message)

        print(f"\nPress and hold '{hotkey.push_to_talk_key}' to record.")
        print("Press Ctrl+C to exit.")

        # Get the current event loop
        loop = asyncio.get_running_loop()
        hotkey.start(loop)

        # Start WebSocket connection
        websocket_task = asyncio.create_task(ws_client.connect())

        # Keep the program running
        while True:
            await asyncio.sleep(0.1)

    except KeyboardInterrupt:
        print("\nExiting...")
        hotkey.stop()
        await ws_client.disconnect()
        processor.cleanup()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_websocket())