import os
import time
import json
import threading
import tempfile
import queue
from typing import Optional

# Optional imports - gracefully handle missing system packages during static analysis
try:
    import pygame
except Exception:
    pygame = None

try:
    import speech_recognition as sr
except Exception:
    sr = None

try:
    from gtts import gTTS
except Exception:
    gTTS = None

try:
    import pocketsphinx
except Exception:
    pocketsphinx = None

try:
    import pyttsx3
except Exception:
    pyttsx3 = None

class VoiceEngine:
    """Handles speech-to-text and thread-safe text-to-speech for Kali Linux.

    This implementation is defensive: heavy external libraries are optional at import time.
    Runtime operations will check availability and report clear errors if missing.
    """

    def __init__(self):
        # 1. Load config
        config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.json'))
        cfg = None
        try:
            with open(config_path, 'r') as f:
                cfg = json.load(f)
        except Exception:
            cfg = None

        # 2. Recognizer Setup
        self.recognizer = sr.Recognizer() if sr else None
        if self.recognizer:
            mic_cfg = (cfg or {}).get('microphone', {})
            # Capping threshold to prevent "deafness" in noisy environments
            self.recognizer.energy_threshold = min(mic_cfg.get('energy_threshold', 150), 300)
            self.recognizer.dynamic_energy_threshold = mic_cfg.get('dynamic_energy', True)
            self.recognizer.pause_threshold = 0.5 
            self.recognizer.non_speaking_duration = 0.4

        # 3. Mixer Init
        try:
            if pygame and not pygame.mixer.get_init():
                pygame.mixer.pre_init(44100, -16, 2, 2048)
                pygame.mixer.init()
        except Exception as e:
            print(f"Mixer Init Error: {e}")

        # 4. KALI-SPECIFIC MIC INITIALIZATION
        self.mic = None
        if sr:
            # Based on your scan, Index 4 is 'pulse' and Index 5 is 'default'
            # These are significantly more stable than the HDMI indexes (0-2)
            try:
                print("Attempting to lock PulseAudio source (Index 4)...")
                self.mic = sr.Microphone(device_index=4, sample_rate=16000)
            except Exception:
                try:
                    print("Index 4 busy, attempting Default (Index 5)...")
                    self.mic = sr.Microphone(device_index=5, sample_rate=16000)
                except Exception as e:
                    print(f"Hardware initialization failed: {e}")
                    self.mic = None

        # 5. TTS Settings & Threading
        self.tts_queue = queue.Queue()
        self.stop_event = threading.Event()
        
        sr_cfg = (cfg or {}).get('speech_recognition', {})
        self.sr_timeout = int(sr_cfg.get('timeout', 10))
        self.sr_phrase_limit = int(sr_cfg.get('phrase_limit', 15))

        assistant_cfg = (cfg or {}).get('assistant', {})
        self.tts_rate = assistant_cfg.get('voice_speed', 135) # Slightly faster for "Friday" feel
        self.tts_volume = assistant_cfg.get('voice_volume', 0.85)
        self.prefer_online_tts = bool(assistant_cfg.get('prefer_online_tts', False))
        
        self.preferred_voice = None
        # Voice discovery is handled in a separate method to keep init clean
        if pyttsx3:
            try:
                self.discover_and_set_female_voice()
            except Exception:
                pass

        # Start the TTS processing thread
        threading.Thread(target=self._process_tts_queue, daemon=True).start()

    def listen_for_command(self):
        """Hardened listener to prevent crashes on ALSA/Hardware failure."""
        if not self.recognizer or not self.mic:
            print("Hardware not initialized.")
            return None

        try:
            # Entering the 'with' block is what actually opens the ALSA stream.
            with self.mic as source:
                print("Listening...")
                
                # Check if the stream actually opened (Kali hardware check)
                if not hasattr(source, 'stream') or source.stream is None:
                    raise RuntimeError("ALSA stream failed to open.")

                # 1. Faster calibration
                try:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                except Exception:
                    pass

                # 2. Capture with explicit source verification
                try:
                    # We pass 'source' here, NOT 'self.mic' or 'audio_source'
                    audio = self.recognizer.listen(
                        source, 
                        timeout=self.sr_timeout, 
                        phrase_time_limit=self.sr_phrase_limit
                    )
                except sr.WaitTimeoutError:
                    return None
                except Exception as e:
                    print(f"Capture error: {e}")
                    return None

                # 3. Recognition
                try:
                    return self.recognizer.recognize_google(audio).lower()
                except sr.UnknownValueError:
                    # Fallback to Sphinx if internet/Google fails
                    if pocketsphinx:
                        try:
                            return self.recognizer.recognize_sphinx(audio).lower()
                        except Exception:
                            return None
                    return None
                    
        except Exception as e:
            # This catches the 'NoneType' close error and 'Audio source' error
            if "Audio source must be entered" in str(e) or "NoneType" in str(e):
                print("Critical: Audio hardware is locked or busy.")
            else:
                print(f"Unexpected Mic Error: {e}")
            return None

    def speak(self, text: str):
        """Adds text to the speech queue. Call this from any thread."""
        if not text or not text.strip():
            return
        print(f"Queueing: {text}")
        self.tts_queue.put(text)

    def _process_tts_queue(self):
        """gTTS playback thread. If gTTS/pygame missing, log and drain queue."""
        # lazy-init engine inside the TTS thread to avoid cross-thread issues
        pyttsx3_engine = None
        # simple on-disk cache for generated gTTS mp3s to avoid re-generating
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'voice_cache')
        try:
            os.makedirs(cache_dir, exist_ok=True)
        except Exception:
            cache_dir = None
        # If local pyttsx3 is available, initialize it immediately inside the thread
        if pyttsx3:
            try:
                pyttsx3_engine = pyttsx3.init()
                try:
                    if self.preferred_voice:
                        pyttsx3_engine.setProperty('voice', self.preferred_voice)
                except Exception:
                    pass
                try:
                    pyttsx3_engine.setProperty('rate', int(self.tts_rate))
                except Exception:
                    pass
                try:
                    pyttsx3_engine.setProperty('volume', float(self.tts_volume))
                except Exception:
                    pass
                try:
                    self._pyttsx3_engine = pyttsx3_engine
                except Exception:
                    pass
            except Exception:
                pyttsx3_engine = None
        while True:
            try:
                text = self.tts_queue.get()
                if text is None:
                    break
                # If configured to prefer online TTS and gTTS+pygame are available, use that first
                if self.prefer_online_tts and gTTS and pygame:
                    try:
                        # ensure mixer is initialized with correct sample rate
                        try:
                            if not pygame.mixer.get_init():
                                pygame.mixer.pre_init(44100, -16, 2, 2048)
                                pygame.mixer.init()
                        except Exception:
                            pass

                        filename = None
                        try:
                            # use cache if available to avoid repeated gTTS calls
                            fn = None
                            if cache_dir:
                                try:
                                    import hashlib
                                    h = hashlib.sha1(text.encode('utf-8')).hexdigest()
                                    fn = os.path.join(cache_dir, f"{h}.mp3")
                                    if os.path.exists(fn):
                                        filename = fn
                                except Exception:
                                    fn = None
                            if not filename:
                                # create temp mp3 file
                                fd, tmpfn = tempfile.mkstemp(prefix='voice_', suffix='.mp3')
                                os.close(fd)
                                filename = tmpfn
                                tts = gTTS(text=text, lang='en', tld='co.uk')
                                tts.save(filename)
                                # save to cache if possible
                                try:
                                    if fn:
                                        import shutil
                                        shutil.copyfile(filename, fn)
                                except Exception:
                                    pass
                            try:
                                # Prefer system PulseAudio/PipeWire player if available
                                from shutil import which
                                paplay = which('paplay') or which('pw-play')
                                if paplay:
                                    try:
                                        import subprocess
                                        subprocess.run([paplay, filename], check=False)
                                    except Exception as e:
                                        print('paplay/pw-play failed, falling back to pygame:', e)
                                        pygame.mixer.music.load(filename)
                                        pygame.mixer.music.set_volume(float(self.tts_volume))
                                        pygame.mixer.music.play()
                                        while pygame.mixer.music.get_busy():
                                            if self.stop_event.is_set():
                                                try:
                                                    pygame.mixer.music.stop()
                                                except Exception:
                                                    pass
                                                break
                                            time.sleep(0.1)
                                        try:
                                            pygame.mixer.music.unload()
                                        except Exception:
                                            pass
                                else:
                                    pygame.mixer.music.load(filename)
                                    pygame.mixer.music.set_volume(float(self.tts_volume))
                                    pygame.mixer.music.play()
                                    while pygame.mixer.music.get_busy():
                                        if self.stop_event.is_set():
                                            try:
                                                pygame.mixer.music.stop()
                                            except Exception:
                                                pass
                                            break
                                        time.sleep(0.1)
                                    try:
                                        pygame.mixer.music.unload()
                                    except Exception:
                                        pass
                            except Exception as e:
                                print('pygame playback error for gTTS:', e)
                        finally:
                            # if we created a temp file that's not the cached file, remove it
                            try:
                                if filename and cache_dir and not filename.startswith(cache_dir):
                                    if os.path.exists(filename):
                                        os.remove(filename)
                            except Exception:
                                pass
                    except Exception as e:
                        print('gTTS TTS error:', e)
                    finally:
                        try:
                            self.tts_queue.task_done()
                        except Exception:
                            pass
                    continue

                # Prefer local pyttsx3 if available (no external network dependency)
                if pyttsx3:
                    try:
                        # initialize engine once per thread
                        # engine was already initialized at thread start if possible
                        if pyttsx3_engine is None:
                            pyttsx3_engine = pyttsx3.init()
                            try:
                                self._pyttsx3_engine = pyttsx3_engine
                            except Exception:
                                pass
                            try:
                                if self.preferred_voice:
                                    pyttsx3_engine.setProperty('voice', self.preferred_voice)
                            except Exception:
                                pass
                            try:
                                pyttsx3_engine.setProperty('rate', int(self.tts_rate))
                            except Exception:
                                pass
                            try:
                                pyttsx3_engine.setProperty('volume', float(self.tts_volume))
                            except Exception:
                                pass

                        # Speak the phrase. Respect stop_event by stopping the engine if triggered.
                        pyttsx3_engine.say(text)
                        pyttsx3_engine.runAndWait()
                        # reset stop_event after successful utterance
                        if self.stop_event.is_set():
                            try:
                                pyttsx3_engine.stop()
                            except Exception:
                                pass
                            self.stop_event.clear()
                    except Exception as e:
                        print(f"pyttsx3 TTS error: {e}")
                    finally:
                        self.tts_queue.task_done()
                    continue

                # Fallback to gTTS + pygame if available and online preference not set
                if gTTS and pygame:
                    try:
                        try:
                            if not pygame.mixer.get_init():
                                pygame.mixer.pre_init(44100, -16, 2, 2048)
                                pygame.mixer.init()
                        except Exception:
                            pass
                        filename = None
                        try:
                            fd, filename = tempfile.mkstemp(prefix='voice_', suffix='.mp3')
                            os.close(fd)
                            tts = gTTS(text=text, lang='en', tld='co.uk')
                            tts.save(filename)
                            try:
                                pygame.mixer.music.load(filename)
                                pygame.mixer.music.set_volume(float(self.tts_volume))
                                pygame.mixer.music.play()
                                while pygame.mixer.music.get_busy():
                                    if self.stop_event.is_set():
                                        try:
                                            pygame.mixer.music.stop()
                                        except Exception:
                                            pass
                                        break
                                    time.sleep(0.1)
                                try:
                                    pygame.mixer.music.unload()
                                except Exception:
                                    pass
                            except Exception as e:
                                print('pygame playback error for gTTS fallback:', e)
                        finally:
                            if filename and os.path.exists(filename):
                                try:
                                    os.remove(filename)
                                except Exception:
                                    pass
                    except Exception as e:
                        print('gTTS fallback error:', e)
                    finally:
                        try:
                            self.tts_queue.task_done()
                        except Exception:
                            pass
                    continue

                # If no TTS backend available, just log
                print('TTS or audio backend not available. Would speak:', text)
                try:
                    self.tts_queue.task_done()
                except Exception:
                    pass

            except Exception as e:
                print(f"CRITICAL VOICE ERROR: {e}")
            finally:
                try:
                    self.tts_queue.task_done()
                except Exception:
                    pass

    def listen(self):
        if not self.recognizer or not self.mic:
            print("SpeechRecognition not available on this host.")
            return None

        with self.mic as source:
            # calibrate to ambient noise
            try:
                self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
            except Exception:
                pass
            try:
                print("Waiting for your voice...")
                audio = self.recognizer.listen(source, timeout=self.sr_timeout, phrase_time_limit=self.sr_phrase_limit)
                try:
                    return self.recognizer.recognize_google(audio).lower()
                except sr.UnknownValueError:
                    if pocketsphinx:
                        try:
                            return self.recognizer.recognize_sphinx(audio).lower()
                        except Exception:
                            self.speak("I'm sorry sir, I couldn't understand you.")
                            return None
                    else:
                        self.speak("I'm sorry sir, I couldn't understand you.")
                        return None
                except sr.RequestError:
                    # network issue; try offline Sphinx if available
                    if pocketsphinx:
                        try:
                            return self.recognizer.recognize_sphinx(audio).lower()
                        except Exception:
                            self.speak("I'm sorry sir, I couldn't hear you.")
                            return None
                    else:
                        self.speak("I'm sorry sir, I couldn't hear you.")
                        return None
            except Exception as e:
                print(f"Mic error: {e}")
                self.speak("I'm sorry sir, I couldn't hear you.")
                return None

    def listen_offline(self, timeout=3):
        
        """Wake Word Listener via system pocketsphinx subprocess.

        Returns the keyphrase string if detected, otherwise None.
        """
        try:
            import time
            import subprocess
            cmd = [
                "pocketsphinx", "kws",
                "-keyphrase", "friday",
                "-threshold", "1e-20",
                "-adcdev", "default",
                "-logfn", "/dev/null",
            ]
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            time.sleep(0.1)
            if "friday" in (process.stdout or "").lower():
                return "friday"
            return None
        except Exception:
            return None

    def stop_speaking(self):
        """Immediately terminates TTS playback and clears pending queue."""
        self.stop_event.set()
        while not self.tts_queue.empty():
            try:
                self.tts_queue.get_nowait()
                self.tts_queue.task_done()
            except queue.Empty:
                break

    def set_voice_properties(self, rate: int = 150, volume: float = 0.9):
        # Update runtime preferences used by pyttsx3 and pygame
        try:
            self.tts_rate = int(rate)
        except Exception:
            pass
        try:
            self.tts_volume = float(volume)
        except Exception:
            pass

        # If a running pyttsx3 engine exists, update it immediately.
        try:
            eng = getattr(self, '_pyttsx3_engine', None)
            if eng is not None:
                try:
                    eng.setProperty('rate', int(self.tts_rate))
                except Exception:
                    pass
                try:
                    eng.setProperty('volume', float(self.tts_volume))
                except Exception:
                    pass
        except Exception:
            pass

        if pygame:
            try:
                pygame.mixer.music.set_volume(float(volume))
            except Exception:
                pass

    def discover_and_set_female_voice(self):
        """Scan and force the best female voice for Linux/Kali."""
        if not pyttsx3:
            return None

        try:
            # We initialize a local probe, but we must also update the 
            # background engine if it exists.
            probe = pyttsx3.init()
            voices = probe.getProperty('voices') or []
            
            # Prioritize 'Natalie' as requested, then high-quality female variants
            female_keywords = ('natalie', 'female', 'zira', 'susan', 'kate', 'victoria', 'anna', 'amy')
            eng_keywords = ('en_us', 'en-us', 'english', 'en_gb', 'en-gb', 'en')

            chosen = None

            # 1) Search for explicit Female/Natalie names in system voices
            for v in voices:
                v_id = str(getattr(v, 'id', '')).lower()
                v_name = str(getattr(v, 'name', '')).lower()
                combined = v_id + " " + v_name
                
                if 'natalie' in combined:
                    chosen = v.id
                    break
                if any(k in combined for k in female_keywords) and any(e in combined for e in eng_keywords):
                    chosen = v.id
                    # Don't break yet, keep looking for a better match like 'natalie'
            
            # 2) If no named female voice found, fallback to espeak-ng female variants
            # On Kali, 'en+f3' is the most natural 'Friday' style voice.
            if not chosen:
                for v in voices:
                    if 'en+f' in str(v.id).lower(): # Look for en+f1, en+f2, en+f3, etc.
                        chosen = v.id
                        break

            # 3) Apply selection to the actual running engine
            if chosen:
                self.preferred_voice = chosen
                print(f"Friday voice set to: {chosen}")
            else:
                # Absolute fallback for Linux espeak
                self.preferred_voice = 'en+f3'

            # Update the background thread's engine if it's already alive
            eng = getattr(self, '_pyttsx3_engine', None)
            if eng is not None:
                try:
                    eng.setProperty('voice', self.preferred_voice)
                    # Friday usually speaks slightly faster but with a calm volume
                    eng.setProperty('rate', 145) 
                except Exception as e:
                    print(f"Could not apply voice property: {e}")

            try:
                probe.stop()
            except:
                pass
                
            return self.preferred_voice
        except Exception as e:
            print(f"Voice Discovery Error: {e}")
            return None