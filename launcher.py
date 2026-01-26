#!/usr/bin/env python3
"""
Personal Voice Assistant - Quick Launch Script
Shows menu of available options
"""

import os
import sys
import subprocess
import platform

def clear_screen():
    """Clear terminal screen."""
    os.system('clear' if platform.system() != 'Windows' else 'cls')

def show_menu():
    """Display main menu."""
    clear_screen()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                                                          ║")
    print("║    🎤  PERSONAL VOICE ASSISTANT LAUNCHER  🎤            ║")
    print("║                                                          ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print("Available Options:")
    print()
    print("  1) Run Standard Voice Assistant")
    print("     └─ Simple, clean interface")
    print()
    print("  2) Run Advanced Voice Assistant")
    print("     └─ Tabs, history, advanced features")
    print()
    print("  3) Setup & Test Environment")
    print("     └─ Verify installation")
    print()
    print("  4) View Documentation")
    print("     └─ Open guides in browser/editor")
    print()
    print("  5) Install/Update Dependencies")
    print("     └─ Reinstall packages from requirements.txt")
    print()
    print("  6) Exit")
    print()
    print("─" * 60)

def run_main():
    """Run the standard assistant."""
    print("\n▶ Starting Personal Voice Assistant...")
    try:
        subprocess.run([sys.executable, "main.py"])
    except KeyboardInterrupt:
        print("\n⏹  Exited.")

def run_advanced():
    """Run the advanced assistant."""
    print("\n▶ Starting Advanced Voice Assistant...")
    try:
        subprocess.run([sys.executable, "advanced.py"])
    except KeyboardInterrupt:
        print("\n⏹  Exited.")

def run_setup():
    """Run setup and tests."""
    print("\n▶ Running Setup & Tests...\n")
    try:
        subprocess.run([sys.executable, "setup.py"])
    except KeyboardInterrupt:
        print("\n⏹  Exited.")

def show_docs():
    """Show documentation files."""
    clear_screen()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                  Documentation Files                     ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print("Available Documentation:")
    print()
    print("  1) OVERVIEW.md - Project overview and quick guide")
    print("  2) README.md - Full documentation and features")
    print("  3) QUICK_START.md - Quick reference guide")
    print("  4) EXTENSIONS.md - How to add custom features")
    print()
    
    choice = input("Select document (1-4, or press Enter to go back): ").strip()
    
    files = {
        '1': 'OVERVIEW.md',
        '2': 'README.md',
        '3': 'QUICK_START.md',
        '4': 'EXTENSIONS.md',
    }
    
    if choice in files:
        filename = files[choice]
        if os.path.exists(filename):
            # Try to open with default text editor
            if platform.system() == 'Darwin':
                subprocess.run(['open', filename])
            elif platform.system() == 'Windows':
                subprocess.run(['notepad', filename])
            else:
                subprocess.run(['xdg-open', filename])
        else:
            print(f"\n✗ File not found: {filename}")
            input("Press Enter to continue...")

def install_deps():
    """Install/update dependencies."""
    print("\n▶ Installing Dependencies...\n")
    
    if not os.path.exists('requirements.txt'):
        print("✗ requirements.txt not found")
        return
    
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--upgrade"])
        print("\n✓ Dependencies installed successfully!")
    except Exception as e:
        print(f"\n✗ Error: {e}")
    
    input("\nPress Enter to continue...")

def main():
    """Main menu loop."""
    
    # Check if we're in the right directory
    if not os.path.exists('main.py'):
        print("✗ Error: main.py not found")
        print("Make sure you're in the voice_assistant directory")
        sys.exit(1)
    
    while True:
        show_menu()
        choice = input("Select an option (1-6): ").strip()
        
        if choice == '1':
            run_main()
        elif choice == '2':
            run_advanced()
        elif choice == '3':
            run_setup()
        elif choice == '4':
            show_docs()
        elif choice == '5':
            install_deps()
        elif choice == '6':
            print("\n👋 Thank you for using Personal Voice Assistant!")
            sys.exit(0)
        else:
            print("\n✗ Invalid option. Please try again.")
            input("Press Enter to continue...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
