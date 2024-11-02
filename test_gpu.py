import torch
import whisperx

def check_gpu():
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU Device: {torch.cuda.get_device_name(0)}")
        print(f"CUDA version: {torch.version.cuda}")

def test_whisperx():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = whisperx.load_model("base", device)
    print(f"WhisperX loaded on {device}")

if __name__ == "__main__":
    check_gpu()
    test_whisperx()