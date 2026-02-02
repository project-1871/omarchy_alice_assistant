# Alice Assistant - Game Plan

## Mission
Build a lightweight, fast personal assistant that grows with you.
No always-listening BS. No slow pipeline. Just a snappy assistant you call when needed.

## Status: ✅ COMPLETE

All phases implemented. Project packaged for distribution.

---

## What We Built

### Voice & Personality
- **Voice**: Alba (en_GB-alba-medium.onnx) - British female, perfect
- **Personality**: Witty, slightly raunchy, gets shit done
- **Boot Greeting**: Time-aware greeting with calendar events

### LLM (Uncensored & Fast)
**Current Model**: `dolphin-phi:2.7b` (1.6GB, fast, uncensored)

| Model | Size | Speed | Quality | Uncensored |
|-------|------|-------|---------|------------|
| `dolphin-phi:2.7b` | 1.6GB | **Fastest** | Good | **YES** |
| `dolphin-mistral:7b` | 4GB | Medium | Great | YES |

### No Always-Listening
- Launch Alice: `Super + A` or `alice` command
- GUI pops up, you talk or type
- She responds, done
- Close when finished

### Core Tools
| Tool | Trigger Examples |
|------|------------------|
| **Notes** | "Take a note:", "What notes do I have?" |
| **Alarms** | "Set timer for 5 minutes", "Alarm for 7am" |
| **Calendar** | "Add meeting on Tuesday at 3pm", "What's on my calendar?" |
| **Apps** | "Open Firefox", "Launch Spotify" |
| **Music** | "Play music", "Next song", "Volume up" |
| **Documents** | "Read this ~/file.pdf", "Search documents for..." |
| **Claude** | "Hey Claude, check this code" |

### System Integration
- **Hyprland**: Super+A launches Alice, boot greeting on startup
- **Waybar**: Calendar dropdown from date click (calcurse)
- **Calcurse**: Shared calendar Alice can read/write

### Memory & Learning
- **Persistent memory** - Survives restarts
- **Context awareness** - Knows what you're working on
- **Document ingestion** - PDFs, images (OCR), text files
- **Learning** - "Remember that I prefer..." stores preferences

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   GUI (GTK4)                     │
│   ┌─────────┐  ┌─────────┐  ┌─────────────────┐ │
│   │  Chat   │  │  Voice  │  │  Status/Memory  │ │
│   │  Area   │  │  Input  │  │  Indicator      │ │
│   └─────────┘  └─────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│              Alice Core Engine                   │
│  ┌──────────┐ ┌──────────┐ ┌─────────────────┐  │
│  │  Intent  │ │  Tool    │ │    Memory       │  │
│  │  Parser  │ │  Router  │ │    Manager      │  │
│  └──────────┘ └──────────┘ └─────────────────┘  │
└─────────────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
┌─────────────┐ ┌───────────┐ ┌───────────┐
│   Ollama    │ │   Piper   │ │  Whisper  │
│   (LLM)     │ │   (TTS)   │ │  (STT)    │
│dolphin-phi  │ │   Alba    │ │   small   │
└─────────────┘ └───────────┘ └───────────┘
```

## File Structure

```
alice-assistant/
├── main.py                 # Entry point (GUI)
├── alice.py                # Core assistant class
├── config.py               # Configuration
├── startup_greeting.py     # Boot greeting script
├── install.sh              # Automated installer
├── README.md               # Full documentation
├── GAMEPLAN.md             # This file
├── CLAUDE.md               # Notes for Claude Code
├── requirements.txt        # Python dependencies
│
├── gui/
│   ├── __init__.py
│   ├── app.py              # GTK4 application
│   ├── window.py           # Main window
│   ├── style.css           # Dark theme
│   └── recorder.py         # Audio recording
│
├── core/
│   ├── __init__.py
│   ├── llm.py              # Ollama integration
│   ├── tts.py              # Piper TTS (Alba)
│   ├── stt.py              # Whisper transcription
│   └── memory.py           # Persistent memory + document ingestion
│
├── tools/
│   ├── __init__.py
│   ├── base.py             # Tool base class + auto-discovery
│   ├── notes.py            # Note taking
│   ├── alarms.py           # Alarms/timers
│   ├── calendar.py         # Calendar (calcurse integration)
│   ├── apps.py             # App launcher
│   ├── music.py            # Music player control
│   ├── documents.py        # PDF/image/text ingestion
│   └── claude.py           # Claude Code handoff
│
├── memory/
│   ├── context.json        # Current context
│   ├── notes.json          # All notes
│   ├── skills.json         # Learned preferences
│   └── docs/               # Ingested documents
│
└── voices/
    └── en_GB-alba-medium.onnx  # THE voice (never change)
```

---

## Implementation Phases

### Phase 1: Foundation ✅ COMPLETE
1. [x] Create project structure
2. [x] Set up Python venv with minimal deps
3. [x] Implement basic LLM integration (Ollama)
4. [x] Port TTS (Piper + Alba)
5. [x] Port STT (Whisper)
6. [x] Basic GUI (GTK4, dark theme)
7. [x] Test full loop: voice → text → LLM → voice

### Phase 2: Core Tools ✅ COMPLETE
1. [x] Notes tool (dictation to file)
2. [x] Alarm tool (systemd timers)
3. [x] App launcher tool
4. [x] Music tool (playerctl)
5. [x] Intent routing (auto-discovery)

### Phase 3: Memory & Growth ✅ COMPLETE
1. [x] Persistent memory system
2. [x] Context awareness
3. [x] Document ingestion (pypdf + pytesseract)
4. [x] Learning from interactions

### Phase 4: Claude Integration ✅ COMPLETE
1. [x] Claude Code handoff for complex tasks
2. [x] Tool building on demand (auto-reload)
3. [ ] Code review requests (future enhancement)

### Phase 5: System Integration ✅ COMPLETE
1. [x] Calendar tool (calcurse integration)
2. [x] Waybar calendar dropdown
3. [x] Boot greeting (time-aware, calendar events)
4. [x] Hyprland keybinding (Super+A)
5. [x] Autostart configuration

### Phase 6: Distribution ✅ COMPLETE
1. [x] Install script (install.sh)
2. [x] README documentation
3. [x] Package archive (alice-assistant.tar.gz)
4. [x] Install folder with instructions

---

## Configuration

### Current Settings (config.py)

```python
# LLM
OLLAMA_MODEL = 'dolphin-phi:2.7b'       # Fast, uncensored (1.6GB)
OLLAMA_MODEL_FULL = 'dolphin-mistral:7b' # Higher quality fallback

# STT
WHISPER_MODEL = 'small'                  # tiny/base/small

# Voice
VOICE_MODEL = 'en_GB-alba-medium.onnx'   # NEVER CHANGE
```

---

## Dependencies

### System (pacman/yay)
```
python python-pip python-gobject gtk4
tesseract tesseract-data-eng
piper-tts-bin (AUR)
ollama
```

### Python (requirements.txt)
```
PyGObject>=3.42.0
requests>=2.28.0
faster-whisper>=0.10.0
python-dateutil>=2.8.0
pypdf>=3.0.0
pytesseract>=0.3.10
Pillow>=9.0.0
```

---

## Hardware Tested

- **CPU**: Intel i7-3770 (8 threads @ 3.9GHz)
- **GPU**: AMD RX 5600 XT / 5700 XT (ROCm capable)
- **RAM**: 16GB
- **OS**: Arch Linux / Omarchy

---

## Boot Greeting

Alice greets you each boot with:
```
"Good morning Glenn. It's Monday, February 3rd.
You have 2 things on your calendar today: dentist at 2pm,
and team meeting at 4pm. Coming up: project deadline on Wednesday.
So Glenn, what are you trying to fuck up today?"
```

---

## Install Package

Location: `~/alice-install/`

Contents:
- `alice-assistant.tar.gz` - Full project archive (56MB)
- `install.sh` - Standalone installer
- `README.txt` - Quick start instructions

Install on new machine:
```bash
tar -xzf alice-assistant.tar.gz
cd alice-assistant
./install.sh
```

---

## Future Enhancements

- [ ] Code review tool (file/diff handling)
- [ ] Weather integration
- [ ] Email integration
- [ ] Smart home control
- [ ] Multi-language support

---

*"So Glenn, what are you trying to fuck up today?"* - Alice
