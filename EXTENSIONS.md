# Advanced Customization & Extensions

This guide helps you extend and customize the Personal Voice Assistant.

## Adding Custom Commands

### Step 1: Define the Command Handler
Edit `lib/command_processor.py` and add a new method:

```python
def my_custom_command(self, command: str):
    """Handle custom command."""
    response = "Doing something custom"
    print(response)
    self.voice_engine.speak(response)
```

### Step 2: Register the Command
In the `_initialize_commands()` method, add your command:

```python
def _initialize_commands(self) -> Dict[str, Callable]:
    return {
        'mycmd': self.my_custom_command,
        # ... existing commands
    }
```

### Step 3: Use It
Say: "mycmd do something"

## Adding Custom Utilities

Create new functions in `lib/utilities.py`:

```python
def my_custom_function(parameter: str) -> str:
    """Your custom functionality."""
    # Your code here
    return result
```

Then import and use in command_processor.py:

```python
from lib.utilities import my_custom_function

def my_command(self, command: str):
    result = my_custom_function(some_param)
    self.voice_engine.speak(result)
```

## Example: Add a Task Reminder

```python
# In lib/utilities.py
import time
from datetime import datetime, timedelta

def schedule_reminder(message: str, delay_minutes: int) -> str:
    """Schedule a reminder."""
    delay_seconds = delay_minutes * 60
    def reminder():
        time.sleep(delay_seconds)
        print(f"REMINDER: {message}")
    
    import threading
    thread = threading.Thread(target=reminder, daemon=True)
    thread.start()
    return f"Reminder set for {delay_minutes} minutes"

# In command_processor.py
def reminder_command(self, command: str):
    """Handle reminder command."""
    # Extract time and message
    words = command.split()
    # Parse and schedule
    response = schedule_reminder("Your reminder", 5)
    self.voice_engine.speak(response)
```

## Example: Add Calculator

```python
# In lib/utilities.py
def calculate(expression: str) -> str:
    """Safely evaluate math expression."""
    try:
        # Remove dangerous characters
        safe_expr = expression.replace('^', '**')
        result = eval(safe_expr, {"__builtins__": {}})
        return f"The result is {result}"
    except Exception as e:
        return f"Calculation error: {str(e)}"

# In command_processor.py
def calculate_command(self, command: str):
    expr = command.replace('calculate', '').replace('math', '').strip()
    if expr:
        result = calculate(expr)
        self.voice_engine.speak(result)
```

## Example: Add Clipboard Manager

```python
# In lib/utilities.py
import pyperclip  # pip install pyperclip

def copy_to_clipboard(text: str) -> str:
    try:
        pyperclip.copy(text)
        return f"Copied to clipboard"
    except:
        return "Failed to copy"

def get_from_clipboard() -> str:
    try:
        return pyperclip.paste()
    except:
        return "Failed to read clipboard"

# In command_processor.py
def clipboard_command(self, command: str):
    if 'copy' in command:
        text = command.replace('copy', '').strip()
        result = copy_to_clipboard(text)
    elif 'paste' in command:
        result = get_from_clipboard()
    self.voice_engine.speak(result)
```

## Example: Add Email Functionality

```python
# Install: pip install secure-smtplib

# In lib/utilities.py
import smtplib
from email.mime.text import MIMEText

def send_email(recipient: str, subject: str, body: str) -> str:
    """Send email (requires Gmail setup)."""
    try:
        # Configure with your Gmail account
        sender_email = "your_email@gmail.com"
        password = "your_app_password"  # Use app-specific password
        
        message = MIMEText(body)
        message["Subject"] = subject
        message["From"] = sender_email
        message["To"] = recipient
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, recipient, message.as_string())
        
        return f"Email sent to {recipient}"
    except Exception as e:
        return f"Email failed: {str(e)}"
```

## Example: Add System Monitoring

```python
# In lib/utilities.py
import psutil  # pip install psutil

def get_system_stats() -> str:
    """Get CPU and memory usage."""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    
    return f"CPU: {cpu_percent}%, Memory: {memory.percent}% used"

# In command_processor.py
def stats_command(self, command: str):
    stats = get_system_stats()
    self.voice_engine.speak(f"System {stats}")
```

## Example: Add File Operations

```python
# In lib/utilities.py
import os
from pathlib import Path

def list_files(directory: str) -> str:
    """List files in directory."""
    try:
        path = Path(directory).expanduser()
        files = [f.name for f in path.iterdir()]
        return f"Files: {', '.join(files[:10])}"
    except Exception as e:
        return f"Cannot list files: {str(e)}"

def create_file(filename: str, content: str) -> str:
    """Create a new file."""
    try:
        with open(filename, 'w') as f:
            f.write(content)
        return f"File {filename} created"
    except Exception as e:
        return f"Failed to create file: {str(e)}"

# In command_processor.py
def file_command(self, command: str):
    if 'create' in command:
        # Parse filename and content
        result = create_file("note.txt", "My note")
    elif 'list' in command:
        result = list_files("~/Documents")
    self.voice_engine.speak(result)
```

## Example: Add Dictionary/Thesaurus

```python
# In lib/utilities.py
# For real implementation, could use PyDictionary
# For now, simple example:

DEFINITIONS = {
    'python': 'A snake or a programming language',
    'code': 'Computer instructions written in a language',
    'program': 'A set of instructions for a computer',
}

def get_definition(word: str) -> str:
    """Get word definition."""
    return DEFINITIONS.get(word.lower(), "Word not found in dictionary")

# In command_processor.py
def define_command(self, command: str):
    word = command.replace('define', '').strip()
    if word:
        definition = get_definition(word)
        self.voice_engine.speak(f"{word} means: {definition}")
```

## Modifying the GUI

### Change Colors
Edit `main.py` or `advanced.py`:

```python
# Change header background
header_frame = tk.Frame(self.root, bg='#FF0000')  # Red

# Change button colors
self.listen_btn = tk.Button(
    button_frame,
    bg='#00FF00',  # Green
    fg='#000000',  # Black text
)
```

### Add New GUI Elements

```python
# In setup_gui method:

# Add a new label
new_label = tk.Label(
    frame,
    text="Your Label",
    font=('Helvetica', 12),
    bg='#CCCCCC',
    fg='#000000'
)
new_label.pack(pady=10)

# Add a new button
new_button = tk.Button(
    frame,
    text="Your Button",
    command=self.your_method
)
new_button.pack()

# Add a new text entry
entry = tk.Entry(frame, width=30)
entry.pack(pady=5)
```

## Working with Threads

The assistant uses threading for voice operations. Here's how to extend it:

```python
def long_running_task(self):
    """Run in background thread."""
    import threading
    thread = threading.Thread(target=self._task_handler, daemon=True)
    thread.start()

def _task_handler(self):
    """Actual task."""
    # This runs without blocking GUI
    result = some_long_operation()
    self.log(f"Task complete: {result}")
```

## Error Handling

Always wrap external calls:

```python
def safe_command(self, command: str):
    try:
        # Your code
        result = risky_operation()
    except FileNotFoundError:
        self.voice_engine.speak("File not found")
    except ConnectionError:
        self.voice_engine.speak("Network error")
    except Exception as e:
        self.voice_engine.speak(f"An error occurred: {str(e)}")
```

## Configuration File

Extend `config.json` for your custom settings:

```json
{
  "custom_features": {
    "reminder_enabled": true,
    "calculator_enabled": true,
    "email_enabled": false
  }
}
```

Load in your code:

```python
import json

def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

config = load_config()
if config['custom_features']['reminder_enabled']:
    # Enable reminder feature
```

## Package Dependencies for Extensions

Install as needed:

```bash
# Email support
pip install secure-smtplib

# Clipboard
pip install pyperclip

# System monitoring
pip install psutil

# Dictionary
pip install pydictionary

# Calendar
pip install python-dateutil

# Database
pip install sqlite3
```

## Testing Your Changes

```python
# In command_processor.py, add to __init__:
self.log("Custom commands loaded")

# Test manually:
if __name__ == "__main__":
    from lib.voice_engine import VoiceEngine
    engine = VoiceEngine()
    processor = CommandProcessor(engine)
    
    # Test your command
    processor.process("your test command")
```

## Debugging

Enable debug logging:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug(f"Processing: {command}")
logger.info(f"Command result: {result}")
logger.error(f"Command error: {e}")
```

## Best Practices

1. **Always handle exceptions** - Wrap external operations
2. **Use threading** - Don't block the GUI
3. **Test thoroughly** - Test new commands before deploying
4. **Document code** - Add docstrings to new functions
5. **Keep commands simple** - Voice input is limited
6. **Feedback to user** - Always speak responses
7. **Log activities** - Use self.log() for troubleshooting
8. **Use type hints** - Help catch bugs early

## Publishing Custom Extensions

Create a new Python package:

```
my_extension/
├── __init__.py
├── commands.py
├── utilities.py
└── README.md
```

Then import in your assistant:

```python
from my_extension.commands import MyCommands

# In CommandProcessor.__init__:
custom_cmds = MyCommands(self.voice_engine)
self.commands.update(custom_cmds.get_commands())
```

---

For more information, refer to the main README.md and the source code comments.
