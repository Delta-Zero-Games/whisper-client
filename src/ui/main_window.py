import customtkinter as ctk
import keyboard
from typing import Optional
import asyncio
import threading
from src.audio.capture import AudioCapture
from src.audio.processor import AudioProcessor
from src.input.hotkey import HotkeyManager
from src.network.websocket import WebSocketClient
import json
import os


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Initialize configuration
        self.config_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.json')
        self.names_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'user_names.json')
        
        self.config = self.load_config()
        self.user_names = self.load_user_names()

        # Setup window
        self.title("Whisper Client")
        self.geometry("600x750")

        # Set custom icon using .ico file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, 'dzp.ico')  # Ensure you have a .ico file
        self.iconbitmap(icon_path)

        # Get default fg_color for frames (darker background)
        self.default_fg_color = ctk.CTkFrame(master=None).cget("fg_color")

        # Set up WebSocket client
        self.ws_client = WebSocketClient()
        self.ws_client.set_message_handler(self.on_server_message)
        self.ws_client.set_status_handler(self.update_ws_status)

        # Initialize audio components
        self.capture = AudioCapture()
        self.processor = AudioProcessor()
        self.hotkey_manager = HotkeyManager(self.processor, self.capture)

        # Set initial hotkey
        self.hotkey_manager.push_to_talk_key = self.config.get('push_to_talk_key', 'alt')
        self.hotkey_manager.set_action_hotkeys({
            'tts': self.config.get('tts_hotkey'),
            'follows': self.config.get('follows_hotkey'),
            'subs': self.config.get('subs_hotkey'),
            'gifts': self.config.get('gifts_hotkey')
        })

        # Load devices
        self.available_devices = self.capture.list_input_devices()

        # Create main containers
        self.create_settings_frame()
        self.create_status_frame()
        self.create_transcript_frame()
        self.create_status_bar()

        self.update_device_menu()

        # Start async loop in separate thread
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._run_async_loop, daemon=True).start()

        # Setup callbacks
        self.hotkey_manager.set_transcription_callback(self.on_transcription)
        self.hotkey_manager.set_action_callback(self.on_action)

        # Assign callbacks for recording status updates
        self.capture.on_recording_start = self.on_recording_start
        self.capture.on_recording_stop = self.on_recording_stop

        # Assign callbacks for processing status updates
        self.processor.on_processing_start = self.on_processing_start
        self.processor.on_processing_end = self.on_processing_end

        # Set recording mode based on config
        recording_mode = self.config.get('recording_mode', 'push')
        if recording_mode == 'toggle':
            self.recording_mode_switch.select()
            self.hotkey_manager.set_mode('toggle')
        else:
            self.recording_mode_switch.deselect()
            self.hotkey_manager.set_mode('push')

    def create_status_bar(self):
        """Create the status bar section"""
        status_bar = ctk.CTkFrame(self, fg_color=self.default_fg_color)
        status_bar.pack(fill="x", side="bottom", padx=10, pady=5)

        # Configure grid columns for even spacing
        for i in range(4):
            status_bar.grid_columnconfigure(i, weight=1)

        # Create labels for each metric with exact names
        metrics = [
            ('TTS Queue:', 'tts_in_queue'),
            ('New Followers:', 'new_followers_count'),
            ('New Subscribers:', 'new_subs_count'),
            ('New Givers:', 'new_giver_count')
        ]

        self.metric_labels = {}

        for i, (label_text, key) in enumerate(metrics):
            frame = ctk.CTkFrame(status_bar, fg_color="transparent")
            frame.grid(row=0, column=i, padx=5, sticky="ew")

            ctk.CTkLabel(frame, text=label_text).pack(side="left", padx=2)
            count_label = ctk.CTkLabel(frame, text="0")
            count_label.pack(side="left", padx=2)

            self.metric_labels[key] = count_label

    def update_metrics(self, metrics: dict):
        """Update the metrics display"""
        # If no metrics provided, set all to 0 (disconnected state)
        if not metrics:
            metrics = {
                'tts_in_queue': 0,
                'new_followers_count': 0,
                'new_subs_count': 0,
                'new_giver_count': 0
            }

        # Update each metric, defaulting to 0 if not provided
        for key in self.metric_labels:
            value = metrics.get(key, 0)
            self.metric_labels[key].configure(text=str(value))

    def update_ws_status(self, connected: bool):
        """Update the WebSocket status indicator in the UI."""
        color = "green" if connected else "red"
        self.after(0, self.update_status_indicator, self.ws_status, color)

    async def toggle_websocket(self):
        """Toggle WebSocket connection."""
        if self.ws_toggle.get():
            # Enable WebSocket
            self.ip_entry.configure(state="normal")
            self.port_entry.configure(state="normal")
            asyncio.run_coroutine_threadsafe(self.ws_client.connect(), self.loop)
        else:
            # Disable WebSocket
            asyncio.run_coroutine_threadsafe(self.ws_client.disconnect(), self.loop)
            self.ip_entry.configure(state="disabled")
            self.port_entry.configure(state="disabled")
            # Update the status indicator and reset metrics in a thread-safe manner
            self.loop.call_soon_threadsafe(self.update_ws_status, False)
            self.update_metrics({})  # Reset all metrics to 0

    def toggle_recording_mode(self):
        """Toggle between push-to-talk and toggle-to-talk modes"""
        if self.recording_mode_switch.get():
            self.hotkey_manager.set_mode('toggle')
            print("Switched to Toggle-to-Talk mode")
        else:
            self.hotkey_manager.set_mode('push')
            print("Switched to Push-to-Talk mode")

    def load_user_names(self) -> list:
        """Load user names from file"""
        try:
            if os.path.exists(self.names_file):
                with open(self.names_file, 'r') as f:
                    data = json.load(f)
                    return data.get('names', ['Default'])
            else:
                # Create default names file if it doesn't exist
                default_names = {'names': ['Default']}
                with open(self.names_file, 'w') as f:
                    json.dump(default_names, f, indent=4)
                return default_names['names']
        except Exception as e:
            print(f"Error loading user names: {e}")
            return ['Default']

    def create_settings_frame(self):
        """Create the settings section"""
        settings_frame = ctk.CTkFrame(self, fg_color=self.default_fg_color)
        settings_frame.pack(fill="x", padx=10, pady=5)

        # Microphone selection
        ctk.CTkLabel(settings_frame, text="Microphone:").pack(anchor="w", padx=5)
        self.device_menu = ctk.CTkOptionMenu(settings_frame, values=["Loading..."])
        self.device_menu.pack(fill="x", padx=5, pady=2)

        # User selection (replacing name entry with dropdown)
        ctk.CTkLabel(settings_frame, text="User:").pack(anchor="w", padx=5)
        self.user_menu = ctk.CTkOptionMenu(
            settings_frame,
            values=self.user_names
        )
        self.user_menu.pack(fill="x", padx=5, pady=2)

        # Set initial user selection if saved in config
        saved_name = self.config.get('preferred_name')
        if saved_name in self.user_names:
            self.user_menu.set(saved_name)
        else:
            self.user_menu.set(self.user_names[0])

        # WebSocket settings
        ws_frame = ctk.CTkFrame(settings_frame, fg_color=self.default_fg_color)
        ws_frame.pack(fill="x", padx=5, pady=2)

        ws_header_frame = ctk.CTkFrame(ws_frame, fg_color="transparent")
        ws_header_frame.pack(fill="x")

        ctk.CTkLabel(ws_header_frame, text="WebSocket:").pack(side="left")

        # Add WebSocket toggle button
        self.ws_toggle = ctk.CTkSwitch(
            ws_header_frame,
            text="Enable",
            command=self.toggle_websocket,
            onvalue=True,
            offvalue=False
        )
        self.ws_toggle.pack(side="right", padx=5)

        ip_frame = ctk.CTkFrame(ws_frame, fg_color="transparent")
        ip_frame.pack(fill="x")

        self.ip_entry = ctk.CTkEntry(ip_frame, placeholder_text="IP Address")
        self.ip_entry.pack(side="left", expand=True, fill="x", padx=2)
        self.ip_entry.insert(0, self.config.get('ws_ip', 'localhost'))

        self.port_entry = ctk.CTkEntry(ip_frame, placeholder_text="Port", width=100)
        self.port_entry.pack(side="right", padx=2)
        self.port_entry.insert(0, self.config.get('ws_port', '3001'))

        # Twitch Action Hotkeys
        ctk.CTkLabel(settings_frame, text="Twitch Action Hotkeys:").pack(anchor="w", padx=5)

        # Button row
        hotkey_buttons_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        hotkey_buttons_frame.pack(fill="x", padx=2, pady=2)

        # Entry row
        hotkey_entries_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        hotkey_entries_frame.pack(fill="x", padx=2, pady=2)

        # Configure grid columns for even spacing
        for i in range(4):
            hotkey_buttons_frame.grid_columnconfigure(i, weight=1)
            hotkey_entries_frame.grid_columnconfigure(i, weight=1)

        # Create hotkey entries and buttons
        self.action_hotkeys = {}
        for i, action in enumerate(['TTS', 'Follows', 'Subs', 'Gifts']):
            # Button
            btn = ctk.CTkButton(
                hotkey_buttons_frame,
                text=f"Set {action} Key",
                command=lambda a=action: self.set_action_hotkey(a)
            )
            btn.grid(row=0, column=i, padx=2)
            
            # Entry
            entry = ctk.CTkEntry(hotkey_entries_frame)
            entry.grid(row=0, column=i, padx=2, sticky="ew")
            entry.insert(0, self.config.get(f'{action.lower()}_hotkey', ''))
            entry.configure(state="disabled")
            
            self.action_hotkeys[action] = {
                'button': btn,
                'entry': entry,
                'key': self.config.get(f'{action.lower()}_hotkey', '')
            }

        # Push to talk key
        ctk.CTkLabel(settings_frame, text="Push to Talk Key:").pack(anchor="w", padx=5)
        self.hotkey_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        self.hotkey_frame.pack(side="left", padx=2)
    
        # Configure grid columns
        self.hotkey_frame.columnconfigure(0, weight=0)
        self.hotkey_frame.columnconfigure(1, weight=0)
        self.hotkey_frame.columnconfigure(2, weight=0)
        self.hotkey_frame.columnconfigure(3, weight=0)

        # Hotkey Entry
        self.hotkey_entry = ctk.CTkEntry(self.hotkey_frame, width=100)
        self.hotkey_entry.grid(row=0, column=0, padx=2)
        self.hotkey_entry.insert(0, self.config.get('push_to_talk_key', 'alt'))
        self.hotkey_entry.configure(state="disabled")

        # Set Key Button
        self.hotkey_button = ctk.CTkButton(
            self.hotkey_frame, text="Set Key", command=self.set_hotkey, width=100)
        self.hotkey_button.grid(row=0, column=1, padx=2)

        # Recording Mode Label
        ctk.CTkLabel(self.hotkey_frame, text="Push Mode ").grid(row=0, column=2, padx=2)

        # Recording Mode Switch
        self.recording_mode_switch = ctk.CTkSwitch(
            self.hotkey_frame,
            text="Toggle Mode",
            command=self.toggle_recording_mode,
            onvalue=True,
            offvalue=False
        )
        self.recording_mode_switch.grid(row=0, column=3, padx=2)
        self.recording_mode_switch.deselect()  # Default to push-to-talk

        # Define controls_frame to hold the save button
        controls_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        controls_frame.pack(fill="x", padx=2, pady=2)

        # Save Settings Button (inside controls_frame)
        self.save_button = ctk.CTkButton(
            controls_frame, text="Save Settings", command=self.save_settings)
        self.save_button.pack(side="right", anchor="w", padx=2)

        # Set initial WebSocket state after creating all elements
        if not self.config.get('ws_enabled', True):
            self.ws_toggle.deselect()
            self.ip_entry.configure(state="disabled")
            self.port_entry.configure(state="disabled")
        else:
            self.ws_toggle.select()

    def create_status_frame(self):
        """Create the status section"""
        status_frame = ctk.CTkFrame(self, fg_color=self.default_fg_color)
        status_frame.pack(fill="x", padx=10, pady=5)

        # Status indicators
        indicators_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
        indicators_frame.pack(fill="x", padx=5, pady=5)

        # WebSocket status
        ws_status_frame = ctk.CTkFrame(indicators_frame, fg_color="transparent")
        ws_status_frame.pack(side="left", padx=5)
        ctk.CTkLabel(ws_status_frame, text="WebSocket:").pack(side="left", padx=5)
        self.ws_status = ctk.CTkLabel(ws_status_frame, text="⬤", text_color="red")
        self.ws_status.pack(side="left")

        # Recording status
        rec_status_frame = ctk.CTkFrame(indicators_frame, fg_color="transparent")
        rec_status_frame.pack(side="left", padx=5)
        ctk.CTkLabel(rec_status_frame, text="Recording:").pack(side="left", padx=5)
        self.rec_status = ctk.CTkLabel(rec_status_frame, text="⬤", text_color="red")
        self.rec_status.pack(side="left")

        # Processing status
        proc_status_frame = ctk.CTkFrame(indicators_frame, fg_color="transparent")
        proc_status_frame.pack(side="left", padx=5)
        ctk.CTkLabel(proc_status_frame, text="Processing:").pack(side="left", padx=5)
        self.proc_status = ctk.CTkLabel(proc_status_frame, text="⬤", text_color="red")
        self.proc_status.pack(side="left")

        # Bot status
        bot_status_frame = ctk.CTkFrame(indicators_frame, fg_color="transparent")
        bot_status_frame.pack(fill="x", expand=True, side="left", padx=2)  # Changed to fill and expand
        
        # Status indicators on the left
        status_container = ctk.CTkFrame(bot_status_frame, fg_color="transparent")
        status_container.pack(side="left")
        
        ctk.CTkLabel(status_container, text="Bot:").pack(side="left", padx=5)
        self.bot_status = ctk.CTkLabel(status_container, text="⬤", text_color="red")
        self.bot_status.pack(side="left")

        # Bot control button on the right
        self.bot_button = ctk.CTkButton(
            bot_status_frame,
            text="Connect Bot",
            command=self.toggle_bot,
            fg_color="green",
            width=100
        )
        self.bot_button.pack(side="right", padx=0)

    def create_transcript_frame(self):
        """Create the transcript section"""
        transcript_frame = ctk.CTkFrame(self)  # Use default background color
        transcript_frame.pack(fill="both", expand=True, padx=10, pady=5)

        ctk.CTkLabel(transcript_frame, text="Transcription Results:").pack(
            anchor="w", padx=5)

        self.transcript_text = ctk.CTkTextbox(transcript_frame, wrap="word")
        self.transcript_text.pack(fill="both", expand=True, padx=5, pady=5)

    def load_config(self) -> dict:
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
        return {}

    def update_device_menu(self):
        """Update the device selection menu"""
        self.device_map = {f"{device[1]}": device[0] for device in self.available_devices}
        device_names = list(self.device_map.keys())
        self.device_menu.configure(values=device_names)

        # Set to saved device if available
        saved_device = self.config.get('audio_device')
        if saved_device in device_names:
            self.device_menu.set(saved_device)
            # Set the device in audio capture
            self.capture.set_device(self.device_map[saved_device])

    def save_settings(self):
        """Save settings to config file"""
        config = {
            'preferred_name': self.user_menu.get(),
            'ws_ip': self.ip_entry.get(),
            'ws_port': self.port_entry.get(),
            'push_to_talk_key': self.hotkey_entry.get(),
            'audio_device': self.device_menu.get(),
            'ws_enabled': self.ws_toggle.get()
        }
        
        # Add action hotkeys to config
        for action, data in self.action_hotkeys.items():
            config[f'{action.lower()}_hotkey'] = data['entry'].get()
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
                
            # Update device
            if config['audio_device'] in self.device_map:
                device_id = self.device_map[config['audio_device']]
                self.capture.set_device(device_id)
                
            # Update hotkeys
            self.hotkey_manager.set_hotkey(config['push_to_talk_key'])
            self.hotkey_manager.set_action_hotkeys({
                'tts': config.get('tts_hotkey'),
                'follows': config.get('follows_hotkey'),
                'subs': config.get('subs_hotkey'),
                'gifts': config.get('gifts_hotkey')
            })
            
            # Update WebSocket
            if config['ws_enabled']:
                self.restart_websocket()
            else:
                asyncio.run_coroutine_threadsafe(self.ws_client.disconnect(), self.loop)
                
        except Exception as e:
            print(f"Error saving config: {e}")

    def set_action_hotkey(self, action):
        """Set hotkey for specific action"""
        self.action_hotkeys[action]['button'].configure(text=f"Press any key...")
        self.action_hotkeys[action]['entry'].configure(state="normal")
        self.action_hotkeys[action]['entry'].delete(0, 'end')
        
        def on_key(event):
            if event.name != 'escape':
                self.action_hotkeys[action]['entry'].delete(0, 'end')
                self.action_hotkeys[action]['entry'].insert(0, event.name)
                self.action_hotkeys[action]['entry'].configure(state="disabled")
                self.action_hotkeys[action]['button'].configure(text=f"Set {action} Key")
                self.action_hotkeys[action]['key'] = event.name
                keyboard.unhook(on_key)
        
        keyboard.hook(on_key)

    def set_hotkey(self):
        """Set push to talk key"""
        self.hotkey_button.configure(text="Press any key...")
        self.hotkey_entry.configure(state="normal")  # Enable editing
        self.hotkey_entry.delete(0, 'end')

        def on_key(event):
            if event.name != 'escape':
                self.hotkey_entry.delete(0, 'end')
                self.hotkey_entry.insert(0, event.name)
                self.hotkey_entry.configure(state="disabled")  # Disable editing again
                self.hotkey_button.configure(text="Set Key")
                keyboard.unhook(on_key)

        keyboard.hook(on_key)

    def _run_async_loop(self):
        """Run the async event loop in a separate thread"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def restart_websocket(self):
        """Restart WebSocket connection with new settings"""
        async def restart():
            if self.ws_client:
                await self.ws_client.disconnect()

            # Update WebSocket URI
            ws_uri = f"ws://{self.ip_entry.get()}:{self.port_entry.get()}"
            self.ws_client.uri = ws_uri

            # Reconnect
            await self.ws_client.connect()

        asyncio.run_coroutine_threadsafe(restart(), self.loop)

    async def on_transcription(self, result):
        """Handle transcription results"""
        try:
            # Update transcript text box
            self.transcript_text.insert('end', f"\n[{self.user_menu.get()}]: {result['text']}\n")
            self.transcript_text.see('end')

            # Only send to WebSocket if enabled
            if self.ws_toggle.get() and self.ws_client.connected:
                preferred_name = self.user_menu.get()
                await self.ws_client.send_transcript(result, preferred_name)
        except Exception as e:
            print(f"Error handling transcription: {e}")

    def toggle_bot(self):
        """Toggle bot connection state"""
        try:
            if self.bot_button.cget("text") == "Connect Bot":
                # Request bot to join
                asyncio.run_coroutine_threadsafe(
                    self.ws_client.send_message({
                        'type': 'bot_control',
                        'action': 'connect'
                    }),
                    self.loop
                )
            else:
                # Request bot to disconnect
                asyncio.run_coroutine_threadsafe(
                    self.ws_client.send_message({
                        'type': 'bot_control',
                        'action': 'disconnect'
                    }),
                    self.loop
                )
        except Exception as e:
            print(f"Error toggling bot: {e}")

    def update_bot_status(self, is_connected: bool):
        """Update bot status in UI"""
        # Update status indicator
        color = "green" if is_connected else "red"
        self.bot_status.configure(text_color=color)
        
        # Update button
        if is_connected:
            self.bot_button.configure(
                text="Disconnect Bot",
                fg_color="red"
            )
        else:
            self.bot_button.configure(
                text="Connect Bot",
                fg_color="green"
            )

    async def on_server_message(self, message):
        """Handle messages from the server"""
        try:
            message_type = message.get('type')
            
            if message_type == 'metrics_update':
                # Update metrics display
                self.update_metrics(message.get('metrics', {}))
            elif message_type == 'bot_status':
                # Update bot status
                self.loop.call_soon_threadsafe(
                    self.update_bot_status,
                    message.get('connected', False)
                )
            else:
                # Regular message for transcript
                self.transcript_text.insert('end', f"\n[Server]: {message}\n")
                self.transcript_text.see('end')
        except Exception as e:
            print(f"Error handling server message: {e}")

    async def on_action(self, action):
        """Handle action hotkey press"""
        action_names = {
            'tts': 'TTS Queue',
            'follows': 'New Followers',
            'subs': 'New Subscribers',
            'gifts': 'New Givers'
        }
        
        self.transcript_text.insert('end', f"\n[System] Requesting {action_names[action['type']]}...\n")
        self.transcript_text.see('end')
        
        if self.ws_toggle.get():
            await self.ws_client.send_action(action)

    # Callback methods for recording status
    def on_recording_start(self):
        print("Recording started (UI update)")
        self.update_status_indicator(self.rec_status, "green")

    def on_recording_stop(self):
        print("Recording stopped (UI update)")
        self.update_status_indicator(self.rec_status, "red")

    # Callback methods for processing status
    def on_processing_start(self):
        print("Processing started (UI update)")
        self.update_status_indicator(self.proc_status, "green")

    def on_processing_end(self):
        print("Processing ended (UI update)")
        self.update_status_indicator(self.proc_status, "red")

    def update_status_indicator(self, indicator_label, color):
        """Thread-safe UI update"""
        self.after(0, lambda: indicator_label.configure(text_color=color))

    def start(self):
        """Start the application"""
        # Start WebSocket connection if enabled
        if self.ws_toggle.get():
            asyncio.run_coroutine_threadsafe(self.ws_client.connect(), self.loop)

        # Start hotkey manager
        self.hotkey_manager.start(self.loop)

        # Start UI
        self.mainloop()

    def on_closing(self):
        """Clean up on window close"""
        self.hotkey_manager.stop()
        asyncio.run_coroutine_threadsafe(self.ws_client.disconnect(), self.loop)
        self.loop.stop()
        self.quit()


def main():
    app = MainWindow()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.start()


if __name__ == "__main__":
    main()