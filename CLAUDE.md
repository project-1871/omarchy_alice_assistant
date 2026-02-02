# Alice Assistant - Notes for Claude Code

## Project Status: ✅ COMPLETE
All phases implemented. Packaged for distribution at `~/alice-install/`

---

## CRITICAL: Voice Configuration
**NEVER change the TTS voice from `en_GB-alba-medium.onnx` (Alba - British female)**
Glenn specifically chose this voice. It's perfect. Don't touch it.

---

## Project Philosophy
- **SPEED** is the #1 priority
- No always-listening, no monitoring
- Simple, lightweight, extensible
- Grows with Glenn's learning
- Uncensored responses (no content filtering)

---

## Current Configuration

### LLM
- **Backend**: Ollama
- **Primary model**: `dolphin-phi:2.7b` (1.6GB, fast, uncensored)
- **Fallback model**: `dolphin-mistral:7b` (higher quality when needed)
- **Host**: `http://localhost:11434`

### TTS
- **Engine**: Piper (AUR: `piper-tts-bin`, installed at `/opt/piper-tts/piper`)
- **Voice**: `voices/en_GB-alba-medium.onnx` (NEVER CHANGE)
- **Sample rate**: 22050

### STT
- **Engine**: faster-whisper
- **Model**: `small` (can use tiny/base for speed)
- **Language**: English

---

## Hardware
- **CPU**: Intel i7-3770 (8 threads)
- **GPU**: AMD RX 5600 XT / 5700 XT (ROCm capable)
- **RAM**: 16GB
- **OS**: Arch Linux / Omarchy

---

## Python Version Note
**IMPORTANT**: Arch uses Python 3.14 by default, which has compatibility issues with faster-whisper and other dependencies. The venv MUST be created with Python 3.13 (or 3.12/3.11):

```bash
python3.13 -m venv venv
```

The install.sh has been updated to handle this automatically. If the venv breaks or goes missing, recreate it with:
```bash
cd ~/alice-assistant
rm -rf venv
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Available Tools

| Tool | File | Purpose |
|------|------|---------|
| Notes | `tools/notes.py` | Take and search dictated notes |
| Alarms | `tools/alarms.py` | Timers and alarms (systemd) |
| Calendar | `tools/calendar.py` | Calcurse integration |
| Apps | `tools/apps.py` | Launch applications |
| Music | `tools/music.py` | Playerctl music control |
| Documents | `tools/documents.py` | PDF/image/text ingestion |
| Claude | `tools/claude.py` | Hand off to Claude Code |

### Adding New Tools
1. Create file in `tools/` directory
2. Inherit from `Tool` base class
3. Define `name`, `description`, `triggers`, `execute()`
4. Say "reload tools" to Alice to load it

---

## Special Commands
- **"Reload tools"** - Re-discover tools without restart
- **"Remember that I..."** - Store a preference
- **"My name is..."** - Store user name

---

## System Integration

### Hyprland
- **Keybinding**: `Super + A` launches Alice
- **Config**: `~/.config/hypr/bindings.conf`
- **Autostart**: `~/.config/hypr/autostart.conf`
- **Window rule**: Calcurse floats at 1000x700

### Waybar
- **Calendar**: Click date → opens calcurse
- **Config**: `~/.config/waybar/config.jsonc`

### Calcurse
- **Data**: `~/.local/share/calcurse/apts`
- **Format**: `MM/DD/YYYY @ HH:MM -> MM/DD/YYYY @ HH:MM |Description`
- **All-day**: `MM/DD/YYYY [1] |Description`

---

## Boot Greeting
Script: `startup_greeting.py`
Launcher: `~/.local/bin/alice-greeting`

Greeting includes:
- Time-appropriate greeting (morning/afternoon/evening)
- User name (Glenn)
- Day and date
- Today's calendar events
- Upcoming events (next 5 days)
- Sign-off: "So Glenn, what are you trying to fuck up today?"

---

## Memory System

### Files
- `memory/context.json` - Current context, user name, preferences
- `memory/notes.json` - All dictated notes
- `memory/skills.json` - Learned preferences
- `memory/docs/` - Ingested documents (PDFs, images, text)

### Learning
- Preferences stored via "Remember that I..."
- Context passed to LLM in system prompt
- User name tracked and used

---

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point (launches GUI) |
| `alice.py` | Core assistant class |
| `config.py` | All configuration |
| `startup_greeting.py` | Boot greeting |
| `install.sh` | Automated installer |
| `core/llm.py` | Ollama integration |
| `core/tts.py` | Piper TTS |
| `core/stt.py` | Whisper STT |
| `core/memory.py` | Persistent memory + document ingestion |
| `tools/base.py` | Tool base class + auto-discovery |

---

## USB Mic Setup (if needed)
```bash
pactl set-card-profile alsa_card.usb-USB_AUDIO_USB_AUDIO_20200508V100-00 "output:iec958-stereo+input:mono-fallback"
pactl set-default-source alsa_input.usb-USB_AUDIO_USB_AUDIO_20200508V100-00.mono-fallback
```

---

## Testing Commands

```bash
# Activate venv first
cd ~/alice-assistant && source venv/bin/activate

# Test TTS
echo "Hello Glenn" | /opt/piper-tts/piper --model voices/en_GB-alba-medium.onnx --output-raw | paplay --raw --channels=1 --rate=22050

# Test Ollama
ollama run dolphin-phi:2.7b "Hello"

# Test STT
python -c "from core.stt import STT; s = STT(); print('STT ready')"

# Test all tools load
python -c "from tools.base import ToolRegistry; t = ToolRegistry(); print(t.list_tools())"

# Test calendar
python -c "from tools.calendar import CalendarTool; t = CalendarTool(); print(t.execute('what is on my calendar today'))"

# Run startup greeting
python startup_greeting.py
```

---

## Install Package

Location: `~/alice-install/`

Contents:
- `alice-assistant.tar.gz` (56MB) - Full project
- `install.sh` - Standalone installer
- `README.txt` - Quick instructions

Install on new machine:
```bash
tar -xzf alice-assistant.tar.gz
cd alice-assistant
./install.sh
```

---

## Personality Notes

Alice is:
- Witty and direct
- Slightly raunchy humor
- Helpful but not sycophantic
- Efficient - no fluff
- British accent (Alba voice)

Sign-off: *"So Glenn, what are you trying to fuck up today?"*

---

## Future Enhancements (Not Yet Implemented)
- [ ] Code review tool (file/diff handling)
- [ ] Weather integration
- [ ] Email integration
- [ ] Smart home control

---

*Last updated: February 2026*
