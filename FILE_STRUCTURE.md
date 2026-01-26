# File Structure & Descriptions

## Root Directory Files

### Executables
- **launcher.py** - Menu-driven launcher (run this first!)
  ```bash
  python launcher.py
  ```

- **main.py** - Standard voice assistant application
  ```bash
  python main.py
  ```

- **advanced.py** - Advanced version with tabs and features
  ```bash
  python advanced.py
  ```

- **setup.py** - Setup wizard and diagnostic tests
  ```bash
  python setup.py
  ```

### Installation Scripts
- **install.sh** - Linux/macOS installation script
  ```bash
  chmod +x install.sh
  ./install.sh
  ```

- **install.bat** - Windows installation script
  ```cmd
  install.bat
  ```

### Configuration
- **requirements.txt** - Python package dependencies
  ```
  pyttsx3==2.90                      # Text-to-speech
  SpeechRecognition==3.10.0         # Voice recognition
  pyaudio==0.2.13                   # Audio I/O
  pyautogui==0.9.53                 # GUI automation
  requests==2.31.0                  # HTTP requests
  beautifulsoup4==4.12.2            # Web scraping
  lxml==4.9.3                       # XML parsing
  ```

- **config.json** - Configuration template
  - Voice settings
  - Microphone settings
  - Feature toggles
  - Customization options

### Documentation
- **README.md** - Comprehensive documentation
  - Features list
  - Installation guide
  - Usage instructions
  - Command reference
  - Troubleshooting
  - Customization

- **OVERVIEW.md** - Project overview
  - Quick summary
  - Technology stack
  - Architecture diagram
  - Getting started
  - Key features

- **QUICK_START.md** - Quick reference
  - Installation commands
  - Common commands
  - Project structure
  - Troubleshooting tips

- **EXTENSIONS.md** - Customization guide
  - Adding custom commands
  - Adding utilities
  - Example implementations
  - Best practices
  - GUI modification

- **FILE_STRUCTURE.md** - This file
  - File descriptions
  - Purpose of each component
  - How to navigate

## Library Directory (lib/)

### Core Modules

**voice_engine.py** (250 lines)
```
Purpose: Handle all voice I/O operations
Contains:
  - VoiceEngine class
  - listen() method - captures voice input
  - speak() method - outputs voice
  - Threading for non-blocking audio
Key Dependencies:
  - pyttsx3 (text-to-speech)
  - SpeechRecognition (speech-to-text)
  - PyAudio (audio I/O)
```

**command_processor.py** (350 lines)
```
Purpose: Parse and execute voice commands
Contains:
  - CommandProcessor class
  - Command pattern matching
  - Command handlers (get_time, search, etc)
  - Natural language processing
Key Methods:
  - process() - main command handler
  - _initialize_commands() - command registry
  - Handler methods for each command type
```

**utilities.py** (200 lines)
```
Purpose: Helper functions for external operations
Contains:
  - search_web() - DuckDuckGo search
  - get_weather() - Weather from wttr.in
  - open_application() - Cross-platform app launcher
  - execute_system_command() - Shell command execution
  - open_url() - URL opener
Key Features:
  - No API keys required
  - Cross-platform support
  - Error handling
  - Fallback mechanisms
```

**__init__.py** (20 lines)
```
Purpose: Package initialization
Exports:
  - VoiceEngine
  - CommandProcessor
  - Utility functions
Allows: from lib import VoiceEngine
```

## Size & Complexity

```
Total Lines of Code:
  main.py           ~350 lines
  advanced.py       ~450 lines
  setup.py          ~200 lines
  launcher.py       ~200 lines
  lib/voice_engine.py    ~250 lines
  lib/command_processor.py ~350 lines
  lib/utilities.py       ~200 lines
  ───────────────────────────────
  TOTAL            ~2,000 lines

Documentation:
  README.md        ~500 lines
  OVERVIEW.md      ~350 lines
  EXTENSIONS.md    ~600 lines
  QUICK_START.md   ~200 lines
```

## Data Files

### Configuration
- **config.json** - User settings
  - Location: Project root
  - Loaded by: Advanced assistant
  - Contains: Voice settings, feature toggles

### Runtime Data
- **~/.voice_assistant/command_history.json** (Advanced version)
  - Location: User home directory
  - Created by: advanced.py
  - Contains: Command history with timestamps

## External Dependencies

### Direct Imports
```python
import tkinter                      # GUI framework
import speech_recognition as sr     # Voice-to-text
import pyttsx3                      # Text-to-speech
import pyaudio                      # Audio processing
import pyautogui                    # GUI automation
import requests                     # HTTP requests
from bs4 import BeautifulSoup       # Web scraping
```

### Standard Library
```python
import threading                    # Threading
import json                         # JSON handling
import datetime                     # Date/time
import subprocess                   # System commands
import webbrowser                   # Browser control
import os, sys, platform            # System info
import queue                        # Thread queues
```

## Execution Flow

```
launcher.py
    ├─► main.py (Simple)
    │   ├─ VoiceEngine (listen/speak)
    │   ├─ CommandProcessor (parse commands)
    │   ├─ Utilities (search, weather, etc)
    │   └─ Tkinter GUI
    │
    ├─► advanced.py (Full-Featured)
    │   ├─ VoiceEngine
    │   ├─ CommandProcessor
    │   ├─ Utilities
    │   ├─ Advanced Tkinter GUI (tabbed)
    │   └─ JSON history storage
    │
    ├─► setup.py (Diagnostic)
    │   └─ Test all components
    │
    └─► Documentation (README, etc)
```

## Configuration Hierarchy

```
Default Config
    ↓
config.json (if exists)
    ↓
Runtime Overrides (from GUI)
```

## Feature Implementation Locations

| Feature | File | Function |
|---------|------|----------|
| Listen for voice | voice_engine.py | listen() |
| Speak response | voice_engine.py | speak() |
| Recognize command | command_processor.py | process() |
| Get time | command_processor.py | get_time() |
| Get weather | utilities.py | get_weather() |
| Search web | utilities.py | search_web() |
| Open URL | utilities.py | open_url() |
| Open app | utilities.py | open_application() |
| GUI interface | main.py | VoiceAssistantGUI |
| Advanced GUI | advanced.py | AdvancedVoiceAssistant |
| Settings panel | advanced.py | setup_settings_tab() |
| History | advanced.py | command history |

## How to Navigate

### For Users
1. Start with **launcher.py**
   ```bash
   python launcher.py
   ```
2. Choose "Run Standard Voice Assistant"
3. Check **README.md** for full guide

### For Developers
1. Read **OVERVIEW.md** for architecture
2. Review **main.py** to understand GUI
3. Check **lib/voice_engine.py** for voice handling
4. Read **lib/command_processor.py** for command logic
5. See **EXTENSIONS.md** for adding features

### For Customization
1. Read **EXTENSIONS.md** for examples
2. Edit **lib/command_processor.py** to add commands
3. Modify **lib/utilities.py** for new features
4. Customize GUI in **main.py**

## Version Differences

### main.py (Standard)
- Simpler interface
- Core features only
- ~350 lines
- Lighter on resources
- Single window

### advanced.py (Full)
- Tabbed interface
- Command history
- JSON export
- Settings panel
- Help documentation
- ~450 lines
- More features

## Testing

Run diagnostics:
```bash
python setup.py
```

Tests included:
- ✓ Python version check
- ✓ Module imports
- ✓ Microphone detection
- ✓ TTS engine
- ✓ System compatibility

## Extensibility

All major components designed for extension:

```
CommandProcessor
  └─ Add new handlers

Utilities
  └─ Add new functions

GUI (main.py)
  └─ Add new widgets

Config (config.json)
  └─ Add new settings
```

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Listen (voice) | Variable | 3-10 seconds typical |
| Process command | <100ms | Fast pattern matching |
| TTS (5 words) | ~2s | Depends on speed setting |
| Web search | 1-5s | Depends on connection |
| GUI response | <100ms | Threaded non-blocking |

## Storage Requirements

```
Python packages    ~300 MB (with dependencies)
Source code        ~2 MB
Documentation      ~2 MB
Config/History     <1 MB
Total              ~305 MB
```

## System Dependencies

### Linux
```bash
sudo apt-get install python3-dev portaudio19-dev pulseaudio
```

### macOS
```bash
brew install portaudio
```

### Windows
- PyAudio included with pip
- Microphone drivers (built-in usually)

---

This completes the file structure documentation. All components are fully integrated and ready to use!
