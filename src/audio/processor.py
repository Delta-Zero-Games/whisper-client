import warnings
import whisperx
import torch
import numpy as np
from typing import Optional, Dict, Callable
import shutil
from pathlib import Path
from src.config.settings import CONFIG

# Suppress deprecation warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)


class AudioProcessor:
    def __init__(self):
        self.device = CONFIG.get('DEVICE', 'cpu')
        self.compute_type = "float32"  # Using float32 for better compatibility
        self.on_processing_start: Optional[Callable] = None  # Callback for processing start
        self.on_processing_end: Optional[Callable] = None    # Callback for processing end
        self._clean_cache()  # Clean cache before loading
        self._load_model()

    def _clean_cache(self) -> None:
        """Clean WhisperX cache and redownload models"""
        try:
            cache_dir = Path.home() / '.cache' / 'torch' / 'whisperx-vad-segmentation.bin'
            if cache_dir.exists():
                print("Cleaning existing WhisperX cache...")
                cache_dir.unlink()

            huggingface_cache = Path.home() / '.cache' / 'huggingface'
            if huggingface_cache.exists():
                print("Cleaning Hugging Face cache...")
                shutil.rmtree(huggingface_cache, ignore_errors=True)

            print("Cache cleaned successfully")
        except Exception as e:
            print(f"Error cleaning cache: {e}")

    def _load_model(self) -> None:
        """Load WhisperX model"""
        try:
            print("Loading WhisperX model...")
            # First load whisper model
            self.model = whisperx.load_model(
                CONFIG.get('MODEL_SIZE', 'base'),
                self.device,
                compute_type=self.compute_type
            )
            print(f"WhisperX model loaded on {self.device}")

            # Load alignment model separately
            print("Loading alignment model...")
            self.alignment_model, self.metadata = whisperx.load_align_model(
                language_code="en",
                device=self.device
            )
            print("Alignment model loaded")

        except Exception as e:
            print(f"Error loading WhisperX model: {e}")
            raise

    async def process_audio(self, audio_data: np.ndarray) -> Optional[Dict]:
        """
        Process audio data and return transcription.
        Returns None if processing fails.
        """
        if audio_data is None or len(audio_data) == 0:
            print("No audio data to process")
            return None

        if self.on_processing_start:
            self.on_processing_start()  # Notify that processing has started

        try:
            # Ensure audio data is in the correct format
            audio_data = audio_data.squeeze()
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)

            # Initial transcription
            print("Starting transcription...")
            result = self.model.transcribe(audio_data)

            # Check if transcription was successful
            if result and 'segments' in result and len(result['segments']) > 0:
                print("Transcription completed, starting alignment...")
                # Align the transcription
                result = whisperx.align(
                    result["segments"],
                    self.alignment_model,
                    self.metadata,
                    audio_data,
                    self.device,
                    return_char_alignments=False
                )

                # Get the text from all segments
                text = ' '.join(segment['text'] for segment in result['segments'])
                print("Alignment completed")
                return {
                    'text': text.strip(),
                    'language': result.get('language', 'en'),
                    'segments': result['segments']
                }
            else:
                print("No speech detected in the audio")
                return None

        except Exception as e:
            print(f"Error processing audio: {e}")
            return None

        finally:
            if self.on_processing_end:
                self.on_processing_end()  # Notify that processing has ended

    def cleanup(self) -> None:
        """Cleanup resources"""
        try:
            del self.model
            del self.alignment_model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("Processor cleanup completed")
        except Exception as e:
            print(f"Error during cleanup: {e}")

    # Additional methods or improvements can be added here


def test_processor():
    """Test the audio processor with the audio capture"""
    from src.audio.capture import AudioCapture
    import asyncio
    import time

    async def run_test():
        try:
            processor = AudioProcessor()
            capture = AudioCapture()

            # Assign processing callbacks for testing purposes
            processor.on_processing_start = lambda: print("Processing started (Test)")
            processor.on_processing_end = lambda: print("Processing ended (Test)")

            # Let user choose device if not already set
            print("\nStarting audio capture test...")
            print("Say something when recording starts...")
            print("Recording will start in 3 seconds...")

            await asyncio.sleep(3)  # Give time to prepare

            capture.start_recording()
            print("Recording...")
            await asyncio.sleep(3)  # Record for 3 seconds
            audio_data = capture.stop_recording()

            if audio_data is not None:
                print("\nProcessing audio...")
                result = await processor.process_audio(audio_data)
                if result:
                    print("\nTranscription result:")
                    print(f"Text: {result['text']}")
                    print(f"Language: {result['language']}")
                    print("\nSegments:")
                    for segment in result['segments']:
                        print(f"[{segment['start']:.1f}s -> {segment['end']:.1f}s] {segment['text']}")
                else:
                    print("No transcription result")
            else:
                print("No audio data captured")

            processor.cleanup()

        except Exception as e:
            print(f"Error during test: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(run_test())


if __name__ == "__main__":
    test_processor()