import asyncio
import json
import websockets
from typing import Optional, Callable, Dict
from src.config.settings import CONFIG

class WebSocketClient:
    def __init__(self):
        self.uri = CONFIG['WEBSOCKET_SERVER']
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.message_handler: Optional[Callable] = None
        self.reconnect_interval = 5  # seconds

    async def connect(self):
        """Connect to WebSocket server"""
        while True:
            try:
                self.websocket = await websockets.connect(self.uri)
                self.connected = True
                print(f"Connected to WebSocket server at {self.uri}")
                
                # Send initial connection message with user ID
                await self.send_message({
                    'type': 'connect',
                    'user_id': CONFIG['DISCORD_USER_ID']
                })
                
                # Start listening for messages
                await self._listen()
                
            except Exception as e:
                print(f"WebSocket connection error: {e}")
                self.connected = False
                print(f"Reconnecting in {self.reconnect_interval} seconds...")
                await asyncio.sleep(self.reconnect_interval)

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

    async def send_transcript(self, transcript: Dict):
        """Send transcription result to server"""
        message = {
            'type': 'transcript',
            'user_id': CONFIG['DISCORD_USER_ID'],
            'content': transcript['text'],
            'language': transcript['language'],
            'segments': transcript['segments']
        }
        await self.send_message(message)

    async def disconnect(self):
        """Disconnect from WebSocket server"""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            print("Disconnected from WebSocket server")

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