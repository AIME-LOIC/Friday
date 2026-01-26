"""Utility functions for the personal assistant."""

import webbrowser
import subprocess
import os
import platform
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from typing import List, Tuple, Optional

def search_web(query: str, num_results: int = 5) -> List[Tuple[str, str]]:
    """
    Search the web and return results.
    
    Args:
        query: Search query
        num_results: Number of results to return
        
    Returns:
        List of (title, url) tuples
    """
    try:
        # Using DuckDuckGo (no API key required)
        search_url = f"https://duckduckgo.com/html/?q={quote(query)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(search_url, headers=headers, timeout=5)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        results = []
        
        # Extract search results
        for result in soup.find_all('div', class_='result'):
            title_elem = result.find('a', class_='result__url')
            url_elem = result.find('a', class_='result__link')
            
            if title_elem and url_elem:
                title = title_elem.get_text(strip=True)
                url = url_elem.get('href')
                
                if title and url:
                    results.append((title, url))
                    if len(results) >= num_results:
                        break
        
        return results
    
    except Exception as e:
        print(f"Search error: {e}")
        return []


def get_weather() -> str:
    """Get weather information (returns placeholder)."""
    try:
        # Using wttr.in API (no key required)
        response = requests.get('https://wttr.in/?format=3', timeout=5)
        if response.status_code == 200:
            return response.text.strip()
        else:
            return "Could not retrieve weather information"
    except Exception as e:
        return f"Weather unavailable: {str(e)}"


def open_application(app_name: str) -> bool:
    """
    Open an application by name.
    
    Args:
        app_name: Name of the application
        
    Returns:
        True if successful
    """
    try:
        system = platform.system()
        
        if system == 'Windows':
            # Windows - search in common paths
            os.startfile(app_name) if '.' in app_name else subprocess.Popen(app_name)
            return True
        
        elif system == 'Darwin':  # macOS
            subprocess.run(['open', '-a', app_name])
            return True
        
        elif system == 'Linux':
            # Linux - try to launch using xdg-open or direct execution
            subprocess.Popen([app_name])
            return True
        
        return False
    
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"Error opening application: {e}")
        return False


def execute_system_command(command: str) -> str:
    """
    Execute a system command and return output.
    
    Args:
        command: Command to execute
        
    Returns:
        Command output as string
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        output = result.stdout.strip() if result.stdout else result.stderr.strip()
        return output if output else "Command executed successfully"
    
    except subprocess.TimeoutExpired:
        return "Command timed out"
    except Exception as e:
        return f"Command execution failed: {str(e)}"


def open_url(url: str) -> bool:
    """
    Open a URL in the default browser.
    
    Args:
        url: URL to open
        
    Returns:
        True if successful
    """
    try:
        if not url.startswith('http'):
            url = 'https://' + url
        webbrowser.open(url)
        return True
    except Exception as e:
        print(f"Error opening URL: {e}")
        return False
