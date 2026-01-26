"""Voice Assistant Library."""

from lib.voice_engine import VoiceEngine
from lib.command_processor import CommandProcessor
from lib.utilities import search_web, get_weather, open_application, execute_system_command

__all__ = [
    'VoiceEngine',
    'CommandProcessor',
    'search_web',
    'get_weather',
    'open_application',
    'execute_system_command',
]
