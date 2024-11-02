import keyboard
import asyncio
from typing import Callable, Optional
from src.config.settings import CONFIG
from src.audio.capture import AudioCapture
from src.audio.processor import AudioProcessor

class HotkeyManager:
    def __init__(self, processor: AudioProcessor, capture: AudioCapture):
        self.processor = processor
        self.capture = capture
        self.push_to_talk_key = CONFIG['PUSH_TO_TALK_KEY']  # Initial default from CONFIG
        self.mode = 'push'  # Default to push-to-talk
        self.is_recording = False
        self.callback: Optional[Callable] = None
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

    def start(self, loop: asyncio.AbstractEventLoop):
        """Start listening for hotkey"""
        self.loop = loop
        self.stop()  # Clear any existing hooks
        if self.mode == 'push':
            keyboard.on_press_key(self.push_to_talk_key, self._on_key_press)
            keyboard.on_release_key(self.push_to_talk_key, self._on_key_release)
        elif self.mode == 'toggle':
            keyboard.on_press_key(self.push_to_talk_key, self._on_key_press)
        self._hooks_active = True
        print(f"Listening for push-to-talk key: {self.push_to_talk_key} in {self.mode} mode")

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