import os
import sys
import json
import time
import threading
import datetime
import subprocess
import webbrowser
import platform
import re
import random
import logging
from PIL import Image, ImageTk
import customtkinter as ctk
import pyttsx3
import speech_recognition as sr
import psutil
import pyautogui
import pystray
import numpy as np
import cv2
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER, windll
from comtypes import CLSCTX_ALL
from fuzzywuzzy import fuzz, process
import wikipedia
import pywhatkit
# icon
# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("Dexa.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DexaAI")

# Set appearance mode and default color theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
class VoiceWaveform(ctk.CTkCanvas):
    """Custom canvas widget for voice waveform visualization"""
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.bars = 20
        self.bar_width = 2
        self.bar_gap = 2
        self.bar_max_height = 20
        self.is_animating = False
        self.animation_thread = None
        
    def start_animation(self):
        """Start the waveform animation"""
        if self.is_animating:
            return
            
        self.is_animating = True
        
        def animate():
            while self.is_animating:
                self.delete("all")
                for i in range(self.bars):
                    # Generate random height for each bar
                    height = random.random() * self.bar_max_height + 5
                    
                    # Calculate x position
                    x = i * (self.bar_width + self.bar_gap)
                    
                    # Draw bar with gradient (approximated in tkinter)
                    self.create_rectangle(
                        x, self.winfo_height() - height, 
                        x + self.bar_width, self.winfo_height(),
                        fill="#06b6d4", outline=""
                    )
                
                time.sleep(0.05)
                self.update()
        
        self.animation_thread = threading.Thread(target=animate)
        self.animation_thread.daemon = True
        self.animation_thread.start()

    def stop_animation(self):
        """Stop the waveform animation"""
        self.is_animating = False
        if self.animation_thread:
            self.animation_thread.join(timeout=1)
        self.delete("all")

class PopupAssistant(ctk.CTkToplevel):
    """Popup window for the assistant when activated"""
    def __init__(self, master, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        
        # Configure window
        self.title("Dexa Assistant")
        self.geometry("300x150")
        self.attributes("-topmost", True)
        self.overrideredirect(True)  # Remove window decorations
        
        # Position in bottom right
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = screen_width - 320
        y = screen_height - 200
        self.geometry(f"+{x}+{y}")
        
        # Make semi-transparent with rounded corners
        self.attributes("-alpha", 0.95)
        
        # Create frame with rounded corners
        self.frame = ctk.CTkFrame(self, corner_radius=15)
        self.frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Header with Dexa logo and status
        self.header_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=10, pady=10)
        
        # Dexa logo (circle with gradient)
        self.logo_frame = ctk.CTkFrame(self.header_frame, width=40, height=40, corner_radius=20, fg_color="#06b6d4")
        self.logo_frame.pack(side="left", padx=(0, 10))
        self.logo_frame.pack_propagate(False)
        
        # Status indicator (inner circle)
        self.status_indicator = ctk.CTkLabel(self.logo_frame, text="", fg_color="#22c55e", width=20, height=20, corner_radius=10)
        self.status_indicator.place(relx=0.5, rely=0.5, anchor="center")
        
        # Title and status
        self.title_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.title_frame.pack(side="left", fill="both", expand=True)
        
        self.title_label = ctk.CTkLabel(self.title_frame, text="Dexa", font=("Helvetica", 18, "bold"), text_color="#06b6d4")
        self.title_label.pack(anchor="w")
        
        self.status_label = ctk.CTkLabel(self.title_frame, text="Listening...", font=("Helvetica", 12), text_color="#9ca3af")
        self.status_label.pack(anchor="w")
        
        # Waveform visualization
        self.waveform = VoiceWaveform(self.frame, height=30, width=280, bg="#1a1a2e")
        self.waveform.pack(pady=10)
        
        # Response text
        self.response_label = ctk.CTkLabel(self.frame, text="", font=("Helvetica", 12), text_color="#e5e7eb", wraplength=260)
        self.response_label.pack(pady=5, fill="x")
        
        # Start hidden
        self.withdraw()
        
    def show_listening(self):
        """Show the popup in listening state"""
        self.status_label.configure(text="Listening...")
        self.status_indicator.configure(fg_color="#22c55e")  # Green
        self.waveform.start_animation()
        self.response_label.configure(text="")
        self.deiconify()
        self.lift()
        
    def show_processing(self):
        """Show the popup in processing state"""
        self.status_label.configure(text="Processing...")
        self.status_indicator.configure(fg_color="#eab308")  # Yellow
        self.waveform.stop_animation()
        
    def show_responding(self, text):
        """Show the popup in responding state with text"""
        self.status_label.configure(text="Responding...")
        self.status_indicator.configure(fg_color="#3b82f6")  # Blue
        self.response_label.configure(text=text)
        
    def hide(self):
        """Hide the popup"""
        self.waveform.stop_animation()
        self.withdraw()

class CommandCard(ctk.CTkFrame):
    """Card widget for displaying voice commands"""
    def __init__(self, master, phrase, action, icon_path=None, edit_callback=None, delete_callback=None, **kwargs):
        super().__init__(master, corner_radius=10, fg_color="#1a1a2e", border_width=1, border_color="#2a2a3a", **kwargs)
        
        # Content frame
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Icon (placeholder circle if no icon)
        icon_frame = ctk.CTkFrame(content, width=40, height=40, corner_radius=20, fg_color="#252542")
        icon_frame.pack(side="left", padx=(0, 10))
        icon_frame.pack_propagate(False)
        
        # If we had an icon system, we'd use it here
        icon_label = ctk.CTkLabel(icon_frame, text="", font=("Helvetica", 16), text_color="#06b6d4")
        icon_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Command text
        text_frame = ctk.CTkFrame(content, fg_color="transparent")
        text_frame.pack(side="left", fill="both", expand=True)
        
        phrase_label = ctk.CTkLabel(text_frame, text=f'"{phrase}"', font=("Helvetica", 12, "bold"), text_color="#ffffff")
        phrase_label.pack(anchor="w")
        
        action_label = ctk.CTkLabel(text_frame, text=action, font=("Helvetica", 10), text_color="#9ca3af")
        action_label.pack(anchor="w")
        
        # Buttons
        buttons_frame = ctk.CTkFrame(content, fg_color="transparent")
        buttons_frame.pack(side="right")
        
        edit_button = ctk.CTkButton(
            buttons_frame, 
            text="Edit", 
            width=60, 
            height=25, 
            corner_radius=8,
            fg_color="#252542", 
            hover_color="#2a2a4a",
            command=lambda: edit_callback(phrase) if edit_callback else None
        )
        edit_button.pack(side="left", padx=2)
        
        delete_button = ctk.CTkButton(
            buttons_frame, 
            text="Delete", 
            width=60, 
            height=25, 
            corner_radius=8,
            fg_color="#252542", 
            hover_color="#2a2a4a",
            command=lambda: delete_callback(phrase) if delete_callback else None
        )
        delete_button.pack(side="left", padx=2)

class TaskReminderPopup(ctk.CTkToplevel):
    """Popup window for task reminders"""
    def __init__(self, master, task_description, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        
        # Configure window
        self.title("Dexa Reminder")
        self.geometry("300x150")
        self.attributes("-topmost", True)
        
        # Position in center
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - 300) // 2
        y = (screen_height - 150) // 2
        self.geometry(f"+{x}+{y}")
        
        # Create frame with rounded corners
        self.frame = ctk.CTkFrame(self, corner_radius=15)
        self.frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Reminder icon
        icon_frame = ctk.CTkFrame(self.frame, width=50, height=50, corner_radius=25, fg_color="#06b6d4")
        icon_frame.pack(pady=(15, 5))
        icon_frame.pack_propagate(False)
        
        icon_label = ctk.CTkLabel(icon_frame, text="⏰", font=("Helvetica", 20), text_color="#ffffff")
        icon_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Reminder text
        reminder_label = ctk.CTkLabel(
            self.frame, 
            text="Reminder", 
            font=("Helvetica", 16, "bold"), 
            text_color="#ffffff"
        )
        reminder_label.pack(pady=(5, 0))
        
        task_label = ctk.CTkLabel(
            self.frame, 
            text=task_description, 
            font=("Helvetica", 12), 
            text_color="#e5e7eb",
            wraplength=260
        )
        task_label.pack(pady=5)
        
        # Dismiss button
        dismiss_button = ctk.CTkButton(
            self.frame, 
            text="Dismiss", 
            width=100, 
            height=30, 
            corner_radius=8,
            fg_color="#252542", 
            hover_color="#2a2a4a",
            command=self.destroy
        )
        dismiss_button.pack(pady=10)

class ResourceMonitorPopup(ctk.CTkToplevel):
    """Popup window for resource monitoring"""
    def __init__(self, master, duration=60, threshold=90, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        
        # Configure window
        self.title("Dexa Resource Monitor")
        self.geometry("400x300")
        self.attributes("-topmost", True)
        
        # Position in center
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - 400) // 2
        y = (screen_height - 300) // 2
        self.geometry(f"+{x}+{y}")
        
        # Create frame with rounded corners
        self.frame = ctk.CTkFrame(self, corner_radius=15)
        self.frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Header
        header_label = ctk.CTkLabel(
            self.frame, 
            text="System Resource Monitor", 
            font=("Helvetica", 18, "bold"), 
            text_color="#ffffff"
        )
        header_label.pack(pady=(15, 5))
        
        desc_label = ctk.CTkLabel(
            self.frame, 
            text=f"Monitoring for {duration} seconds with {threshold}% threshold", 
            font=("Helvetica", 12), 
            text_color="#9ca3af"
        )
        desc_label.pack(pady=(0, 15))
        
        # Resource frames
        self.cpu_frame = self._create_resource_frame("CPU Usage", "#3b82f6")
        self.cpu_frame.pack(fill="x", padx=15, pady=5)
        
        self.memory_frame = self._create_resource_frame("Memory Usage", "#06b6d4")
        self.memory_frame.pack(fill="x", padx=15, pady=5)
        
        self.disk_frame = self._create_resource_frame("Disk Usage", "#8b5cf6")
        self.disk_frame.pack(fill="x", padx=15, pady=5)
        
        # Status label
        self.status_label = ctk.CTkLabel(
            self.frame, 
            text="Monitoring...", 
            font=("Helvetica", 12), 
            text_color="#9ca3af"
        )
        self.status_label.pack(pady=10)
        
        # Start monitoring
        self.threshold = threshold
        self.duration = duration
        self.start_time = time.time()
        self.end_time = self.start_time + duration
        self.alert_sent = False
        
        # Start monitoring thread
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_resources)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        # Bind close event
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_resource_frame(self, title, color):
        """Create a resource monitoring frame"""
        frame = ctk.CTkFrame(self.frame, fg_color="#252542", corner_radius=8)
        
        title_label = ctk.CTkLabel(
            frame, 
            text=title, 
            font=("Helvetica", 12, "bold"), 
            text_color="#ffffff"
        )
        title_label.pack(side="left", padx=10)
        
        value_label = ctk.CTkLabel(
            frame, 
            text="0%", 
            font=("Helvetica", 12, "bold"), 
            text_color=color
        )
        value_label.pack(side="right", padx=10)
        
        # Store the value label for updating
        frame.value_label = value_label
        
        return frame
    
    def _monitor_resources(self):
        """Monitor system resources"""
        while self.monitoring and time.time() < self.end_time:
            try:
                # Get resource usage
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                disk = psutil.disk_usage('/')
                disk_percent = disk.percent
                
                # Update UI
                self._update_resource(self.cpu_frame, cpu_percent)
                self._update_resource(self.memory_frame, memory_percent)
                self._update_resource(self.disk_frame, disk_percent)
                
                # Check for alerts
                if not self.alert_sent:
                    if cpu_percent > self.threshold:
                        self._send_alert(f"CPU usage is at {cpu_percent}%, which exceeds the threshold of {self.threshold}%")
                    elif memory_percent > self.threshold:
                        self._send_alert(f"Memory usage is at {memory_percent}%, which exceeds the threshold of {self.threshold}%")
                    elif disk_percent > self.threshold:
                        self._send_alert(f"Disk usage is at {disk_percent}%, which exceeds the threshold of {self.threshold}%")
                
                # Update remaining time
                remaining = int(self.end_time - time.time())
                if remaining >= 0:
                    self.status_label.configure(text=f"Monitoring... {remaining}s remaining")
                
                # Sleep for a bit
                time.sleep(2)
            except Exception as e:
                print(f"Error in resource monitoring: {e}")
        
        # Monitoring complete
        if self.monitoring:
            self.status_label.configure(text="Monitoring complete")
    
    def _update_resource(self, frame, value):
        """Update a resource value"""
        if not self.monitoring:
            return
            
        # Determine color based on value
        color = "#22c55e"  # Green
        if value > self.threshold:
            color = "#ef4444"  # Red
        elif value > self.threshold * 0.8:
            color = "#eab308"  # Yellow
            
        # Update label
        frame.value_label.configure(text=f"{value:.1f}%", text_color=color)
    
    def _send_alert(self, message):
        """Send a resource alert"""
        self.alert_sent = True
        self.status_label.configure(text="Alert: Resource threshold exceeded!", text_color="#ef4444")
        
        # Create a flash effect
        def flash():
            for _ in range(3):
                self.frame.configure(fg_color="#450a0a")
                time.sleep(0.2)
                self.frame.configure(fg_color="#1a1a2e")
                time.sleep(0.2)
        
        threading.Thread(target=flash, daemon=True).start()
    
    def _on_close(self):
        """Handle window close event"""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1)
        self.destroy()

class NotesManager:
    """Class to manage notes functionality"""
    def __init__(self, notes_dir=None):
        if notes_dir is None:
            self.notes_dir = os.path.join(os.environ['USERPROFILE'], 'Documents', 'Dexa Notes')
        else:
            self.notes_dir = notes_dir
            
        # Create notes directory if it doesn't exist
        os.makedirs(self.notes_dir, exist_ok=True)
        
    def create_note(self, title, content):
        """Create a new note"""
        if not title:
            title = f"Note_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
        # Sanitize title for filename
        filename = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
        filepath = os.path.join(self.notes_dir, f"{filename}.txt")
        
        # Add timestamp to note
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_content = f"Title: {title}\nDate: {timestamp}\n\n{content}"
        
        try:
            with open(filepath, 'w') as f:
                f.write(full_content)
            return filepath
        except Exception as e:
            print(f"Error creating note: {e}")
            return None
            
    def get_note(self, title):
        """Get a note by title"""
        # Try exact match first
        sanitized = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
        filepath = os.path.join(self.notes_dir, f"{sanitized}.txt")
        
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    return f.read()
            except Exception as e:
                print(f"Error reading note: {e}")
                return None
                
        # Try fuzzy matching
        try:
            notes = [f for f in os.listdir(self.notes_dir) if f.endswith('.txt')]
            if not notes:
                return None
                
            # Remove .txt extension for matching
            note_names = [os.path.splitext(n)[0] for n in notes]
            matches = process.extractBests(sanitized, note_names, scorer=fuzz.ratio, score_cutoff=70, limit=1)
            
            if matches:
                best_match = matches[0][0]
                filepath = os.path.join(self.notes_dir, f"{best_match}.txt")
                
                with open(filepath, 'r') as f:
                    return f.read()
            return None
        except Exception as e:
            print(f"Error finding note: {e}")
            return None
            
    def list_notes(self):
        """List all notes"""
        try:
            notes = [f for f in os.listdir(self.notes_dir) if f.endswith('.txt')]
            return [os.path.splitext(n)[0].replace('_', ' ') for n in notes]
        except Exception as e:
            print(f"Error listing notes: {e}")
            return []
            
    def delete_note(self, title):
        """Delete a note by title"""
        sanitized = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
        filepath = os.path.join(self.notes_dir, f"{sanitized}.txt")
        
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                return True
            except Exception as e:
                print(f"Error deleting note: {e}")
                return False
                
        # Try fuzzy matching
        try:
            notes = [f for f in os.listdir(self.notes_dir) if f.endswith('.txt')]
            if not notes:
                return False
                
            # Remove .txt extension for matching
            note_names = [os.path.splitext(n)[0] for n in notes]
            matches = process.extractBests(sanitized, note_names, scorer=fuzz.ratio, score_cutoff=70, limit=1)
            
            if matches:
                best_match = matches[0][0]
                filepath = os.path.join(self.notes_dir, f"{best_match}.txt")
                os.remove(filepath)
                return True
            return False
        except Exception as e:
            print(f"Error finding note to delete: {e}")
            return False

class Dexa(ctk.CTk):
    """Main application class for Dexa AI Assistant"""
    def __init__(self):
        super().__init__()
        
        # Configure window
        self.title("DexaAI - Digital EXpert Assistant")
        self.geometry("900x700")
        self.minsize(800, 600)
        
        # Initialize TTS engine
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 175)
        
        # Initialize speech recognition
        self.recognizer = sr.Recognizer()
        
        # Load settings and commands
        self.load_settings()
        self.load_commands()
        
        # Initialize variables
        self.is_listening = False
        self.listening_thread = None
        self.background_thread = None
        self.background_listening = False
        self.command_logs = []
        self.is_recording = False
        self.recording_thread = None
        self.stop_recording_flag = False
        self.microphone_lock = threading.Lock()
        self.wake_word_detected = threading.Event()
        self.scheduled_tasks = []
        
        # Initialize volume control
        self._init_volume_control()
        
        # Create popup assistant
        self.popup = PopupAssistant(self)
        
        # Create system tray
        self.setup_system_tray()
        
        # Create UI
        self.create_ui()
        
        # Initialize notes manager
        self.notes_manager = NotesManager()
        
        # Greetings
        self.greetings = [
            "Yes, how can I assist you today?",
            "At your service. What can I do for you?",
            "Hello, I'm listening. How may I help you?",
            "Yes, I'm here. What do you need?"
        ]
        
        self.acknowledgments = [
            "On it",
            "Right away",
            "Working on it",
            "Consider it done"
        ]
        
        # Initialize app cache
        self.installed_apps_cache = {}
        self.last_cache_update = 0
        self.cache_validity = 3600  # 1 hour
        
        # Apply voice settings
        self.apply_voice_settings()
        
        # Start background listening if wake word is enabled
        if self.settings.get("wake_word_enabled", True) and self.settings.get("background_listening", True):
            self.start_background_listening()
        
        # Bind close event
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def apply_voice_settings(self):
        """Apply voice settings to the TTS engine"""
        # Set voice type
        voice_type = self.settings.get("voice_type", "male")
        voices = self.engine.getProperty('voices')
        
        if voice_type == "male":
            # Try to find a male voice
            for i, voice in enumerate(voices):
                if "male" in voice.name.lower():
                    self.engine.setProperty('voice', voice.id)
                    logger.info(f"Set voice to male: {voice.name}")
                    break
            else:
                # If no male voice found, use the first voice
                if voices:
                    self.engine.setProperty('voice', voices[0].id)
                    logger.info(f"No male voice found, using: {voices[0].name}")
        elif voice_type == "female":
            # Try to find a male voice
            for i, voice in enumerate(voices):
                if "female" in voice.name.lower() and "male" not in voice.name.lower():
                    self.engine.setProperty('voice', voice.id)
                    logger.info(f"Set voice to female: {voice.name}")
                    break
            else:
                # If no female voice found, use the first voice
                if len(voices) > 1:
                    self.engine.setProperty('voice', voices[1].id)
                    logger.info(f"No female voice found, using: {voices[1].name if len(voices) > 1 else voices[0].name}")
        
        # Set speech rate
        speech_speed = self.settings.get("speech_speed", 175)
        self.engine.setProperty('rate', speech_speed)
        logger.info(f"Set speech rate to: {speech_speed}")
        
        # Set volume
        volume = self.settings.get("volume", 75) / 100.0
        self.engine.setProperty('volume', volume)
        logger.info(f"Set speech volume to: {volume}")

    def _init_volume_control(self):
        """Initialize volume control interface"""
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self.volume_interface = cast(interface, POINTER(IAudioEndpointVolume))
            logger.info("Volume control initialized")
        except Exception as e:
            logger.error(f"Failed to initialize volume control: {e}")
            self.volume_interface = None

    def load_settings(self):
        """Load settings from file or use defaults"""
        # Default settings
        self.settings = {
            "wake_word_enabled": True,
            "wake_word": "Hey Dexa",
            "voice_type": "female",
            "response_style": "casual",
            "volume": 75,
            "speech_speed": 175,
            "sensitivity": 70,
            "start_on_boot": True,
            "minimize_to_tray": True,
            "show_notifications": True,
            "work_offline": True,
            "save_command_history": True,
            "share_anonymous_data": False,
            "speech_recognition_engine": "sphinx",
            "speech_synthesis_engine": "pyttsx3",
            "theme": "dark",
            "background_listening": True  # New setting for background listening
        }
        
        # Try to load from file
        try:
            if os.path.exists("settings.json"):
                with open("settings.json", "r") as f:
                    loaded_settings = json.load(f)
                    self.settings.update(loaded_settings)
                logger.info("Settings loaded successfully")
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            print(f"Error loading settings: {e}")

    def save_settings(self):
        """Save settings to file"""
        try:
            with open("settings.json", "w") as f:
                json.dump(self.settings, f, indent=4)
            logger.info("Settings saved successfully")
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            print(f"Error saving settings: {e}")

    def load_commands(self):
        """Load commands from file or use defaults"""
        # Default commands
        self.commands = {
            "what time is it": {"action": "say_time", "params": {}},
            "what's the day today": {"action": "say_day", "params": {}},
            "open notepad": {"action": "open_app", "params": {"app": "notepad.exe"}},
            "play music": {"action": "open_app", "params": {"app": "spotify.exe"}},
            "check battery": {"action": "check_battery", "params": {}},
            "take screenshot": {"action": "take_screenshot", "params": {}},
            "mute volume": {"action": "mute_volume", "params": {}},
            "shutdown pc": {"action": "shutdown_pc", "params": {}},
            "tell me a joke": {"action": "tell_joke", "params": {}},
            "system info": {"action": "get_system_info", "params": {}},
            "lock computer": {"action": "lock_computer", "params": {}},
        }
        
        # Add search command with dynamic parameter
        self.commands["search for"] = {"action": "search_web", "params": {"dynamic": True}}
        self.commands["play"] = {"action": "play_youtube", "params": {"dynamic": True}}
        self.commands["who is"] = {"action": "search_wikipedia", "params": {"dynamic": True}}
        self.commands["what is"] = {"action": "search_wikipedia", "params": {"dynamic": True}}
        
        # Add new JARVIS-inspired commands
        self.commands["start recording"] = {"action": "screen_recording", "params": {"action": "start"}}
        self.commands["stop recording"] = {"action": "screen_recording", "params": {"action": "stop"}}
        self.commands["dictate"] = {"action": "dictate_to_file", "params": {}}
        self.commands["monitor resources"] = {"action": "monitor_resources", "params": {}}
        self.commands["remind me"] = {"action": "schedule_task", "params": {"dynamic": True}}
        
        # Add folder and file commands
        self.commands["open folder"] = {"action": "open_folder", "params": {"dynamic": True}}
        self.commands["open file"] = {"action": "open_file", "params": {"dynamic": True}}
        
        # Add note commands
        self.commands["create note"] = {"action": "create_note", "params": {"dynamic": True}}
        self.commands["read note"] = {"action": "read_note", "params": {"dynamic": True}}
        self.commands["list notes"] = {"action": "list_notes", "params": {}}
        self.commands["delete note"] = {"action": "delete_note", "params": {"dynamic": True}}
        
        # Try to load from file
        try:
            if os.path.exists("commands.json"):
                with open("commands.json", "r") as f:
                    loaded_commands = json.load(f)
                    self.commands.update(loaded_commands)
                logger.info(f"Loaded {len(self.commands)} commands")
        except Exception as e:
            logger.error(f"Error loading commands: {e}")
            print(f"Error loading commands: {e}")

    def save_commands(self):
        """Save commands to file"""
        try:
            with open("commands.json", "w") as f:
                json.dump(self.commands, f, indent=4)
            logger.info("Commands saved successfully")
        except Exception as e:
            logger.error(f"Error saving commands: {e}")
            print(f"Error saving commands: {e}")

    def setup_system_tray(self):
        """Set up system tray icon and menu"""
        # Create system tray icon
        try:
            image = Image.open("Dexa_icon.png") if os.path.exists("Dexa_icon.png") else Image.new('RGB', (64, 64), color = (6, 182, 212))
            
            def on_exit(icon, item):
                icon.stop()
                self.destroy()
                sys.exit()
                
            def show_window(icon, item):
                self.deiconify()
                self.lift()
                
            def toggle_listening(icon, item):
                if self.is_listening:
                    self.stop_listening()
                else:
                    self.start_listening()
            
            # Create menu
            menu = pystray.Menu(
                pystray.MenuItem("Open DexaAI", show_window),
                pystray.MenuItem("Toggle Listening", toggle_listening),
                pystray.MenuItem("Exit", on_exit)
            )
            
            # Create icon
            self.icon = pystray.Icon("Dexa", image, "DexaAI", menu)
            
            # Run in separate thread
            threading.Thread(target=self.icon.run, daemon=True).start()
            logger.info("System tray icon initialized")
        except Exception as e:
            logger.error(f"Error setting up system tray: {e}")
            print(f"Error setting up system tray: {e}")
            # Create a dummy icon object with a stop method
            class DummyIcon:
                def stop(self):
                    pass
            self.icon = DummyIcon()

    def create_ui(self):
        """Create the main UI"""
        # Create main frame
        self.main_frame = ctk.CTkFrame(self, fg_color="#0a0a0f")
        self.main_frame.pack(fill="both", expand=True)
        
        # Create header
        self.create_header()
        
        # Create tabview
        self.create_tabview()
        
        # Create footer
        self.create_footer()

    def create_header(self):
        """Create the header section of the UI"""
        # Header frame
        header = ctk.CTkFrame(self.main_frame, fg_color="#0f0f17", height=60)
        header.pack(fill="x", pady=(0, 10))
        header.pack_propagate(False)
        
        # Logo and title
        logo_frame = ctk.CTkFrame(header, width=50, height=50, corner_radius=25, fg_color="#06b6d4")
        logo_frame.pack(side="left", padx=15)
        logo_frame.pack_propagate(False)
        
        # Status indicator
        status_indicator = ctk.CTkLabel(
            logo_frame, 
            text="", 
            fg_color="#3b82f6", 
            width=15, 
            height=15, 
            corner_radius=7
        )
        status_indicator.place(relx=0.8, rely=0.8, anchor="center")
        self.status_indicator = status_indicator
        
        # Title and status
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=10)
        
        title_label = ctk.CTkLabel(
            title_frame, 
            text="DexaAI", 
            font=("Helvetica", 24, "bold"), 
            text_color="#06b6d4"
        )
        title_label.pack(anchor="w")
        
        status_label = ctk.CTkLabel(
            title_frame, 
            text="Idle", 
            font=("Helvetica", 12), 
            text_color="#9ca3af"
        )
        status_label.pack(anchor="w")
        self.status_label = status_label
        
        # Background listening toggle
        bg_listen_frame = ctk.CTkFrame(header, fg_color="transparent")
        bg_listen_frame.pack(side="right", padx=(0, 15))
        
        bg_listen_label = ctk.CTkLabel(
            bg_listen_frame, 
            text="Background Listening", 
            font=("Helvetica", 12), 
            text_color="#9ca3af"
        )
        bg_listen_label.pack(side="left", padx=(0, 10))
        
        self.bg_listen_switch = ctk.CTkSwitch(
            bg_listen_frame, 
            text="", 
            command=self.toggle_background_listening,
            progress_color="#06b6d4",
            button_color="#ffffff",
            button_hover_color="#e5e7eb"
        )
        self.bg_listen_switch.pack(side="left")
        
        if self.settings.get("background_listening", True):
            self.bg_listen_switch.select()
        else:
            self.bg_listen_switch.deselect()
        
        # Window controls
        controls_frame = ctk.CTkFrame(header, fg_color="transparent")
        controls_frame.pack(side="right", padx=15)
        
        minimize_button = ctk.CTkButton(
            controls_frame, 
            text="—", 
            width=30, 
            height=30, 
            corner_radius=15,
            fg_color="#252542", 
            hover_color="#2a2a4a",
            command=self.iconify
        )
        minimize_button.pack(side="left", padx=5)
        
        close_button = ctk.CTkButton(
            controls_frame, 
            text="✕", 
            width=30, 
            height=30, 
            corner_radius=15,
            fg_color="#252542", 
            hover_color="#c53030",
            command=self.on_close
        )
        close_button.pack(side="left", padx=5)

    def create_tabview(self):
        """Create the tabview with all tabs"""
        # Create tabview
        self.tabview = ctk.CTkTabview(self.main_frame, fg_color="#0a0a0f")
        self.tabview.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Configure tab colors
        self.tabview._segmented_button.configure(
            fg_color="#0f0f17",
            selected_color="#1a1a2e",
            selected_hover_color="#1a1a2e",
            unselected_color="#0f0f17",
            unselected_hover_color="#252542"
        )
        
        # Add tabs
        self.tabview.add("Home")
        self.tabview.add("Commands")
        self.voice_tab = self.tabview.add("Voice")
        self.tabview.add("Settings")
        self.tabview.add("Learn")
        self.tabview.add("Advanced")  # New tab for advanced features
        
        # Create content for each tab
        self.create_home_tab()
        self.create_commands_tab()
        self.create_voice_tab()
        self.create_settings_tab()
        self.create_learn_tab()
        self.create_advanced_tab()  # Create the new advanced tab

    def create_home_tab(self):
        """Create the home tab content"""
        tab = self.tabview.tab("Home")
        
        # Create two-column layout
        left_frame = ctk.CTkFrame(tab, fg_color="transparent")
        left_frame.grid(row=0, column=0, padx=(0, 10), pady=10, sticky="nsew")
        
        right_frame = ctk.CTkFrame(tab, fg_color="transparent")
        right_frame.grid(row=0, column=1, padx=(10, 0), pady=10, sticky="nsew")
        
        tab.grid_columnconfigure(0, weight=2)
        tab.grid_columnconfigure(1, weight=1)
        
        # Status card
        status_card = ctk.CTkFrame(left_frame, corner_radius=10, fg_color="#1a1a2e", border_width=1, border_color="#2a2a3a")
        status_card.pack(fill="both", expand=True, pady=(0, 10))
        
        status_title = ctk.CTkLabel(status_card, text="Status", font=("Helvetica", 18, "bold"), text_color="#ffffff")
        status_title.pack(anchor="w", padx=15, pady=(15, 5))
        
        status_desc = ctk.CTkLabel(status_card, text="Current status and controls", font=("Helvetica", 12), text_color="#9ca3af")
        status_desc.pack(anchor="w", padx=15, pady=(0, 15))
        
        # Activation button with concentric circles
        activation_frame = ctk.CTkFrame(status_card, fg_color="transparent")
        activation_frame.pack(pady=20)
        
        # Outer circle
        outer_circle = ctk.CTkFrame(activation_frame, width=140, height=140, corner_radius=70, fg_color="#252542")
        outer_circle.pack()
        outer_circle.pack_propagate(False)
        
        # Middle circle
        middle_circle = ctk.CTkFrame(outer_circle, width=110, height=110, corner_radius=55, fg_color="#1e1e30")
        middle_circle.place(relx=0.5, rely=0.5, anchor="center")
        
        # Inner circle
        inner_circle = ctk.CTkFrame(middle_circle, width=80, height=80, corner_radius=40, fg_color="#252542")
        inner_circle.place(relx=0.5, rely=0.5, anchor="center")
        
        # Activation button
        self.activation_button = ctk.CTkButton(
            inner_circle, 
            text="", 
            width=60, 
            height=60, 
            corner_radius=30,
            fg_color="#06b6d4", 
            hover_color="#0891b2",
            command=self.toggle_listening
        )
        self.activation_button.place(relx=0.5, rely=0.5, anchor="center")
        
        # Waveform visualization (only shown when listening)
        self.home_waveform = VoiceWaveform(status_card, height=30, width=280, bg="#1a1a2e")
        self.home_waveform.pack(pady=10)
        self.home_waveform.pack_forget()  # Hide initially
        
        # Status text
        self.activation_status = ctk.CTkLabel(
            status_card, 
            text="Click to activate Dexa", 
            font=("Helvetica", 14, "bold"), 
            text_color="#06b6d4"
        )
        self.activation_status.pack(pady=(10, 5))
        
        self.activation_desc = ctk.CTkLabel(
            status_card, 
            text=f'Or say "{self.settings["wake_word"]}" to activate with your voice', 
            font=("Helvetica", 12), 
            text_color="#9ca3af"
        )
        self.activation_desc.pack(pady=(0, 10))
        
        # Wake word toggle
        wake_word_frame = ctk.CTkFrame(status_card, fg_color="transparent")
        wake_word_frame.pack(pady=10)
        
        wake_word_label = ctk.CTkLabel(wake_word_frame, text="Wake Word", font=("Helvetica", 12), text_color="#9ca3af")
        wake_word_label.pack(side="left", padx=(0, 10))
        
        self.wake_word_switch = ctk.CTkSwitch(
            wake_word_frame, 
            text="", 
            command=self.toggle_wake_word,
            progress_color="#06b6d4",
            button_color="#ffffff",
            button_hover_color="#e5e7eb"
        )
        self.wake_word_switch.pack(side="left")
        
        if self.settings.get("wake_word_enabled", True):
            self.wake_word_switch.select()
        else:
            self.wake_word_switch.deselect()
        
        # Command log card
        log_card = ctk.CTkFrame(right_frame, corner_radius=10, fg_color="#1a1a2e", border_width=1, border_color="#2a2a3a")
        log_card.pack(fill="both", expand=True)
        
        log_title = ctk.CTkLabel(log_card, text="Command Log", font=("Helvetica", 18, "bold"), text_color="#ffffff")
        log_title.pack(anchor="w", padx=15, pady=(15, 5))
        
        log_desc = ctk.CTkLabel(log_card, text="Recent voice commands", font=("Helvetica", 12), text_color="#9ca3af")
        log_desc.pack(anchor="w", padx=15, pady=(0, 15))
        
        # Scrollable log area
        log_frame = ctk.CTkScrollableFrame(log_card, fg_color="transparent", height=300)
        log_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        self.log_frame = log_frame
        
        # Quick commands card
        quick_card = ctk.CTkScrollableFrame(tab, corner_radius=10, fg_color="#1a1a2e", border_width=1, border_color="#2a2a3a", height=220)
        quick_card.grid(row=1, column=0, columnspan=2, padx=0, pady=10, sticky="nsew")

        
        quick_title = ctk.CTkLabel(quick_card, text="Quick Commands", font=("Helvetica", 18, "bold"), text_color="#ffffff")
        quick_title.pack(anchor="w", padx=15, pady=(15, 5))
        
        quick_desc = ctk.CTkLabel(quick_card, text="Your most used commands", font=("Helvetica", 12), text_color="#9ca3af")
        quick_desc.pack(anchor="w", padx=15, pady=(0, 15))
        
        # Quick command buttons
        quick_frame = ctk.CTkFrame(quick_card, fg_color="transparent")
        quick_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        # Add more quick commands (now 6 instead of 4)
        quick_commands = [
            "what time is it", 
            "tell me a joke", 
            "system info", 
            "take screenshot", 
            "dictate", 
            "monitor resources"
        ]
        
        for i, cmd in enumerate(quick_commands):
            row = i // 3
            col = i % 3
            
            quick_frame.grid_columnconfigure(col, weight=1)
            
            cmd_button = ctk.CTkButton(
                quick_frame, 
                text=cmd.capitalize(),
                height=80,
                corner_radius=10,
                fg_color="#252542", 
                hover_color="#2a2a4a",
                command=lambda c=cmd: self.execute_command(c)
            )
            cmd_button.grid(row=row, column=col, padx=5, pady=5, sticky="ew")

    def create_commands_tab(self):
        """Create the commands tab content"""
        tab = self.tabview.tab("Commands")
        
        # Header with buttons
        header_frame = ctk.CTkFrame(tab, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))
        
        title = ctk.CTkLabel(header_frame, text="Voice Commands", font=("Helvetica", 20, "bold"), text_color="#ffffff")
        title.pack(side="left")
        
        buttons_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        buttons_frame.pack(side="right")
        
        add_button = ctk.CTkButton(
            buttons_frame, 
            text="Add Command", 
            corner_radius=8,
            fg_color="#06b6d4", 
            hover_color="#0891b2",
            command=self.add_command
        )
        add_button.pack(side="left", padx=5)
        
        import_button = ctk.CTkButton(
            buttons_frame, 
            text="Import", 
            corner_radius=8,
            fg_color="#252542", 
            hover_color="#2a2a4a",
            command=self.import_commands
        )
        import_button.pack(side="left", padx=5)
        
        export_button = ctk.CTkButton(
            buttons_frame, 
            text="Export", 
            corner_radius=8,
            fg_color="#252542", 
            hover_color="#2a2a4a",
            command=self.export_commands
        )
        export_button.pack(side="left", padx=5)
        
        # Search bar
        search_frame = ctk.CTkFrame(tab, fg_color="transparent")
        search_frame.pack(fill="x", pady=(0, 15))
        
        search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="Search commands...",
            height=35,
            corner_radius=8,
            fg_color="#252542",
            border_color="#2a2a3a"
        )
        search_entry.pack(fill="x")
        
        # Commands scrollable area
        commands_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        commands_frame.pack(fill="both", expand=True)
        self.commands_frame = commands_frame
        
        # Add command cards
        self.refresh_commands()
        
        # Connect search functionality
        def search_commands(event=None):
            query = search_entry.get().lower()
            self.refresh_commands(query)
            
        search_entry.bind("<KeyRelease>", search_commands)

    def create_voice_tab(self):
        """Create the voice tab content"""
        tab = self.tabview.tab("Voice")
        
        # Create two-column layout
        left_frame = ctk.CTkFrame(tab, fg_color="transparent")
        left_frame.grid(row=0, column=0, padx=(0, 10), pady=10, sticky="nsew")
        
        right_frame = ctk.CTkFrame(tab, fg_color="transparent")
        right_frame.grid(row=0, column=1, padx=(10, 0), pady=10, sticky="nsew")
        
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        
        # Voice settings card
        voice_card = ctk.CTkFrame(left_frame, corner_radius=10, fg_color="#1a1a2e", border_width=1, border_color="#2a2a3a")
        voice_card.pack(fill="both", expand=True)
        
        voice_title = ctk.CTkLabel(voice_card, text="Voice Settings", font=("Helvetica", 18, "bold"), text_color="#ffffff")
        voice_title.pack(anchor="w", padx=15, pady=(15, 5))
        
        voice_desc = ctk.CTkLabel(voice_card, text="Customize Dexa's voice", font=("Helvetica", 12), text_color="#9ca3af")
        voice_desc.pack(anchor="w", padx=15, pady=(0, 15))
        
        # Voice type
        voice_type_frame = ctk.CTkFrame(voice_card, fg_color="transparent")
        voice_type_frame.pack(fill="x", padx=15, pady=5)
        
        voice_type_label = ctk.CTkLabel(voice_type_frame, text="Voice Type", font=("Helvetica", 12), text_color="#ffffff")
        voice_type_label.pack(anchor="w", pady=(0, 5))
        
        self.voice_type_var = ctk.StringVar(value=self.settings.get("voice_type", "female"))
        voice_type_menu = ctk.CTkOptionMenu(
            voice_type_frame, 
            values=["male", "female", "system"],
            variable=self.voice_type_var,
            command=self.update_voice_type,
            fg_color="#252542",
            button_color="#252542",
            button_hover_color="#2a2a4a",
            dropdown_fg_color="#252542",
            dropdown_hover_color="#2a2a4a"
        )
        voice_type_menu.pack(fill="x")
        
        # Response style
        style_frame = ctk.CTkFrame(voice_card, fg_color="transparent")
        style_frame.pack(fill="x", padx=15, pady=5)
        
        style_label = ctk.CTkLabel(style_frame, text="Response Style", font=("Helvetica", 12), text_color="#ffffff")
        style_label.pack(anchor="w", pady=(0, 5))
        
        self.response_style_var = ctk.StringVar(value=self.settings.get("response_style", "casual"))
        style_menu = ctk.CTkOptionMenu(
            style_frame, 
            values=["formal", "casual", "silent"],
            variable=self.response_style_var,
            command=self.update_response_style,
            fg_color="#252542",
            button_color="#252542",
            button_hover_color="#2a2a4a",
            dropdown_fg_color="#252542",
            dropdown_hover_color="#2a2a4a"
        )
        style_menu.pack(fill="x")
        
        # Volume slider
        volume_frame = ctk.CTkFrame(voice_card, fg_color="transparent")
        volume_frame.pack(fill="x", padx=15, pady=5)
        
        volume_label = ctk.CTkLabel(volume_frame, text="Volume", font=("Helvetica", 12), text_color="#ffffff")
        volume_label.pack(anchor="w", pady=(0, 5))
        
        self.volume_var = ctk.IntVar(value=self.settings.get("volume", 75))
        volume_slider = ctk.CTkSlider(
            volume_frame, 
            from_=0, 
            to=100, 
            variable=self.volume_var,
            command=self.update_volume,
            progress_color="#06b6d4",
            button_color="#06b6d4",
            button_hover_color="#0891b2"
        )
        volume_slider.pack(fill="x")
        
        volume_value = ctk.CTkLabel(volume_frame, text=f"{self.volume_var.get()}%", font=("Helvetica", 10), text_color="#9ca3af")
        volume_value.pack(anchor="e", pady=(5, 0))
        self.volume_value = volume_value
        
        # Speech speed slider
        speed_frame = ctk.CTkFrame(voice_card, fg_color="transparent")
        speed_frame.pack(fill="x", padx=15, pady=5)
        
        speed_label = ctk.CTkLabel(speed_frame, text="Speech Speed", font=("Helvetica", 12), text_color="#ffffff")
        speed_label.pack(anchor="w", pady=(0, 5))
        
        self.speed_var = ctk.IntVar(value=self.settings.get("speech_speed", 175))
        speed_slider = ctk.CTkSlider(
            speed_frame, 
            from_=50, 
            to=300, 
            variable=self.speed_var,
            command=self.update_speech_speed,
            progress_color="#06b6d4",
            button_color="#06b6d4",
            button_hover_color="#0891b2"
        )
        speed_slider.pack(fill="x")
        
        speed_value = ctk.CTkLabel(speed_frame, text=f"{self.speed_var.get()}", font=("Helvetica", 10), text_color="#9ca3af")
        speed_value.pack(anchor="e", pady=(5, 0))
        self.speed_value = speed_value
        
        # Wake word card
        wake_card = ctk.CTkFrame(right_frame, corner_radius=10, fg_color="#1a1a2e", border_width=1, border_color="#2a2a3a")
        wake_card.pack(fill="both", expand=True)
        
        wake_title = ctk.CTkLabel(wake_card, text="Wake Word", font=("Helvetica", 18, "bold"), text_color="#ffffff")
        wake_title.pack(anchor="w", padx=15, pady=(15, 5))
        
        wake_desc = ctk.CTkLabel(wake_card, text="Customize activation phrase", font=("Helvetica", 12), text_color="#9ca3af")
        wake_desc.pack(anchor="w", padx=15, pady=(0, 15))
        
        # Wake word activation
        wake_activation_frame = ctk.CTkFrame(wake_card, fg_color="transparent")
        wake_activation_frame.pack(fill="x", padx=15, pady=5)
        
        wake_activation_label = ctk.CTkLabel(wake_activation_frame, text="Wake Word Activation", font=("Helvetica", 12), text_color="#ffffff")
        wake_activation_label.pack(anchor="w")
        
        wake_activation_desc = ctk.CTkLabel(wake_activation_frame, text="Enable or disable wake word detection", font=("Helvetica", 10), text_color="#9ca3af")
        wake_activation_desc.pack(anchor="w", pady=(0, 5))
        
        self.wake_activation_switch = ctk.CTkSwitch(
            wake_activation_frame, 
            text="", 
            command=self.toggle_wake_word,
            progress_color="#06b6d4",
            button_color="#ffffff",
            button_hover_color="#e5e7eb"
        )
        self.wake_activation_switch.pack(anchor="w")
        
        if self.settings.get("wake_word_enabled", True):
            self.wake_activation_switch.select()
        else:
            self.wake_activation_switch.deselect()
        
        # Separator
        separator1 = ctk.CTkFrame(wake_card, height=1, fg_color="#2a2a3a")
        separator1.pack(fill="x", padx=15, pady=10)
        
        # Current wake word
        wake_current_frame = ctk.CTkFrame(wake_card, fg_color="transparent")
        wake_current_frame.pack(fill="x", padx=15, pady=5)
        
        wake_current_label = ctk.CTkLabel(wake_current_frame, text="Current Wake Word", font=("Helvetica", 12), text_color="#ffffff")
        # wake_  text="Current Wake Word", font=("Helvetica", 12), text_color="#ffffff")
        # wake_ = ctk.CTkLabel(master=self.voice_tab, text="Current Wake Word", font=("Helvetica", 12), text_color="#ffffff")

        wake_current_label.pack(anchor="w", pady=(0, 5))
        
        wake_word_display = ctk.CTkFrame(wake_current_frame, fg_color="transparent")
        wake_word_display.pack(fill="x")
        
        self.wake_word_label = ctk.CTkLabel(
            wake_word_display, 
            text=self.settings.get("wake_word", "Hey Dexa"), 
            font=("Helvetica", 16, "bold"), 
            text_color="#06b6d4"
        )
        self.wake_word_label.pack(side="left")
        
        change_button = ctk.CTkButton(
            wake_word_display, 
            text="Change", 
            width=80,
            corner_radius=8,
            fg_color="#252542", 
            hover_color="#2a2a4a",
            command=self.change_wake_word
        )
        change_button.pack(side="right")
        
        wake_word_desc = ctk.CTkLabel(
            wake_current_frame, 
            text="This is the phrase that will activate Dexa when spoken", 
            font=("Helvetica", 10), 
            text_color="#9ca3af"
        )
        wake_word_desc.pack(anchor="w", pady=(5, 0))
        
        # Separator
        separator2 = ctk.CTkFrame(wake_card, height=1, fg_color="#2a2a3a")
        separator2.pack(fill="x", padx=15, pady=10)
        
        # Sensitivity
        sensitivity_frame = ctk.CTkFrame(wake_card, fg_color="transparent")
        sensitivity_frame.pack(fill="x", padx=15, pady=5)
        
        sensitivity_label = ctk.CTkLabel(sensitivity_frame, text="Sensitivity", font=("Helvetica", 12), text_color="#ffffff")
        sensitivity_label.pack(anchor="w", pady=(0, 5))
        
        self.sensitivity_var = ctk.IntVar(value=self.settings.get("sensitivity", 70))
        sensitivity_slider = ctk.CTkSlider(
            sensitivity_frame, 
            from_=0, 
            to=100, 
            variable=self.sensitivity_var,
            command=self.update_sensitivity,
            progress_color="#06b6d4",
            button_color="#06b6d4",
            button_hover_color="#0891b2"
        )
        sensitivity_slider.pack(fill="x")
        
        sensitivity_labels = ctk.CTkFrame(sensitivity_frame, fg_color="transparent")
        sensitivity_labels.pack(fill="x", pady=(5, 0))
        
        low_label = ctk.CTkLabel(sensitivity_labels, text="Low", font=("Helvetica", 10), text_color="#9ca3af")
        low_label.pack(side="left")
        
        high_label = ctk.CTkLabel(sensitivity_labels, text="High", font=("Helvetica", 10), text_color="#9ca3af")
        high_label.pack(side="right")
        
        sensitivity_desc = ctk.CTkLabel(
            sensitivity_frame, 
            text="Higher sensitivity may cause more false activations", 
            font=("Helvetica", 10), 
            text_color="#9ca3af"
        )
        sensitivity_desc.pack(anchor="w", pady=(5, 0))
        
        # Test voice card
        test_card = ctk.CTkFrame(tab, corner_radius=10, fg_color="#1a1a2e", border_width=1, border_color="#2a2a3a")
        test_card.grid(row=1, column=0, columnspan=2, padx=0, pady=10, sticky="ew")
        
        test_title = ctk.CTkLabel(test_card, text="Test Voice", font=("Helvetica", 18, "bold"), text_color="#ffffff")
        test_title.pack(anchor="w", padx=15, pady=(15, 5))
        
        test_desc = ctk.CTkLabel(test_card, text="Preview Dexa's voice with your current settings", font=("Helvetica", 12), text_color="#9ca3af")
        test_desc.pack(anchor="w", padx=15, pady=(0, 15))
        
        test_frame = ctk.CTkFrame(test_card, fg_color="transparent")
        test_frame.pack(pady=(0, 15))
        
        self.test_text = ctk.CTkEntry(
            test_frame, 
            width=400,
            height=35,
            corner_radius=8,
            fg_color="#252542",
            border_color="#2a2a3a",
            placeholder_text="Enter text for Dexa to speak..."
        )
        self.test_text.pack(side="left", padx=(0, 10))
        self.test_text.insert(0, "Hello, I'm Dexa, your personal AI assistant.")
        
        test_button = ctk.CTkButton(
            test_frame, 
            text="Test Voice", 
            corner_radius=8,
            fg_color="#06b6d4", 
            hover_color="#0891b2",
            command=self.test_voice
        )
        test_button.pack(side="left")

    def create_settings_tab(self):
        """Create the settings tab content"""
        tab = self.tabview.tab("Settings")

        # 🔁 Wrap the entire tab content in a scrollable frame
        scroll_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Use grid layout inside the scrollable frame
        scroll_frame.grid_columnconfigure(0, weight=1)
        scroll_frame.grid_columnconfigure(1, weight=1)

        # Left column
        left_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        left_frame.grid(row=0, column=0, padx=(0, 10), pady=10, sticky="nsew")

        # Right column
        right_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        right_frame.grid(row=0, column=1, padx=(10, 0), pady=10, sticky="nsew")

        # Example: General settings card (your existing code)
        general_card = ctk.CTkFrame(left_frame, corner_radius=10, fg_color="#1a1a2e", border_width=1, border_color="#2a2a3a")
        general_card.pack(fill="both", expand=True)

        general_title = ctk.CTkLabel(general_card, text="General Settings", font=("Helvetica", 18, "bold"), text_color="#ffffff")
        general_title.pack(anchor="w", padx=15, pady=(15, 5))

        general_desc = ctk.CTkLabel(general_card, text="Configure Dexa's behavior", font=("Helvetica", 12), text_color="#9ca3af")
        general_desc.pack(anchor="w", padx=15, pady=(0, 15))

        # 🔽 Continue all your current layout logic as it is, using `left_frame`, `right_frame`, etc.
        # 🔽 Also, your advanced_card.grid(...) stays the same — it will now scroll correctly

        # Background listening
        bg_listen_frame = ctk.CTkFrame(general_card, fg_color="transparent")
        bg_listen_frame.pack(fill="x", padx=15, pady=5)
        
        bg_listen_text = ctk.CTkFrame(bg_listen_frame, fg_color="transparent")
        bg_listen_text.pack(side="left", fill="x", expand=True)
        
        bg_listen_label = ctk.CTkLabel(bg_listen_text, text="Background Listening", font=("Helvetica", 12), text_color="#ffffff")
        bg_listen_label.pack(anchor="w")
        
        bg_listen_desc = ctk.CTkLabel(bg_listen_text, text="Keep Dexa running in background when closed", font=("Helvetica", 10), text_color="#9ca3af")
        bg_listen_desc.pack(anchor="w")
        
        self.bg_listen_settings_switch = ctk.CTkSwitch(
            bg_listen_frame, 
            text="", 
            command=self.toggle_background_listening,
            progress_color="#06b6d4",
            button_color="#ffffff",
            button_hover_color="#e5e7eb"
        )
        self.bg_listen_settings_switch.pack(side="right")
        
        if self.settings.get("background_listening", True):
            self.bg_listen_settings_switch.select()
        else:
            self.bg_listen_settings_switch.deselect()
        
        # Separator
        separator0 = ctk.CTkFrame(general_card, height=1, fg_color="#2a2a3a")
        separator0.pack(fill="x", padx=15, pady=10)
        
        # Start on boot
        boot_frame = ctk.CTkFrame(general_card, fg_color="transparent")
        boot_frame.pack(fill="x", padx=15, pady=5)
        
        boot_text = ctk.CTkFrame(boot_frame, fg_color="transparent")
        boot_text.pack(side="left", fill="x", expand=True)
        
        boot_label = ctk.CTkLabel(boot_text, text="Start on Boot", font=("Helvetica", 12), text_color="#ffffff")
        boot_label.pack(anchor="w")
        
        boot_desc = ctk.CTkLabel(boot_text, text="Launch Dexa when your computer starts", font=("Helvetica", 10), text_color="#9ca3af")
        boot_desc.pack(anchor="w")
        
        self.boot_switch = ctk.CTkSwitch(
            boot_frame, 
            text="", 
            command=self.toggle_start_on_boot,
            progress_color="#06b6d4",
            button_color="#ffffff",
            button_hover_color="#e5e7eb"
        )
        self.boot_switch.pack(side="right")
        
        if self.settings.get("start_on_boot", True):
            self.boot_switch.select()
        else:
            self.boot_switch.deselect()
        
        # Separator
        separator1 = ctk.CTkFrame(general_card, height=1, fg_color="#2a2a3a")
        separator1.pack(fill="x", padx=15, pady=10)
        
        # Minimize to tray
        tray_frame = ctk.CTkFrame(general_card, fg_color="transparent")
        tray_frame.pack(fill="x", padx=15, pady=5)
        
        tray_text = ctk.CTkFrame(tray_frame, fg_color="transparent")
        tray_text.pack(side="left", fill="x", expand=True)
        
        tray_label = ctk.CTkLabel(tray_text, text="Minimize to Tray", font=("Helvetica", 12), text_color="#ffffff")
        tray_label.pack(anchor="w")
        
        tray_desc = ctk.CTkLabel(tray_text, text="Keep Dexa running in the system tray when closed", font=("Helvetica", 10), text_color="#9ca3af")
        tray_desc.pack(anchor="w")
        
        self.tray_switch = ctk.CTkSwitch(
            tray_frame, 
            text="", 
            command=self.toggle_minimize_to_tray,
            progress_color="#06b6d4",
            button_color="#ffffff",
            button_hover_color="#e5e7eb"
        )
        self.tray_switch.pack(side="right")
        
        if self.settings.get("minimize_to_tray", True):
            self.tray_switch.select()
        else:
            self.tray_switch.deselect()
        
        # Separator
        separator2 = ctk.CTkFrame(general_card, height=1, fg_color="#2a2a3a")
        separator2.pack(fill="x", padx=15, pady=10)
        
        # Show notifications
        notif_frame = ctk.CTkFrame(general_card, fg_color="transparent")
        notif_frame.pack(fill="x", padx=15, pady=5)
        
        notif_text = ctk.CTkFrame(notif_frame, fg_color="transparent")
        notif_text.pack(side="left", fill="x", expand=True)
        
        notif_label = ctk.CTkLabel(notif_text, text="Show Notifications", font=("Helvetica", 12), text_color="#ffffff")
        notif_label.pack(anchor="w")
        
        notif_desc = ctk.CTkLabel(notif_text, text="Display system notifications for Dexa events", font=("Helvetica", 10), text_color="#9ca3af")
        notif_desc.pack(anchor="w")
        
        self.notif_switch = ctk.CTkSwitch(
            notif_frame, 
            text="", 
            command=self.toggle_notifications,
            progress_color="#06b6d4",
            button_color="#ffffff",
            button_hover_color="#e5e7eb"
        )
        self.notif_switch.pack(side="right")
        
        if self.settings.get("show_notifications", True):
            self.notif_switch.select()
        else:
            self.notif_switch.deselect()
        
        # Separator
        separator3 = ctk.CTkFrame(general_card, height=1, fg_color="#2a2a3a")
        separator3.pack(fill="x", padx=15, pady=10)
        
        # Theme
        theme_frame = ctk.CTkFrame(general_card, fg_color="transparent")
        theme_frame.pack(fill="x", padx=15, pady=5)
        
        theme_text = ctk.CTkFrame(theme_frame, fg_color="transparent")
        theme_text.pack(side="left", fill="x", expand=True)
        
        theme_label = ctk.CTkLabel(theme_text, text="Theme", font=("Helvetica", 12), text_color="#ffffff")
        theme_label.pack(anchor="w")
        
        theme_desc = ctk.CTkLabel(theme_text, text="Choose between light and dark mode", font=("Helvetica", 10), text_color="#9ca3af")
        theme_desc.pack(anchor="w")
        
        theme_buttons = ctk.CTkFrame(theme_frame, fg_color="transparent")
        theme_buttons.pack(side="right")
        
        # Set button colors based on current theme
        light_fg = "#06b6d4" if self.settings.get("theme", "dark") == "light" else "#252542"
        light_hover = "#0891b2" if self.settings.get("theme", "dark") == "light" else "#2a2a4a"
        
        dark_fg = "#06b6d4" if self.settings.get("theme", "dark") == "dark" else "#252542"
        dark_hover = "#0891b2" if self.settings.get("theme", "dark") == "dark" else "#2a2a4a"
        
        self.light_button = ctk.CTkButton(
            theme_buttons, 
            text="Light", 
            width=60,
            corner_radius=8,
            fg_color=light_fg, 
            hover_color=light_hover,
            command=lambda: self.change_theme("light")
        )
        self.light_button.pack(side="left", padx=(0, 5))
        
        self.dark_button = ctk.CTkButton(
            theme_buttons, 
            text="Dark", 
            width=60,
            corner_radius=8,
            fg_color=dark_fg, 
            hover_color=dark_hover,
            command=lambda: self.change_theme("dark")
        )
        self.dark_button.pack(side="left")
        
        # Privacy settings card
        privacy_card = ctk.CTkFrame(right_frame, corner_radius=10, fg_color="#1a1a2e", border_width=1, border_color="#2a2a3a")
        privacy_card.pack(fill="both", expand=True)
        
        privacy_title = ctk.CTkLabel(privacy_card, text="Privacy Settings", font=("Helvetica", 18, "bold"), text_color="#ffffff")
        privacy_title.pack(anchor="w", padx=15, pady=(15, 5))
        
        privacy_desc = ctk.CTkLabel(privacy_card, text="Control your data and privacy", font=("Helvetica", 12), text_color="#9ca3af")
        privacy_desc.pack(anchor="w", padx=15, pady=(0, 15))
        
        # Work offline
        offline_frame = ctk.CTkFrame(privacy_card, fg_color="transparent")
        offline_frame.pack(fill="x", padx=15, pady=5)
        
        self.offline_var = ctk.BooleanVar(value=self.settings.get("work_offline", True))
        offline_check = ctk.CTkCheckBox(
            offline_frame, 
            text="Work completely offline", 
            variable=self.offline_var,
            command=self.toggle_offline_mode,
            checkbox_width=20,
            checkbox_height=20,
            corner_radius=4,
            fg_color="#06b6d4",
            hover_color="#0891b2"
        )
        offline_check.pack(anchor="w")
        
        offline_desc = ctk.CTkLabel(
            offline_frame, 
            text="Dexa will only use local processing and won't send data to the internet", 
            font=("Helvetica", 10), 
            text_color="#9ca3af"
        )
        offline_desc.pack(anchor="w", padx=(25, 0), pady=(5, 0))
        
        # Separator
        separator4 = ctk.CTkFrame(privacy_card, height=1, fg_color="#2a2a3a")
        separator4.pack(fill="x", padx=15, pady=10)
        
        # Save command history
        history_frame = ctk.CTkFrame(privacy_card, fg_color="transparent")
        history_frame.pack(fill="x", padx=15, pady=5)
        
        self.history_var = ctk.BooleanVar(value=self.settings.get("save_command_history", True))
        history_check = ctk.CTkCheckBox(
            history_frame, 
            text="Save command history", 
            variable=self.history_var,
            command=self.toggle_command_history,
            checkbox_width=20,
            checkbox_height=20,
            corner_radius=4,
            fg_color="#06b6d4",
            hover_color="#0891b2"
        )
        history_check.pack(anchor="w")
        
        history_desc = ctk.CTkLabel(
            history_frame, 
            text="Keep a log of your voice commands and Dexa's responses", 
            font=("Helvetica", 10), 
            text_color="#9ca3af"
        )
        history_desc.pack(anchor="w", padx=(25, 0), pady=(5, 0))
        
        # Separator
        separator5 = ctk.CTkFrame(privacy_card, height=1, fg_color="#2a2a3a")
        separator5.pack(fill="x", padx=15, pady=10)
        
        # Share anonymous data
        anon_frame = ctk.CTkFrame(privacy_card, fg_color="transparent")
        anon_frame.pack(fill="x", padx=15, pady=5)
        
        self.anon_var = ctk.BooleanVar(value=self.settings.get("share_anonymous_data", False))
        anon_check = ctk.CTkCheckBox(
            anon_frame, 
            text="Share anonymous usage data", 
            variable=self.anon_var,
            command=self.toggle_anonymous_data,
            checkbox_width=20,
            checkbox_height=20,
            corner_radius=4,
            fg_color="#06b6d4",
            hover_color="#0891b2"
        )
        anon_check.pack(anchor="w")
        
        anon_desc = ctk.CTkLabel(
            anon_frame, 
            text="Help improve Dexa by sharing anonymous usage statistics", 
            font=("Helvetica", 10), 
            text_color="#9ca3af"
        )
        anon_desc.pack(anchor="w", padx=(25, 0), pady=(5, 0))
        
        # Separator
        separator6 = ctk.CTkFrame(privacy_card, height=1, fg_color="#2a2a3a")
        separator6.pack(fill="x", padx=15, pady=10)
        
        # Clear data button
        clear_button = ctk.CTkButton(
            privacy_card, 
            text="Clear All Data", 
            corner_radius=8,
            fg_color="#c53030", 
            hover_color="#9b2c2c",
            command=self.clear_all_data
        )
        clear_button.pack(fill="x", padx=15, pady=(0, 15))
        
        # Advanced settings card
        advanced_card = ctk.CTkFrame(tab, corner_radius=10, fg_color="#1a1a2e", border_width=1, border_color="#2a2a3a")
        advanced_card.pack(fill="x", padx=0, pady=10)

        
        advanced_title = ctk.CTkLabel(advanced_card, text="Advanced Settings", font=("Helvetica", 18, "bold"), text_color="#ffffff")
        advanced_title.pack(anchor="w", padx=15, pady=(15, 5))
        
        advanced_desc = ctk.CTkLabel(advanced_card, text="Configure technical aspects of Dexa", font=("Helvetica", 12), text_color="#9ca3af")
        advanced_desc.pack(anchor="w", padx=15, pady=(0, 15))
        
        # Two-column layout for advanced settings
        adv_frame = ctk.CTkFrame(advanced_card, fg_color="transparent")
        adv_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        adv_frame.grid_columnconfigure(0, weight=1)
        adv_frame.grid_columnconfigure(1, weight=1)
        
        # Speech recognition engine
        recog_frame = ctk.CTkFrame(adv_frame, fg_color="transparent")
        recog_frame.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="ew")
        
        recog_label = ctk.CTkLabel(recog_frame, text="Speech Recognition Engine", font=("Helvetica", 12), text_color="#ffffff")
        recog_label.pack(anchor="w", pady=(0, 5))
        
        self.recog_var = ctk.StringVar(value=self.settings.get("speech_recognition_engine", "sphinx"))
        recog_menu = ctk.CTkOptionMenu(
            recog_frame, 
            values=["sphinx", "google", "vosk"],
            variable=self.recog_var,
            command=self.update_recognition_engine,
            fg_color="#252542",
            button_color="#252542",
            button_hover_color="#2a2a4a",
            dropdown_fg_color="#252542",
            dropdown_hover_color="#2a2a4a"
        )
        recog_menu.pack(fill="x")
        
        # Speech synthesis engine
        synth_frame = ctk.CTkFrame(adv_frame, fg_color="transparent")
        synth_frame.grid(row=0, column=1, padx=(10, 0), pady=5, sticky="ew")
        
        synth_label = ctk.CTkLabel(synth_frame, text="Speech Synthesis Engine", font=("Helvetica", 12), text_color="#ffffff")
        synth_label.pack(anchor="w", pady=(0, 5))
        
        self.synth_var = ctk.StringVar(value=self.settings.get("speech_synthesis_engine", "pyttsx3"))
        synth_menu = ctk.CTkOptionMenu(
            synth_frame, 
            values=["pyttsx3", "system"],
            variable=self.synth_var,
            command=self.update_synthesis_engine,
            fg_color="#252542",
            button_color="#252542",
            button_hover_color="#2a2a4a",
            dropdown_fg_color="#252542",
            dropdown_hover_color="#2a2a4a"
        )
        synth_menu.pack(fill="x")

    def create_learn_tab(self):
        """Create the learn tab content"""
        tab = self.tabview.tab("Learn")
        
        # Teach Dexa card
        teach_card = ctk.CTkFrame(tab, corner_radius=10, fg_color="#1a1a2e", border_width=1, border_color="#2a2a3a")
        teach_card.pack(fill="both", expand=True, pady=(0, 10))
        
        teach_title = ctk.CTkLabel(teach_card, text="Teach Dexa New Commands", font=("Helvetica", 18, "bold"), text_color="#ffffff")
        teach_title.pack(anchor="w", padx=15, pady=(15, 5))
        
        teach_desc = ctk.CTkLabel(teach_card, text="Create custom voice commands", font=("Helvetica", 12), text_color="#9ca3af")
        teach_desc.pack(anchor="w", padx=15, pady=(0, 15))
        
        # Command creation form
        form_frame = ctk.CTkFrame(teach_card, fg_color="transparent")
        form_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        form_frame.grid_columnconfigure(0, weight=1)
        form_frame.grid_columnconfigure(1, weight=1)
        
        # When I say...
        say_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        say_frame.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="ew")
        
        say_label = ctk.CTkLabel(say_frame, text="When I say...", font=("Helvetica", 12), text_color="#ffffff")
        say_label.pack(anchor="w", pady=(0, 5))
        
        self.command_phrase = ctk.CTkEntry(
            say_frame, 
            height=35,
            corner_radius=8,
            fg_color="#252542",
            border_color="#2a2a3a",
            placeholder_text="Enter voice command..."
        )
        self.command_phrase.pack(fill="x")
        
        say_example = ctk.CTkLabel(say_frame, text='Example: "Open my documents"', font=("Helvetica", 10), text_color="#9ca3af")
        say_example.pack(anchor="w", pady=(5, 0))
        
        # Dexa should...
        action_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        action_frame.grid(row=0, column=1, padx=(10, 0), pady=5, sticky="ew")
        
        action_label = ctk.CTkLabel(action_frame, text="Dexa should...", font=("Helvetica", 12), text_color="#ffffff")
        action_label.pack(anchor="w", pady=(0, 5))
        
        self.action_var = ctk.StringVar(value="app")
        action_menu = ctk.CTkOptionMenu(
            action_frame, 
            values=["app", "website", "folder", "command", "text", "say"],
            variable=self.action_var,
            command=self.update_action_type,
            fg_color="#252542",
            button_color="#252542",
            button_hover_color="#2a2a4a",
            dropdown_fg_color="#252542",
            dropdown_hover_color="#2a2a4a"
        )
        action_menu.pack(fill="x")
        
        # Action details
        details_frame = ctk.CTkFrame(teach_card, fg_color="transparent")
        details_frame.pack(fill="x", padx=15, pady=5)
        
        details_label = ctk.CTkLabel(details_frame, text="Action Details", font=("Helvetica", 12), text_color="#ffffff")
        details_label.pack(anchor="w", pady=(0, 5))
        
        details_input_frame = ctk.CTkFrame(details_frame, fg_color="transparent")
        details_input_frame.pack(fill="x")
        
        self.action_details = ctk.CTkEntry(
            details_input_frame, 
            height=35,
            corner_radius=8,
            fg_color="#252542",
            border_color="#2a2a3a",
            placeholder_text="Enter path, URL, or text..."
        )
        self.action_details.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        browse_button = ctk.CTkButton(
            details_input_frame, 
            text="Browse...", 
            width=80,
            corner_radius=8,
            fg_color="#252542", 
            hover_color="#2a2a4a",
            command=self.browse_action
        )
        browse_button.pack(side="right")
        
        details_example = ctk.CTkLabel(
            details_frame, 
            text='Example: "C:\\Program Files\\Mozilla Firefox\\firefox.exe"', 
            font=("Helvetica", 10), 
            text_color="#9ca3af"
        )
        details_example.pack(anchor="w", pady=(5, 0))
        
        # Buttons
        buttons_frame = ctk.CTkFrame(teach_card, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=15, pady=10)
        
        cancel_button = ctk.CTkButton(
            buttons_frame, 
            text="Cancel", 
            width=80,
            corner_radius=8,
            fg_color="#252542", 
            hover_color="#2a2a4a",
            command=self.clear_command_form
        )
        cancel_button.pack(side="right", padx=(5, 0))
        
        save_button = ctk.CTkButton(
            buttons_frame, 
            text="Save Command", 
            corner_radius=8,
            fg_color="#06b6d4", 
            hover_color="#0891b2",
            command=self.save_command
        )
        save_button.pack(side="right")
        
        # Unrecognized commands card
        unrec_card = ctk.CTkFrame(tab, corner_radius=10, fg_color="#1a1a2e", border_width=1, border_color="#2a2a3a")
        unrec_card.pack(fill="both", expand=True)
        
        unrec_title = ctk.CTkLabel(unrec_card, text="Unrecognized Commands", font=("Helvetica", 18, "bold"), text_color="#ffffff")
        unrec_title.pack(anchor="w", padx=15, pady=(15, 5))
        
        unrec_desc = ctk.CTkLabel(unrec_card, text="Commands Dexa didn't understand", font=("Helvetica", 12), text_color="#9ca3af")
        unrec_desc.pack(anchor="w", padx=15, pady=(0, 15))
        
        # Scrollable area for unrecognized commands
        unrec_frame = ctk.CTkScrollableFrame(unrec_card, fg_color="transparent", height=200)
        unrec_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        self.unrec_frame = unrec_frame
        
        # Sample unrecognized commands
        unrecognized = ["Open my documents", "Show me the news", "What's on my schedule", "Turn off the lights"]
        
        for cmd in unrecognized:
            cmd_frame = ctk.CTkFrame(unrec_frame, corner_radius=8, fg_color="#252542", border_width=1, border_color="#2a2a3a")
            cmd_frame.pack(fill="x", pady=2)
            
            cmd_label = ctk.CTkLabel(cmd_frame, text=f'"{cmd}"', font=("Helvetica", 12), text_color="#ffffff")
            cmd_label.pack(side="left", padx=10, pady=8)
            
            teach_button = ctk.CTkButton(
                cmd_frame, 
                text="Teach Dexa", 
                width=100,
                height=28,
                corner_radius=8,
                fg_color="#06b6d4", 
                hover_color="#0891b2",
                command=lambda c=cmd: self.teach_unrecognized(c)
            )
            teach_button.pack(side="right", padx=10, pady=8)

    def create_advanced_tab(self):
        """Create the advanced tab with JARVIS-inspired features"""
        tab = self.tabview.tab("Advanced")
    
        # Use a scrollable frame inside the tab
        scroll_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)
    
        # All content goes inside scroll_frame now
    
        # Optional: you can keep this or delete
        # my_card = ctk.CTkFrame(scroll_frame, corner_radius=10)
        # my_card.pack(pady=10)
    
        # Replace the two-column layout with pack (no grid!)
        left_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        left_frame.pack(fill="both", expand=True, pady=(0, 10))
    
        right_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        right_frame.pack(fill="both", expand=True, pady=(0, 10))
    
        # --- EXAMPLE: Dictation card inside left_frame ---
        dictation_card = ctk.CTkFrame(left_frame, corner_radius=10, fg_color="#1a1a2e", border_width=1, border_color="#2a2a3a")
        dictation_card.pack(fill="both", expand=True, pady=(0, 10))
    
        dictation_title = ctk.CTkLabel(dictation_card, text="Voice Dictation", font=("Helvetica", 18, "bold"), text_color="#ffffff")
        dictation_title.pack(anchor="w", padx=15, pady=(15, 5))

        
        dictation_desc = ctk.CTkLabel(dictation_card, text="Transcribe speech to text files", font=("Helvetica", 12), text_color="#9ca3af")
        dictation_desc.pack(anchor="w", padx=15, pady=(0, 15))
        
        # Dictation settings
        dictation_settings_frame = ctk.CTkFrame(dictation_card, fg_color="transparent")
        dictation_settings_frame.pack(fill="x", padx=15, pady=5)
        
        dictation_duration_label = ctk.CTkLabel(dictation_settings_frame, text="Dictation Duration (seconds)", font=("Helvetica", 12), text_color="#ffffff")
        dictation_duration_label.pack(anchor="w", pady=(0, 5))
        
        self.dictation_duration_var = ctk.IntVar(value=30)
        dictation_duration_slider = ctk.CTkSlider(
            dictation_settings_frame, 
            from_=10, 
            to=120, 
            variable=self.dictation_duration_var,
            progress_color="#06b6d4",
            button_color="#06b6d4",
            button_hover_color="#0891b2"
        )
        dictation_duration_slider.pack(fill="x")
        
        dictation_duration_value = ctk.CTkLabel(dictation_settings_frame, text=f"{self.dictation_duration_var.get()} seconds", font=("Helvetica", 10), text_color="#9ca3af")
        dictation_duration_value.pack(anchor="e", pady=(5, 0))
        
        # Update duration label when slider changes
        def update_duration_label(value):
            dictation_duration_value.configure(text=f"{int(value)} seconds")
        
        dictation_duration_slider.configure(command=update_duration_label)
        
        # Dictation buttons
        dictation_buttons_frame = ctk.CTkFrame(dictation_card, fg_color="transparent")
        dictation_buttons_frame.pack(fill="x", padx=15, pady=15)
        
        start_dictation_button = ctk.CTkButton(
            dictation_buttons_frame, 
            text="Start Dictation", 
            corner_radius=8,
            fg_color="#06b6d4", 
            hover_color="#0891b2",
            command=lambda: self.dictate_to_file(self.dictation_duration_var.get())
        )
        start_dictation_button.pack(fill="x")
        
        # Resource monitoring card
        monitor_card = ctk.CTkFrame(left_frame, corner_radius=10, fg_color="#1a1a2e", border_width=1, border_color="#2a2a3a")
        monitor_card.pack(fill="both", expand=True)
        
        monitor_title = ctk.CTkLabel(monitor_card, text="Resource Monitoring", font=("Helvetica", 18, "bold"), text_color="#ffffff")
        monitor_title.pack(anchor="w", padx=15, pady=(15, 5))
        
        monitor_desc = ctk.CTkLabel(monitor_card, text="Monitor system resources and get alerts", font=("Helvetica", 12), text_color="#9ca3af")
        monitor_desc.pack(anchor="w", padx=15, pady=(0, 15))
        
        # Monitoring settings
        monitor_settings_frame = ctk.CTkFrame(monitor_card, fg_color="transparent")
        monitor_settings_frame.pack(fill="x", padx=15, pady=5)
        
        # Threshold setting
        threshold_label = ctk.CTkLabel(monitor_settings_frame, text="Alert Threshold (%)", font=("Helvetica", 12), text_color="#ffffff")
        threshold_label.pack(anchor="w", pady=(0, 5))
        
        self.threshold_var = ctk.IntVar(value=90)
        threshold_slider = ctk.CTkSlider(
            monitor_settings_frame, 
            from_=50, 
            to=95, 
            variable=self.threshold_var,
            progress_color="#06b6d4",
            button_color="#06b6d4",
            button_hover_color="#0891b2"
        )
        threshold_slider.pack(fill="x")
        
        threshold_value = ctk.CTkLabel(monitor_settings_frame, text=f"{self.threshold_var.get()}%", font=("Helvetica", 10), text_color="#9ca3af")
        threshold_value.pack(anchor="e", pady=(5, 0))
        
        # Update threshold label when slider changes
        def update_threshold_label(value):
            threshold_value.configure(text=f"{int(value)}%")
        
        threshold_slider.configure(command=update_threshold_label)
        
        # Duration setting
        duration_label = ctk.CTkLabel(monitor_settings_frame, text="Monitoring Duration (seconds)", font=("Helvetica", 12), text_color="#ffffff")
        duration_label.pack(anchor="w", pady=(10, 5))
        
        self.monitor_duration_var = ctk.IntVar(value=60)
        duration_slider = ctk.CTkSlider(
            monitor_settings_frame, 
            from_=30, 
            to=300, 
            variable=self.monitor_duration_var,
            progress_color="#06b6d4",
            button_color="#06b6d4",
            button_hover_color="#0891b2"
        )
        duration_slider.pack(fill="x")
        
        duration_value = ctk.CTkLabel(monitor_settings_frame, text=f"{self.monitor_duration_var.get()} seconds", font=("Helvetica", 10), text_color="#9ca3af")
        duration_value.pack(anchor="e", pady=(5, 0))
        
        # Update duration label when slider changes
        def update_monitor_duration_label(value):
            duration_value.configure(text=f"{int(value)} seconds")
        
        duration_slider.configure(command=update_monitor_duration_label)
        
        # Start monitoring button
        start_monitor_button = ctk.CTkButton(
            monitor_card, 
            text="Start Monitoring", 
            corner_radius=8,
            fg_color="#06b6d4", 
            hover_color="#0891b2",
            command=lambda: self.monitor_resources(self.threshold_var.get(), self.monitor_duration_var.get())
        )
        start_monitor_button.pack(fill="x", padx=15, pady=15)
        
        # Screen recording card
        recording_card = ctk.CTkFrame(right_frame, corner_radius=10, fg_color="#1a1a2e", border_width=1, border_color="#2a2a3a")
        recording_card.pack(fill="both", expand=True, pady=(0, 10))
        
        recording_title = ctk.CTkLabel(recording_card, text="Screen Recording", font=("Helvetica", 18, "bold"), text_color="#ffffff")
        recording_title.pack(anchor="w", padx=15, pady=(15, 5))
        
        recording_desc = ctk.CTkLabel(recording_card, text="Record your screen with voice commands", font=("Helvetica", 12), text_color="#9ca3af")
        recording_desc.pack(anchor="w", padx=15, pady=(0, 15))
        
        # Recording status
        recording_status_frame = ctk.CTkFrame(recording_card, fg_color="#252542", corner_radius=8)
        recording_status_frame.pack(fill="x", padx=15, pady=5)
        
        recording_status_label = ctk.CTkLabel(recording_status_frame, text="Status:", font=("Helvetica", 12), text_color="#ffffff")
        recording_status_label.pack(side="left", padx=10, pady=10)
        
        self.recording_status_value = ctk.CTkLabel(recording_status_frame, text="Not Recording", font=("Helvetica", 12, "bold"), text_color="#ef4444")
        self.recording_status_value.pack(side="left", padx=5, pady=10)
        
        # Recording buttons
        recording_buttons_frame = ctk.CTkFrame(recording_card, fg_color="transparent")
        recording_buttons_frame.pack(fill="x", padx=15, pady=15)
        
        start_recording_button = ctk.CTkButton(
            recording_buttons_frame, 
            text="Start Recording", 
            corner_radius=8,
            fg_color="#06b6d4", 
            hover_color="#0891b2",
            command=lambda: self.screen_recording("start")
        )
        start_recording_button.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        stop_recording_button = ctk.CTkButton(
            recording_buttons_frame, 
            text="Stop Recording", 
            corner_radius=8,
            fg_color="#ef4444", 
            hover_color="#c53030",
            command=lambda: self.screen_recording("stop")
        )
        stop_recording_button.pack(side="right", fill="x", expand=True, padx=(5, 0))
        
        # Task scheduler card
        task_card = ctk.CTkFrame(right_frame, corner_radius=10, fg_color="#1a1a2e", border_width=1, border_color="#2a2a3a")
        task_card.pack(fill="both", expand=True)
        
        task_title = ctk.CTkLabel(task_card, text="Task Scheduler", font=("Helvetica", 18, "bold"), text_color="#ffffff")
        task_title.pack(anchor="w", padx=15, pady=(15, 5))
        
        task_desc = ctk.CTkLabel(task_card, text="Schedule reminders and tasks", font=("Helvetica", 12), text_color="#9ca3af")
        task_desc.pack(anchor="w", padx=15, pady=(0, 15))
        
        # Task form
        task_form_frame = ctk.CTkFrame(task_card, fg_color="transparent")
        task_form_frame.pack(fill="x", padx=15, pady=5)
        
        task_label = ctk.CTkLabel(task_form_frame, text="Task Description", font=("Helvetica", 12), text_color="#ffffff")
        task_label.pack(anchor="w", pady=(0, 5))
        
        self.task_entry = ctk.CTkEntry(
            task_form_frame, 
            height=35,
            corner_radius=8,
            fg_color="#252542",
            border_color="#2a2a3a",
            placeholder_text="Enter task description..."
        )
        self.task_entry.pack(fill="x")
        
        # Time settings
        time_frame = ctk.CTkFrame(task_card, fg_color="transparent")
        time_frame.pack(fill="x", padx=15, pady=10)
        
        time_label = ctk.CTkLabel(time_frame, text="Remind in (minutes)", font=("Helvetica", 12), text_color="#ffffff")
        time_label.pack(anchor="w", pady=(0, 5))
        
        self.time_var = ctk.IntVar(value=5)
        time_slider = ctk.CTkSlider(
            time_frame, 
            from_=1, 
            to=60, 
            variable=self.time_var,
            progress_color="#06b6d4",
            button_color="#06b6d4",
            button_hover_color="#0891b2"
        )
        time_slider.pack(fill="x")
        
        time_value = ctk.CTkLabel(time_frame, text=f"{self.time_var.get()} minutes", font=("Helvetica", 10), text_color="#9ca3af")
        time_value.pack(anchor="e", pady=(5, 0))
        
        # Update time label when slider changes
        def update_time_label(value):
            time_value.configure(text=f"{int(value)} minutes")
        
        time_slider.configure(command=update_time_label)
        
        # Schedule button
        schedule_button = ctk.CTkButton(
            task_card, 
            text="Schedule Task", 
            corner_radius=8,
            fg_color="#06b6d4", 
            hover_color="#0891b2",
            command=self.schedule_task_from_ui
        )
        schedule_button.pack(fill="x", padx=15, pady=15)
        
        # Active tasks
        active_label = ctk.CTkLabel(task_card, text="Active Tasks", font=("Helvetica", 12, "bold"), text_color="#ffffff")
        active_label.pack(anchor="w", padx=15, pady=(0, 5))
        
        # Scrollable area for active tasks
        self.active_tasks_frame = ctk.CTkScrollableFrame(task_card, fg_color="transparent", height=100)
        self.active_tasks_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # Add a placeholder if no tasks
        no_tasks_label = ctk.CTkLabel(self.active_tasks_frame, text="No active tasks", font=("Helvetica", 10), text_color="#9ca3af")
        no_tasks_label.pack(pady=10)

    def create_footer(self):
        """Create the footer section of the UI"""
        # Footer frame
        footer = ctk.CTkFrame(self.main_frame, fg_color="#0f0f17", height=30)
        footer.pack(fill="x")
        footer.pack_propagate(False)
        
        # Version info
        version_label = ctk.CTkLabel(footer, text="DexaAI v2.0.0 | Offline Mode", font=("Helvetica", 10), text_color="#9ca3af")
        version_label.pack(side="left", padx=15)
        
        # Copyright
        copyright_label = ctk.CTkLabel(footer, text="© 2025 DexaAI", font=("Helvetica", 10), text_color="#9ca3af")
        copyright_label.pack(side="right", padx=15)

    def toggle_listening(self):
        """Toggle listening state"""
        if self.is_listening:
            self.stop_listening()
        else:
            self.start_listening()

    def toggle_background_listening(self):
        """Toggle background listening setting"""
        enabled = self.bg_listen_switch.get() == 1
        self.settings["background_listening"] = enabled
        
        # Update both switches to be in sync
        if self.bg_listen_settings_switch.get() != enabled:
            if enabled:
                self.bg_listen_settings_switch.select()
            else:
                self.bg_listen_settings_switch.deselect()
        
        self.save_settings()
        
        if enabled:
            if self.settings.get("wake_word_enabled", True):
                self.start_background_listening()
            self.speak("Background listening enabled")
            logger.info("Background listening enabled")
        else:
            self.stop_background_listening()
            self.speak("Background listening disabled")
            logger.info("Background listening disabled")

    def start_listening(self):
        """Start active listening for commands"""
        if self.is_listening:
            return
            
        self.is_listening = True
        self.status_label.configure(text="Listening")
        self.status_indicator.configure(fg_color="#22c55e")  # Green
        self.activation_status.configure(text="Listening...")
        self.activation_desc.configure(text="Speak your command now")
        self.activation_button.configure(fg_color="#22c55e")
        
        # Show waveform
        self.home_waveform.pack(pady=10)
        self.home_waveform.start_animation()
        
        # Show popup
        self.popup.show_listening()
        
        # Start listening in a separate thread
        self.listening_thread = threading.Thread(target=self.listen_for_command)
        self.listening_thread.daemon = True
        self.listening_thread.start()
        
        logger.info("Listening started")

    def stop_listening(self):
        """Stop active listening"""
        if not self.is_listening:
            return
            
        self.is_listening = False
        self.status_label.configure(text="Idle")
        self.status_indicator.configure(fg_color="#3b82f6")  # Blue
        self.activation_status.configure(text="Click to activate Dexa")
        self.activation_desc.configure(text=f'Or say "{self.settings["wake_word"]}" to activate with your voice')
        self.activation_button.configure(fg_color="#06b6d4")
        
        # Hide waveform
        self.home_waveform.stop_animation()
        self.home_waveform.pack_forget()
        
        # Hide popup after a delay
        self.after(1000, self.popup.hide)
        
        logger.info("Listening stopped")

    def listen_for_command(self):
        """Listen for a voice command and process it"""
        try:
            with self.microphone_lock:  # Use lock to prevent concurrent access
                # Create a new recognizer instance each time
                recognizer = sr.Recognizer()
                
                # Adjust energy threshold based on sensitivity setting
                # Lower threshold for better recognition
                base_energy = 3000  # Reduced from 4000
                sensitivity_factor = 1.0 - (self.settings.get("sensitivity", 70) / 100.0)  # Invert so higher sensitivity = lower threshold
                recognizer.energy_threshold = base_energy * sensitivity_factor
                recognizer.dynamic_energy_threshold = True
                
                # Increase pause threshold for better phrase detection
                recognizer.pause_threshold = 0.8  # Default is 0.8, increased for better phrase completion
                
                # Create a new microphone instance each time
                with sr.Microphone() as source:
                    logger.debug("Adjusting for ambient noise")
                    recognizer.adjust_for_ambient_noise(source, duration=1.0)  # Increased from 0.5 to 1.0
                    logger.debug("Listening for command")
                    try:
                        # Increased timeout and phrase_time_limit for better recognition
                        audio = recognizer.listen(source, timeout=8, phrase_time_limit=10)
                    except sr.WaitTimeoutError:
                        logger.warning("No speech detected within timeout")
                        self.after(0, lambda: self.popup.show_responding("I didn't hear anything. Please try again."))
                        self.after(2000, self.stop_listening)
                        return
            
            # Show processing state
            self.after(0, lambda: self.popup.show_processing())
            
            try:
                # Recognize speech
                text = ""
                if self.settings["speech_recognition_engine"] == "sphinx":
                    # Try Google first if available (better accuracy), fall back to Sphinx
                    try:
                        text = recognizer.recognize_google(audio).lower()
                        logger.info(f"Recognized with Google: {text}")
                    except (sr.RequestError, Exception) as e:
                        logger.warning(f"Google recognition failed, falling back to Sphinx: {e}")
                        text = recognizer.recognize_sphinx(audio).lower()
                        logger.info(f"Recognized with Sphinx: {text}")
                else:
                    text = recognizer.recognize_google(audio).lower()
                    logger.info(f"Recognized with Google: {text}")
                
                # Process command
                self.process_command(text)
            except sr.UnknownValueError:
                logger.warning("Speech not recognized")
                response = "Sorry, I didn't understand that. Could you please speak more clearly?"
                self.after(0, lambda: self.popup.show_responding(response))
                self.speak(response)
            except sr.RequestError as e:
                logger.error(f"Speech recognition service error: {e}")
                response = "Sorry, I'm having trouble processing your request. Please try again."
                self.after(0, lambda: self.popup.show_responding(response))
                self.speak(response)
        except Exception as e:
            logger.error(f"Error in listen_for_command: {e}")
            print(f"Error in listen_for_command: {e}")
        finally:
            # Stop listening after processing
            self.after(2000, self.stop_listening)

    def process_command(self, text):
        """Process a voice command and execute appropriate action"""
        # Log the command
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        logger.info(f"Processing command: {text}")
        
        # Check if command matches any known commands
        response = "I don't know how to do that yet."
        executed = False
        
        # Try exact matches first
        for cmd, details in self.commands.items():
            if text.startswith(cmd):
                # Handle dynamic commands (like "search for X")
                if details.get("params", {}).get("dynamic", False):
                    param = text[len(cmd):].strip()
                    if param:
                        response = self.execute_action(details["action"], {**details["params"], "query": param})
                        executed = True
                else:
                    # Handle static commands
                    response = self.execute_action(details["action"], details.get("params", {}))
                    executed = True
                break
        
        # If no exact match, try fuzzy matching with a lower threshold (more permissive)
        if not executed:
            best_matches = process.extractBests(text, self.commands.keys(), scorer=fuzz.ratio, score_cutoff=60, limit=3)
            if best_matches:
                best_match, score = best_matches[0]
                logger.info(f"Fuzzy matched '{text}' to '{best_match}' with score {score}")
                
                # If score is high enough, execute the command
                if score >= 60:
                    details = self.commands[best_match]
                    response = self.execute_action(details["action"], details.get("params", {}))
                    executed = True
                    
                    # If score is lower, confirm with the user
                    if score < 75:
                        response = f"I think you said '{best_match}'. {response}"
            
            # If still not executed, try advanced pattern matching (JARVIS-style)
            if not executed:
                response = self.advanced_command_processing(text)
                executed = response != "I don't know how to do that yet."
        
        # Add to log
        self.add_log_entry(timestamp, text, response)
        
        # Show response in popup
        self.after(0, lambda: self.popup.show_responding(response))
        
        # Speak response
        self.speak(response)
        
        # If not executed and save_command_history is enabled, add to unrecognized commands
        if not executed and self.settings.get("save_command_history", True):
            self.add_unrecognized_command(text)

    def advanced_command_processing(self, command):
        """Process commands using advanced pattern matching (JARVIS-style)"""
        # Time and date
        if re.search(r'time', command) and re.search(r'what', command):
            current_time = datetime.datetime.now().strftime('%I:%M %p')
            return f"The current time is {current_time}"
            
        elif re.search(r'date', command) and re.search(r'what', command):
            current_date = datetime.datetime.now().strftime('%A, %B %d, %Y')
            return f"Today is {current_date}"
        
        # Wikipedia and web search
        elif re.search(r'who is|what is', command):
            query = re.sub(r'who is|what is', '', command).strip()
            try:
                info = wikipedia.summary(query, sentences=2)
                return info
            except:
                webbrowser.open(f'https://www.google.com/search?q={query}')
                return f"I've searched the web for information about {query}"
        
        # Web search
        elif re.search(r'search|google', command):
            query = re.sub(r'search|google|for', '', command).strip()
            webbrowser.open(f'https://www.google.com/search?q={query}')
            return f"Searching for {query}"
        
        # Open website
        elif re.search(r'open website|go to', command):
            site = re.sub(r'open website|go to', '', command).strip()
            
            # Add https:// if not present
            if not site.startswith('http'):
                site = 'https://' + site
                
            # Add .com if no domain extension
            if '.' not in site.split('/')[-1]:
                site += '.com'
                
            webbrowser.open(site)
            return f"Opening {site}"
        
        # Lock screen
        elif re.search(r'lock', command) and re.search(r'screen|computer', command):
            try:
                windll.user32.LockWorkStation()
                return "Computer locked"
            except Exception as e:
                return f"Error locking computer: {e}"
        
        # System shutdown/restart
        elif re.search(r'shutdown computer|turn off computer', command):
            os.system("shutdown /s /t 60")
            return "Shutting down your computer in 60 seconds. Say 'cancel shutdown' to abort."
            
        elif re.search(r'restart computer|reboot computer', command):
            os.system("shutdown /r /t 60")
            return "Restarting your computer in 60 seconds. Say 'cancel shutdown' to abort."
            
        elif re.search(r'cancel shutdown|abort shutdown|cancel restart', command):
            os.system("shutdown /a")
            return "Shutdown or restart cancelled."
        
        # Set reminders
        elif re.search(r'remind me|set reminder', command):
            reminder_text = re.sub(r'remind me|set reminder|to|in', '', command).strip()
            
            # Try to extract time information
            time_match = re.search(r'(\d+)\s*(minute|minutes|min|mins)', command)
            if time_match:
                minutes = int(time_match.group(1))
                self.schedule_task(reminder_text, minutes)
                return f"I'll remind you about {reminder_text} in {minutes} minutes"
            else:
                self.schedule_task(reminder_text, 5)  # Default 5 minutes
                return f"I'll remind you about {reminder_text} in 5 minutes"
        
        # Dictation
        elif re.search(r'dictate|transcribe|take notes', command):
            duration_match = re.search(r'(\d+)\s*(second|seconds|minute|minutes)', command)
            if duration_match:
                value = int(duration_match.group(1))
                unit = duration_match.group(2)
                
                if unit.startswith('minute'):
                    duration = value * 60
                else:
                    duration = value
                    
                self.dictate_to_file(duration)
                return f"Starting dictation for {duration} seconds"
            else:
                self.dictate_to_file()  # Default duration
                return "Starting dictation for 30 seconds"
        
        # Resource monitoring
        elif re.search(r'monitor (system|resources|computer)', command):
            threshold_match = re.search(r'threshold (\d+)', command)
            duration_match = re.search(r'for (\d+) (second|seconds|minute|minutes)', command)
            
            threshold = 90  # Default
            duration = 60   # Default
            
            if threshold_match:
                threshold = int(threshold_match.group(1))
            
            if duration_match:
                value = int(duration_match.group(1))
                unit = duration_match.group(2)
                
                if unit.startswith('minute'):
                    duration = value * 60
                else:
                    duration = value
            
            self.monitor_resources(threshold, duration)
            return f"Monitoring system resources for {duration} seconds with {threshold}% threshold"
        
            # Notes functionality
        elif re.search(r'create note|make note|take note', command):
                # Extract title and content
                title_match = re.search(r'title(?:d)?\s+(.+?)(?:\s+content|\s+saying|\s+with|\s+that says|\s+$)', command)
                content_match = re.search(r'(?:content|saying|with|that says)\s+(.+)', command)
                
                title = title_match.group(1) if title_match else f"Note_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
                content = content_match.group(1) if content_match else "Empty note"
                
                filepath = self.notes_manager.create_note(title, content)
                if filepath:
                    return f"Note created with title: {title}"
                else:
                    return "Failed to create note"
                    
        elif re.search(r'read note|show note|open note', command):
                title = re.sub(r'read note|show note|open note|titled|called', '', command).strip()
                if not title:
                    return "Please specify a note title"
                    
                content = self.notes_manager.get_note(title)
                if content:
                    return f"Here's your note: {content}"
                else:
                    return f"I couldn't find a note with title {title}"
                    
        elif re.search(r'list notes|show all notes|what notes', command):
                notes = self.notes_manager.list_notes()
                if notes:
                    return f"You have {len(notes)} notes: {', '.join(notes)}"
                else:
                    return "You don't have any notes yet"
                    
        elif re.search(r'delete note|remove note', command):
                title = re.sub(r'delete note|remove note|titled|called', '', command).strip()
                if not title:
                    return "Please specify a note title to delete"
                    
                success = self.notes_manager.delete_note(title)
                if success:
                    return f"Note {title} deleted"
                else:
                    return f"I couldn't find a note with title {title} to delete"
        
        # Open folder
        elif re.search(r'open folder|open directory', command):
            folder_name = re.sub(r'open folder|open directory', '', command).strip()
            if not folder_name:
                return "Please specify a folder name"
                
            # Search for folder in common locations
            folder_path = self.find_folder(folder_name)
            if folder_path:
                try:
                    if platform.system() == 'Windows':
                        subprocess.run(['explorer', folder_path], check=True)
                    elif platform.system() == 'Darwin':  # macOS
                        subprocess.run(['open', folder_path], check=True)
                    else:  # Linux
                        subprocess.run(['xdg-open', folder_path], check=True)
                        
                    return f"Opening folder {os.path.basename(folder_path)}"
                except Exception as e:
                    return f"Error opening folder: {e}"
            else:
                return f"I couldn't find a folder named {folder_name}"
        
        # Default response
        return "I don't know how to do that yet."

    def execute_action(self, action, params):
        """Execute an action based on the command"""
        try:
            if action == "say_time":
                now = datetime.datetime.now()
                return f"It's {now.strftime('%I:%M %p')}."
            
            elif action == "say_day":
                now = datetime.datetime.now()
                return f"Today is {now.strftime('%A, %B %d')}."
            
            elif action == "open_app":
                app = params.get("app", "")
                if app:
                    subprocess.Popen(app, shell=True)
                    return f"Opening {app}."
                return "No application specified."
            
            elif action == "check_battery":
                battery = psutil.sensors_battery()
                if battery:
                    percent = battery.percent
                    plugged = battery.power_plugged
                    status = "plugged in" if plugged else "not plugged in"
                    return f"Battery is at {percent}% and {status}."
                return "Battery information not available."
            
            elif action == "take_screenshot":
                filename = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                screenshot = pyautogui.screenshot()
                screenshot.save(filename)
                return f"Screenshot saved as {filename}."
            
            elif action == "mute_volume":
                if self.volume_interface:
                    mute_state = self.volume_interface.GetMute()
                    self.volume_interface.SetMute(not mute_state, None)
                    state = "muted" if not mute_state else "unmuted"
                    return f"Volume {state}."
                else:
                    # Fallback to pyautogui
                    pyautogui.press('volumemute')
                    return "Volume toggled."
            
            elif action == "shutdown_pc":
                os.system("shutdown /s /t 60")
                return "Shutting down your PC in 60 seconds. Say 'cancel shutdown' to abort."
            
            elif action == "search_web":
                query = params.get("query", "")
                if query:
                    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
                    webbrowser.open(url)
                    return f"Searching for {query}."
                return "No search query specified."
                
            elif action == "play_youtube":
                query = params.get("query", "")
                if query:
                    pywhatkit.playonyt(query)
                    return f"Playing {query} on YouTube."
                return "No video specified."
                
            elif action == "search_wikipedia":
                query = params.get("query", "")
                if query:
                    try:
                        info = wikipedia.summary(query, sentences=2)
                        return info
                    except:
                        # Fallback to web search
                        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
                        webbrowser.open(url)
                        return f"I couldn't find specific information, so I searched the web for {query}."
                return "No search query specified."
                
            elif action == "tell_joke":
                jokes = [
                    "Why don't scientists trust atoms? Because they make up everything!",
                    "Why did the scarecrow win an award? Because he was outstanding in his field!",
                    "What do you call a fake noodle? An impasta!",
                    "How does a computer get drunk? It takes screenshots!",
                    "Why don't eggs tell jokes? They'd crack each other up!",
                    "Why was the math book sad? It had too many problems!",
                    "What do you call a bear with no teeth? A gummy bear!",
                    "What's orange and sounds like a parrot? A carrot!",
                    "Why did the bicycle fall over? Because it was two-tired!",
                    "What's the best time to go to the dentist? Tooth-hurty!"
                ]
                return random.choice(jokes)
                
            elif action == "get_system_info":
                cpu_percent = psutil.cpu_percent()
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                disk = psutil.disk_usage('/')
                disk_percent = disk.percent
                battery = psutil.sensors_battery()
                
                info = f"CPU usage is at {cpu_percent}%. Memory usage is at {memory_percent}%. Disk usage is at {disk_percent}%."
                
                if battery:
                    battery_percent = battery.percent
                    plugged = "plugged in" if battery.power_plugged else "not plugged in"
                    info += f" Battery is at {battery_percent}% and is {plugged}."
                    
                return info
                
            elif action == "lock_computer":
                try:
                    windll.user32.LockWorkStation()
                    return "Computer locked."
                except Exception as e:
                    logger.error(f"Error locking computer: {e}")
                    return f"Error locking computer: {e}"
            
            # New JARVIS-inspired actions
            elif action == "screen_recording":
                recording_action = params.get("action", "")
                if recording_action == "start":
                    self.screen_recording("start")
                    return "Screen recording started."
                elif recording_action == "stop":
                    self.screen_recording("stop")
                    return "Screen recording stopped and saved."
                return "Invalid recording action."
                
            elif action == "dictate_to_file":
                duration = params.get("duration", 30)
                self.dictate_to_file(duration)
                return f"Starting dictation for {duration} seconds."
                
            elif action == "monitor_resources":
                threshold = params.get("threshold", 90)
                duration = params.get("duration", 60)
                self.monitor_resources(threshold, duration)
                return f"Monitoring system resources for {duration} seconds with {threshold}% threshold."
                
            elif action == "schedule_task":
                task = params.get("query", "")
                minutes = params.get("minutes", 5)
                if task:
                    self.schedule_task(task, minutes)
                    return f"Task scheduled: {task} in {minutes} minutes."
                return "No task specified."
                
            # New folder and file actions
            elif action == "open_folder":
                folder_name = params.get("query", "")
                if not folder_name:
                    return "Please specify a folder name."
                    
                folder_path = self.find_folder(folder_name)
                if folder_path:
                    try:
                        if platform.system() == 'Windows':
                            subprocess.run(['explorer', folder_path], check=True)
                        elif platform.system() == 'Darwin':  # macOS
                            subprocess.run(['open', folder_path], check=True)
                        else:  # Linux
                            subprocess.run(['xdg-open', folder_path], check=True)
                            
                        return f"Opening folder {os.path.basename(folder_path)}."
                    except Exception as e:
                        return f"Error opening folder: {e}"
                else:
                    return f"I couldn't find a folder named {folder_name}."
                    
            elif action == "open_file":
                file_name = params.get("query", "")
                if not file_name:
                    return "Please specify a file name."
                    
                # Search for file in common locations
                file_path = self.find_file(file_name)
                if file_path:
                    try:
                        os.startfile(file_path)
                        return f"Opening file {os.path.basename(file_path)}."
                    except Exception as e:
                        return f"Error opening file: {e}"
                else:
                    return f"I couldn't find a file named {file_name}."
                    
            # Note actions
            elif action == "create_note":
                note_text = params.get("query", "")
                if not note_text:
                    return "Please provide content for the note."
                    
                # Extract title if provided
                title_match = re.search(r'title(?:d)?\s+(.+?)(?:\s+content|\s+saying|\s+with|\s+that says|\s+$)', note_text)
                content_match = re.search(r'(?:content|saying|with|that says)\s+(.+)', note_text)
                
                title = title_match.group(1) if title_match else f"Note_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
                content = content_match.group(1) if content_match else note_text
                
                filepath = self.notes_manager.create_note(title, content)
                if filepath:
                    return f"Note created with title: {title}."
                else:
                    return "Failed to create note."
                    
            elif action == "read_note":
                title = params.get("query", "")
                if not title:
                    return "Please specify a note title."
                    
                content = self.notes_manager.get_note(title)
                if content:
                    return f"Here's your note: {content}"
                else:
                    return f"I couldn't find a note with title {title}."
                    
            elif action == "list_notes":
                notes = self.notes_manager.list_notes()
                if notes:
                    return f"You have {len(notes)} notes: {', '.join(notes)}."
                else:
                    return "You don't have any notes yet."
                    
            elif action == "delete_note":
                title = params.get("query", "")
                if not title:
                    return "Please specify a note title to delete."
                    
                success = self.notes_manager.delete_note(title)
                if success:
                    return f"Note {title} deleted."
                else:
                    return f"I couldn't find a note with title {title} to delete."
            
            else:
                logger.warning(f"Action {action} not implemented")
                return f"Action {action} not implemented yet."
        
        except Exception as e:
            logger.error(f"Error executing action {action}: {e}")
            return f"Sorry, I encountered an error while executing that command: {e}"

    def speak(self, text):
        """Speak text using the TTS engine"""
        if self.settings.get("response_style", "casual") != "silent":
            logger.info(f"Speaking: {text}")
            
            def _speak():
                try:
                    self.engine.say(text)
                    self.engine.runAndWait()
                except Exception as e:
                    logger.error(f"Error in TTS: {e}")
                    print(f"Error in TTS: {e}")
            
            # Run in a separate thread to avoid blocking the UI
            threading.Thread(target=_speak, daemon=True).start()
        else:
            logger.info(f"Silent mode, not speaking: {text}")

    def add_log_entry(self, timestamp, command, response):
        """Add an entry to the command log"""
        # Create log entry frame
        log_entry = ctk.CTkFrame(self.log_frame, corner_radius=8, fg_color="#252542", border_width=1, border_color="#2a2a3a")
        log_entry.pack(fill="x", pady=2, padx=5)
        
        # Add timestamp
        time_label = ctk.CTkLabel(log_entry, text=timestamp, font=("Helvetica", 10), text_color="#9ca3af")
        time_label.pack(anchor="w", padx=10, pady=(10, 5))
        
        # Add command
        cmd_label = ctk.CTkLabel(log_entry, text=command, font=("Helvetica", 12, "bold"), text_color="#06b6d4")
        cmd_label.pack(anchor="w", padx=10, pady=0)
        
        # Add response
        resp_label = ctk.CTkLabel(log_entry, text=response, font=("Helvetica", 10), text_color="#e5e7eb", wraplength=250)
        resp_label.pack(anchor="w", padx=10, pady=(5, 10))
        
        # Add to command logs
        self.command_logs.insert(0, {"timestamp": timestamp, "command": command, "response": response})
        
        # Limit log size
        if len(self.command_logs) > 50:
            self.command_logs.pop()
            
        logger.debug(f"Added log entry: {timestamp} - {command}")

    def add_unrecognized_command(self, command):
        """Add a command to the unrecognized commands list"""
        # Check if command already exists in the list
        for widget in self.unrec_frame.winfo_children():
            if isinstance(widget, ctk.CTkFrame):
                for child in widget.winfo_children():
                    if isinstance(child, ctk.CTkLabel) and child.cget("text") == f'"{command}"':
                        return  # Command already exists
        
        # Remove "No unrecognized commands" label if it exists
        for widget in self.unrec_frame.winfo_children():
            if isinstance(widget, ctk.CTkLabel) and "No" in widget.cget("text"):
                widget.destroy()
        
        # Create command frame
        cmd_frame = ctk.CTkFrame(self.unrec_frame, corner_radius=8, fg_color="#252542", border_width=1, border_color="#2a2a3a")
        cmd_frame.pack(fill="x", pady=2)
        
        cmd_label = ctk.CTkLabel(cmd_frame, text=f'"{command}"', font=("Helvetica", 12), text_color="#ffffff")
        cmd_label.pack(side="left", padx=10, pady=8)
        
        teach_button = ctk.CTkButton(
            cmd_frame, 
            text="Teach Dexa", 
            width=100,
            height=28,
            corner_radius=8,
            fg_color="#06b6d4", 
            hover_color="#0891b2",
            command=lambda c=command: self.teach_unrecognized(c)
        )
        teach_button.pack(side="right", padx=10, pady=8)
        
        logger.debug(f"Added unrecognized command: {command}")

    def find_folder(self, folder_name):
        """Find a folder by name in common locations"""
        folder_name = folder_name.lower().strip()
        
        # Common locations to search
        search_locations = [
            os.environ['USERPROFILE'],
            os.path.join(os.environ['USERPROFILE'], 'Desktop'),
            os.path.join(os.environ['USERPROFILE'], 'Documents'),
            os.path.join(os.environ['USERPROFILE'], 'Downloads'),
            os.path.join(os.environ['USERPROFILE'], 'Pictures'),
            os.path.join(os.environ['USERPROFILE'], 'OneDrive')
        ]
        
        best_match = None
        highest_score = 0
        
        for location in search_locations:
            if not os.path.exists(location):
                continue
                
            try:
                for item in os.listdir(location):
                    item_path = os.path.join(location, item)
                    if os.path.isdir(item_path):
                        score = fuzz.ratio(folder_name, item.lower())
                        if score > highest_score and score >= 80:
                            highest_score = score
                            best_match = item_path
                            
                            if score >= 95:  # Perfect match
                                return item_path
            except PermissionError:
                continue
        
        return best_match
        
    def find_file(self, file_name):
        """Find a file by name in common locations"""
        file_name = file_name.lower().strip()
        
        # Common locations to search
        search_locations = [
            os.environ['USERPROFILE'],
            os.path.join(os.environ['USERPROFILE'], 'Desktop'),
            os.path.join(os.environ['USERPROFILE'], 'Documents'),
            os.path.join(os.environ['USERPROFILE'], 'Downloads'),
            os.path.join(os.environ['USERPROFILE'], 'Pictures'),
            os.path.join(os.environ['USERPROFILE'], 'OneDrive')
        ]
        
        best_match = None
        highest_score = 0
        
        for location in search_locations:
            if not os.path.exists(location):
                continue
                
            try:
                for item in os.listdir(location):
                    item_path = os.path.join(location, item)
                    if os.path.isfile(item_path):
                        score = fuzz.ratio(file_name, item.lower())
                        if score > highest_score and score >= 80:
                            highest_score = score
                            best_match = item_path
                            
                            if score >= 95:  # Perfect match
                                return item_path
            except PermissionError:
                continue
        
        return best_match

    def refresh_commands(self, search_query=None):
        """Refresh the commands display with optional search filtering"""
        # Clear existing commands
        for widget in self.commands_frame.winfo_children():
            widget.destroy()
        
        # Filter commands if search query is provided
        commands_to_display = {}
        if search_query:
            for phrase, details in self.commands.items():
                if search_query in phrase.lower():
                    commands_to_display[phrase] = details
        else:
            commands_to_display = self.commands
        
        # Add command cards
        if commands_to_display:
            for phrase, details in commands_to_display.items():
                CommandCard(
                    self.commands_frame, 
                    phrase=phrase, 
                    action=details.get("action", ""),
                    edit_callback=self.edit_command,
                    delete_callback=self.delete_command
                ).pack(fill="x", pady=2, padx=5)
        else:
            # Show "No commands found" message
            no_commands_label = ctk.CTkLabel(
                self.commands_frame, 
                text="No commands found", 
                font=("Helvetica", 12), 
                text_color="#9ca3af"
            )
            no_commands_label.pack(pady=20)
            
        logger.debug(f"Refreshed commands display with {len(commands_to_display)} commands")

    def add_command(self):
        """Initiate adding a new command"""
        # Switch to Learn tab
        self.tabview.set("Learn")
        # Clear form
        self.clear_command_form()
        logger.info("Add command initiated")

    def edit_command(self, phrase):
        """Edit an existing command"""
        # Switch to Learn tab
        self.tabview.set("Learn")
        
        # Fill form with command details
        self.command_phrase.delete(0, "end")
        self.command_phrase.insert(0, phrase)
        
        details = self.commands.get(phrase, {})
        action_type = details.get("action", "")
        
        # Map action to form action type
        action_map = {
            "open_app": "app",
            "search_web": "website",
            "say_time": "say",
            "say_day": "say",
        }
        
        form_action = action_map.get(action_type, "command")
        self.action_var.set(form_action)
        
        # Set action details
        params = details.get("params", {})
        if "app" in params:
            self.action_details.delete(0, "end")
            self.action_details.insert(0, params["app"])
        elif "query" in params:
            self.action_details.delete(0, "end")
            self.action_details.insert(0, params["query"])
            
        logger.info(f"Editing command: {phrase}")

    def delete_command(self, phrase):
        """Delete a command"""
        if phrase in self.commands:
            # Ask for confirmation
            confirm = ctk.CTkInputDialog(
                text=f'Are you sure you want to delete the command "{phrase}"?\nType "yes" to confirm.',
                title="Confirm Delete"
            )
            result = confirm.get_input()
            
            if result and result.lower() == "yes":
                del self.commands[phrase]
                self.save_commands()
                self.refresh_commands()
                logger.info(f"Command deleted: {phrase}")

    def save_command(self):
        """Save a new or edited command"""
        phrase = self.command_phrase.get().strip().lower()
        action_type = self.action_var.get()
        details = self.action_details.get().strip()
        
        if not phrase or not details:
            return
        
        # Map form action type to actual action
        action_map = {
            "app": {"action": "open_app", "params": {"app": details}},
            "website": {"action": "search_web", "params": {"query": details}},
            "folder": {"action": "open_folder", "params": {"path": details}},
            "command": {"action": "run_command", "params": {"cmd": details}},
            "text": {"action": "type_text", "params": {"text": details}},
            "say": {"action": "say_text", "params": {"text": details}},
        }
        
        self.commands[phrase] = action_map.get(action_type, {"action": "unknown"})
        self.save_commands()
        self.refresh_commands()
        self.clear_command_form()
        
        # Show confirmation
        self.speak(f"Command {phrase} has been added.")
        logger.info(f"Command saved: {phrase} -> {action_type}")

    def clear_command_form(self):
        """Clear the command form"""
        self.command_phrase.delete(0, "end")
        self.action_var.set("app")
        self.action_details.delete(0, "end")
        logger.debug("Command form cleared")

    def teach_unrecognized(self, command):
        """Teach Dexa an unrecognized command"""
        # Fill the command phrase and switch to Learn tab
        self.tabview.set("Learn")
        self.command_phrase.delete(0, "end")
        self.command_phrase.insert(0, command)
        logger.info(f"Teaching unrecognized command: {command}")

    def update_action_type(self, action_type):
        """Update the action type in the command form"""
        # Update placeholder based on action type
        placeholders = {
            "app": "Enter application path...",
            "website": "Enter website URL...",
            "folder": "Enter folder path...",
            "command": "Enter command to run...",
            "text": "Enter text to type...",
            "say": "Enter text for Dexa to say...",
        }
        
        self.action_details.configure(placeholder_text=placeholders.get(action_type, "Enter details..."))
        logger.debug(f"Action type updated to: {action_type}")

    def browse_action(self):
        """Browse for a file or folder for the command action"""
        action_type = self.action_var.get()
        
        if action_type == "app":
            filename = ctk.filedialog.askopenfilename(
                title="Select Application",
                filetypes=[("Executable files", "*.exe"), ("All files", "*.*")]
            )
            if filename:
                self.action_details.delete(0, "end")
                self.action_details.insert(0, filename)
                logger.info(f"Selected application: {filename}")
        
        elif action_type == "folder":
            folder = ctk.filedialog.askdirectory(title="Select Folder")
            if folder:
                self.action_details.delete(0, "end")
                self.action_details.insert(0, folder)
                logger.info(f"Selected folder: {folder}")

    def import_commands(self):
        """Import commands from a JSON file"""
        filename = ctk.filedialog.askopenfilename(
            title="Import Commands",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, "r") as f:
                    imported_commands = json.load(f)
                    self.commands.update(imported_commands)
                    self.save_commands()
                    self.refresh_commands()
                    self.speak("Commands imported successfully.")
                    logger.info(f"Commands imported from {filename}")
            except Exception as e:
                logger.error(f"Error importing commands: {e}")
                print(f"Error importing commands: {e}")
                self.speak("Error importing commands.")

    def export_commands(self):
        """Export commands to a JSON file"""
        filename = ctk.filedialog.asksaveasfilename(
            title="Export Commands",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, "w") as f:
                    json.dump(self.commands, f, indent=4)
                    self.speak("Commands exported successfully.")
                    logger.info(f"Commands exported to {filename}")
            except Exception as e:
                logger.error(f"Error exporting commands: {e}")
                print(f"Error exporting commands: {e}")
                self.speak("Error exporting commands.")

    def toggle_wake_word(self):
        """Toggle wake word detection"""
        enabled = self.wake_word_switch.get() == 1
        self.settings["wake_word_enabled"] = enabled
        self.wake_activation_switch.select() if enabled else self.wake_activation_switch.deselect()
        self.save_settings()
        
        if enabled:
            if self.settings.get("background_listening", True):
                self.start_background_listening()
            logger.info("Wake word detection enabled")
        else:
            self.stop_background_listening()
            logger.info("Wake word detection disabled")

    def change_wake_word(self):
        """Change the wake word"""
        dialog = ctk.CTkInputDialog(
            text="Enter new wake word:",
            title="Change Wake Word"
        )
        result = dialog.get_input()
        
        if result:
            self.settings["wake_word"] = result
            self.wake_word_label.configure(text=result)
            self.activation_desc.configure(text=f'Or say "{result}" to activate with your voice')
            self.save_settings()
            self.speak(f"Wake word changed to {result}")
            logger.info(f"Wake word changed to: {result}")

    def update_voice_type(self, voice_type):
        """Update the voice type"""
        self.settings["voice_type"] = voice_type
        self.save_settings()
        
        # Apply the voice change
        self.apply_voice_settings()
        
        # Provide feedback
        self.speak(f"Voice type changed to {voice_type}")

    def update_response_style(self, style):
        """Update the response style"""
        self.settings["response_style"] = style
        self.save_settings()
        logger.info(f"Response style changed to: {style}")
        
        # Provide feedback based on style
        if style != "silent":
            self.speak(f"Response style changed to {style}")

    def update_volume(self, volume):
        """Update the voice volume"""
        volume = int(volume)
        self.settings["volume"] = volume
        self.volume_value.configure(text=f"{volume}%")
        self.save_settings()
        
        # Update TTS volume (0.0 to 1.0)
        self.engine.setProperty('volume', volume / 100.0)
        logger.info(f"Voice volume set to {volume}%")
        
        # Provide feedback
        if volume > 0:
            self.speak("Volume updated")

    def update_speech_speed(self, speed):
        """Update the speech speed"""
        speed = int(speed)
        self.settings["speech_speed"] = speed
        self.speed_value.configure(text=f"{speed}")
        self.save_settings()
        
        # Update TTS rate
        self.engine.setProperty('rate', speed)
        logger.info(f"Speech speed set to {speed}")
        
        # Provide feedback
        self.speak("Speech speed updated")

    def update_sensitivity(self, sensitivity):
        """Update the voice recognition sensitivity"""
        sensitivity = int(sensitivity)
        self.settings["sensitivity"] = sensitivity
        self.save_settings()
        logger.info(f"Voice recognition sensitivity set to {sensitivity}%")

    def toggle_start_on_boot(self):
        """Toggle start on boot setting"""
        enabled = self.boot_switch.get() == 1
        self.settings["start_on_boot"] = enabled
        self.save_settings()
        
        # Here you would add/remove from startup in the registry
        # This is just a placeholder
        logger.info(f"Start on boot: {enabled}")

    def toggle_minimize_to_tray(self):
        """Toggle minimize to tray setting"""
        enabled = self.tray_switch.get() == 1
        self.settings["minimize_to_tray"] = enabled
        self.save_settings()
        logger.info(f"Minimize to tray: {enabled}")

    def toggle_notifications(self):
        """Toggle notifications setting"""
        enabled = self.notif_switch.get() == 1
        self.settings["show_notifications"] = enabled
        self.save_settings()
        logger.info(f"Show notifications: {enabled}")

    def toggle_offline_mode(self):
        """Toggle offline mode setting"""
        enabled = self.offline_var.get()
        self.settings["work_offline"] = enabled
        self.save_settings()
        logger.info(f"Work offline: {enabled}")

    def toggle_command_history(self):
        """Toggle command history setting"""
        enabled = self.history_var.get()
        self.settings["save_command_history"] = enabled
        self.save_settings()
        logger.info(f"Save command history: {enabled}")

    def toggle_anonymous_data(self):
        """Toggle anonymous data sharing setting"""
        enabled = self.anon_var.get()
        self.settings["share_anonymous_data"] = enabled
        self.save_settings()
        logger.info(f"Share anonymous data: {enabled}")

    def clear_all_data(self):
        """Clear all data and reset to defaults"""
        # Ask for confirmation
        confirm = ctk.CTkInputDialog(
            text='Are you sure you want to clear all data?\nThis will reset all settings and commands.\nType "yes" to confirm.',
            title="Confirm Clear All Data"
        )
        result = confirm.get_input()
        
        if result and result.lower() == "yes":
            # Clear logs
            for widget in self.log_frame.winfo_children():
                widget.destroy()
            
            self.command_logs = []
            
            # Reset settings to defaults
            self.load_settings()
            
            # Reset commands to defaults
            self.load_commands()
            
            # Refresh UI
            self.refresh_commands()
            
            # Update UI elements with new settings
            self.wake_word_label.configure(text=self.settings["wake_word"])
            self.activation_desc.configure(text=f'Or say "{self.settings["wake_word"]}" to activate with your voice')
            
            self.voice_type_var.set(self.settings["voice_type"])
            self.response_style_var.set(self.settings["response_style"])
            self.volume_var.set(self.settings["volume"])
            self.speed_var.set(self.settings["speech_speed"])
            
            if self.settings["wake_word_enabled"]:
                self.wake_word_switch.select()
                self.wake_activation_switch.select()
            else:
                self.wake_word_switch.deselect()
                self.wake_activation_switch.deselect()
            
            if self.settings["background_listening"]:
                self.bg_listen_switch.select()
                self.bg_listen_settings_switch.select()
            else:
                self.bg_listen_switch.deselect()
                self.bg_listen_settings_switch.deselect()
            
            if self.settings["start_on_boot"]:
                self.boot_switch.select()
            else:
                self.boot_switch.deselect()
            
            if self.settings["minimize_to_tray"]:
                self.tray_switch.select()
            else:
                self.tray_switch.deselect()
            
            if self.settings["show_notifications"]:
                self.notif_switch.select()
            else:
                self.notif_switch.deselect()
            
            self.offline_var.set(self.settings["work_offline"])
            self.history_var.set(self.settings["save_command_history"])
            self.anon_var.set(self.settings["share_anonymous_data"])
            
            self.recog_var.set(self.settings["speech_recognition_engine"])
            self.synth_var.set(self.settings["speech_synthesis_engine"])
            
            # Apply voice settings
            self.apply_voice_settings()
            
            self.speak("All data has been cleared.")
            logger.info("All data cleared")

    def change_theme(self, theme):
        """Change the UI theme"""
        self.settings["theme"] = theme
        self.save_settings()
        
        # Update UI appearance
        ctk.set_appearance_mode(theme)
        
        # Update theme buttons
        if theme == "light":
            self.light_button.configure(fg_color="#06b6d4", hover_color="#0891b2")
            self.dark_button.configure(fg_color="#252542", hover_color="#2a2a4a")
        else:
            self.light_button.configure(fg_color="#252542", hover_color="#2a2a4a")
            self.dark_button.configure(fg_color="#06b6d4", hover_color="#0891b2")
            
        logger.info(f"Theme changed to: {theme}")

    def update_recognition_engine(self, engine):
        """Update the speech recognition engine"""
        self.settings["speech_recognition_engine"] = engine
        self.save_settings()
        logger.info(f"Speech recognition engine changed to: {engine}")

    def update_synthesis_engine(self, engine):
        """Update the speech synthesis engine"""
        self.settings["speech_synthesis_engine"] = engine
        self.save_settings()
        logger.info(f"Speech synthesis engine changed to: {engine}")

    def test_voice(self):
        """Test the voice with the current settings"""
        text = self.test_text.get()
        if text:
            self.speak(text)
            logger.info(f"Testing voice with text: {text}")

    def start_background_listening(self):
        """Start background listening for wake word"""
        if self.background_listening:
            return
            
        self.background_listening = True
        logger.info("Background listening started")
        
        def listen_for_wake_word():
            logger.debug("Background listening thread started")
            
            while self.background_listening:
                try:
                    with self.microphone_lock:  # Use lock to prevent concurrent access
                        # Create a new recognizer instance each time
                        recognizer = sr.Recognizer()
                        
                        # Adjust energy threshold based on sensitivity setting
                        # Lower threshold for better recognition
                        base_energy = 3000  # Reduced from 4000
                        sensitivity_factor = 1.0 - (self.settings.get("sensitivity", 70) / 100.0)
                        recognizer.energy_threshold = base_energy * sensitivity_factor
                        recognizer.dynamic_energy_threshold = True
                        
                        # Create a new microphone instance each time
                        with sr.Microphone() as source:
                            try:
                                # Adjust for ambient noise
                                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                                # Shorter timeout for wake word detection
                                audio = recognizer.listen(source, timeout=1, phrase_time_limit=3)
                            except sr.WaitTimeoutError:
                                # This is normal for wake word detection, just continue
                                continue
                    
                    # Only process if we're still in background listening mode
                    if not self.background_listening:
                        break
                        
                    try:
                        # Try multiple recognition engines for better wake word detection
                        text = ""
                        try:
                            # Try Google first (better accuracy)
                            text = recognizer.recognize_google(audio).lower()
                            logger.debug(f"Wake word check with Google: {text}")
                        except:
                            # Fall back to Sphinx
                            text = recognizer.recognize_sphinx(audio).lower()
                            logger.debug(f"Wake word check with Sphinx: {text}")
                        
                        # Check if wake word is in the recognized text using fuzzy matching
                        wake_word = self.settings["wake_word"].lower()
                        
                        # Use multiple matching methods for better detection
                        ratio_score = fuzz.ratio(wake_word, text)
                        partial_score = fuzz.partial_ratio(wake_word, text)
                        token_sort_score = fuzz.token_sort_ratio(wake_word, text)
                        
                        # Use the best score
                        best_score = max(ratio_score, partial_score, token_sort_score)
                        
                        # Lower threshold for better detection
                        if best_score >= 65:  # Reduced from 75
                            logger.info(f"Wake word detected: '{text}' matched '{wake_word}' with score {best_score}")
                            # Set the wake word detected event
                            self.wake_word_detected.set()
                            # Start active listening on the main thread
                            self.after(0, self.start_listening)
                            # Pause background listening while actively listening
                            time.sleep(10)
                    except sr.UnknownValueError:
                        pass  # Normal for wake word detection
                    except sr.RequestError as e:
                        logger.error(f"Error with speech recognition service: {e}")
                        time.sleep(5)  # Wait before retrying
                except Exception as e:
                    logger.error(f"Error in background listening: {e}")
                    time.sleep(1)
                
                time.sleep(0.1)  # Small delay to prevent CPU overuse
        
        # Start background listening in a separate thread
        self.background_thread = threading.Thread(target=listen_for_wake_word)
        self.background_thread.daemon = True
        self.background_thread.start()

    def stop_background_listening(self):
        """Stop background listening for wake word"""
        self.background_listening = False
        if self.background_thread:
            self.background_thread.join(timeout=1)
        logger.info("Background listening stopped")

    def execute_command(self, command):
        """Execute a command from the quick commands"""
        # Simulate executing a command from the quick commands
        self.start_listening()
        
        # Simulate processing
        self.after(1000, lambda: self.process_command(command))
        logger.info(f"Executing quick command: {command}")

    # New JARVIS-inspired methods
    def screen_recording(self, action):
        """Handle screen recording start/stop"""
        if action == "start":
            if self.is_recording:
                self.speak("Recording is already in progress")
                return
                
            try:
                recordings_folder = os.path.join(os.environ['USERPROFILE'], 'Videos', 'Screen Recordings')
                os.makedirs(recordings_folder, exist_ok=True)
                
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                self.recording_path = os.path.join(recordings_folder, f"screen_recording_{timestamp}.avi")
                
                self.stop_recording_flag = False
                self.recording_thread = threading.Thread(target=self._record_screen)
                self.recording_thread.daemon = True
                self.recording_thread.start()
                
                self.is_recording = True
                self.recording_status_value.configure(text="Recording", text_color="#22c55e")
                self.speak("Screen recording started")
                logger.info("Screen recording started")
            except Exception as e:
                self.speak(f"Error starting recording: {e}")
                logger.error(f"Error starting recording: {e}")
                
        elif action == "stop":
            if not self.is_recording:
                self.speak("No recording is in progress")
                return
                
            try:
                self.stop_recording_flag = True
                if self.recording_thread and self.recording_thread.is_alive():
                    self.recording_thread.join(timeout=5)
                    
                self.is_recording = False
                self.recording_status_value.configure(text="Not Recording", text_color="#ef4444")
                self.speak("Screen recording stopped and saved")
                logger.info("Screen recording stopped")
            except Exception as e:
                self.speak(f"Error stopping recording: {e}")
                logger.error(f"Error stopping recording: {e}")

    def _record_screen(self):
        """Internal method to handle screen recording"""
        try:
            screen_width, screen_height = pyautogui.size()
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            out = cv2.VideoWriter(self.recording_path, fourcc, 20.0, (screen_width, screen_height))
            
            start_time = time.time()
            
            while not self.stop_recording_flag:
                img = pyautogui.screenshot()
                frame = np.array(img)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                out.write(frame)
                
                if time.time() - start_time > 1800:  # 30 min limit
                    break
                    
                time.sleep(0.05)
                
            out.release()
            
        except Exception as e:
            logger.error(f"Error in recording thread: {e}")
            self.is_recording = False
            self.after(0, lambda: self.recording_status_value.configure(text="Not Recording", text_color="#ef4444"))

    def dictate_to_file(self, duration=30):
        """Transcribe speech to a text file"""
        self.speak(f"Starting dictation for {duration} seconds. Speak clearly.")
        logger.info(f"Starting dictation for {duration} seconds")
        
        recognizer = sr.Recognizer()
        text_parts = []
        
        # Create a popup to show dictation progress
        dictation_popup = ctk.CTkToplevel(self)
        dictation_popup.title("Dexa Dictation")
        dictation_popup.geometry("400x200")
        dictation_popup.attributes("-topmost", True)
        
        # Position in center
        screen_width = dictation_popup.winfo_screenwidth()
        screen_height = dictation_popup.winfo_screenheight()
        x = (screen_width - 400) // 2
        y = (screen_height - 200) // 2
        dictation_popup.geometry(f"+{x}+{y}")
        
        # Create frame with rounded corners
        frame = ctk.CTkFrame(dictation_popup, corner_radius=15)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title
        title_label = ctk.CTkLabel(
            frame, 
            text="Voice Dictation", 
            font=("Helvetica", 18, "bold"), 
            text_color="#ffffff"
        )
        title_label.pack(pady=(15, 5))
        
        # Status
        status_label = ctk.CTkLabel(
            frame, 
            text=f"Listening for {duration} seconds...", 
            font=("Helvetica", 12), 
            text_color="#9ca3af"
        )
        status_label.pack(pady=5)
        
        # Progress bar
        progress_bar = ctk.CTkProgressBar(frame, width=300)
        progress_bar.pack(pady=10)
        progress_bar.set(0)
        
        # Recognized text
        text_label = ctk.CTkLabel(
            frame, 
            text="Recognized text will appear here...", 
            font=("Helvetica", 10), 
            text_color="#e5e7eb",
            wraplength=350
        )
        text_label.pack(pady=5, fill="x", expand=True)
        
        # Cancel button
        cancel_button = ctk.CTkButton(
            frame, 
            text="Cancel", 
            width=100, 
            height=30, 
            corner_radius=8,
            fg_color="#ef4444", 
            hover_color="#c53030",
            command=dictation_popup.destroy
        )
        cancel_button.pack(pady=10)
        
        def dictation_thread():
            start_time = time.time()
            end_time = start_time + duration
            
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=1)
                
                while time.time() < end_time and dictation_popup.winfo_exists():
                    remaining = int(end_time - time.time())
                    progress = 1 - (remaining / duration)
                    
                    # Update UI
                    self.after(0, lambda: status_label.configure(text=f"Listening... {remaining}s remaining"))
                    self.after(0, lambda: progress_bar.set(progress))
                    
                    try:
                        audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)
                        text = recognizer.recognize_google(audio)
                        text_parts.append(text)
                        
                        # Update UI with recognized text
                        self.after(0, lambda t=text: text_label.configure(text=t))
                        logger.info(f"Dictation recognized: {text}")
                    except sr.WaitTimeoutError:
                        continue
                    except sr.UnknownValueError:
                        self.after(0, lambda: text_label.configure(text="Could not understand audio"))
                    except Exception as e:
                        logger.error(f"Error in dictation: {e}")
            
            # Save dictation if we have text and the popup wasn't cancelled
            if text_parts and dictation_popup.winfo_exists():
                try:
                    documents_folder = os.path.join(os.environ['USERPROFILE'], 'Documents')
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_path = os.path.join(documents_folder, f"dictation_{timestamp}.txt")
                    
                    with open(file_path, 'w') as f:
                        f.write(" ".join(text_parts))
                    
                    self.after(0, lambda: status_label.configure(text=f"Dictation saved to {file_path}"))
                    self.after(0, lambda: progress_bar.set(1))
                    self.after(0, lambda: text_label.configure(text="Dictation complete and saved to file"))
                    self.after(0, lambda: cancel_button.configure(text="Close", fg_color="#06b6d4", hover_color="#0891b2"))
                    
                    self.speak(f"Dictation saved to file")
                    logger.info(f"Dictation saved to {file_path}")
                except Exception as e:
                    self.after(0, lambda: status_label.configure(text=f"Error saving dictation: {e}"))
                    logger.error(f"Error saving dictation: {e}")
            elif dictation_popup.winfo_exists():
                self.after(0, lambda: status_label.configure(text="No speech was detected during dictation"))
                self.after(0, lambda: text_label.configure(text="No text to save"))
                self.after(0, lambda: cancel_button.configure(text="Close", fg_color="#06b6d4", hover_color="#0891b2"))
                
                self.speak("No speech was detected during dictation")
                logger.info("No speech detected during dictation")
        
        # Start dictation in a separate thread
        threading.Thread(target=dictation_thread, daemon=True).start()

    def monitor_resources(self, threshold=90, duration=60):
        """Monitor system resources and alert if thresholds are exceeded"""
        logger.info(f"Monitoring resources with threshold {threshold}% for {duration} seconds")
        
        # Create and show the resource monitor popup
        monitor_popup = ResourceMonitorPopup(self, duration=duration, threshold=threshold)
        
        # Speak confirmation
        self.speak(f"Monitoring system resources for {duration} seconds with {threshold}% threshold")

    def schedule_task(self, task_description, minutes):
        """Schedule a task reminder"""
        try:
            minutes = max(1, min(60, int(minutes)))
            logger.info(f"Scheduling task: {task_description} in {minutes} minutes")
            
            # Add to active tasks list
            self.add_active_task(task_description, minutes)
            
            def reminder_task():
                time.sleep(minutes * 60)
                
                # Create reminder popup
                reminder = TaskReminderPopup(self, task_description)
                
                # Speak reminder
                for _ in range(3):  # Repeat 3 times to ensure it's heard
                    self.speak(f"Reminder: {task_description}")
                    time.sleep(1)
                
                # Remove from active tasks
                self.remove_active_task(task_description)
            
            reminder_thread = threading.Thread(target=reminder_task)
            reminder_thread.daemon = True
            reminder_thread.start()
            
            # Add to scheduled tasks list
            task_id = len(self.scheduled_tasks) + 1
            self.scheduled_tasks.append({
                "id": task_id,
                "description": task_description,
                "minutes": minutes,
                "scheduled_time": datetime.datetime.now(),
                "thread": reminder_thread
            })
            
            return True
        except Exception as e:
            logger.error(f"Error scheduling task: {e}")
            return False

    def schedule_task_from_ui(self):
        """Schedule a task from the UI"""
        task_description = self.task_entry.get().strip()
        minutes = self.time_var.get()
        
        if not task_description:
            self.speak("Please enter a task description")
            return
        
        success = self.schedule_task(task_description, minutes)
        
        if success:
            self.speak(f"Task scheduled: {task_description} in {minutes} minutes")
            self.task_entry.delete(0, "end")
        else:
            self.speak("Error scheduling task")

    def add_active_task(self, task_description, minutes):
        """Add a task to the active tasks list"""
        # Remove "No active tasks" label if it exists
        for widget in self.active_tasks_frame.winfo_children():
            if isinstance(widget, ctk.CTkLabel) and "No active" in widget.cget("text"):
                widget.destroy()
        
        # Create task frame
        task_frame = ctk.CTkFrame(self.active_tasks_frame, corner_radius=8, fg_color="#252542", border_width=1, border_color="#2a2a3a")
        task_frame.pack(fill="x", pady=2)
        
        # Calculate due time
        due_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        due_time_str = due_time.strftime("%H:%M:%S")
        
        # Task info
        task_info = ctk.CTkFrame(task_frame, fg_color="transparent")
        task_info.pack(side="left", fill="x", expand=True, padx=10, pady=8)
        
        task_label = ctk.CTkLabel(task_info, text=task_description, font=("Helvetica", 12, "bold"), text_color="#ffffff")
        task_label.pack(anchor="w")
        
        due_label = ctk.CTkLabel(task_info, text=f"Due at {due_time_str}", font=("Helvetica", 10), text_color="#9ca3af")
        due_label.pack(anchor="w")
        
        # Cancel button
        cancel_button = ctk.CTkButton(
            task_frame, 
            text="Cancel", 
            width=70,
            height=25,
            corner_radius=8,
            fg_color="#ef4444", 
            hover_color="#c53030",
            command=lambda: self.remove_active_task(task_description)
        )
        cancel_button.pack(side="right", padx=10, pady=8)
        
        # Store reference to task frame
        task_frame.task_description = task_description
        
        logger.debug(f"Added active task: {task_description}")

    def remove_active_task(self, task_description):
        """Remove a task from the active tasks list"""
        # Find and remove the task frame
        for widget in self.active_tasks_frame.winfo_children():
            if hasattr(widget, 'task_description') and widget.task_description == task_description:
                widget.destroy()
                logger.debug(f"Removed active task: {task_description}")
                break
        
        # Remove from scheduled tasks list
        for task in self.scheduled_tasks[:]:
            if task["description"] == task_description:
                self.scheduled_tasks.remove(task)
                break
        
        # Add "No active tasks" label if no tasks left
        if not self.active_tasks_frame.winfo_children():
            no_tasks_label = ctk.CTkLabel(self.active_tasks_frame, text="No active tasks", font=("Helvetica", 10), text_color="#9ca3af")
            no_tasks_label.pack(pady=10)

    def on_close(self):
        """Handle window close event"""
        if self.settings.get("minimize_to_tray", True) and self.settings.get("background_listening", True):
            self.withdraw()  # Hide window instead of closing
            logger.info("Application minimized to tray")
        else:
            # Stop background listening if it's running
            if self.background_listening:
                self.stop_background_listening()
            
            # Stop system tray icon
            self.icon.stop()
            
            # Destroy window
            self.destroy()
            logger.info("Application closed")
            sys.exit()

if __name__ == "__main__":
    app = Dexa()
    app.mainloop()