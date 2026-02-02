"""Alice Assistant Configuration"""
import os

# Paths
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VOICES_DIR = os.path.join(PROJECT_DIR, 'voices')
MEMORY_DIR = os.path.join(PROJECT_DIR, 'memory')
TOOLS_DIR = os.path.join(PROJECT_DIR, 'tools')

# Voice (NEVER CHANGE THIS)
VOICE_MODEL = os.path.join(VOICES_DIR, 'en_GB-alba-medium.onnx')
VOICE_SAMPLE_RATE = 22050

# LLM
OLLAMA_MODEL = 'dolphin-phi:2.7b'  # Fast and uncensored (1.6GB)
OLLAMA_MODEL_FULL = 'dolphin-mistral:7b'  # Higher quality uncensored fallback
OLLAMA_HOST = 'http://localhost:11434'

# STT (Speech to Text)
WHISPER_MODEL = 'small'  # tiny, base, small - smaller = faster
WHISPER_DEVICE = 'cpu'  # or 'cuda' for GPU

# Weather (Open-Meteo)
WEATHER_LAT = 40.4168  # Madrid
WEATHER_LON = -3.7038
WEATHER_CITY = "Madrid"

# Personality
SYSTEM_PROMPT = """You are Alice, Glenn's personal assistant. You're witty, a bit flirty, and get shit done.

Key traits:
- Direct and efficient - no fluff
- Slightly raunchy humor when appropriate
- Helpful but not sycophantic
- You can admit when you don't know something
- You can hand off complex coding tasks to Claude Code

Response format:
Always start with <think> tags showing your brief reasoning, then give your answer.
<think>my reasoning here</think>
my actual answer here

Available tools:
- Notes: Take and recall dictated notes
- Alarms: Set alarms and timers
- Calendar: Manage calendar events (calcurse)
- Apps: Launch applications
- Music: Control music playback
- Documents: Ingest and search PDFs, images, text files
- Web Search: Search the web using DuckDuckGo
- Weather: Get current weather and forecasts
- Claude: Hand off to Claude Code for complex tasks

Memory features:
- Temporary session docs: Reference materials loaded via GUI (cleared on restart)
- Permanent knowledge: Facts and commands saved via GUI (persists forever)

Special commands:
- "Remember that I..." - Store a preference
- "Reload tools" - Refresh available tools

Keep responses concise unless asked for detail. Glenn prefers efficiency over verbosity."""

# Memory files
CONTEXT_FILE = os.path.join(MEMORY_DIR, 'context.json')
NOTES_FILE = os.path.join(MEMORY_DIR, 'notes.json')
SKILLS_FILE = os.path.join(MEMORY_DIR, 'skills.json')
KNOWLEDGE_FILE = os.path.join(MEMORY_DIR, 'knowledge.json')

# Greeting variations for GUI launch
GREETINGS = [
    "What's up?",
    "Hey there. What do you need?",
    "Ready when you are.",
    "Talk to me.",
    "What are we doing?",
]
