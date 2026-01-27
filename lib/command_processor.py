"""Command processor for the personal assistant."""

from random import random
import re
import webbrowser
import subprocess
import datetime
import os
# Instead of just 'import pywhatkit', use this:
try:
    import pywhatkit
except Exception as e:
    print(f"Warning: pywhatkit failed to load (Internet issue). Some features will be disabled. Error: {e}")
    pywhatkit = None
from click import command
from click import command
import pyautogui
import platform
from typing import Dict, Callable, Optional

from requests import options
import wikipedia
from lib.utilities import search_web, get_weather, open_application, execute_system_command

class CommandProcessor:
    """Process and execute voice commands."""
    
    def __init__(self, voice_engine):
        self.voice_engine = voice_engine
        self.commands = self._initialize_commands()
    
    def _initialize_commands(self) -> Dict[str, Callable]:
        """Initialize command mappings."""
        return {
            'time': self.get_time,
            'date': self.get_date,
            'open': self.open_url_or_app,
            'search': self.search,
            'research': self.research,
            'weather': self.get_weather_info,
            'app': self.launch_app,
            'hello': self.greet,
            'help': self.show_help,
            'tell': self.handle_tell_command,
            'execute': self.execute_command,
            'mouse': self.handle_mouse,
            'click': self.handle_mouse,
            'copy': self.handle_shortcuts,
            'paste': self.handle_shortcuts,
            'tab': self.handle_shortcuts,
            'scroll': self.handle_mouse,
            'write': self.handle_writing,
            'type': self.handle_writing,
            'youtube': self.play_on_youtube,
            'play': self.play_on_youtube,
            'shut up': self.silence_assistant,
            'stop talking': self.silence_assistant,
            'be quiet': self.silence_assistant,
            'tell me about': self.perform_research,
            'what is': self.perform_research,
            'play a game': self.start_game,
            'guess': self.play_guess,
            'rock paper scissors': self.play_rps,
            'rock': self.play_rps,
            'paper': self.play_rps,
            'scissors': self.play_rps,
            'rock paper': self.play_rps,
        }
    
    def process(self, command: str) -> bool:
        if not command:
            return False
        
        command = command.strip().lower()

        # 1. Check for "Search" first
        if "search" in command:
            self.search(command)
            return True
            
        # 2. Check for "Research" or "Tell me about"
        if any(word in command for word in ["research", "tell me about", "what is"]):
            # This calls your handle_tell_command which we linked to Wikipedia
            self.handle_tell_command(command)
            return True

        # 3. Check for exact command matches (Games, Time, etc.)
        for key, handler in self.commands.items():
            if key in command:
                try:
                    handler(command)
                    return True
                except Exception as e:
                    self.voice_engine.speak(f"Error: {str(e)}")
                    return False
        
        # 4. Fallback
        self.voice_engine.speak("I didn't recognize that command.")
        return False
    
    def get_time(self, command: str):
        """Get current time."""
        time_str = datetime.datetime.now().strftime("%I:%M %p")
        response = f"The current time is {time_str}"
        print(response)
        self.voice_engine.speak(response)
    
    def get_date(self, command: str):
        """Get current date."""
        date_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
        response = f"Today is {date_str}"
        print(response)
        self.voice_engine.speak(response)
    
    def greet(self, command: str):
        """Greet the user."""
        hour = datetime.datetime.now().hour
        if hour < 12:
            greeting = "Good morning!"
        elif hour < 18:
            greeting = "Good afternoon!"
        else:
            greeting = "Good evening!"
        
        self.voice_engine.speak(greeting)
    
    def show_help(self, command: str):
        """Show available commands."""
        help_text = """
        Available commands:
        - Time: Say "what is the time" or "tell me the time"
        - Date: Say "what is the date" or "tell me the date"
        - Weather: Say "what is the weather" or "weather forecast"
        - Open URL: Say "open" followed by a URL
        - Search: Say "search for [topic]"
        - Research: Say "research [topic]"
        - Open App: Say "open [application name]"
        - Execute: Say "execute" followed by a command
        - Help: Say "help" for this message
        """
        print(help_text)
        self.voice_engine.speak("Showing help. Check the console for a complete list of commands.")
    
    def open_url_or_app(self, command: str):
        """Open a URL or application."""
        # Extract URL from command
        url_pattern = r'(http[s]?://\S+|www\.\S+|\S+\.\S+)'
        match = re.search(url_pattern, command)
        
        if match:
            url = match.group(0)
            if not url.startswith('http'):
                url = 'https://' + url
            
            try:
                webbrowser.open(url)
                self.voice_engine.speak(f"Opening {url}")
            except Exception as e:
                self.voice_engine.speak(f"Could not open URL: {str(e)}")
        else:
            self.voice_engine.speak("Please provide a valid URL")
    
    def handle_tell_command(self, command: str):
        """Handle 'tell me' variations of commands."""
        if 'time' in command:
            self.get_time(command)
        elif 'date' in command:
            self.get_date(command)
        elif 'weather' in command:
            self.get_weather_info(command)
        else:
            # Try to extract what to tell about
            words = command.split('tell me')[-1].strip()
            if words:
                self.research(f"research {words}")
    
    def search(self, command: str):
        """Search the web for a topic."""
        topic = command.replace('search', '').replace('for', '').strip()
        if topic:
            response = f"Searching for {topic}"
            print(response)
            self.voice_engine.speak(response)
            results = search_web(topic, num_results=3)
            
            if results:
                self.voice_engine.speak(f"Found results for {topic}")
                for i, (title, url) in enumerate(results[:3], 1):
                    print(f"{i}. {title}")
                    print(f"   {url}")
            else:
                self.voice_engine.speak("Could not find any results")
    
    def research(self, command: str):
        """Research a topic and provide information."""
        topic = command.replace('research', '').strip()
        if topic:
            response = f"Researching {topic}"
            print(response)
            self.voice_engine.speak(response)
            results = search_web(topic, num_results=5)
            
            if results:
                self.voice_engine.speak(f"Found information about {topic}")
                for title, url in results[:3]:
                    print(f"- {title}")
                    self.voice_engine.speak(title)
            else:
                self.voice_engine.speak("Could not find research results")
    
    def get_weather_info(self, command: str):
        """Get weather information."""
        weather_data = get_weather()
        self.voice_engine.speak(weather_data)
    
    def launch_app(self, command: str):
        """Launch an application."""
        app_name = command.replace('open', '').replace('app', '').strip()
        if app_name:
            response = f"Opening {app_name}"
            print(response)
            self.voice_engine.speak(response)
            success = open_application(app_name)
            if not success:
                self.voice_engine.speak(f"Could not find or open {app_name}")
    
    def execute_command(self, command: str):
        """Execute a system command."""
        cmd = command.replace('execute', '').strip()
        if cmd:
            result = execute_system_command(cmd)
            self.voice_engine.speak(result)

    def handle_mouse(self, command: str):
        """Handle mouse movements and clicks via voice."""
        distance = 250  # Pixels to move
        scroll_amount = 500
        if "up" in command:
            pyautogui.moveRel(0, -distance)
        elif "down" in command:
            pyautogui.moveRel(0, distance)
        elif "left" in command:
            pyautogui.moveRel(-distance, 0)
        elif "right" in command:
            pyautogui.moveRel(distance, 0)
        elif "double" in command:
            pyautogui.doubleClick()
        elif "click" in command:
            pyautogui.click()
        elif "scroll down" in command:
            pyautogui.scroll(-scroll_amount) # Negative is down
        elif "scroll up" in command:
            pyautogui.scroll(scroll_amount) # Positive is up

    def handle_shortcuts(self, command: str):
        """Execute keyboard shortcuts."""
        if "copy" in command:
            pyautogui.hotkey('ctrl', 'c')
            self.voice_engine.speak("Copied")
        elif "paste" in command:
            pyautogui.hotkey('ctrl', 'v')
            self.voice_engine.speak("Pasted")
        elif "tab" in command:
            pyautogui.hotkey('alt', 'tab')
    def handle_writing(self, command: str):
       """Types out what you dictate."""
    # Removes the word "write" or "type" from the start
       text_to_type = command.replace('write', '').replace('type', '').strip()
       if text_to_type:
         pyautogui.write(text_to_type, interval=0.1)
         self.voice_engine.speak(f"Typed: {text_to_type}")

    def play_on_youtube(self, command: str):
     """Search for a song/video and play it on YouTube."""
    # Clean the command string
     query = command.replace('play', '').replace('youtube', '').replace('search', '').strip()
    
     if query:
        self.voice_engine.speak(f"Playing {query} on YouTube, sir.")
        
        # 1. Primary Method: Try pywhatkit for auto-play
        try:
            import pywhatkit
            # Note: pywhatkit can sometimes hang if the internet is slow
            pywhatkit.playonyt(query)
        except Exception as e:
            print(f"Pywhatkit error: {e}")
            # 2. Fallback Method: Standard browser search (Super stable on Kali)
            import webbrowser
            url = f"https://www.youtube.com/results?search_query={query}"
            webbrowser.open(url)
     else:
        self.voice_engine.speak("What would you like me to play?")
    def silence_assistant(self, command: str):
        """Triggers the engine to stop speaking."""
        self.voice_engine.stop_speaking()
    

    # Wikipedia is used by perform_research; import if available
    try:
        import wikipedia
    except Exception:
        wikipedia = None

    def perform_research(self, topic: str):
        """Fetch a short summary about a topic using Wikipedia when available."""
        if not topic:
            self.voice_engine.speak("What would you like to know about?")
            return

        self.voice_engine.speak(f"Looking up {topic} for you.")
        if wikipedia:
            try:
                summary = wikipedia.summary(topic, sentences=2)
                print(f"Feedback: {summary}")
                self.voice_engine.speak(summary)
            except wikipedia.exceptions.DisambiguationError:
                self.voice_engine.speak("There are several meanings for that topic. Could you be more specific?")
            except wikipedia.exceptions.PageError:
                self.voice_engine.speak("I'm sorry, I couldn't find a page for that topic.")
            except Exception:
                self.voice_engine.speak("I had trouble connecting to the internet to find that.")
        else:
            self.voice_engine.speak("Wikipedia is not available in this environment.")

    import random

    def start_game(self, command: str):
        self.voice_engine.speak("I have two games: Guess the Number or Rock Paper Scissors. Which one do you want?")

    def play_guess(self, command: str):
        """Simple number guessing game (starter only)."""
        target = random.randint(1, 10)
        self.voice_engine.speak("I am thinking of a number between 1 and 10. Can you guess it?")

    def play_rps(self, command: str):
        """Rock Paper Scissors game logic."""
        options = ["rock", "paper", "scissors"]
        bot_choice = random.choice(options)

        user_choice = None
        if "rock" in command:
            user_choice = "rock"
        elif "paper" in command:
            user_choice = "paper"
        elif "scissors" in command:
            user_choice = "scissors"

        if not user_choice:
            self.voice_engine.speak("Please choose rock, paper, or scissors to play!")
            return

        if user_choice == bot_choice:
            result = f"It's a tie! I also chose {bot_choice}."
        elif (user_choice == "rock" and bot_choice == "scissors") or \
             (user_choice == "paper" and bot_choice == "rock") or \
             (user_choice == "scissors" and bot_choice == "paper"):
            result = f"You win! I chose {bot_choice}."
        else:
            result = f"I win! I chose {bot_choice}."

        print(f"RPS Result: {result}")
        self.voice_engine.speak(result)

    def silence_assistant(self, command: str):
        """Stops any active TTS playback."""
        self.voice_engine.stop_speaking()