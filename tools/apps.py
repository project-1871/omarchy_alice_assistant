"""App launcher tool."""
import subprocess
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.base import Tool


class AppsTool(Tool):
    """Launch applications."""

    name = "apps"
    description = "Launch applications and programs"
    triggers = [
        "open", "launch", "start", "run", "go to", "navigate to", "browse to"
    ]

    # Common app mappings
    APP_ALIASES = {
        # Browsers
        "browser": "firefox",
        "firefox": "firefox",
        "chrome": "chromium",
        "chromium": "chromium",

        # Terminals
        "terminal": "ghostty",
        "term": "ghostty",
        "ghostty": "ghostty",
        "kitty": "kitty",
        "alacritty": "alacritty",

        # File managers
        "files": "nautilus",
        "file manager": "nautilus",
        "nautilus": "nautilus",
        "thunar": "thunar",

        # Editors
        "code": "code",
        "vscode": "code",
        "editor": "code",
        "vim": "ghostty -e nano",
        "nvim": "ghostty -e nano",
        "nano": "ghostty -e nano",

        # Media
        "spotify": "spotify",
        "music": "spotify",
        "vlc": "vlc",

        # Communication
        "discord": "discord",
        "slack": "slack",
        "signal": "signal-desktop",

        # Utils
        "calculator": "gnome-calculator",
        "calc": "gnome-calculator",
        "settings": "gnome-control-center",
        "obsidian": "obsidian",
        "passwords": "1password",
        "1password": "1password",
    }

    # Web apps - launched via omarchy-launch-webapp
    WEB_APPS = {
        "chatgpt": "https://chatgpt.com",
        "chat gpt": "https://chatgpt.com",
        "grok": "https://grok.com",
        "calendar": "https://app.hey.com/calendar/weeks/",
        "email": "https://app.hey.com",
        "hey": "https://app.hey.com",
        "youtube": "https://youtube.com/",
        "whatsapp": "https://web.whatsapp.com/",
        "google messages": "https://messages.google.com/web/conversations",
        "messages": "https://messages.google.com/web/conversations",
        "google photos": "https://photos.google.com/",
        "photos": "https://photos.google.com/",
        "twitter": "https://x.com/",
        "x": "https://x.com/",
    }

    def execute(self, query: str, **kwargs) -> str:
        query_lower = query.lower()

        # Check for URL patterns first
        url_pattern = r'(https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9][-a-zA-Z0-9]*\.(com|org|net|io|dev|co|ai|gov|edu)[^\s]*)'
        url_match = re.search(url_pattern, query, re.IGNORECASE)

        if url_match:
            url = url_match.group(0)
            # Add https:// if missing
            if not url.startswith('http'):
                url = 'https://' + url
            try:
                subprocess.Popen(
                    ['firefox', url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                return f"Opening {url} in Firefox."
            except Exception as e:
                return f"Failed to open URL: {e}"

        # Check for "go to [website]" pattern without full URL
        go_to_match = re.search(r'(?:go to|navigate to|browse to|open.*(?:and|to))\s+([a-zA-Z0-9]+(?:\s+[a-zA-Z0-9]+)?)', query_lower)
        if go_to_match:
            site = go_to_match.group(1).strip()
            # Common site mappings
            site_urls = {
                "google": "https://google.com",
                "amazon": "https://amazon.com",
                "reddit": "https://reddit.com",
                "github": "https://github.com",
                "netflix": "https://netflix.com",
                "twitch": "https://twitch.tv",
                "facebook": "https://facebook.com",
                "instagram": "https://instagram.com",
                "linkedin": "https://linkedin.com",
            }
            if site in site_urls:
                url = site_urls[site]
            else:
                # Try adding .com
                url = f"https://{site.replace(' ', '')}.com"
            try:
                subprocess.Popen(
                    ['firefox', url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                return f"Opening {url} in Firefox."
            except Exception as e:
                return f"Failed to open: {e}"

        # Extract app name
        app_name = None
        for trigger in self.triggers:
            if trigger in query_lower:
                # Get everything after the trigger word
                parts = query_lower.split(trigger, 1)
                if len(parts) > 1:
                    app_name = parts[1].strip()
                    break

        if not app_name:
            return "What would you like me to open?"

        # Clean up common filler words
        for filler in ["the", "a", "an", "my", "please", "app", "application", "program"]:
            app_name = app_name.replace(f" {filler} ", " ").replace(f"{filler} ", "").replace(f" {filler}", "")

        app_name = app_name.strip()

        if not app_name:
            return "What would you like me to open?"

        # Check if it's a web app first
        if app_name in self.WEB_APPS:
            url = self.WEB_APPS[app_name]
            try:
                subprocess.Popen(
                    ['omarchy-launch-webapp', url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                return f"Opening {app_name}."
            except Exception as e:
                return f"Failed to open {app_name}: {e}"

        # Look up alias or use direct name
        command = self.APP_ALIASES.get(app_name, app_name)

        try:
            # Launch the app
            subprocess.Popen(
                command.split(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            return f"Opening {app_name}."
        except FileNotFoundError:
            return f"Couldn't find '{app_name}'. Is it installed?"
        except Exception as e:
            return f"Failed to open {app_name}: {e}"
