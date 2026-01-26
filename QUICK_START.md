# Personal Voice Assistant - Quick Reference

## Installation
```bash
cd voice_assistant
chmod +x install.sh
./install.sh
# or on Windows:
install.bat
```

## Running the Application

### Standard Version
```bash
python main.py
```

### Advanced Version (with more features)
```bash
python advanced.py
```

### Setup & Testing
```bash
python setup.py
```

## Voice Commands Quick Reference

| Command | Example |
|---------|---------|
| **Time** | "What is the time?" |
| **Date** | "What is the date?" |
| **Weather** | "What is the weather?" |
| **Search** | "Search for Python tutorials" |
| **Research** | "Research artificial intelligence" |
| **Open URL** | "Open google.com" |
| **Open App** | "Open notepad" |
| **Execute** | "Execute ls" |
| **Help** | "Help" |

## Project Structure
```
voice_assistant/
├── main.py              # Main application
├── advanced.py          # Advanced features version
├── setup.py             # Setup and test script
├── lib/
│   ├── voice_engine.py  # Speech processing
│   ├── command_processor.py  # Command handling
│   └── utilities.py     # Helper functions
├── requirements.txt     # Dependencies
├── config.json          # Configuration
└── README.md           # Full documentation
```

## Features Checklist
- [x] Voice Recognition (Speech-to-Text)
- [x] Voice Synthesis (Text-to-Speech)
- [x] Tkinter GUI
- [x] Command Processing
- [x] Web Search
- [x] Weather Information
- [x] Time & Date
- [x] URL Opening
- [x] App Launcher
- [x] System Commands
- [x] Command History
- [x] Voice Settings
- [x] Activity Logging
- [x] Advanced Version with Tabs

## Troubleshooting

**Microphone not detected:**
```bash
python -c "import speech_recognition as sr; print(sr.Microphone.list_microphone_indexes())"
```

**TTS not working:**
```bash
python -c "import pyttsx3; e = pyttsx3.init(); e.say('test'); e.runAndWait()"
```

**Import errors:**
```bash
pip install -r requirements.txt --upgrade
```

## Key Features

### Voice Engine
- Offline text-to-speech with pyttsx3
- Google Speech Recognition API
- Microphone input with noise adjustment
- Queue-based threaded TTS

### Command Processing
- Natural language understanding
- Pattern matching for commands
- Error handling and feedback
- Extensible command system

### Utilities
- DuckDuckGo web search (no API key)
- wttr.in weather API (no API key)
- Cross-platform app launcher
- System command execution
- URL opening in default browser

### GUI Features
- Modern Tkinter interface
- Real-time activity logging
- Voice speed/volume control
- Multiple tabs (advanced version)
- Command history (advanced version)
- Settings customization

## No API Keys Required
All core features work without API keys:
- ✓ Speech Recognition (uses Google's public API)
- ✓ Text-to-Speech (local with pyttsx3)
- ✓ Web Search (DuckDuckGo)
- ✓ Weather (wttr.in)
- ✓ App Launcher (system commands)

## Performance Recommendations
1. Use headphones for better microphone input
2. Minimize background noise
3. Speak clearly and naturally
4. Ensure internet connection for web searches
5. Keep microphone close for accuracy

## Customization
Edit `lib/command_processor.py` to add custom commands:
```python
def your_command(self, command: str):
    response = "Your response"
    self.voice_engine.speak(response)
```

## Additional Notes
- Python 3.7+ required
- Works on Windows, macOS, Linux
- Microphone and speaker required
- ~50MB disk space needed
- Internet connection recommended

For more information, see README.md
