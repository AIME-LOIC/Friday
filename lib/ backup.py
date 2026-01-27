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
        # config.json lives at the repository root (one level up from lib)
        config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.json'))
        cfg = None
        try:
            with open(config_path, 'r') as f:
                cfg = json.load(f)
        except Exception:
            cfg = None

        # Recognizer may be None if speech_recognition isn't installed
        self.recognizer = sr.Recognizer() if sr else None
        if self.recognizer:
            mic_cfg = (cfg or {}).get('microphone', {})
            self.recognizer.energy_threshold = min(mic_cfg.get('energy_threshold', 150), 300)
            self.recognizer.dynamic_energy_threshold = mic_cfg.get('dynamic_energy', True)
            self.recognizer.pause_threshold = mic_cfg.get('pause_threshold', 0.45)

        # 2. Audio Mixer Init
        try:
            if pygame and not pygame.mixer.get_init():
                pygame.mixer.pre_init(44100, -16, 2, 2048)
                pygame.mixer.init()
        except Exception as e:
            print(f"Mixer Init Error: {e}")

        # 3. HARDENED Microphone Initialization
        self.mic = None
        if sr:
            mic_cfg = (cfg or {}).get('microphone', {})
            sample_rate = mic_cfg.get('sample_rate', 48000)
            device_index = mic_cfg.get('device_index', None)

            try:
                # On Kali, sometimes we need to force a specific chunk size to avoid ALSA underruns
                if device_index is not None:
                    self.mic = sr.Microphone(device_index=device_index, sample_rate=sample_rate)
                else:
                    # Logic to find a working default
                    self.mic = sr.Microphone(sample_rate=sample_rate)
            except Exception as e:
                print(f"ALSA/Jack Mic Error: {e}. Attempting fallback...")
                try:
                    # Fallback to standard 16k rate if 48k is rejected by the driver
                    self.mic = sr.Microphone(sample_rate=16000)
                except Exception as e:
                    
                    print("Critical Error: No working microphone found. ",e)
                    self.mic = None

        # TTS queue and control
        self.tts_queue = queue.Queue()
        self.stop_event = threading.Event()

        # Speech recognition runtime settings (defaults can be overridden by config.json)
        sr_cfg = (cfg or {}).get('speech_recognition', {})
        self.sr_timeout = int(sr_cfg.get('timeout', 10))
        self.sr_phrase_limit = int(sr_cfg.get('phrase_limit', 15))

        # TTS runtime prefs (can be overridden in config.json under 'assistant')
        assistant_cfg = (cfg or {}).get('assistant', {})
        # Use a slightly slower and softer default to sound less robotic.
        self.tts_rate = assistant_cfg.get('voice_speed', 120)
        self.tts_volume = assistant_cfg.get('voice_volume', 0.85)
        # prefer online (gTTS) when configured and installed
        self.prefer_online_tts = bool(assistant_cfg.get('prefer_online_tts', False))
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

        # After TTS thread is started, attempt to discover and set the best
        # available female voice (this will also update a running pyttsx3
        # engine if one is created).
        try:
            self.discover_and_set_female_voice()
        except Exception:
            pass

    def listen_for_command(self):
        """Hardened listener to prevent crashes on ALSA/Hardware failure."""
        if not self.recognizer or not self.mic:
            print("SpeechRecognition or Microphone not initialized.")
            return None

        # PRE-FLIGHT CHECK: Avoid the 'NoneType' close error
        # If the microphone object exists but the hardware is locked, 
        # entering the context manager will fail.
        try:
            source = self.mic
            # We use a manual open check if possible, or a wrapped context
            with source as audio_source:
                print("Listening for command...")
                
                # 1. Faster calibration (1.0s is long and can cause ALSA timeouts)
                try:
                    self.recognizer.adjust_for_ambient_noise(audio_source, duration=0.5)
                except Exception as e:
                    print(f"Noise calibration failed: {e}")

                # 2. Capture Audio
                try:
                    audio = self.recognizer.listen(
                        audio_source, 
                        timeout=self.sr_timeout, 
                        phrase_time_limit=self.sr_phrase_limit
                    )
                except sr.WaitTimeoutError:
                    self.speak("I didn't hear anything, sir.")
                    return None
                except Exception as e:
                    print(f"Capture error: {e}")
                    return None

                # 3. Recognition
                try:
                    return self.recognizer.recognize_google(audio).lower()
                except sr.UnknownValueError:
                    # Don't speak here to avoid spamming if there's background noise
                    return None
                except sr.RequestError:
                    self.speak("Network error. Check your connection.")
                    return None

        except (AttributeError, AssertionError) as e:
            # This specifically catches the 'NoneType' close and stream errors
            print(f"Microphone Hardware Lock: {e}")
            self.speak("The audio hardware is currently busy or unavailable.")
            return None
        except Exception as e:
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