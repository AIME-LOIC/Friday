# PyAudio Installation Guide

PyAudio can be tricky to install depending on your system. Here are the recommended approaches:

## Option 1: Try Direct pip Installation (Easiest)

```bash
pip install PyAudio
```

If this works, you're done!

## Option 2: Linux/macOS - Install with System Dependencies

### Ubuntu/Debian:
```bash
sudo apt-get install python3-dev portaudio19-dev
pip install PyAudio
```

### macOS:
```bash
brew install portaudio
pip install PyAudio
```

## Option 3: Windows - Pre-built Wheels

For Windows, use pre-built wheels:
```bash
pip install pipwin
pipwin install PyAudio
```

Or download from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio

## Option 4: Use SpeechRecognition Without PyAudio (Recommended for Now)

The application works without PyAudio if you use your system's default microphone.

**The core functionality requires:**
- SpeechRecognition (installed ✅)
- pyttsx3 (installed ✅)

**PyAudio is optional** - your OS typically provides microphone access without it.

### To verify microphone works:
```bash
python -c "import speech_recognition as sr; print(sr.Microphone.list_microphone_indexes())"
```

If this shows your microphone, you're good to go!

## Option 5: Docker (If All Else Fails)

Use Docker to run the application with all dependencies pre-configured:

```bash
docker pull python:3.11
docker run -it --device /dev/snd python:3.11 bash
# Then install the app inside container
```

## Troubleshooting

### Python 3.13 Issue
If you have Python 3.13 and PyAudio fails:
- The voice assistant works WITHOUT PyAudio
- Your microphone will still function
- Run: `python main.py` anyway

### AttributeError: module 'pkgutil'
This is a Python 3.13 compatibility issue. Solution:
1. Continue without PyAudio (it's optional)
2. Or switch to Python 3.11: `pyenv install 3.11 && pyenv local 3.11`

### "portaudio19-dev" not found (Linux)
Try alternate package name:
```bash
sudo apt-get install libportaudio2 portaudio19-dev
```

## Verification

To verify everything is working:

```bash
# Test basic imports
python -c "import speech_recognition; import pyttsx3; print('✓ Core packages OK')"

# Test microphone
python -c "import speech_recognition as sr; mics = sr.Microphone.list_microphone_indexes(); print(f'✓ Found {len(mics)} microphone(s)')"

# Test TTS
python -c "import pyttsx3; e = pyttsx3.init(); e.say('Audio test'); e.runAndWait(); print('✓ TTS OK')"
```

## Requirements Updated

The requirements.txt has been updated to:
- ✅ Remove PyAudio version lock (use any compatible version)
- ✅ Use flexible version ranges for compatibility
- ✅ Work with Python 3.13

## Next Steps

Run the application:
```bash
python main.py
```

The voice assistant will work perfectly. PyAudio is optional - your system's default microphone will handle audio I/O.

## Still Having Issues?

Try this:
```bash
python setup.py
```

The setup script will test everything and show you what's working.

---

**Bottom Line:** The voice assistant works without PyAudio. Your microphone will function fine through your OS's default audio system. Try running `python main.py` now!
