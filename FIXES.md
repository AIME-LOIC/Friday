# Fixes applied (summary)

Date: 2026-01-27

This document lists the code fixes and verification steps I applied to get the project importing and to stabilize the speech path. It focuses on the urgent import failure and STT/TTS stabilizations in `lib/voice_engine.py`.

## Files changed

- `lib/voice_engine.py`
  - Fixed a SyntaxError caused by an unbalanced nested try/except in `listen_for_command()` which prevented `python main.py` from importing the package.
  - Simplified and clarified the `listen_for_command()` control flow. Behavior now:
    - ambient calibration (`adjust_for_ambient_noise`) -> `recognizer.listen(...)` with configured timeouts -> try Google STT -> fallback to pocketsphinx if available -> speak helpful messages on errors.
  - Ensured `recognizer.non_speaking_duration` is set and does not exceed `pause_threshold` to avoid the internal assertion (`pause_threshold >= non_speaking_duration >= 0`).
  - Kept previously-introduced TTS improvements:
    - `natalie`/female voice preference heuristic
    - gTTS (lang='en', tld='co.uk') with a small on-disk cache for repeated phrases
    - paplay/pw-play fallback for PulseAudio/PipeWire, then `pygame.mixer` fallback
    - pyttsx3 initialization and reuse INSIDE the TTS worker thread to avoid cross-thread engine issues and reduce latency

## Problems resolved

1. Import-time SyntaxError
   - Symptom: `Traceback ... lib/voice_engine.py line 232 except Exception: SyntaxError: expected 'except' or 'finally' block` when running `python main.py`.
   - Action: Rewrote `listen_for_command()` to remove the nested/mismatched try/except blocks and ensure proper exception handling.
   - Result: `lib/voice_engine.py` compiles and imports.

2. speech_recognition assertion
   - Symptom: `AssertionError` from inside `speech_recognition.listen()` complaining that `pause_threshold >= non_speaking_duration >= 0` was violated.
   - Action: Set a conservative `non_speaking_duration` default and forced `non_speaking_duration <= pause_threshold` when initializing the recognizer.
   - Result: Confirmed values after instantiation: `pause_threshold = 0.45` and `non_speaking_duration = 0.45` (satisfies assertion).

## Verification performed

- Syntax compile check:
  - `python -m py_compile lib/voice_engine.py` — PASS

- Direct import smoke test (loaded the module directly to avoid `lib/__init__` side-effects):
  - Loaded `lib/voice_engine.py` and confirmed `VoiceEngine` class exists.

- Instantiate and smoke-run TTS:
  - Created an instance of `VoiceEngine()` and called `.speak('Quick test phrase')`.
  - The phrase was queued; the TTS thread accepted the job. (Audio backend logs are printed on this host; you may or may not hear audio depending on system routing.)

- Recognizer checks:
  - Printed `pause_threshold` and `non_speaking_duration` after `VoiceEngine()` construction to confirm they are within acceptable bounds.

## Remaining issues / next steps (recommended)

- `ModuleNotFoundError: No module named 'pywhatkit'` when importing the `lib` package
  - Cause: `lib/__init__.py` imports `lib.command_processor`, which imports optional third-party packages that are not installed in the current venv.
  - Options to resolve:
    - Install the project requirements into the venv: `pip install -r requirements.txt` (recommended if you want the full app running).
    - Or modify `lib/__init__.py` to lazy-import `CommandProcessor` and other optional things so importing `lib` doesn't require every optional dependency.

- Audio routing warnings
  - You may see ALSA/SDL/JACK warnings in the logs. They are typically non-fatal; if you don't hear audio, check PulseAudio/PipeWire sinks and ensure the correct default sink is selected/unmuted.

- Second PC voice sounds robotic (espeak)
  - Linux systems often ship only espeak voices. To get a natural female voice you can:
    - Use gTTS (online) — already supported by code (requires internet and gTTS installed).
    - Install better system voices (e.g., `espeak-ng`, `festival`, or OS vendor voices), or install a local neural TTS (Coqui, Mimic3) — larger setup.

## Commands I ran (examples)

- Syntax check:
```bash
python -m py_compile lib/voice_engine.py
```

- Direct-module load and smoke test (example used during verification):
```bash
python - <<'PY'
import importlib.util
spec = importlib.util.spec_from_file_location('voice_engine','./lib/voice_engine.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
VE = mod.VoiceEngine()
VE.speak('Quick test phrase queued.')
PY
```

- To run the full app after installing deps:
```bash
source friday/bin/activate
pip install -r requirements.txt
python main.py
```

## Suggested small follow-ups I can do now (pick one)

- Install missing Python dependencies into the repo venv and then run `python main.py` to validate full app startup and flows.
- Modify `lib/__init__.py` to lazy-import `CommandProcessor` and optional helpers so `import lib` won't fail when optional deps are missing.
- Run the microphone/STT diagnostic: list microphones, record a short `debug_recording.wav`, and attempt recognition to confirm STT works end-to-end on this machine.

If you want, tell me which follow-up to run and I'll proceed (I can install deps or make `lib/__init__` lazy-imports, or run the mic diagnostic).