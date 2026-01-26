"""
Personal Voice Assistant
A Python application using Tkinter GUI, PyAutoGUI, and voice recognition/synthesis
without any API dependencies for core functionality.
"""

from pydoc import text
from email.mime import text
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import datetime
from lib.voice_engine import VoiceEngine
from lib.command_processor import CommandProcessor
import os
import time
import pygame
# This hides the 'ALSA lib...' and 'JACK...' errors from the console
import os
import sys

# Suppress ALSA/JACK error messages in the terminal
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
f = open(os.devnull, 'w')
sys.stderr = f
class VoiceAssistantGUI:
    """Main GUI application for the voice assistant."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Friday Assistant")
        self.root.geometry("800x600")
        
        # 1. Initialize engines
        self.voice_engine = VoiceEngine()
        self.command_processor = CommandProcessor(self.voice_engine)
        self.processor = self.command_processor 
        
        # 2. Build the UI
        self.setup_gui()
        
        # 3. Startup Greeting Logic
        # Give Kali/PipeWire 0.5s to stabilize the audio stream
        import time
        time.sleep(0.5)
        self.voice_engine.speak("Systems online. I am ready, Aime.")
        
        self.is_listening = False
        self.is_hidden = True 
        
        # 4. Start the background thread
        threading.Thread(target=self.background_listener, daemon=True).start()
        pygame.mixer.music.set_volume(1.0) # Ensure volume is at 100%
    def background_listener(self):
        print("Friday is synchronized and standing by...")
        while True:
            try:
                # 1. Safety: Don't use mic if Friday is already talking
                if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                    time.sleep(1)
                    continue

                # 2. Only run wake-word detection if UI is hidden
                if self.is_hidden:
                    # We use a shorter timeout to keep the loop responsive
                    result = self.voice_engine.listen_offline(timeout=2)
                    
                    if result == "friday":
                        print(">>> Wake word 'Friday' detected!")
                        self.is_hidden = False 
                        self.root.after(0, self.show_interface)
            
            except Exception as e:
                # This prevents the thread from crashing if the mic glitches
                print(f"Background Thread Warning: {e}")
            
            # 3. Prevent CPU spiking
            time.sleep(0.4)
    def show_interface(self):
        """Bring Friday to the front and start listening."""
        self.is_hidden = False
        self.root.deiconify() # Show window
        self.root.attributes("-topmost", True) # Force to front
        self.voice_engine.speak("Yes? I am here.")
        self.start_listening()

    def stop_listening(self):
        """Modified: Stop listening and hide window."""
        self.is_listening = False
        self.is_hidden = True
        self.listen_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.update_status("Sleeping...", '#7f8c8d')
        self.root.withdraw() # Hide window
    
    def setup_gui(self):
        """Set up the Tkinter GUI components."""
        
        # Header
        header_frame = tk.Frame(self.root, bg='#2c3e50')
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        
        title_label = tk.Label(
            header_frame,
            text="🎤 Personal Voice Assistant",
            font=('Helvetica', 18, 'bold'),
            bg='#2c3e50',
            fg='white'
        )
        title_label.pack(pady=15)
        
        # Control Frame
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=20, pady=15)
        
        # Listen Button
        self.listen_button = tk.Button(
            control_frame,
            text="🎙️ Start Listening",
            command=self.start_listening,
            bg='#27ae60',
            fg='white',
            font=('Helvetica', 12, 'bold'),
            padx=20,
            pady=10,
            relief=tk.RAISED,
            cursor='hand2'
        )
        self.listen_button.pack(side=tk.LEFT, padx=5)
        
        # Stop Button
        self.stop_button = tk.Button(
            control_frame,
            text="⏹️ Stop",
            command=self.stop_listening,
            bg='#e74c3c',
            fg='white',
            font=('Helvetica', 12, 'bold'),
            padx=20,
            pady=10,
            relief=tk.RAISED,
            cursor='hand2',
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Clear Button
        clear_button = tk.Button(
            control_frame,
            text="🗑️ Clear Log",
            command=self.clear_log,
            bg='#95a5a6',
            fg='white',
            font=('Helvetica', 12, 'bold'),
            padx=20,
            pady=10,
            relief=tk.RAISED,
            cursor='hand2'
        )
        clear_button.pack(side=tk.LEFT, padx=5)
        
        # Help Button
        help_button = tk.Button(
            control_frame,
            text="❓ Help",
            command=self.show_help,
            bg='#3498db',
            fg='white',
            font=('Helvetica', 12, 'bold'),
            padx=20,
            pady=10,
            relief=tk.RAISED,
            cursor='hand2'
        )
        help_button.pack(side=tk.LEFT, padx=5)
        
        # Settings Frame
        settings_frame = ttk.LabelFrame(self.root, text="Settings", padding=10)
        settings_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Voice Speed
        speed_label = tk.Label(settings_frame, text="Voice Speed:", font=('Helvetica', 10))
        speed_label.pack(side=tk.LEFT, padx=5)
        
        self.speed_var = tk.IntVar(value=150)
        speed_scale = ttk.Scale(
            settings_frame,
            from_=50,
            to=300,
            orient=tk.HORIZONTAL,
            variable=self.speed_var,
            command=self.update_voice_settings
        )
        speed_scale.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Volume
        volume_label = tk.Label(settings_frame, text="Volume:", font=('Helvetica', 10))
        volume_label.pack(side=tk.LEFT, padx=5)
        
        self.volume_var = tk.DoubleVar(value=0.9)
        volume_scale = ttk.Scale(
            settings_frame,
            from_=0.0,
            to=1.0,
            orient=tk.HORIZONTAL,
            variable=self.volume_var,
            command=self.update_voice_settings
        )
        volume_scale.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Output Log
        log_frame = ttk.LabelFrame(self.root, text="Activity Log", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=15,
            font=('Courier', 10),
            bg='#ecf0f1',
            fg='#2c3e50',
            state=tk.DISABLED
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Status Bar
        status_frame = tk.Frame(self.root, bg='#34495e', height=30)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_label = tk.Label(
            status_frame,
            text="Ready",
            font=('Helvetica', 10),
            bg='#34495e',
            fg='#2ecc71',
            anchor=tk.W,
            padx=10
        )
        self.status_label.pack(fill=tk.X, padx=10, pady=5)
        # Add these where you define your buttons or window properties
        self.root.bind('<space>', lambda e: self.start_listening())
        self.root.bind('<Escape>', lambda e: self.stop_listening())
        # --- Inside your GUI Class (setup_gui) ---
        # Create a text entry field
        self.command_entry = tk.Entry(self.root, font=("Arial", 12))
        self.command_entry.pack(pady=10, padx=20, fill='x')
        
        # Create a Send button
        self.send_button = tk.Button(self.root, text="Execute Command", command=self.handle_text_command)
        self.send_button.pack(pady=5)
        
        # Bind the 'Enter' key to the send function for speed
        self.command_entry.bind('<Return>', lambda event: self.handle_text_command())

# --- Add this method to your GUI Class ---
    def handle_command(self, text):
     if not text:
        # This is where she should speak if you stay silent
        self.voice_engine.speak("I didn't catch that, sir.") 
        return

     print(f"Processing: {text}")
    # Example command
     if "hello" in text:
        self.voice_engine.speak("Hello sir, how can I help you today?")
     else:
        # If the command isn't recognized, she MUST speak this:
        self.voice_engine.speak("I understood the command, but I don't have a protocol for that yet.")
    
    def log(self, message: str):
        """Add a message to the activity log."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, log_message)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def clear_log(self):
        """Clear the activity log."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log("Log cleared")
    
    def update_status(self, status: str, color: str = '#2ecc71'):
        """Update the status bar."""
        self.status_label.config(text=status, fg=color)
        self.root.update()
    
    def update_voice_settings(self, value=None):
        """Update voice speed and volume."""
        speed = self.speed_var.get()
        volume = self.volume_var.get()
        self.voice_engine.set_voice_properties(rate=speed, volume=volume)
    
    def start_listening(self):
        """Start listening for voice commands."""
        if self.is_listening:
            return
            
        # --- NEW: Interrupt the assistant if it's currently talking ---
        if hasattr(self, 'voice_engine'):
            self.voice_engine.stop_speaking()
        
        self.is_listening = True
        self.listen_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.update_status("Listening...", '#f39c12')
        self.log("Voice listening started")
        
        # Start listening in a separate thread
        self.listen_thread = threading.Thread(target=self.listen_loop, daemon=True)
        self.listen_thread.start()
    
    def stop_listening(self):
        """Stop listening for voice commands."""
        self.is_listening = False
        self.listen_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.update_status("Stopped", '#e74c3c')
        self.log("Voice listening stopped")
    
    def listen_loop(self):
     print("Friday is standing by...")
     while True:
        try:
            # SAFETY CHECK: Only check busy if mixer is actually running
            if pygame.mixer.get_init():
                if pygame.mixer.music.get_busy():
                    time.sleep(0.5)
                    continue
            else:
                # Try to re-init if it died
                pygame.mixer.init()
                continue
            
            # ... rest of your listening logic ...
        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(1)
    def start_friday(self):
    # 1. Start the permanent background listener
    # This keeps the mic stream OPEN and STABLE
     self.voice_engine.recognizer.listen_in_background(
        self.voice_engine.mic, 
        self.background_callback
    )
    print("Mic stream stabilized.")

    def background_callback(self, recognizer, audio):
     """This runs every time the mic hears sound without closing the stream."""
     try:
        if self.is_hidden:
            # Fast check for wake word
            text = recognizer.recognize_google(audio).lower()
            if "friday" in text:
                self.root.after(0, self.show_interface)
     except:
        pass
    
    def show_help(self):
        """Show help information."""
        help_text = """
PERSONAL VOICE ASSISTANT - COMMAND GUIDE
==========================================

VOICE COMMANDS:
- Time: "What is the time?" or "Tell me the time"
- Date: "What is the date?" or "Tell me the date"
- Weather: "What is the weather?" or "Weather forecast"
- Greeting: "Hello" or "Hi"
- Open URL: "Open [website]" (e.g., "Open google.com")
- Search: "Search for [topic]"
- Research: "Research [topic]"
- Open App: "Open [application name]"
- Execute Command: "Execute [command]"
- Help: "Help"

TIPS:
1. Click "Start Listening" to activate voice recognition
2. Speak clearly and naturally
3. Wait for the beep to finish speaking
4. Adjust voice speed and volume in Settings
5. Check the Activity Log for command history

REQUIREMENTS:
- Microphone (for voice input)
- Speaker (for voice output)
- Internet connection (for web searches and weather)

Powered by Python, Tkinter, PyAutoGUI, and Local Voice Engine
        """
        
        help_window = tk.Toplevel(self.root)
        help_window.title("Help - Personal Voice Assistant")
        help_window.geometry("600x500")
        
        text_widget = scrolledtext.ScrolledText(help_window, font=('Courier', 10))
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.insert(tk.END, help_text)
        text_widget.config(state=tk.DISABLED)


def main():
    """Main entry point for the application."""
    root = tk.Tk()
    app = VoiceAssistantGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
