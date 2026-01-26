# Personal Voice Assistant 🎤

A Python-based personal voice assistant with Tkinter GUI that understands voice commands and responds with voice. No API keys required for core functionality.

## Features

✅ **Voice Recognition** - Listen to voice commands  
✅ **Voice Synthesis** - Respond with natural speech  
✅ **GUI Interface** - Beautiful Tkinter interface  
✅ **Web Search** - Search the web for information  
✅ **Weather** - Get weather information  
✅ **Time & Date** - Tell current time and date  
✅ **Open URLs** - Open websites in your browser  
✅ **Launch Apps** - Open applications by name  
✅ **System Commands** - Execute system commands  
✅ **Adjustable Voice** - Control speed and volume  
✅ **Activity Log** - Track command history  

## Requirements

- Python 3.7 or higher
- Microphone (for voice input)
- Speaker (for voice output)
- Internet connection (for web searches)

## Installation

### 1. Navigate to the project directory:
```bash
cd /home/aime/PA/ass/voice_assistant
```

### 2. Install system dependencies (Ubuntu/Debian):
```bash
# Install audio libraries
sudo apt-get install python3-dev portaudio19-dev
sudo apt-get install pulseaudio alsa-utils

# Install espeak for TTS (optional, for better offline support)
sudo apt-get install espeak
```

### 3. Create a virtual environment (optional but recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 4. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Quick Start

Run the application:
```bash
python main.py
```

## Usage

### Starting the Assistant
1. Launch the application
2. You'll hear "Personal Voice Assistant Ready"
3. Click the **"Start Listening"** button
4. Speak a command naturally

### Available Voice Commands

#### Time & Date
- "What is the time?"
- "Tell me the time"
- "What is the date?"
- "Tell me the date"

#### Greetings
- "Hello"
- "Hi"
- "Good morning"

#### Web Searching
- "Search for [topic]"
  - Example: "Search for Python programming"
- "Research [topic]"
  - Example: "Research machine learning"

#### Web Browsing
- "Open [website]"
  - Example: "Open google.com"
  - Example: "Open youtube.com"

#### Applications
- "Open [app name]"
  - Example: "Open notepad" (Windows)
  - Example: "Open gedit" (Linux)
  - Example: "Open terminal"

#### Weather
- "What is the weather?"
- "Weather forecast"

#### System Commands
- "Execute [command]"
  - Example: "Execute ls"
  - Example: "Execute dir" (Windows)

#### Other
- "Help" - Show help information

## Settings

### Voice Speed
Adjust the speaking speed using the Speed slider (50-300)

### Volume
Control voice output volume (0.0-1.0)

## Architecture

```
voice_assistant/
├── main.py                    # Main GUI application
├── lib/
│   ├── __init__.py           # Package initialization
│   ├── voice_engine.py       # Speech-to-text and TTS
│   ├── command_processor.py  # Command parsing and handling
│   └── utilities.py          # Helper functions
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## Technical Details

### Voice Engine (`voice_engine.py`)
- Uses **pyttsx3** for text-to-speech (no API key required)
- Uses **SpeechRecognition** with Google's speech API
- Handles audio input/output with PyAudio
- Non-blocking voice output using threading

### Command Processor (`command_processor.py`)
- Pattern matching for natural language commands
- Extensible command system
- Error handling and user feedback

### Utilities (`utilities.py`)
- Web search using DuckDuckGo (no API key)
- Weather info from wttr.in (no API key)
- Application launcher (cross-platform)
- System command executor

## Troubleshooting

### Microphone Not Detected
```bash
# Check audio devices
python -c "import speech_recognition; print(sr.Microphone.list_microphone_indexes())"
```

### "No module named" errors
```bash
pip install -r requirements.txt
```

### Voice Not Playing
- Check system volume
- Verify speakers are connected
- Test with: `python -c "import pyttsx3; engine = pyttsx3.init(); engine.say('test'); engine.runAndWait()"`

### Speech Recognition Not Working
- Check microphone permissions
- Speak clearly and slowly
- Adjust ambient noise
- Ensure internet connection (for better recognition)

## Customization

### Add New Commands
Edit `lib/command_processor.py` and add to `_initialize_commands()`:

```python
def _initialize_commands(self) -> Dict[str, Callable]:
    return {
        'your_command': self.your_handler,
        # ... existing commands
    }

def your_handler(self, command: str):
    """Your custom command handler."""
    response = "Your custom response"
    self.voice_engine.speak(response)
```

### Change Voice Properties
Edit settings in `lib/voice_engine.py`:

```python
self.tts_engine.setProperty('rate', 150)    # Speech speed
self.tts_engine.setProperty('volume', 0.9)  # Volume (0.0-1.0)
```

## Performance Tips

1. **Use headphones** for better microphone input
2. **Minimize background noise** for accurate recognition
3. **Speak clearly** with proper pronunciation
4. **Keep internet stable** for web searches
5. **Close unnecessary apps** to free up resources

## Limitations & Notes

⚠️ **Speech Recognition Quality** depends on:
- Microphone quality
- Background noise levels
- Internet connection (for Google Speech API)
- Accent and pronunciation

⚠️ **TTS Voice** is system-dependent and may vary

⚠️ **Commands** are case-insensitive but should be natural language

⚠️ **Web Searches** require internet connection

## Future Enhancements

- [ ] Offline speech recognition (Pocketsphinx)
- [ ] Machine learning for command learning
- [ ] Calendar integration
- [ ] Email sending
- [ ] Smart home control
- [ ] Custom voice profiles
- [ ] Command shortcuts
- [ ] Multi-language support

## License

This project is free to use and modify.

## Support

For issues or questions, check:
1. The console output for error messages
2. The Activity Log in the GUI
3. Microphone and speaker permissions
4. Internet connectivity

---

**Powered by:** Python | Tkinter | PyAutoGUI | pyttsx3 | SpeechRecognition
