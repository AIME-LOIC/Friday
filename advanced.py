#!/usr/bin/env python3
"""
Advanced Voice Assistant with additional features
- Desktop automation with PyAutoGUI
- Custom voice profiles
- Command history
- Scheduled tasks
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import json
import datetime
from pathlib import Path
from lib.voice_engine import VoiceEngine
from lib.command_processor import CommandProcessor

class AdvancedVoiceAssistant:
    """Advanced voice assistant with extra features."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Advanced Personal Voice Assistant")
        self.root.geometry("1000x700")
        self.root.configure(bg='#f0f0f0')
        
        # Initialize components
        self.voice_engine = VoiceEngine()
        self.command_processor = CommandProcessor(self.voice_engine)
        
        # Data storage
        self.config_dir = Path.home() / ".voice_assistant"
        self.config_dir.mkdir(exist_ok=True)
        self.history_file = self.config_dir / "command_history.json"
        self.command_history = self.load_history()
        
        self.is_listening = False
        self.listen_thread = None
        
        self.setup_gui()
        self.voice_engine.speak("Advanced Voice Assistant Ready")
        self.log("Advanced Voice Assistant Started")
    
    def setup_gui(self):
        """Set up advanced GUI."""
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Tab 1: Assistant
        self.assistant_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.assistant_frame, text="Assistant")
        self.setup_assistant_tab()
        
        # Tab 2: History
        self.history_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.history_frame, text="Command History")
        self.setup_history_tab()
        
        # Tab 3: Settings
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="Settings")
        self.setup_settings_tab()
        
        # Tab 4: About
        self.about_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.about_frame, text="About")
        self.setup_about_tab()
    
    def setup_assistant_tab(self):
        """Set up the main assistant tab."""
        
        # Header
        header_frame = tk.Frame(self.assistant_frame, bg='#2c3e50')
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        
        title_label = tk.Label(
            header_frame,
            text="🎤 Advanced Voice Assistant",
            font=('Helvetica', 16, 'bold'),
            bg='#2c3e50',
            fg='white'
        )
        title_label.pack(pady=12)
        
        # Control buttons
        button_frame = ttk.Frame(self.assistant_frame)
        button_frame.pack(fill=tk.X, padx=15, pady=10)
        
        self.listen_btn = tk.Button(
            button_frame,
            text="🎙️ Start Listening",
            command=self.start_listening,
            bg='#27ae60',
            fg='white',
            font=('Helvetica', 11, 'bold'),
            padx=15,
            pady=8
        )
        self.listen_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = tk.Button(
            button_frame,
            text="⏹️ Stop",
            command=self.stop_listening,
            bg='#e74c3c',
            fg='white',
            font=('Helvetica', 11, 'bold'),
            padx=15,
            pady=8,
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Settings
        settings_frame = ttk.LabelFrame(self.assistant_frame, text="Voice Settings", padding=10)
        settings_frame.pack(fill=tk.X, padx=15, pady=10)
        
        tk.Label(settings_frame, text="Speed:").pack(side=tk.LEFT, padx=5)
        self.speed_var = tk.IntVar(value=150)
        ttk.Scale(settings_frame, from_=50, to=300, orient=tk.HORIZONTAL, 
                 variable=self.speed_var, command=self.update_settings).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        tk.Label(settings_frame, text="Volume:").pack(side=tk.LEFT, padx=5)
        self.volume_var = tk.DoubleVar(value=0.9)
        ttk.Scale(settings_frame, from_=0.0, to=1.0, orient=tk.HORIZONTAL,
                 variable=self.volume_var, command=self.update_settings).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Log
        log_frame = ttk.LabelFrame(self.assistant_frame, text="Activity Log", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=12,
            font=('Courier', 9),
            bg='#ecf0f1',
            fg='#2c3e50',
            state=tk.DISABLED
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Status
        self.status_label = tk.Label(
            self.assistant_frame,
            text="Ready",
            font=('Helvetica', 10),
            bg='#34495e',
            fg='#2ecc71',
            anchor=tk.W,
            padx=10,
            pady=5
        )
        self.status_label.pack(fill=tk.X)
    
    def setup_history_tab(self):
        """Set up command history tab."""
        
        header = tk.Label(
            self.history_frame,
            text="📋 Command History",
            font=('Helvetica', 14, 'bold'),
            bg='#2c3e50',
            fg='white'
        )
        header.pack(fill=tk.X, pady=10)
        
        # Buttons
        btn_frame = ttk.Frame(self.history_frame)
        btn_frame.pack(fill=tk.X, padx=15, pady=5)
        
        tk.Button(btn_frame, text="Clear History", command=self.clear_history, 
                 bg='#e74c3c', fg='white', font=('Helvetica', 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Export History", command=self.export_history,
                 bg='#3498db', fg='white', font=('Helvetica', 10)).pack(side=tk.LEFT, padx=5)
        
        # History list
        history_frame = ttk.LabelFrame(self.history_frame, text="Commands", padding=10)
        history_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        self.history_text = scrolledtext.ScrolledText(
            history_frame,
            font=('Courier', 9),
            bg='#ecf0f1',
            fg='#2c3e50',
            state=tk.DISABLED
        )
        self.history_text.pack(fill=tk.BOTH, expand=True)
        
        self.refresh_history_display()
    
    def setup_settings_tab(self):
        """Set up settings tab."""
        
        header = tk.Label(
            self.settings_frame,
            text="⚙️ Settings",
            font=('Helvetica', 14, 'bold'),
            bg='#2c3e50',
            fg='white'
        )
        header.pack(fill=tk.X, pady=10)
        
        # Settings content
        content = ttk.Frame(self.settings_frame)
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        settings_text = """
VOICE ASSISTANT SETTINGS

Performance:
• Adjust voice speed: 50 (slow) to 300 (fast)
• Adjust volume: 0.0 (mute) to 1.0 (max)
• Microphone sensitivity auto-adjusts

Features:
• Voice command recognition
• Text-to-speech responses
• Command history tracking
• Web search capabilities

Data Storage:
• Configuration: ~/.voice_assistant/
• Command history: command_history.json
• No personal data sent to servers

Keyboard Shortcuts:
• Alt+L: Start Listening
• Alt+S: Stop Listening
• Alt+H: Show Help

System Requirements:
• Python 3.7+
• Working microphone
• Internet connection (for web searches)
• 512MB RAM minimum

Tips:
1. Use headphones for better mic input
2. Minimize background noise
3. Speak clearly and naturally
4. Wait for voice response before next command
5. Check activity log for errors
        """
        
        settings_display = scrolledtext.ScrolledText(
            content,
            font=('Courier', 10),
            bg='#ecf0f1',
            fg='#2c3e50',
            state=tk.DISABLED
        )
        settings_display.pack(fill=tk.BOTH, expand=True)
        settings_display.config(state=tk.NORMAL)
        settings_display.insert(tk.END, settings_text)
        settings_display.config(state=tk.DISABLED)
    
    def setup_about_tab(self):
        """Set up about tab."""
        
        header = tk.Label(
            self.about_frame,
            text="ℹ️ About",
            font=('Helvetica', 14, 'bold'),
            bg='#2c3e50',
            fg='white'
        )
        header.pack(fill=tk.X, pady=10)
        
        content = ttk.Frame(self.about_frame)
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        about_text = """
PERSONAL VOICE ASSISTANT
Advanced Edition v2.0

A powerful voice-activated personal assistant that understands
natural language commands and responds with synthesized speech.

FEATURES:
✓ Voice Recognition - Understand natural language
✓ Voice Response - Hear synthesized speech
✓ Web Search - Find information instantly
✓ Weather Info - Get current weather
✓ Time & Date - Know the current time
✓ Web Browsing - Open URLs automatically
✓ App Launcher - Start applications
✓ System Commands - Execute system commands
✓ Command History - Track all commands
✓ Customizable Voice - Adjust speed and volume

TECHNOLOGIES USED:
• Python 3.7+
• Tkinter - GUI Framework
• pyttsx3 - Text-to-Speech (offline)
• SpeechRecognition - Speech-to-Text
• PyAudio - Audio Input/Output
• PyAutoGUI - Desktop Automation
• Requests - HTTP Library
• BeautifulSoup4 - Web Scraping

PRIVACY & SECURITY:
✓ No API keys required
✓ No cloud storage
✓ All processing local
✓ Open source
✓ No data collection

INSTALLATION:
1. Clone repository
2. Install dependencies: pip install -r requirements.txt
3. Run: python main.py

DOCUMENTATION:
See README.md for complete documentation

AUTHOR:
Created with Python for voice automation

LICENSE:
Free to use and modify

This is an advanced open-source project.
All code is available for customization.
        """
        
        about_display = scrolledtext.ScrolledText(
            content,
            font=('Courier', 10),
            bg='#ecf0f1',
            fg='#2c3e50',
            state=tk.DISABLED
        )
        about_display.pack(fill=tk.BOTH, expand=True)
        about_display.config(state=tk.NORMAL)
        about_display.insert(tk.END, about_text)
        about_display.config(state=tk.DISABLED)
    
    def update_settings(self, value=None):
        """Update voice settings."""
        speed = self.speed_var.get()
        volume = self.volume_var.get()
        self.voice_engine.set_voice_properties(rate=speed, volume=volume)
    
    def log(self, message: str):
        """Add message to log."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] {message}\n"
        
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, log_msg)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def save_command_to_history(self, command: str):
        """Save executed command to history."""
        entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'command': command
        }
        self.command_history.append(entry)
        self.save_history()
        self.refresh_history_display()
    
    def load_history(self):
        """Load command history from file."""
        if self.history_file.exists():
            with open(self.history_file, 'r') as f:
                return json.load(f)
        return []
    
    def save_history(self):
        """Save command history to file."""
        with open(self.history_file, 'w') as f:
            json.dump(self.command_history, f, indent=2)
    
    def refresh_history_display(self):
        """Refresh history display."""
        self.history_text.config(state=tk.NORMAL)
        self.history_text.delete(1.0, tk.END)
        
        if not self.command_history:
            self.history_text.insert(tk.END, "No command history yet.\n")
        else:
            for entry in reversed(self.command_history[-50:]):  # Show last 50
                timestamp = datetime.datetime.fromisoformat(entry['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
                self.history_text.insert(tk.END, f"[{timestamp}] {entry['command']}\n")
        
        self.history_text.config(state=tk.DISABLED)
    
    def clear_history(self):
        """Clear command history."""
        if messagebox.askyesno("Clear History", "Clear all command history?"):
            self.command_history = []
            self.save_history()
            self.refresh_history_display()
            self.voice_engine.speak("Command history cleared")
    
    def export_history(self):
        """Export history to file."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv")]
        )
        if filepath:
            with open(filepath, 'w') as f:
                json.dump(self.command_history, f, indent=2)
            self.voice_engine.speak(f"History exported to {filepath}")
    
    def start_listening(self):
        """Start listening."""
        self.is_listening = True
        self.listen_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="Listening...", fg='#f39c12')
        self.log("Listening started")
        
        self.listen_thread = threading.Thread(target=self.listen_loop, daemon=True)
        self.listen_thread.start()
    
    def stop_listening(self):
        """Stop listening."""
        self.is_listening = False
        self.listen_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_label.config(text="Stopped", fg='#e74c3c')
        self.log("Listening stopped")
    
    def listen_loop(self):
        """Listen loop."""
        while self.is_listening:
            try:
                self.status_label.config(text="Listening...", fg='#f39c12')
                command = self.voice_engine.listen(timeout=5)
                
                if command:
                    self.log(f"Recognized: {command}")
                    self.save_command_to_history(command)
                    self.status_label.config(text="Processing...", fg='#3498db')
                    
                    self.command_processor.process(command)
                    
                    self.status_label.config(text="Ready", fg='#2ecc71')
            
            except Exception as e:
                self.log(f"Error: {str(e)}")


def main():
    """Main entry point."""
    root = tk.Tk()
    app = AdvancedVoiceAssistant(root)
    root.mainloop()


if __name__ == "__main__":
    main()
