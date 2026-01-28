"""
Friday Chatbot Module - Natural conversation mode with context awareness.
"""

import random
import re
from typing import Dict, List, Optional
from datetime import datetime


class FridayChatbot:
    """
    Chatbot mode for Friday - enables natural, extended conversations.
    
    Features:
    - Context-aware responses
    - Remembers conversation history
    - Asks follow-up questions
    - Learns user preferences
    - Casual, friendly "savage" personality
    """
    
    def __init__(self, voice_engine, memory_store=None):
        self.voice_engine = voice_engine
        self.memory = memory_store  # Optional PostgreSQL memory
        
        # Conversation state
        self.conversation_history: List[Dict[str, str]] = []
        self.user_preferences: Dict[str, str] = {}
        self.current_topic: Optional[str] = None
        self.chat_mode_active = False
        
        # Personality responses
        self.greetings = [
            "Uhm, hey bro! What's up?",
            "Dude, what's going on?",
            "Hey man, what's good?",
            "Bro, what's happening?",
        ]
        
        self.farewells = [
            "Uhm, later bro! Hit me up anytime.",
            "Alright dude, catch you later!",
            "Peace out, man!",
            "See you later, bro!",
        ]
        
        # Topic-based responses
        self.topic_responses = {
            "coding": [
                "Uhm, coding is life, bro! What are you working on?",
                "Dude, programming is where it's at. What language you vibing with?",
                "Man, I love talking code. What's your stack?",
            ],
            "music": [
                "Bro, music is everything! What's your vibe right now?",
                "Uhm, I'm always down to talk music. What are you listening to?",
                "Dude, music hits different. What genre you into?",
            ],
            "games": [
                "Games are fire, bro! What you playing?",
                "Uhm, gaming is the move. What's your favorite?",
                "Dude, I'm always down to talk games. What's good?",
            ],
            "food": [
                "Bro, food is life! What's your favorite?",
                "Uhm, I'm always hungry for food talk. What you craving?",
                "Dude, food conversations are the best. What's your go-to?",
            ],
            "bored": [
                "Uhm, bored again, bro? Let me help you out.",
                "Dude, boredom is the worst. Want me to play something?",
                "Man, let's fix that boredom. What do you want to do?",
            ],
        }
    
    def activate(self):
        """Activate chatbot mode."""
        self.chat_mode_active = True
        self.conversation_history = []
        greeting = random.choice(self.greetings)
        self.voice_engine.speak(greeting)
        return greeting
    
    def deactivate(self):
        """Deactivate chatbot mode."""
        self.chat_mode_active = False
        farewell = random.choice(self.farewells)
        self.voice_engine.speak(farewell)
        return farewell
    
    def process_message(self, user_input: str) -> str:
        """
        Process user input and generate a conversational response.
        
        Args:
            user_input: What the user said
            
        Returns:
            Friday's response text
        """
        if not self.chat_mode_active:
            return "Chat mode isn't active, bro. Say 'activate chatbot' or 'chat mode'."
        
        user_input = user_input.strip().lower()
        
        # Save to conversation history
        self.conversation_history.append({
            "user": user_input,
            "timestamp": datetime.now().isoformat()
        })
        
        # Detect intent and respond
        response = self._generate_response(user_input)
        
        # Save Friday's response
        self.conversation_history.append({
            "friday": response,
            "timestamp": datetime.now().isoformat()
        })
        
        # Speak the response
        self.voice_engine.speak(response)
        
        # Optionally save to memory store
        if self.memory and self.memory.enabled:
            try:
                self.memory.log("chatbot_conversation", user_input, {
                    "response": response,
                    "topic": self.current_topic
                })
            except Exception:
                pass
        
        return response
    
    def _generate_response(self, user_input: str) -> str:
        """Generate a contextual response based on user input."""
        
        # Check for greetings
        if any(word in user_input for word in ["hi", "hello", "hey", "what's up", "whats up"]):
            return random.choice([
                "Uhm, hey bro! What's going on?",
                "Dude, what's good?",
                "Hey man, how's it going?",
            ])
        
        # Check for boredom
        if any(word in user_input for word in ["bored", "nothing to do", "nothing todo"]):
            self.current_topic = "bored"
            return self._handle_boredom()
        
        # Check for coding topics
        if any(word in user_input for word in ["code", "coding", "programming", "developer", "python", "javascript"]):
            self.current_topic = "coding"
            return random.choice(self.topic_responses["coding"])
        
        # Check for music topics
        if any(word in user_input for word in ["music", "song", "artist", "album", "spotify", "youtube"]):
            self.current_topic = "music"
            return self._handle_music_topic(user_input)
        
        # Check for game topics
        if any(word in user_input for word in ["game", "gaming", "play", "gamer", "steam"]):
            self.current_topic = "games"
            return random.choice(self.topic_responses["games"])
        
        # Check for food topics
        if any(word in user_input for word in ["food", "eat", "hungry", "restaurant", "pizza", "burger"]):
            self.current_topic = "food"
            return random.choice(self.topic_responses["food"])
        
        # Check for questions about Friday
        if any(word in user_input for word in ["who are you", "what are you", "tell me about yourself"]):
            return self._handle_about_friday()
        
        # Check for preference questions
        if "favorite" in user_input or "prefer" in user_input:
            return self._handle_preference_question(user_input)
        
        # Check for requests
        if any(word in user_input for word in ["play", "open", "search", "find"]):
            return self._handle_action_request(user_input)
        
        # Check for emotional states
        if any(word in user_input for word in ["sad", "happy", "tired", "excited", "stressed"]):
            return self._handle_emotion(user_input)
        
        # Default conversational response
        return self._default_response(user_input)
    
    def _handle_boredom(self) -> str:
        """Handle when user says they're bored."""
        fav_song = self.user_preferences.get("favorite_song")
        fav_app = self.user_preferences.get("favorite_app")
        
        if fav_song:
            # Actually play the song
            try:
                import webbrowser
                import urllib.parse
                q = urllib.parse.quote(fav_song)
                webbrowser.open(f"https://www.youtube.com/results?search_query={q}")
            except Exception:
                pass
            return random.choice([
                f"Uhm, bored again, bro? Let me drop your favorite song—{fav_song}.",
                f"Dude, I got you. Playing {fav_song} right now.",
            ])
        elif fav_app:
            # Actually open the app
            try:
                from lib.utilities import open_application
                open_application(fav_app)
            except Exception:
                pass
            return random.choice([
                f"Alright bro, let's open {fav_app} and do something.",
                f"Uhm, let's fire up {fav_app} and get productive, dude.",
            ])
        else:
            return random.choice([
                "Uhm, bored huh? Want to play a game or something?",
                "Dude, let's do something fun. Want to play XO or chat?",
                "Bro, I can play music, open apps, or we can just chill and talk.",
            ])
    
    def _handle_music_topic(self, user_input: str) -> str:
        """Handle music-related conversations."""
        # Extract song/artist name if mentioned
        song_match = re.search(r'(?:song|track|music|listen to|play)\s+(?:is|called|named)?\s*["\']?([^"\']+)["\']?', user_input)
        if song_match:
            song = song_match.group(1).strip()
            self.user_preferences["favorite_song"] = song
            return random.choice([
                f"Uhm, {song}? That's fire, bro! I'll remember that.",
                f"Dude, {song} is a vibe! Got it saved.",
            ])
        
        return random.choice(self.topic_responses["music"])
    
    def _handle_about_friday(self) -> str:
        """Tell user about Friday."""
        return random.choice([
            "Uhm, I'm Friday, bro! Your AI assistant. I'm here to help, chat, play games, and just vibe with you.",
            "Dude, I'm Friday—your personal assistant. I can do commands, chat, play XO, and just hang out.",
            "Bro, I'm Friday! Think of me like your chill AI buddy who can help with stuff and talk about anything.",
        ])
    
    def _handle_preference_question(self, user_input: str) -> str:
        """Handle questions about user preferences."""
        if "song" in user_input or "music" in user_input:
            fav = self.user_preferences.get("favorite_song")
            if fav:
                return f"Uhm, your favorite song is {fav}, bro. Want me to play it?"
            else:
                return "Dude, I don't know your favorite song yet. What is it?"
        
        if "app" in user_input or "application" in user_input:
            fav = self.user_preferences.get("favorite_app")
            if fav:
                return f"Bro, your favorite app is {fav}. Want me to open it?"
            else:
                return "Uhm, I don't know your favorite app yet. What is it?"
        
        return "Uhm, what preference you asking about, bro?"
    
    def _handle_action_request(self, user_input: str) -> str:
        """Handle action requests like play, open, search."""
        if "play" in user_input:
            song_match = re.search(r'play\s+(.+)', user_input)
            if song_match:
                song = song_match.group(1).strip()
                # Actually play it via YouTube
                try:
                    import webbrowser
                    import urllib.parse
                    q = urllib.parse.quote(song)
                    webbrowser.open(f"https://www.youtube.com/results?search_query={q}")
                    return f"Uhm, playing {song} for you, bro!"
                except Exception:
                    return f"Uhm, couldn't play {song} right now, bro. Try again?"
        
        if "open" in user_input:
            app_match = re.search(r'open\s+(.+)', user_input)
            if app_match:
                app = app_match.group(1).strip()
                # Actually open the app
                try:
                    from lib.utilities import open_application
                    if open_application(app):
                        return f"Alright dude, opening {app} for you!"
                    else:
                        return f"Uhm, couldn't find {app}, bro. Is it installed?"
                except Exception:
                    return f"Uhm, couldn't open {app} right now, bro."
        
        if "search" in user_input or "find" in user_input:
            search_match = re.search(r'(?:search|find)\s+(?:for\s+)?(.+)', user_input)
            if search_match:
                query = search_match.group(1).strip()
                try:
                    import webbrowser
                    import urllib.parse
                    q = urllib.parse.quote(query)
                    webbrowser.open(f"https://www.google.com/search?q={q}")
                    return f"Uhm, searching for {query}, bro!"
                except Exception:
                    return f"Uhm, couldn't search right now, bro."
        
        return "Uhm, I got you, bro. What do you want me to do?"
    
    def _handle_emotion(self, user_input: str) -> str:
        """Handle emotional states."""
        if "sad" in user_input:
            return random.choice([
                "Uhm, sorry you're feeling down, bro. Want to talk about it or play something?",
                "Dude, that sucks. I'm here if you want to chat or do something fun.",
            ])
        if "happy" in user_input or "excited" in user_input:
            return random.choice([
                "Uhm, that's awesome, bro! Love to hear it!",
                "Dude, that's great! What's got you excited?",
            ])
        if "tired" in user_input:
            return random.choice([
                "Uhm, tired huh? Maybe take a break, bro. I can play some chill music.",
                "Dude, rest up! Want me to play something relaxing?",
            ])
        if "stressed" in user_input:
            return random.choice([
                "Uhm, stress is rough, bro. Want to chat or do something to unwind?",
                "Dude, I got you. Want to play a game or listen to music?",
            ])
        
        return "Uhm, I hear you, bro. How can I help?"
    
    def _default_response(self, user_input: str) -> str:
        """Default conversational response when intent isn't clear."""
        responses = [
            "Uhm, that's interesting, bro. Tell me more.",
            "Dude, I see what you mean. What else?",
            "Bro, that's cool. What's on your mind?",
            "Uhm, alright. What do you want to do?",
            "Dude, I'm listening. Go on.",
            "Bro, that's a vibe. Keep talking.",
        ]
        
        # Sometimes ask follow-up questions
        if random.random() < 0.3:
            follow_ups = [
                "What's your favorite thing about that?",
                "How does that make you feel?",
                "What else is going on?",
                "Want to do something about it?",
            ]
            return random.choice(follow_ups)
        
        return random.choice(responses)
    
    def get_conversation_summary(self) -> str:
        """Get a summary of the conversation."""
        if not self.conversation_history:
            return "No conversation yet, bro."
        
        topics = []
        for entry in self.conversation_history:
            if "user" in entry:
                text = entry["user"].lower()
                if any(word in text for word in ["music", "song"]):
                    topics.append("music")
                elif any(word in text for word in ["code", "programming"]):
                    topics.append("coding")
                elif any(word in text for word in ["game", "gaming"]):
                    topics.append("games")
        
        if topics:
            unique_topics = list(set(topics))
            return f"Uhm, we talked about {', '.join(unique_topics)}, bro."
        
        return "Uhm, we've been chatting, bro. Nothing specific."
