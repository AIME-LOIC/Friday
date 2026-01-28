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
    
    def __init__(self, voice_engine, memory_store=None):
        self.voice_engine = voice_engine
        self.commands = self._initialize_commands()
        self.xo_game_window = None  # Track XO game window
        self.conversation_mode = False  # When True, treat responses as casual chat, not commands
        # Simple chatbot state (favorites / follow-ups)
        self.pending_question: Optional[str] = None
        self.preferences: Dict[str, str] = {}
        
        # Full chatbot mode
        try:
            from lib.chatbot import FridayChatbot
            self.chatbot = FridayChatbot(voice_engine, memory_store)
        except Exception as e:
            print(f"Chatbot not available: {e}")
            self.chatbot = None
    
    def _initialize_commands(self) -> Dict[str, Callable]:
        """Initialize command mappings."""
        return {
            'time': self.get_time,
            'date': self.get_date,
            # Wake / name detection
            'friday': self.handle_friday_name,
            # Session / exit control
            'bye': self.say_goodbye,
            'goodbye': self.say_goodbye,
            'shutdown': self.shutdown_system,
            'power off': self.shutdown_system,
            'open': self.open_url_or_app,
            'search': self.search,
            'research': self.research,
            'learn': self.handle_learn_command,
            'learn about': self.handle_learn_command,
            # Chatbot / chill mode
            "let's chat": self.start_chat_mode,
            "let chat": self.start_chat_mode,
            'chat': self.start_chat_mode,
            'talk': self.start_chat_mode,
            "activate chatbot": self.activate_chatbot,
            "chatbot mode": self.activate_chatbot,
            "chat mode": self.activate_chatbot,
            "deactivate chatbot": self.deactivate_chatbot,
            "exit chatbot": self.deactivate_chatbot,
            "i'm bored": self.handle_bored,
            "im bored": self.handle_bored,
            "i am bored": self.handle_bored,
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
            # XO / Tic-Tac-Toe game
            'xo': self.start_xo_game,
            'tic tac toe': self.start_xo_game,
            'tic-tac-toe': self.start_xo_game,
        }

    def handle_friday_name(self, command: str):
        """Respond politely whenever the user says Friday's name."""
        # Only trigger when the name is actually used, to avoid false positives
        if "friday" in command:
            # Short, natural acknowledgement with casual flavor
            import random
            responses = [
                "Uhm, yes sir, what's up?",
                "Yeah bro, what can I do for you?",
                "What's good, dude?",
                "Hey man, how can I help?",
                "Uhm, yeah, what's going on?",
            ]
            self.voice_engine.speak(random.choice(responses))
        else:
            # Fallback to a generic greeting if somehow called directly
            self.greet(command)

    def say_goodbye(self, command: str):
        """Simple polite exit phrase."""
        import random
        responses = [
            "Uhm, later bro! I'll be here when you need me.",
            "See you later, dude!",
            "Alright man, catch you later!",
            "Peace out, bro!",
        ]
        self.voice_engine.speak(random.choice(responses))

    def shutdown_system(self, command: str):
        """Attempt to shut down the operating system."""
        self.voice_engine.speak("Understood. Attempting to shut the system down now.")
        try:
            system = platform.system()
            if system == "Windows":
                cmd = "shutdown /s /t 0"
            elif system == "Darwin":
                cmd = "sudo shutdown -h now"
            else:  # Linux and others
                cmd = "shutdown now"
            result = execute_system_command(cmd)
            if "permission denied" in result.lower():
                self.voice_engine.speak("I was not allowed to shut the system down. Please run me with the required permissions.")
            elif result and "Command executed successfully" not in result:
                # Log but don't read long shell output
                print(f"Shutdown command result: {result}")
        except Exception as e:
            print(f"Shutdown error: {e}")
            self.voice_engine.speak("I could not complete the shutdown request.")

    def handle_learn_command(self, command: str):
        """Use web + Wikipedia helpers to 'learn' about a topic."""
        # Strip leading cue words
        topic = command
        for prefix in ("learn about", "learn", "study", "find out about"):
            if topic.startswith(prefix):
                topic = topic[len(prefix):].strip()
                break

        if not topic:
            self.voice_engine.speak("What would you like me to learn about?")
            return

        # Combine quick web search plus a short Wikipedia summary if possible
        try:
            self.voice_engine.speak(f"Let me learn about {topic} for you.")
            # First do a brief research pass using existing helper
            try:
                self.research(f"research {topic}")
            except Exception:
                pass

            # Then try a focused Wikipedia summary using perform_research, if available
            try:
                self.perform_research(topic)
            except Exception:
                pass
        except Exception:
            self.voice_engine.speak("I had trouble learning from the internet just now.")
    
    def process(self, command: str) -> bool:
        if not command:
            return False
        
        command = command.strip().lower()

        # 0. Check if chatbot mode is active - route everything to chatbot
        if self.chatbot and self.chatbot.chat_mode_active:
            self.chatbot.process_message(command)
            return True

        # 0. If we asked a question (favorites), treat next response as an answer
        if self.pending_question:
            try:
                self._handle_pending_answer(command)
            except Exception as e:
                print("Pending answer error:", e)
                self.voice_engine.speak("Uhm, my bad bro, I couldn't save that. Say it again?")
            return True

        # 0. Check if this is a casual response (not a command)
        if self._is_casual_response(command):
            self._handle_casual_response(command)
            return True

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
        
        # 4. Fallback - but if in conversation mode, be more friendly
        if self.conversation_mode:
            self._handle_casual_response(command)
            return True
        
        # Casual fallback for unrecognized commands
        import random
        responses = [
            "Uhm, I didn't catch that, bro.",
            "Sorry dude, I didn't understand that.",
            "Man, I'm not sure what you mean.",
            "Uhm, could you say that again?",
        ]
        self.voice_engine.speak(random.choice(responses))
        return False

    # ---------------- Chatbot / favorites ----------------

    def start_chat_mode(self, command: str):
        """Enter a chill chat flow and ask for favorites."""
        import random
        self.conversation_mode = True
        openers = [
            "Uhm, alright bro. Let's chat. Quick question—what's your favorite song?",
            "Alright dude, chat mode. What's your favorite song?",
            "Okay man, I'm listening. Favorite song—what is it?",
        ]
        self.voice_engine.speak(random.choice(openers))
        self.pending_question = "favorite_song"
    
    def activate_chatbot(self, command: str):
        """Activate full chatbot mode for extended conversations."""
        if self.chatbot:
            self.chatbot.activate()
        else:
            self.voice_engine.speak("Uhm, chatbot mode isn't available right now, bro.")
    
    def deactivate_chatbot(self, command: str):
        """Deactivate chatbot mode."""
        if self.chatbot:
            self.chatbot.deactivate()
        else:
            self.voice_engine.speak("Chatbot wasn't active, bro.")

    def _handle_pending_answer(self, text: str):
        """Store answer to the current pending question and ask the next one."""
        q = self.pending_question
        self.pending_question = None

        # Basic cleanup
        answer = (text or "").strip()
        if not answer:
            self.voice_engine.speak("Uhm, say it again bro—what was it?")
            self.pending_question = q
            return

        # Save answer
        if q:
            self.preferences[q] = answer

        import random
        acks = [
            "Nice, bro.",
            "Okay dude, got you.",
            "Cool, man.",
            "Uhm, that's a vibe.",
        ]
        self.voice_engine.speak(random.choice(acks))

        # Ask next question in the mini-profile
        if q == "favorite_song":
            self.voice_engine.speak("Alright—what's your favorite app to open? Like VS Code, Firefox, whatever.")
            self.pending_question = "favorite_app"
            return
        if q == "favorite_app":
            self.voice_engine.speak("Last one—got a favorite Bible verse or just say 'none'.")
            self.pending_question = "favorite_bible_verse"
            return
        if q == "favorite_bible_verse":
            self.voice_engine.speak("Cool. I’ll remember that, bro. If you say 'I'm bored', I'll help you chill.")
            self.conversation_mode = False
            return

        # Unknown question key -> just keep conversation mode on
        self.conversation_mode = False

    def handle_bored(self, command: str):
        """When user says they're bored, do something based on favorites."""
        import random

        # Use chatbot preferences if available, otherwise use command processor preferences
        if self.chatbot and self.chatbot.user_preferences:
            fav_song = self.chatbot.user_preferences.get("favorite_song")
            fav_app = self.chatbot.user_preferences.get("favorite_app")
        else:
            fav_song = self.preferences.get("favorite_song")
            fav_app = self.preferences.get("favorite_app")
        
        fav_verse = self.preferences.get("favorite_bible_verse")

        # If we don't know anything yet, prompt to chat
        if not (fav_song or fav_app or fav_verse):
            self.voice_engine.speak("Uhm, bored huh? Let's set your favorites first. Say 'activate chatbot' or 'let's chat'.")
            return

        # Prefer playing the favorite song if we have one
        if fav_song:
            self.voice_engine.speak(random.choice([
                "Uhm, say less bro. Putting on your favorite song.",
                "Alright dude, let's fix that boredom—music time.",
                "Okay man, dropping your favorite track.",
            ]))
            try:
                # reuse existing YouTube helper (it expects 'play ...')
                self.play_on_youtube(f"play {fav_song}")
            except Exception:
                # fallback to web search/open
                try:
                    import webbrowser
                    import urllib.parse
                    q = urllib.parse.quote(fav_song)
                    webbrowser.open(f"https://www.youtube.com/results?search_query={q}")
                except Exception:
                    pass
            return

        # Otherwise open their favorite app
        if fav_app:
            self.voice_engine.speak(random.choice([
                "Alright bro, opening your favorite app.",
                "Okay dude, let's do something—opening it now.",
            ]))
            try:
                open_application(fav_app)
            except Exception:
                pass
            return

        # Or open a Bible verse search
        if fav_verse and fav_verse != "none":
            self.voice_engine.speak("Uhm, let's pull up a verse real quick, bro.")
            try:
                import webbrowser
                import urllib.parse
                q = urllib.parse.quote(fav_verse)
                webbrowser.open(f"https://www.biblegateway.com/quicksearch/?quicksearch={q}&version=NIV")
            except Exception:
                pass
    
    def _is_casual_response(self, text: str) -> bool:
        """Detect if this is casual conversation, not a command."""
        casual_patterns = [
            # Short affirmatives/negatives
            r'^(yes|yeah|yep|yup|no|nope|nah|ok|okay|sure|alright|fine|cool)$',
            # "It was..." responses
            r'^(it was|it\'s|it is|they were|they\'re)',
            # "I (like/prefer/love/hate)..." casual statements
            r'^i (like|prefer|love|hate|enjoy|think|feel|want|need)',
            # "That's..." casual statements
            r'^(that\'s|that is|this is|these are)',
            # Simple answers to "how" questions
            r'^(good|great|fine|okay|bad|terrible|amazing|awesome|nice|cool)',
            # "I would..." hypothetical answers
            r'^i would (go|travel|visit|choose|pick)',
        ]
        import re
        for pattern in casual_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _add_casual_flavor(self, text: str) -> str:
        """Add casual filler words and make it sound more chill."""
        import random
        fillers = ["uhm", "uh", "like", "you know"]
        casual_terms = ["bro", "dude", "man"]
        
        # 30% chance to add a filler at the start
        if random.random() < 0.3:
            text = f"{random.choice(fillers)}, {text}"
        
        # 20% chance to add casual term
        if random.random() < 0.2:
            term = random.choice(casual_terms)
            # Add it naturally - either at start or end
            if random.random() < 0.5:
                text = f"{term}, {text}"
            else:
                text = f"{text}, {term}"
        
        return text
    
    def _handle_casual_response(self, text: str):
        """Handle casual conversation responses naturally."""
        text_lower = text.lower()
        
        # Acknowledge based on sentiment/content
        if any(word in text_lower for word in ['good', 'great', 'fine', 'okay', 'nice', 'cool', 'awesome', 'amazing']):
            responses = [
                "That's great to hear, bro!",
                "Nice, dude!",
                "Uhm, that's awesome!",
                "That sounds good, man.",
                "Sweet!",
                "That's cool, bro.",
            ]
        elif any(word in text_lower for word in ['bad', 'terrible', 'awful', 'sucks']):
            responses = [
                "Uhm, that sucks, bro.",
                "Ah man, that's rough.",
                "Dude, that's unfortunate.",
                "Sorry to hear that, man.",
            ]
        elif any(word in text_lower for word in ['yes', 'yeah', 'yep', 'sure', 'okay', 'alright']):
            responses = [
                "Got it, bro!",
                "Alright, cool.",
                "Uhm, understood, dude.",
                "Sure thing, man.",
            ]
        elif any(word in text_lower for word in ['no', 'nope', 'nah']):
            responses = [
                "Okay, no problem, bro.",
                "Got it, dude.",
                "Alright, man.",
            ]
        else:
            # Generic friendly acknowledgment
            responses = [
                "Uhm, I see, bro.",
                "That's interesting, dude.",
                "Thanks for sharing that, man.",
                "Got it, bro.",
                "Cool, man.",
            ]
        
        import random
        response = random.choice(responses)
        # Sometimes add extra casual flavor
        if random.random() < 0.4:
            response = self._add_casual_flavor(response)
        self.voice_engine.speak(response)
    
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
        import random
        hour = datetime.datetime.now().hour
        if hour < 12:
            greetings = [
                "Uhm, good morning, bro!",
                "Morning, dude!",
                "Hey man, good morning!",
            ]
        elif hour < 18:
            greetings = [
                "Uhm, good afternoon, bro!",
                "Afternoon, dude!",
                "Hey man, what's up?",
            ]
        else:
            greetings = [
                "Uhm, good evening, bro!",
                "Evening, dude!",
                "Hey man, what's going on?",
            ]
        
        self.voice_engine.speak(random.choice(greetings))
    
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

    def start_xo_game(self, command: str):
        """Start a Tic-Tac-Toe game window."""
        try:
            from lib.xo_game import XOGame
            
            # If game window already exists and is still alive, don't create another
            if self.xo_game_window is not None:
                try:
                    # Check if window still exists
                    if self.xo_game_window.root.winfo_exists():
                        self.voice_engine.speak("The game window is already open!")
                        return
                except Exception:
                    # Window was closed, reset reference
                    self.xo_game_window = None
            
            # Create new game window
            def on_game_end(user_wins, friday_wins, draws):
                """Callback when game window closes."""
                self.xo_game_window = None
                self.conversation_mode = False  # Disable conversation mode when game ends
                score_msg = (
                    f"Final score: You won {user_wins}, "
                    f"I won {friday_wins}, "
                    f"and we had {draws} draws."
                )
                self.voice_engine.speak(score_msg)
            
            self.xo_game_window = XOGame(self.voice_engine, on_game_end, command_processor=self)
            
        except Exception as e:
            print(f"Error starting XO game: {e}")
            self.voice_engine.speak("I couldn't start the game. Sorry!")

    def silence_assistant(self, command: str):
        """Stops any active TTS playback."""
        self.voice_engine.stop_speaking()