import os
from dotenv import load_dotenv

load_dotenv()

CONFIG = {
    'WEBSOCKET_SERVER': os.getenv('WEBSOCKET_SERVER', 'ws://localhost:3001'),
    'DISCORD_USER_ID': os.getenv('DISCORD_USER_ID'),
    'PUSH_TO_TALK_KEY': os.getenv('PUSH_TO_TALK_KEY', 'alt'),
    'SAMPLE_RATE': 16000,  # Required rate for WhisperX
    'CHUNK_SIZE': 1024,    # Audio buffer size
    'DEVICE': 'cuda' if os.getenv('USE_CPU', '0') == '0' else 'cpu',
    'DEBUG': os.getenv('DEBUG', 'False').lower() == 'true',
    'MODEL_SIZE': os.getenv('MODEL_SIZE', 'base')  # Add this line
}

if __name__ == "__main__":
    print("Current configuration:")
    for key, value in CONFIG.items():
        print(f"{key}: {value}")