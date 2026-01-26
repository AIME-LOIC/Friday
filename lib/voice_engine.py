import os
import time
import json
import threading
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
    import pyttsx3
except Exception:
    pyttsx3 = None

class VoiceEngine:
    """Handles speech-to-text and thread-safe text-to-speech for Kali Linux.

    This implementation is defensive: heavy external libraries are optional at import time.
    Runtime operations will check availability and report clear errors if missing.
    """

    def __init__(self):
        # Load optional runtime config (device index, thresholds)
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'config.json')
        cfg = None
        try:
            with open(config_path, 'r') as f:
                cfg = json.load(f)
        except Exception:
            cfg = None

        # Recognizer may be None if speech_recognition isn't installed
        self.recognizer = sr.Recognizer() if sr else None
        if self.recognizer:
            # Allow config overrides, fallback to sensible defaults
            mic_cfg = (cfg or {}).get('microphone', {})
            self.recognizer.energy_threshold = mic_cfg.get('energy_threshold', 150)
            # Enable dynamic energy by default to adapt to ambient noise quickly
            self.recognizer.dynamic_energy_threshold = mic_cfg.get('dynamic_energy', True)
            # Lower pause_threshold for snappier detection of short phrases
            self.recognizer.pause_threshold = mic_cfg.get('pause_threshold', 0.45)

        # Mixer init if pygame is available
        try:
            if pygame and not pygame.mixer.get_init():
                pygame.mixer.pre_init(44100, -16, 2, 2048)
                pygame.mixer.init()
        except Exception as e:
            print(f"Mixer Init Error: {e}")

        # Microphone object (may be None). Respect config device_index if provided.
        self.mic = None
        if sr:
            try:
                mic_cfg = (cfg or {}).get('microphone', {})
                device_index = mic_cfg.get('device_index', None)
                sample_rate = mic_cfg.get('sample_rate', 48000)
                if device_index is not None:
                    self.mic = sr.Microphone(device_index=device_index, sample_rate=sample_rate)
                else:
                    self.mic = sr.Microphone(sample_rate=sample_rate)
            except Exception as e:
                print(f"Warning: could not open configured microphone: {e}")
                try:
                    self.mic = sr.Microphone(sample_rate=48000)
                except Exception:
                    self.mic = None

        # TTS queue and control
        self.tts_queue = queue.Queue()
        self.stop_event = threading.Event()

        # TTS runtime prefs (can be overridden in config.json under 'assistant')
        assistant_cfg = (cfg or {}).get('assistant', {})
        # Use a slightly slower and softer default to sound less robotic.
        self.tts_rate = assistant_cfg.get('voice_speed', 120)
        self.tts_volume = assistant_cfg.get('voice_volume', 0.85)
        self.preferred_voice = None
        # We do not create a long-lived pyttsx3 engine on the main thread; instead
        # we'll initialize and reuse it inside the TTS thread to avoid cross-thread
        # issues. Here we only inspect available voices (best-effort) to pick a
        # likely female/English voice id.
        if pyttsx3:
            try:
                _probe = pyttsx3.init()
                _voices = _probe.getProperty('voices') or []
                # scoring heuristic: prefer voices that mention 'natalie' first (explicit user request),
                # then female indicators or common names
                # add 'natalie' here to allow explicit selection when available on the host
                female_keywords = ('female', 'natalie', 'zira', 'susan', 'kate', 'victoria', 'anna', 'alloy', 'amy')
                eng_keywords = ('en_us', 'en-us', 'english', 'en_gb', 'en-gb', 'en')
                chosen = None
                # Prefer an explicit 'natalie' voice if present
                for v in _voices:
                    combined = ((getattr(v, 'id', '') or '') + ' ' + (getattr(v, 'name', '') or '')).lower()
                    if 'natalie' in combined:
                        chosen = v.id
                        break
                # Then prefer other female indicators
                if not chosen:
                    for v in _voices:
                        vid = (getattr(v, 'id', '') or '').lower()
                        vname = (getattr(v, 'name', '') or '').lower()
                        combined = vid + ' ' + vname
                        if any(k in combined for k in female_keywords):
                            chosen = v.id
                            break
                if not chosen:
                    # prefer english voices next
                    for v in _voices:
                        vid = (getattr(v, 'id', '') or '').lower()
                        vname = (getattr(v, 'name', '') or '').lower()
                        combined = vid + ' ' + vname
                        if any(k in combined for k in eng_keywords):
                            chosen = v.id
                            break
                # fallback to first available voice
                if not chosen and _voices:
                    chosen = _voices[0].id
                self.preferred_voice = chosen
                try:
                    _probe.stop()
                except Exception:
                    pass
            except Exception:
                self.preferred_voice = None

        threading.Thread(target=self._process_tts_queue, daemon=True).start()

    def listen_for_command(self):
        """Used when the UI is open to catch a specific command."""
        if not self.recognizer or not self.mic:
            print("SpeechRecognition not available on this host.")
            return None

        try:
            with self.mic as source:
                print("Listening for command...")
                # Use shorter timeout and phrase_time_limit for snappier responses
                audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=4)
                return self.recognizer.recognize_google(audio).lower()
        except Exception:
            self.speak("I can't hear you, sir.")
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
        while True:
            try:
                text = self.tts_queue.get()
                if text is None:
                    break
                # Prefer local pyttsx3 if available (no external network dependency)
                if pyttsx3:
                    try:
                        # initialize engine once per thread
                        if pyttsx3_engine is None:
                            pyttsx3_engine = pyttsx3.init()
                            # expose engine on self so runtime setters can modify it
                            try:
                                self._pyttsx3_engine = pyttsx3_engine
                            except Exception:
                                pass
                            # Apply preferred voice/rate/volume if configured
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

                # Fallback to gTTS + pygame if available
                if not gTTS or not pygame:
                    print("TTS or audio backend not available. Would speak:", text)
                    self.tts_queue.task_done()
                    continue

                filename = f"voice_{int(time.time() * 1000)}.mp3"
                try:
                    tts = gTTS(text=text, lang='en')
                    tts.save(filename)
                    pygame.mixer.music.load(filename)
                    pygame.mixer.music.play()

                    while pygame.mixer.music.get_busy():
                        if self.stop_event.is_set():
                            pygame.mixer.music.stop()
                            break
                        time.sleep(0.1)

                    try:
                        pygame.mixer.music.unload()
                    except Exception:
                        pass
                finally:
                    if os.path.exists(filename):
                        try:
                            os.remove(filename)
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
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                print("Waiting for your voice...")
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                text = self.recognizer.recognize_google(audio).lower()
                return text
            except Exception as e:
                print(f"Mic error: {e}")
                self.speak("I'm sorry sir, I couldn't hear you.")
                return None

    def listen_offline(self, timeout=3):
        """Wake Word Listener via system pocketsphinx subprocess.

        Returns the keyphrase string if detected, otherwise None.
        """
        try:
            import subprocess
            cmd = [
                "pocketsphinx", "kws",
                "-keyphrase", "friday",
                "-threshold", "1e-20",
                "-adcdev", "default",
                "-logfn", "/dev/null",
            ]
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
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