import keyboard
import asyncio
from typing import Callable, Optional
from src.config.settings import CONFIG
from src.audio.capture import AudioCapture
from src.audio.processor import AudioProcessor
from datetime import datetime

class HotkeyManager:
    def __init__(self, processor: AudioProcessor, capture: AudioCapture):
        self.processor = processor
        self.capture = capture
        self.push_to_talk_key = CONFIG['PUSH_TO_TALK_KEY']  # Initial default from CONFIG
        self.mode = 'push'  # Default to push-to-talk
        self.action_hotkeys = {}
        self.is_recording = False
        self.callback: Optional[Callable] = None
        self.action_callback: Optional[Callable] = None
        self.loop = None
        self._hooks_active = False  # Track if hooks are active

    def set_transcription_callback(self, callback: Callable[[str], None]):
        """Set callback for when transcription is complete"""
        self.callback = callback

    def set_hotkey(self, new_key: str):
        """Change the push-to-talk key"""
        self.push_to_talk_key = new_key
        if self._hooks_active and self.loop:
            # Restart hooks with new key
            self.stop()
            self.start(self.loop)

    def set_mode(self, mode: str):
        """Set the recording mode ('push' or 'toggle')"""
        self.mode = mode
        if self._hooks_active and self.loop:
            # Restart hooks with new mode
            self.stop()
            self.start(self.loop)

    def set_action_callback(self, callback: Callable[[str], None]):
        """Set callback for action hotkeys"""
        self.action_callback = callback

    def set_action_hotkeys(self, hotkeys: dict):
        """Set action hotkeys"""
        self.action_hotkeys = {k: v for k, v in hotkeys.items() if v}  # Only store non-empty hotkeys
        if self._hooks_active and self.loop:
            self.stop()
            self.start(self.loop)

    def start(self, loop: asyncio.AbstractEventLoop):
        """Start listening for hotkeys"""
        self.loop = loop
        self.stop()  # Clear any existing hooks
        
        # Set push-to-talk hook
        if self.push_to_talk_key:
            keyboard.on_press_key(self.push_to_talk_key, self._on_key_press)
            keyboard.on_release_key(self.push_to_talk_key, self._on_key_release)
            print(f"Listening for push-to-talk key: {self.push_to_talk_key}")
        
        # Set action hotkey hooks
        for action, key in self.action_hotkeys.items():
            if key:
                keyboard.on_press_key(key, lambda e, a=action: self._on_action_key(a))
                print(f"Listening for {action} key: {key}")
        
        self._hooks_active = True

    def _on_action_key(self, action: str):
        """Handle action key press"""
        if self.action_callback and self.loop and self.loop.is_running():
            timestamp = datetime.now().isoformat()
            asyncio.run_coroutine_threadsafe(
                self.action_callback({
                    'type': action,
                    'timestamp': timestamp
                }), 
                self.loop
            )

    def stop(self):
        """Stop listening for hotkey"""
        keyboard.unhook_all()
        self._hooks_active = False
        if self.is_recording:
            self.is_recording = False
            self.capture.stop_recording()

    def _on_key_press(self, event):
        """Handle key press"""
        if self.mode == 'push':
            if not self.is_recording:
                self.is_recording = True
                print("Recording started...")
                self.capture.start_recording()
        elif self.mode == 'toggle':
            if not self.is_recording:
                self.is_recording = True
                print("Recording started...")
                self.capture.start_recording()
            else:
                self.is_recording = False
                print("Recording stopped...")
                # Schedule the coroutine in the event loop
                if self.loop and self.loop.is_running():
                    asyncio.run_coroutine_threadsafe(self._process_audio(), self.loop)

    def _on_key_release(self, event):
        """Handle key release"""
        if self.mode == 'push':
            if self.is_recording:
                self.is_recording = False
                print("Recording stopped...")
                # Schedule the coroutine in the event loop
                if self.loop and self.loop.is_running():
                    asyncio.run_coroutine_threadsafe(self._process_audio(), self.loop)
        # In toggle mode, do nothing on key release

    async def _process_audio(self):
        """Process recorded audio"""
        try:
            audio_data = self.capture.stop_recording()
            if audio_data is not None:
                print("Processing audio...")
                result = await self.processor.process_audio(audio_data)
                if result and self.callback:
                    # Ensure the callback is called in the event loop
                    asyncio.run_coroutine_threadsafe(self.callback(result), self.loop)
                return result
            return None
        except Exception as e:
            print(f"Error processing audio: {e}")
            return None