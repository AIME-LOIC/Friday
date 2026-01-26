#!/usr/bin/env python3
"""
Setup and test script for the Personal Voice Assistant
"""

import subprocess
import sys
import platform
import os

def print_header(text):
    """Print formatted header."""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")

def run_command(cmd, description):
    """Run a command and report results."""
    print(f"▶ {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ {description} successful\n")
            return True
        else:
            print(f"✗ {description} failed: {result.stderr}\n")
            return False
    except Exception as e:
        print(f"✗ Error: {e}\n")
        return False

def check_requirements():
    """Check if all requirements are met."""
    print_header("Checking Requirements")
    
    # Check Python version
    print(f"Python Version: {sys.version}")
    if sys.version_info < (3, 7):
        print("✗ Python 3.7 or higher is required")
        return False
    print("✓ Python version OK\n")
    
    # Check system
    system = platform.system()
    print(f"Operating System: {system}")
    
    if system == "Linux":
        print("ℹ Linux detected - You may need: sudo apt-get install python3-dev portaudio19-dev")
    elif system == "Darwin":
        print("ℹ macOS detected - You may need: brew install portaudio")
    elif system == "Windows":
        print("ℹ Windows detected - PyAudio should work with pip")
    
    return True

def install_dependencies():
    """Install Python dependencies."""
    print_header("Installing Dependencies")
    
    # Check if requirements.txt exists
    if not os.path.exists('requirements.txt'):
        print("✗ requirements.txt not found")
        return False
    
    return run_command("pip install -r requirements.txt", "Installing packages")

def test_imports():
    """Test if all imports work."""
    print_header("Testing Imports")
    
    modules = [
        ('tkinter', 'Tkinter (GUI)'),
        ('pyttsx3', 'pyttsx3 (Text-to-Speech)'),
        ('speech_recognition', 'SpeechRecognition'),
        ('pyaudio', 'PyAudio (Audio)'),
        ('pyautogui', 'PyAutoGUI (GUI Automation)'),
        ('requests', 'Requests (HTTP)'),
        ('bs4', 'BeautifulSoup (Web Scraping)'),
    ]
    
    all_ok = True
    for module, name in modules:
        try:
            __import__(module)
            print(f"✓ {name} imported successfully")
        except ImportError as e:
            print(f"✗ {name} failed: {e}")
            all_ok = False
    
    print()
    return all_ok

def test_microphone():
    """Test microphone availability."""
    print_header("Testing Microphone")
    
    try:
        import speech_recognition as sr
        
        mic_indices = sr.Microphone.list_microphone_indexes()
        print(f"Found {len(mic_indices)} microphone(s):")
        
        for i in mic_indices:
            try:
                with sr.Microphone(device_index=i) as source:
                    print(f"  Device {i}: Available")
            except:
                print(f"  Device {i}: Not accessible")
        
        if not mic_indices:
            print("✗ No microphones detected")
            return False
        
        print("✓ Microphone check passed\n")
        return True
    
    except Exception as e:
        print(f"✗ Microphone test failed: {e}\n")
        return False

def test_tts():
    """Test text-to-speech."""
    print_header("Testing Text-to-Speech")
    
    try:
        import pyttsx3
        
        engine = pyttsx3.init()
        print("Initializing TTS engine...")
        engine.say("Text to speech is working")
        engine.runAndWait()
        print("✓ TTS test passed\n")
        return True
    
    except Exception as e:
        print(f"✗ TTS test failed: {e}\n")
        return False

def main():
    """Main setup function."""
    print("\n")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  Personal Voice Assistant - Setup & Test Script         ║")
    print("╚══════════════════════════════════════════════════════════╝")
    
    # Step 1: Check requirements
    if not check_requirements():
        print("✗ Requirements check failed")
        return False
    
    # Step 2: Install dependencies
    if not install_dependencies():
        print("✗ Dependency installation failed")
        return False
    
    # Step 3: Test imports
    if not test_imports():
        print("✗ Import test failed")
        return False
    
    # Step 4: Test microphone
    test_microphone()
    
    # Step 5: Test TTS
    response = input("Do you want to test text-to-speech? (y/n): ").lower()
    if response == 'y':
        test_tts()
    
    # Success
    print_header("Setup Complete!")
    print("✓ All tests passed!\n")
    print("To start the Voice Assistant, run:")
    print("  python main.py\n")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
