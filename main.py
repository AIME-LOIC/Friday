"""
Personal Voice Assistant
A Python application using Tkinter GUI, PyAutoGUI, and voice recognition/synthesis
without any API dependencies for core functionality.
"""
import os
import ctypes

# Optional window-management imports for Jarvis-style dashboard
try:
    import pygetwindow as gw
except Exception:
    gw = None

# Suppress ALSA/JACK library warnings in the console
def py_error_handler(filename, line, function, err, fmt):
    pass

ERROR_HANDLER_FUNC = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p)
c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

try:
    asound = ctypes.cdll.LoadLibrary('libasound.so.2')
    asound.snd_lib_error_set_handler(c_error_handler)
except:
    pass
from pydoc import text
from email.mime import text
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import datetime
from lib.voice_engine import VoiceEngine
from lib.command_processor import CommandProcessor
from lib.gesture_controller import GestureController
import os
import time
import sys

# If you want to run without audio (CI/headless) set the env var:
#   FRIDAY_HEADLESS=1  or FRIDAY_DISABLE_AUDIO_WARNINGS=1
# This sets SDL to the dummy audio driver which prevents ALSA/JACK noise.
_FRIDAY_HEADLESS = os.environ.get('FRIDAY_HEADLESS') == '1' or os.environ.get('FRIDAY_DISABLE_AUDIO_WARNINGS') == '1'
if _FRIDAY_HEADLESS:
    os.environ['SDL_AUDIODRIVER'] = 'dummy'

# Hide pygame support prompt. If running headless, redirect stderr to reduce C-level ALSA/JACK noise.
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = 'hide'
_stderr_null = None
if _FRIDAY_HEADLESS:
    _stderr_null = open(os.devnull, 'w')
    sys.stderr = _stderr_null

import pygame
class VoiceAssistantGUI:
    """Main GUI application for the voice assistant."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("FRIDAY // Neural Console")
        self.root.geometry("1100x650")
        # Jarvis/eDex-style dark background
        self.root.configure(bg="#050816")
        
        # 1. Initialize engines
        self.voice_engine = VoiceEngine()
        # Try to initialize memory store for chatbot
        try:
            from lib.memory_store import FridayMemory
            memory_store = FridayMemory()
        except Exception:
            memory_store = None
        self.command_processor = CommandProcessor(self.voice_engine, memory_store)
        self.processor = self.command_processor 
        # Optional: gesture controller (hand open = start, fist = stop)
        try:
            self.gesture_controller = GestureController(
                on_open_hand=self.start_listening,
                on_closed_fist=self.stop_listening
            )
        except Exception:
            self.gesture_controller = None
        
        # 2. Build the UI
        self.setup_gui()
        
        # 3. Startup Greeting Logic
        # Give Kali/PipeWire 0.5s to stabilize the audio stream
        import time
        import random
        time.sleep(0.5)
        greetings = [
            "Uhm, systems online, bro. I'm ready, Aime.",
            "Alright dude, I'm online and ready!",
            "Hey man, systems are up. What's good?",
            "Bro, I'm ready to go!",
        ]
        self.voice_engine.speak(random.choice(greetings))
        
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
        import random
        self.is_hidden = False
        self.root.deiconify() # Show window
        self.root.attributes("-topmost", True) # Force to front
        responses = [
            "Uhm, yeah bro, what's up?",
            "Dude, I'm here! What's going on?",
            "Hey man, what can I do for you?",
            "Bro, what's good?",
        ]
        self.voice_engine.speak(random.choice(responses))
        self.start_listening()
    def setup_gui(self):
        """Set up the Tkinter GUI components."""
        
        # Header – holographic style bar
        header_frame = tk.Frame(self.root, bg='#050816')
        header_frame.pack(fill=tk.X, padx=0, pady=0)

        # Left-side "orb" to feel like a tech assistant core
        self.orb_canvas = tk.Canvas(
            header_frame,
            width=64,
            height=64,
            bg="#050816",
            highlightthickness=0,
            bd=0
        )
        self.orb_canvas.pack(side=tk.LEFT, padx=20, pady=8)
        self._init_orb_visual()
        
        title_label = tk.Label(
            header_frame,
            text="FRIDAY // Interactive OS Console",
            font=('Consolas', 20, 'bold'),
            bg='#050816',
            fg='#00d9ff'
        )
        title_label.pack(pady=15)
        
        # Control Frame
        control_frame = tk.Frame(self.root, bg="#050816")
        control_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Listen Button
        self.listen_button = tk.Button(
            control_frame,
            text="▶ LISTEN",
            command=self.start_listening,
            bg='#00c853',
            fg='#050816',
            font=('Consolas', 12, 'bold'),
            padx=20,
            pady=10,
            relief=tk.FLAT,
            cursor='hand2'
        )
        self.listen_button.pack(side=tk.LEFT, padx=5)
        
        # Stop Button
        self.stop_button = tk.Button(
            control_frame,
            text="■ STOP",
            command=self.stop_listening,
            bg='#ff1744',
            fg='#050816',
            font=('Consolas', 12, 'bold'),
            padx=20,
            pady=10,
            relief=tk.FLAT,
            cursor='hand2',
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Clear Button
        clear_button = tk.Button(
            control_frame,
            text="CLR LOG",
            command=self.clear_log,
            bg='#263238',
            fg='#e0f7fa',
            font=('Consolas', 11, 'bold'),
            padx=20,
            pady=10,
            relief=tk.FLAT,
            cursor='hand2'
        )
        clear_button.pack(side=tk.LEFT, padx=5)
        
        # Help Button
        help_button = tk.Button(
            control_frame,
            text="HELP",
            command=self.show_help,
            bg='#2962ff',
            fg='#e3f2fd',
            font=('Consolas', 11, 'bold'),
            padx=20,
            pady=10,
            relief=tk.FLAT,
            cursor='hand2'
        )
        help_button.pack(side=tk.LEFT, padx=5)
        
        # XO Game Button
        xo_button = tk.Button(
            control_frame,
            text="XO GAME",
            command=self.start_xo_game,
            bg='#7b1fa2',
            fg='#e1bee7',
            font=('Consolas', 11, 'bold'),
            padx=20,
            pady=10,
            relief=tk.FLAT,
            cursor='hand2'
        )
        xo_button.pack(side=tk.LEFT, padx=5)
        
        # Chatbot Mode Button
        self.chatbot_button = tk.Button(
            control_frame,
            text="💬 CHATBOT",
            command=self.toggle_chatbot,
            bg='#00bcd4',
            fg='#050816',
            font=('Consolas', 11, 'bold'),
            padx=20,
            pady=10,
            relief=tk.FLAT,
            cursor='hand2'
        )
        self.chatbot_button.pack(side=tk.LEFT, padx=5)
        
        # Settings Frame
        settings_frame = ttk.LabelFrame(self.root, text="AUDIO / VOICE CONTROL", padding=10)
        settings_frame.pack(fill=tk.X, padx=20, pady=8)
        
        # Voice Speed
        speed_label = tk.Label(settings_frame, text="Voice Speed", font=('Consolas', 9))
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
        volume_label = tk.Label(settings_frame, text="Volume", font=('Consolas', 9))
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
        
        # Main content split: left = console, right = active windows
        main_frame = tk.Frame(self.root, bg="#050816")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        left_frame = tk.Frame(main_frame, bg="#050816")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        right_frame = tk.Frame(main_frame, bg="#050816", width=260)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        right_frame.pack_propagate(False)

        # Output Log (left)
        log_frame = ttk.LabelFrame(left_frame, text="SYSTEM BUS / EVENT STREAM", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=15,
            font=('Consolas', 10),
            bg='#050816',
            fg='#00ffae',
            state=tk.DISABLED
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Status Bar
        status_frame = tk.Frame(self.root, bg='#050816', height=30)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_label = tk.Label(
            status_frame,
            text="Ready",
            font=('Consolas', 10),
            bg='#050816',
            fg='#00e676',
            anchor=tk.W,
            padx=10
        )
        self.status_label.pack(fill=tk.X, padx=10, pady=5)
        # Typed command input (left column, under log)
        self.command_entry = tk.Entry(left_frame, font=("Consolas", 11), bg="#000814", fg="#e0f7fa", insertbackground="#00e5ff")
        self.command_entry.pack(pady=(8, 4), fill='x')
        
        self.send_button = tk.Button(left_frame, text="EXECUTE", command=self.handle_text_command,
                                     bg="#1b2735", fg="#e0f7fa", font=("Consolas", 10, "bold"), relief=tk.FLAT)
        self.send_button.pack(pady=(0, 4), anchor="e")

        # Right column: live window / app overview
        sidebar_label = tk.Label(
            right_frame,
            text="ACTIVE WINDOWS",
            font=("Consolas", 10, "bold"),
            bg="#050816",
            fg="#00e5ff",
            anchor="w"
        )
        sidebar_label.pack(fill=tk.X, pady=(0, 4))

        sidebar_frame = tk.Frame(right_frame, bg="#050816")
        sidebar_frame.pack(fill=tk.BOTH, expand=True)

        self.window_listbox = tk.Listbox(
            sidebar_frame,
            font=("Consolas", 9),
            bg="#000814",
            fg="#e0f7fa",
            selectbackground="#00bfa5",
            activestyle="none"
        )
        self.window_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(sidebar_frame, orient=tk.VERTICAL, command=self.window_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.window_listbox.config(yscrollcommand=scrollbar.set)

        self.window_listbox.bind("<Double-Button-1>", self.on_window_activate)
        self._window_handles = []

        # Add these where you define your buttons or window properties
        self.root.bind('<space>', lambda e: self.start_listening())
        self.root.bind('<Escape>', lambda e: self.stop_listening())
        # Bind the 'Enter' key to the send function for speed
        self.command_entry.bind('<Return>', lambda event: self.handle_text_command())

        # Kick off periodic refresh of active window list
        self.refresh_window_list()

    def _init_orb_visual(self):
        """Draw a simple animated orb to act as a 'core' on the side."""
        c = self.orb_canvas
        w = int(c["width"])
        h = int(c["height"])
        cx, cy = w // 2, h // 2

        # Base outer ring
        self._orb_outer = c.create_oval(
            cx - 28, cy - 28, cx + 28, cy + 28,
            outline="#00e5ff",
            width=2
        )
        # Inner glow
        self._orb_inner = c.create_oval(
            cx - 16, cy - 16, cx + 16, cy + 16,
            fill="#00bfa5",
            outline=""
        )
        # Pulsing center
        self._orb_pulse = c.create_oval(
            cx - 6, cy - 6, cx + 6, cy + 6,
            fill="#e0f7fa",
            outline=""
        )
        self._orb_pulse_dir = 1
        self._animate_orb_pulse()

    def _animate_orb_pulse(self):
        """Subtle breathing animation for the orb center."""
        try:
            c = self.orb_canvas
        except Exception:
            return

        try:
            x0, y0, x1, y1 = c.coords(self._orb_pulse)
        except Exception:
            return

        # Compute new size
        delta = 0.8 * self._orb_pulse_dir
        x0 -= delta
        y0 -= delta
        x1 += delta
        y1 += delta

        # Clamp sizes
        max_radius = 10
        min_radius = 4
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2
        r = (x1 - x0) / 2
        if r > max_radius:
            r = max_radius
            self._orb_pulse_dir = -1
        elif r < min_radius:
            r = min_radius
            self._orb_pulse_dir = 1

        c.coords(self._orb_pulse, cx - r, cy - r, cx + r, cy + r)
        # Schedule next frame
        self.root.after(90, self._animate_orb_pulse)

    def refresh_window_list(self):
        """Populate the ACTIVE WINDOWS panel using pygetwindow, if available."""
        if not gw:
            # If pygetwindow missing, do nothing
            return

        try:
            windows = gw.getAllWindows()
        except Exception:
            windows = []

        self._window_handles = []
        self.window_listbox.delete(0, tk.END)

        for w in windows:
            try:
                title = (w.title or "").strip()
                if not title or not w.isVisible:
                    continue
                label = title
                self._window_handles.append(w)
                self.window_listbox.insert(tk.END, label)
            except Exception:
                continue

        # Update every few seconds
        self.root.after(4000, self.refresh_window_list)

    def on_window_activate(self, event=None):
        """When the user double-clicks a window entry, bring that app to the front."""
        if not self._window_handles:
            return
        try:
            idx = self.window_listbox.curselection()
            if not idx:
                return
            w = self._window_handles[idx[0]]
            try:
                w.activate()
            except Exception:
                try:
                    w.minimize()
                    w.restore()
                except Exception:
                    pass
        except Exception:
            pass

    def handle_command(self, text: str):
        """Handle a simple text command (fallback/example)."""
        if not text:
            self.voice_engine.speak("I didn't catch that, sir.")
            return

        print(f"Processing: {text}")
        if "hello" in text:
            self.voice_engine.speak("Hello sir, how can I help you today?")
        else:
            self.voice_engine.speak("I understood the command, but I don't have a protocol for that yet.")

    def handle_text_command(self, event=None):
        """Called by the Send button or Enter key. Routes typed text to the command processor.

        If the processor doesn't recognize the command, fall back to `handle_command`.
        """
        try:
            text = self.command_entry.get().strip()
        except Exception:
            text = ''

        # Clear the entry for convenience
        try:
            self.command_entry.delete(0, tk.END)
        except Exception:
            pass

        if not text:
            self.voice_engine.speak("Please type a command.")
            return

        self.log(f"Typed command: {text}")

        handled = False
        try:
            if hasattr(self, 'command_processor') and self.command_processor:
                handled = self.command_processor.process(text)
        except Exception as e:
            print(f"Error processing text command: {e}")
            self.voice_engine.speak("There was an error processing that command.")

        if not handled:
            # Fallback: local/simple handler
            try:
                self.handle_command(text)
            except Exception as e:
                print(f"Fallback handler error: {e}")
                self.voice_engine.speak("I couldn't handle that command.")
    
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
    
    def start_xo_game(self):
        """Launch XO game via command processor."""
        if hasattr(self, 'command_processor') and self.command_processor:
            self.command_processor.start_xo_game("xo")
        else:
            self.voice_engine.speak("Command processor not available.")
    
    def toggle_chatbot(self):
        """Toggle chatbot mode on/off."""
        if not hasattr(self, 'command_processor') or not self.command_processor:
            self.voice_engine.speak("Command processor not available.")
            return
        
        if not self.command_processor.chatbot:
            self.voice_engine.speak("Chatbot module not available, bro.")
            return
        
        if self.command_processor.chatbot.chat_mode_active:
            self.command_processor.chatbot.deactivate()
            self.chatbot_button.config(text="💬 CHATBOT", bg='#00bcd4')
        else:
            self.command_processor.chatbot.activate()
            self.chatbot_button.config(text="💬 CHAT ON", bg='#4caf50')
    
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
        # Loop while the GUI believes we're listening
        while self.is_listening:
            try:
                # SAFETY CHECK: don't listen while TTS playback is busy
                if pygame and getattr(pygame, 'mixer', None):
                    try:
                        if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                            time.sleep(0.2)
                            continue
                    except Exception:
                        pass

                # Prefer the lightweight listen_for_command helper
                text = None
                try:
                    if hasattr(self.voice_engine, 'listen_for_command'):
                        text = self.voice_engine.listen_for_command()
                    elif hasattr(self.voice_engine, 'listen'):
                        text = self.voice_engine.listen()
                except Exception as e:
                    print(f"Listen error: {e}")
                    text = None

                if text:
                    text = text.strip()
                    self.log(f"Heard: {text}")
                    # Route to the command processor first
                    handled = False
                    try:
                        if hasattr(self, 'command_processor') and self.command_processor:
                            handled = self.command_processor.process(text)
                    except Exception as e:
                        print(f"Processing error: {e}")
                        try:
                            self.voice_engine.speak("There was an error processing your command.")
                        except Exception:
                            pass

                    if not handled:
                        # Fallback local handler
                        try:
                            self.handle_command(text)
                        except Exception as e:
                            print(f"Fallback handler error: {e}")

                # small sleep to avoid busy loop
                time.sleep(0.1)

            except Exception as e:
                print(f"Loop error: {e}")
                time.sleep(0.5)

        # Reset UI state when loop exits
        try:
            self.is_listening = False
            self.listen_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.update_status("Stopped", '#e74c3c')
            self.log("Voice listening stopped")
        except Exception:
            pass
    def start_friday(self):
        # 1. Start the permanent background listener
        # This keeps the mic stream OPEN and STABLE
        if hasattr(self.voice_engine, 'recognizer') and self.voice_engine.recognizer:
            try:
                self.voice_engine.recognizer.listen_in_background(
                    self.voice_engine.mic,
                    self.background_callback
                )
                print("Mic stream stabilized.")
            except Exception as e:
                print(f"Could not start background listener: {e}")

    def background_callback(self, recognizer, audio):
        """This runs every time the mic hears sound without closing the stream."""
        try:
            if self.is_hidden:
                # Fast check for wake word
                text = recognizer.recognize_google(audio).lower()
                if "friday" in text:
                    self.root.after(0, self.show_interface)
        except Exception:
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
