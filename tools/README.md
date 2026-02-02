# Alice Tools Reference

All tools are auto-discovered from this directory. Just say the trigger phrase and Alice handles the rest.

---

## Notes
**File:** `notes.py`

Take and manage dictated notes. Opens in nano for editing.

### Triggers
- "take a note"
- "write down"
- "remember this"
- "show my notes"
- "open notes"

### Examples
```
"Take a note: buy milk and eggs"
"Write down that the server password is abc123"
"Show my notes"
"Open my notes"
```

---

## Web Search
**File:** `websearch.py`

Search the web using DuckDuckGo (no API key needed).

### Triggers
- "search the web for"
- "search for"
- "look up"
- "google"
- "what is"
- "who is"
- "where is"
- "how do"

### Examples
```
"Search for Arch Linux install guide"
"What is the capital of France"
"Look up pacman commands"
"Google how to fix screen tearing"
```

---

## Documents
**File:** `documents.py`

Ingest and search PDFs, images (OCR), and text files into permanent memory.

### Triggers
- "read this"
- "ingest this"
- "save this pdf"
- "scan this" / "ocr this"
- "search documents"
- "find in docs"
- "what do you know about"

### Supported Files
- PDF (`.pdf`)
- Images (`.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`)
- Text (`.txt`, `.md`, `.json`, `.py`, `.sh`, `.conf`)

### Examples
```
"Read this ~/Documents/manual.pdf"
"Ingest ~/notes/arch-tips.txt as arch-tips"
"Search documents for pacman"
"What do you know about systemd"
"List my documents"
```

---

## Calendar
**File:** `calendar.py`

Manage calendar events via calcurse.

### Triggers
- "add to calendar"
- "schedule"
- "add event"
- "remind me on"
- "what's on my calendar"
- "show calendar"
- "my schedule"

### Examples
```
"Add dentist appointment on February 15th at 2pm"
"Schedule meeting with Bob tomorrow at 10am"
"Remind me on Friday to call mom"
"What's on my calendar today"
"Show calendar for next Monday"
"What do I have tomorrow"
```

---

## Alarms & Timers
**File:** `alarms.py`

Set alarms and countdown timers using systemd.

### Triggers
- "set alarm"
- "alarm for"
- "wake me"
- "set timer"
- "timer for"
- "countdown"
- "remind me in"

### Examples
```
"Set alarm for 7:30am"
"Wake me at 6am"
"Set timer for 10 minutes"
"Timer for 1 hour 30 minutes"
"Remind me in 5 minutes"
"Countdown 30 seconds"
```

---

## Music
**File:** `music.py`

Control music playback via playerctl (works with Spotify, etc).

### Triggers
- "play music"
- "pause" / "stop music"
- "resume"
- "next song" / "skip"
- "previous"
- "volume up" / "louder"
- "volume down" / "quieter"

### Examples
```
"Play some music"
"Pause"
"Skip this song"
"Next track"
"Volume up"
"Make it quieter"
```

---

## Apps
**File:** `apps.py`

Launch applications and open URLs.

### Triggers
- "open"
- "launch"
- "start"
- "go to"
- "browse to"

### Built-in Aliases
| Say | Opens |
|-----|-------|
| browser, firefox | Firefox |
| terminal, term | Ghostty |
| files, file manager | Nautilus |
| code, vscode, editor | VS Code |
| vim, nvim, nano | Ghostty + nano |
| spotify, music | Spotify |
| discord | Discord |
| calculator, calc | Calculator |

### Web Apps (via omarchy-launch-webapp)
| Say | Opens |
|-----|-------|
| chatgpt | ChatGPT |
| youtube | YouTube |
| twitter, x | Twitter/X |
| whatsapp | WhatsApp |

### Examples
```
"Open Firefox"
"Launch terminal"
"Open file manager"
"Go to youtube.com"
"Start Spotify"
"Open Discord"
```

---

## Claude Code
**File:** `claude.py`

Hand off complex coding tasks to Claude Code CLI.

### Triggers
- "hey claude"
- "ask claude"
- "code this"
- "write code"
- "debug this"
- "fix this code"
- "build me"
- "create a tool"

### Examples
```
"Hey Claude, write a Python script to rename all files in a folder"
"Code this: a bash script that backs up my home folder"
"Debug this function for me"
"Build me a simple web server"
"Claude, refactor this code"
```

---

## GUI Buttons (Not voice-activated)

These features are accessed via buttons in the Alice window toolbar:

### Load Reference (Temporary Memory)
Click the **"Load Reference"** button to load a document for the current session only.
- Perfect for repair manuals, documentation, reference material
- Content is included in Alice's context while answering questions
- Cleared when Alice restarts
- Supports: PDF, text files, images (OCR)

### Add Knowledge (Permanent Memory)
Click the **"Add Knowledge"** button to save permanent facts.
- Good for: Arch Linux commands, frequently used info, tips
- Persists forever in `memory/knowledge.json`
- Can load content from a text file
- Categories: general, arch-linux, commands, coding, hardware, other

---

## Special Commands

These work anywhere, no tool needed:

| Command | What it does |
|---------|--------------|
| "Remember that I prefer dark themes" | Saves a preference |
| "My name is Glenn" | Saves your name |
| "Reload tools" | Hot-reload all tools |

---

## Creating New Tools

1. Create a new `.py` file in this `tools/` directory
2. Inherit from `Tool` base class
3. Define `name`, `description`, `triggers`, and `execute()` method
4. Say "reload tools" to Alice

### Template
```python
"""My custom tool."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.base import Tool


class MyTool(Tool):
    """Description of what this tool does."""

    name = "mytool"
    description = "Short description"
    triggers = [
        "trigger phrase one",
        "trigger phrase two"
    ]

    def execute(self, query: str, **kwargs) -> str:
        # Your logic here
        return "Response to user"
```

---

*Last updated: February 2026*
