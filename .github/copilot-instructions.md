# Copilot / AI Agent Instructions for "Friday" (Personal Voice Assistant)

This file gives concise, actionable guidance for an AI coding agent to be immediately productive in this codebase.

Overview
- Purpose: a local, offline-capable Personal Voice Assistant (Tkinter GUI) built in Python.
- Key runtime components: `main.py` (GUI + app lifecycle), `launcher.py` (menu/runner), `lib/voice_engine.py` (STT/TTS + audio threading), `lib/command_processor.py` (intent parsing + handlers), `lib/utilities.py` (web, weather, app launcher).

Quick dev workflows
- Create and activate a venv, install deps:
  - python3 -m venv venv
  - source venv/bin/activate
  - pip install -r requirements.txt
- Run the app (dev): `python launcher.py` then choose option 1 or `python main.py`.
- Run diagnostics (imports, mic, TTS): `python setup.py` (automated checks included).

Architecture notes the agent should know
- VoiceEngine uses `speech_recognition` for live STT, `gTTS`+`pygame` for TTS playback and a thread-safe queue (`tts_queue`) to avoid blocking the UI.
- Wake-word detection is implemented by calling the system `pocketsphinx` binary from `VoiceEngine.listen_offline()` — this is a subprocess call, not a Python library call. Ensure system pocketsphinx is installed on the host for wake-word tests.
- `main.py` maintains a background listener thread and an `is_hidden` state used to control wake-word detection vs. full listening.
- `CommandProcessor.process()` uses simple substring matching (ordered checks for 'search', 'research', then scanning command keys). Edit `_initialize_commands()` to add handlers.
- `lib/utilities.py` uses DuckDuckGo scraping (`requests` + `BeautifulSoup`) and `wttr.in` for weather; no API keys required.

Project-specific conventions and gotchas
- TTS implementation: text is rendered to temporary MP3 files via `gTTS` then played with `pygame.mixer`. Files are created and deleted quickly; race conditions handled by unique filenames and `pygame.mixer.unload()`.
- Stopping speech: call `voice_engine.stop_speaking()` which sets `stop_event` and drains the queue.
- Audio device and sample rate: `VoiceEngine` creates the `Microphone(sample_rate=48000)` explicitly. Tests and changes should respect that sample rate to avoid audio glitches.
- Many comments note Python 3.13 quirks; prefer the project's provided venv or Python 3.7+ for development; `friday/bin/python3.13` exists in the workspace but CI may use a different interpreter.

Where to make common edits (examples)
- Add a new voice command:
  - Edit `lib/command_processor.py` -> `_initialize_commands()` add `'my command': self.my_handler`
  - Add method `def my_handler(self, command: str): ...` and call `self.voice_engine.speak("...")` for voice feedback.
- Change voice speed/volume defaults:
  - `config.json` contains `assistant.voice_speed` and `assistant.voice_volume` defaults.
  - Runtime change: `VoiceEngine.set_voice_properties(rate=..., volume=...)` (called from GUI settings in `main.py`).
- Fix wake-word: `VoiceEngine.listen_offline()` calls `pocketsphinx` via subprocess with `-keyphrase friday`. To change the keyword, update that command and any UI / messages referencing the wake-word.

Testing and debugging tips
- Use `python setup.py` to run import, mic and TTS checks before deeper debugging.
- To debug TTS pipeline: insert logging in `_process_tts_queue()`; check that temporary `voice_*.mp3` files are created and deleted.
- If the assistant never hears the wake-word, verify OS-level audio servers (PulseAudio / PipeWire) and that `pocketsphinx` is callable from shell.

Files & locations you will reference frequently
- `main.py` — GUI, lifecycle, background listener
- `launcher.py` — quick entrypoint for running different modes and installing deps
- `lib/voice_engine.py` — STT/TTS implementation, mic config, thread queue
- `lib/command_processor.py` — command mapping and handlers (primary place to add features)
- `lib/utilities.py` — web search, weather, app launcher, system command execution
- `config.json` — runtime tunables (voice speed, mic device, thresholds)
- `requirements.txt`, `install.sh`, `setup.py` — dependency and setup instructions

Security & side-effects
- Code executes system commands (`execute_system_command`) — treat any new input handling that reaches this code as potentially dangerous. Never run arbitrary untrusted strings without sanitization.

If you update this guidance
- Merge preserving short examples above and keep the actionable run/test commands. Ask the human for clarification if any new runtime patterns are introduced (new external services, changed wake-word mechanism, or modified audio stack).

---
Please review these instructions and tell me if you'd like more detail on any section (examples: unit test entry-points, how to add CI checks, or step-by-step TTS debugging). 
