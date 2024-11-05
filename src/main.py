import os
import sys
from src.ui.main_window import MainWindow
import customtkinter as ctk

def setup_environment():
    """Setup any required environment variables or configurations"""
    # Set theme and appearance
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

def main():
    try:
        # Setup environment
        setup_environment()
        
        # Create and start the main window
        app = MainWindow()
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        app.start()
        
    except Exception as e:
        print(f"Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()