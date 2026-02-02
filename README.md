# Alice Assistant

A lightweight, fast, uncensored personal voice assistant for Arch Linux / Omarchy.

No always-listening BS. No slow pipeline. Just a snappy assistant you call when needed.

## Features

- **Voice Input/Output** - Talk to Alice, she talks back (British female voice - Alba)
- **Uncensored AI** - Uses dolphin-phi:2.7b, no content restrictions
- **Calendar Integration** - Manages events via calcurse
- **Note Taking** - Dictate notes, search them later
- **Alarms & Timers** - Natural language time setting
- **App Launcher** - "Open Firefox", "Launch Spotify"
- **Music Control** - Play, pause, skip, volume control
- **Document Memory** - Ingest PDFs, images (OCR), text files
- **Learning** - Remembers your preferences
- **Claude Code Handoff** - Complex coding tasks go to Claude

## Installation

### Quick Install

```bash
# Extract the archive
tar -xzf alice-assistant.tar.gz
cd alice-assistant

# Run installer
./install.sh
```

### Manual Install

1. **System Dependencies**
   ```bash
   sudo pacman -S python python-pip python-gobject gtk4 tesseract tesseract-data-eng
   yay -S piper-tts-bin
   ```

2. **Install Ollama**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull dolphin-phi:2.7b
   ```

3. **Python Environment**
   ```bash
   cd ~/alice-assistant
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Create Launcher**
   ```bash
   mkdir -p ~/.local/bin
   cat > ~/.local/bin/alice << 'EOF'
   #!/bin/bash
   cd "$HOME/alice-assistant"
   source venv/bin/activate
   python main.py "$@"
   EOF
   chmod +x ~/.local/bin/alice
   ```

## Usage

### Launch Alice

- **Keyboard**: Press `Super + A`
- **Terminal**: Run `alice`
- **Waybar**: Click the Alice indicator (if configured)

### Voice Commands

**Notes:**
- "Take a note: remember to buy milk"
- "What notes do I have?"
- "Search notes for project"

**Calendar:**
- "Add dentist appointment on February 10th at 2pm"
- "What's on my calendar tomorrow?"
- "Schedule meeting with Bob next Tuesday at 3pm"

**Alarms & Timers:**
- "Set a timer for 5 minutes"
- "Set alarm for 7am"
- "Remind me in 30 minutes"

**Apps:**
- "Open Firefox"
- "Launch Spotify"
- "Open file manager"

**Music:**
- "Play music" / "Pause"
- "Next song" / "Previous"
- "Volume up" / "Volume down"

**Documents:**
- "Read this ~/Documents/manual.pdf"
- "Search documents for wiring diagram"
- "What documents do I have?"

**Learning:**
- "Remember that I prefer dark themes"
- "My name is Glenn"
- "I always use vim for editing"

**Claude Code:**
- "Hey Claude, check this code for me"
- "Build me a Python script that..."

**System:**
- "Reload tools" - Refresh available tools after adding new ones

### Startup Greeting

Alice greets you at boot with:
- Time-appropriate greeting (morning/afternoon/evening)
- Today's date
- Calendar events for today
- Upcoming events (next 5 days)
- Her signature sign-off

## Waybar Calendar Setup

To add a calendar dropdown to your waybar date, edit `~/.config/waybar/config.jsonc`:

```jsonc
"clock#date": {
  "format": "{:%A %d %b}",
  "interval": 60,
  "tooltip": true,
  "tooltip-format": "<tt>{calendar}</tt>",
  "calendar": {
    "mode": "month",
    "weeks-pos": "left",
    "on-scroll": 1,
    "format": {
      "months": "<span color='#ffead3'><b>{}</b></span>",
      "days": "<span color='#ecc6d9'>{}</span>",
      "weeks": "<span color='#99ffdd'>W{}</span>",
      "weekdays": "<span color='#ffcc66'><b>{}</b></span>",
      "today": "<span color='#ff6699'><b><u>{}</u></b></span>"
    }
  },
  "on-click": "uwsm-app -- xdg-terminal-exec --title=calcurse -e calcurse",
  "on-click-right": "omarchy-launch-floating-terminal-with-presentation omarchy-tz-select"
}
```

Then restart waybar: `omarchy-restart-waybar`

## File Structure

```
alice-assistant/
├── main.py                 # Entry point (GUI)
├── alice.py                # Core assistant class
├── config.py               # Configuration
├── startup_greeting.py     # Boot greeting script
├── install.sh              # Installer
├── requirements.txt        # Python dependencies
│
├── gui/
│   ├── app.py              # GTK4 application
│   ├── window.py           # Main window
│   ├── style.css           # Dark theme
│   └── recorder.py         # Audio recording
│
├── core/
│   ├── llm.py              # Ollama integration
│   ├── tts.py              # Piper TTS (Alba voice)
│   ├── stt.py              # Whisper transcription
│   └── memory.py           # Persistent memory
│
├── tools/
│   ├── base.py             # Tool base class & registry
│   ├── notes.py            # Note taking
│   ├── alarms.py           # Alarms/timers
│   ├── calendar.py         # Calendar (calcurse)
│   ├── apps.py             # App launcher
│   ├── music.py            # Music control
│   ├── documents.py        # Document ingestion
│   └── claude.py           # Claude Code handoff
│
├── memory/
│   ├── context.json        # Current context
│   ├── notes.json          # All notes
│   ├── skills.json         # Learned preferences
│   └── docs/               # Ingested documents
│
└── voices/
    └── en_GB-alba-medium.onnx  # THE voice (never change!)
```

## Configuration

Edit `config.py` to customize:

```python
# LLM Model
OLLAMA_MODEL = 'dolphin-phi:2.7b'      # Fast, uncensored
OLLAMA_MODEL_FULL = 'dolphin-mistral:7b'  # Higher quality

# Speech Recognition
WHISPER_MODEL = 'small'  # tiny, base, small (smaller = faster)

# Personality (edit SYSTEM_PROMPT)
```

## Adding Custom Tools

1. Create a new file in `tools/` (e.g., `tools/weather.py`)
2. Inherit from `Tool` base class
3. Define `name`, `description`, `triggers`, and `execute()` method
4. Say "reload tools" to Alice to load it

Example:
```python
from tools.base import Tool

class WeatherTool(Tool):
    name = "weather"
    description = "Get weather information"
    triggers = ["weather", "temperature", "forecast"]

    def execute(self, query: str, **kwargs) -> str:
        # Your implementation here
        return "It's sunny and 72°F"
```

## Troubleshooting

**Alice doesn't speak:**
- Check audio output: `paplay /usr/share/sounds/freedesktop/stereo/bell.oga`
- Verify piper is installed: `which piper`
- Check voice file exists: `ls ~/alice-assistant/voices/`

**Voice recognition not working:**
- Check microphone: `arecord -d 3 test.wav && aplay test.wav`
- Verify faster-whisper is installed: `pip show faster-whisper`

**LLM not responding:**
- Check Ollama is running: `ollama list`
- Start Ollama: `ollama serve`
- Test model: `ollama run dolphin-phi:2.7b "hello"`

**Calendar events not showing:**
- Check calcurse file: `cat ~/.local/share/calcurse/apts`
- Add test event: `echo "02/15/2026 [1] |Test event" >> ~/.local/share/calcurse/apts`

## License

Personal use. Built for Glenn by Claude.

---

*"So Glenn, what are you trying to fuck up today?"* - Alice
