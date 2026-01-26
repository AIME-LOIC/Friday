import os
import time
import pygame
import threading
import queue
import speech_recognition as sr
from gtts import gTTS
import subprocess
from typing import Optional
import pyttsx3

class VoiceEngine:
    """Handles speech-to-text and thread-safe text-to-speech for Kali Linux."""
    
    def __init__(self):
        # 1. Configuration
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 150 
        self.recognizer.dynamic_energy_threshold = False
        self.recognizer.pause_threshold = 0.6
        
        # 2. Audio Mixer (Safe frequency for gTTS)
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(44100, -16, 2, 2048)
                pygame.mixer.init()
        except Exception as e:
            print(f"Mixer Init Error: {e}")

        # 3. Setup the Mic with the FIXED Sample Rate
        # This is what made your test.py work!
        self.mic = sr.Microphone(sample_rate=48000)
        
        # 4. Threading for TTS
        self.tts_queue = queue.Queue()
        self.stop_event = threading.Event()
        threading.Thread(target=self._process_tts_queue, daemon=True).start()
 
    def listen_for_command(self):
        """Used when the UI is open to catch a specific command."""
        try:
            with self.mic as source:
                # We don't re-adjust noise here to keep the mic 'hot'
                print("Listening for command...")
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                return self.recognizer.recognize_google(audio).lower()
        except Exception:
            self.speak("I can't hear you, sir.")
            return None

    def speak(self, text: str):
        """Adds text to the speech queue. Call this from any thread."""
        if text and text.strip():
            print(f"Queueing: {text}")
            self.tts_queue.put(text)

   

# In __init__
   

    def _process_tts_queue(self):
        """Standard gTTS playback thread with error reporting."""
        if not pygame.mixer.get_init():
            pygame.mixer.init(44100)
            
        while True:
            try:
                text = self.tts_queue.get()
                if text is None: break
                
                print(f"Friday attempting to speak: {text}")
                
                # Create a unique filename to avoid 'File in use' errors
                filename = f"voice_{int(time.time() * 1000)}.mp3"
                
                tts = gTTS(text=text, lang='en')
                tts.save(filename)
                
                pygame.mixer.music.load(filename)
                pygame.mixer.music.play()
                
                while pygame.mixer.music.get_busy():
                    if self.stop_event.is_set():
                        pygame.mixer.music.stop()
                        break
                    time.sleep(0.1)
                
                pygame.mixer.music.unload() # Releases the file
                
                if os.path.exists(filename):
                    os.remove(filename)
                    
            except Exception as e:
                print(f"CRITICAL VOICE ERROR: {e}")
            finally:
                self.tts_queue.task_done()

    def listen(self):
        with self.mic as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                print("Waiting for your voice...")
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                text = self.recognizer.recognize_google(audio).lower()
                return text
            except Exception as e:
                print(f"Mic error: {e}")
                # FORCE a verbal response so you know it failed
                self.speak("I'm sorry sir, I couldn't hear you.")
                return None

    def listen_offline(self, timeout=3):
        """
        Wake Word Listener (High Speed).
        Runs the system pocketsphinx directly to bypass Python 3.13 issues.
        """
        try:
            # We use '-time no' and '-logfn /dev/null' to keep it quiet and fast
            cmd = [
                "pocketsphinx", "kws", 
                "-keyphrase", "friday", 
                "-threshold", "1e-20",
                "-adcdev", "default",
                "-logfn", "/dev/null" 
            ]
            
            # Capture the output of the system-level engine
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            
            if "friday" in process.stdout.lower():
                return "friday"
            return None
        except Exception:
            return None

    def stop_speaking(self):
        """Immediately terminates the current speech and clears pending queue."""
        self.stop_event.set()
        while not self.tts_queue.empty():
            try:
                self.tts_queue.get_nowait()
                self.tts_queue.task_done()
            except queue.Empty:
                break

    def set_voice_properties(self, rate: int = 150, volume: float = 0.9):
        """Adjusts the mixer volume."""
        # Note: gTTS rate cannot be changed mid-playback as it's a static MP3
        pygame.mixer.music.set_volume(volume)


    import subprocess

    # def listen_offline(self, timeout=3):
    #  """
    #  Uses the system-level pocketsphinx to avoid Python 3.13 
    #  compilation errors. Fast and reliable on Kali.
    #   """
    #  try:
    #     # This command listens for 'friday' specifically
    #     # -adcdev default tells it to use your PipeWire mic
    #     cmd = [
    #         "pocketsphinx", "kws", 
    #         "-keyphrase", "friday", 
    #         "-threshold", "1e-20",
    #         "-time", "yes",
    #         "-adcdev", "default"
    #     ]
        
    #     # We run it as a subprocess with a timeout
    #     process = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        
    #     if "friday" in process.stdout.lower():
    #         return "friday"
    #  except subprocess.TimeoutExpired:
    #     return None
    #  except Exception as e:
    #     # Silencing the ALSA noise in the console
    #     return None