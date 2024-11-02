import sounddevice as sd
import numpy as np
from queue import Queue
import threading
from typing import Optional
import os
import sys
import json
import time
from src.config.settings import CONFIG

class AudioCapture:
    def __init__(self):
        self.audio_queue = Queue()
        self.is_recording = False
        self.sample_rate = CONFIG['SAMPLE_RATE']
        self.chunk_size = CONFIG['CHUNK_SIZE']
        self.config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.json')
        self.selected_device = self._load_device_preference()
        self._setup_device()
        self.on_recording_start = None
        self.on_recording_stop = None

    def _load_device_preference(self) -> int:
        """Load saved device preference from config file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    return config.get('audio_device', None)
        except Exception as e:
            print(f"Error loading device preference: {e}")
        return None

    def _save_device_preference(self, device_id: int) -> None:
        """Save device preference to config file"""
        try:
            config = {}
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
            
            config['audio_device'] = device_id
            
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error saving device preference: {e}")

    def _setup_device(self):
        """Setup and verify audio device"""
        if self.selected_device is not None:
            try:
                self.set_device(self.selected_device)
                return
            except Exception as e:
                print(f"Error setting saved device: {e}")
        else:
            # No saved device; optionally set default device or handle accordingly
            print("No saved device found. Using default device.")
            self.selected_device = sd.default.device[0]

    def list_input_devices(self) -> list:
        """Return list of available input devices with IDs"""
        devices = []
        hostapis = sd.query_hostapis()
        for i, dev in enumerate(sd.query_devices()):
            if dev['max_input_channels'] > 0:
                hostapi_name = hostapis[dev['hostapi']]['name']
                devices.append((i, f"{dev['name']} ({hostapi_name})", dev['max_input_channels']))
        return devices

    def set_device(self, device_id: int) -> bool:
        """Set specific audio input device"""
        try:
            device_info = sd.query_devices(device_id)
            if device_info['max_input_channels'] > 0:
                sd.default.device[0] = device_id
                self.selected_device = device_id  # Update selected_device
                print(f"Set input device to: {device_info['name']} (ID: {device_id})")
                return True
            else:
                print(f"Device {device_id} has no input channels")
                return False
        except Exception as e:
            print(f"Error setting device: {e}")
            return False

    def start_recording(self) -> None:
        """Start recording audio"""
        if self.is_recording:
            return

        self.is_recording = True
        self.audio_queue.queue.clear()

        try:
            self.stream = sd.InputStream(
                callback=self._audio_callback,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                device=self.selected_device
            )
            self.stream.start()
            print("Recording started")

            # Call the on_recording_start callback
            if self.on_recording_start:
                self.on_recording_start()

        except Exception as e:
            print(f"Error starting recording: {e}")
            self.is_recording = False

    def stop_recording(self) -> Optional[np.ndarray]:
        """Stop recording and return the audio data"""
        if not self.is_recording:
            return None

        self.is_recording = False

        try:
            self.stream.stop()
            self.stream.close()

            # Combine all audio chunks
            audio_chunks = []
            while not self.audio_queue.empty():
                audio_chunks.append(self.audio_queue.get())

            if not audio_chunks:
                return None

            audio_data = np.concatenate(audio_chunks)
            print(f"Recording stopped. Audio length: {len(audio_data)/self.sample_rate:.2f}s")

            # Call the on_recording_stop callback
            if self.on_recording_stop:
                self.on_recording_stop()

            return audio_data

        except Exception as e:
            print(f"Error stopping recording: {e}")
            return None

    def _audio_callback(self, indata: np.ndarray, frames: int, 
                       time: any, status: sd.CallbackFlags) -> None:
        """Callback function for audio stream"""
        if status:
            print(f"Audio callback status: {status}")
        if self.is_recording:
            self.audio_queue.put(indata.copy())

def test_audio_capture():
    """Interactive test function for audio capture"""
    capture = AudioCapture()
    
    # List available input devices
    print("\nAvailable input devices:")
    input_devices = capture.list_input_devices()
    for device_id, name, channels in input_devices:
        print(f"{device_id}: {name} (inputs: {channels})")
    
    # Let user choose device
    while True:
        try:
            device_id = input("\nEnter device ID to use (or press Enter for default): ")
            if device_id == "":
                break
            device_id = int(device_id)
            if capture.set_device(device_id):
                break
        except ValueError:
            print("Please enter a valid number")
    
    print("\nStarting audio test...")
    print("Will record for 3 seconds...")
    
    capture.start_recording()
    time.sleep(3)
    audio_data = capture.stop_recording()
    
    if audio_data is not None:
        print(f"Successfully captured audio: {len(audio_data)} samples")
        print(f"Audio stats - Min: {audio_data.min():.2f}, Max: {audio_data.max():.2f}")
    else:
        print("Failed to capture audio")

if __name__ == "__main__":
    test_audio_capture()