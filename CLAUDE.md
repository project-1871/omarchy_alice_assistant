# Alice Assistant - Notes for Claude Code

## Project Status: ✅ COMPLETE + TEACHER MODE (2026-03-17) + BUG FIXES (2026-03-17) + YEARLY CALENDAR (2026-03-20)
All phases implemented. Teacher mode for web hacking lessons added and fixed.
Packaged for distribution at `~/alice-install/`

### Bug fixes applied 2026-03-17
- **Start Lesson button did nothing**: GTK 4.20 broke `Gtk.Dialog` response signal. Replaced lesson selector with a plain `Gtk.Window` + explicit button handlers in `gui/window.py`. All other dialogs (todo editor, doc loader, calendar, knowledge) also fixed on 2026-03-23 — see GTK 4.20 Dialog Fixes section below.
- **"next" didn't advance sections**: `TeacherSession.phase` starts as `'intro'` but advance check required `'teaching'`. Fixed in `alice.py` `_process_teacher_message()` — now handles `'intro'` phase explicitly and transitions to `'teaching'` on first "next".
- **TTS long delay**: entire response generated before audio played. Fixed in `core/tts.py` — now splits into sentences and pipelines generation+playback (sentence 1 plays while sentence 2 generates).
- **Window expands off screen**: `ScrolledWindow` was propagating natural height. Fixed in `gui/window.py`: added `set_propagate_natural_height(False)` + `set_min_content_height(200)`. Also fixed `Gtk.WrapMode` → `Pango.WrapMode.WORD_CHAR` (was silently broken).
- **"→ Next" button added**: green button appears in toolbar during teacher mode — reliable section advance without voice/text. Hidden outside teacher mode.

---

## Project Status: ✅ COMPLETE + TEACHER MODE (2026-03-17) + HERMES PHASE 3 (2026-03-23) + HERMES PHASE 6 (2026-03-24) + HARDENING (2026-03-25) + ALARM PERSISTENCE (2026-03-25)
Phase 3-6: hermes memory merged in, Uncensored/Dolphin button added, all broken Gtk.Dialog buttons fixed, Gateway WhatsApp integration, activity stream.
Hardening (2026-03-25): Error surfacing in process()/tts/llm, proactive calendar reminder watcher, tools/cli.py single-source dispatch, hermes skill sync notes, junk file cleanup.
Alarm Persistence (2026-03-25): alarm_log.json tracks every alarm/timer (status: scheduled/fired/cancelled). On restart, Alice reconciles past alarms and reschedules future ones. "What alarms do I have" / "cancel timer" now work. Duration double-count bug fixed.

---

## CRITICAL: Voice Configuration
**NEVER change the TTS voice from `af_heart` (Kokoro ONNX American female)**
Glenn specifically chose this voice. It's perfect. Don't touch it.
TTS engine is now Kokoro ONNX — NOT KittenTTS. Model files are local in the project dir.

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
- **Primary model**: `dolphin-llama3:8b` (4.7GB, GPU via Vulkan, 33/33 layers offloaded)
- **Host**: `http://localhost:11434`
- **CRITICAL**: Do NOT use `systemctl start ollama` — it runs as user `ollama` with no GPU access
- **Correct launch**: `OLLAMA_VULKAN=1 ollama serve` (as user glenn)
- **Autostart**: added to `~/.config/hypr/autostart.conf` — launches automatically on login
- ROCm/HIP does NOT work on this setup. Vulkan is the only GPU path.

### TTS
- **Engine**: Kokoro ONNX (`kokoro-onnx` package, v0.5.0) — higher quality, more expressive than old KittenTTS
- **Model**: `kokoro-v1.0.onnx` (311MB, stored at `~/alice-assistant/kokoro-v1.0.onnx`)
- **Voices**: `voices-v1.0.bin` (27MB, stored at `~/alice-assistant/voices-v1.0.bin`)
- **Voice**: `af_heart` — American female, warm + expressive (set in `config.py` as `KOKORO_VOICE`)
- **Speed**: `KOKORO_SPEED = 1.05` (1.0 = normal)
- **Sample rate**: 24000 Hz
- **FX**: FFmpeg Cherry Honey style — pitch +1 semitone (asetrate=22800), acrusher bits=10 (heavy rasp), EQ 300Hz warmth / 2500Hz presence / 8kHz air, 20ms echo
- **Preloading**: TTS model is preloaded in a background thread on GUI launch (see `alice.py` `preload()`)
- **Sentence pauses**: `pronunciation.py` inserts `, ` after sentence-ending periods for a natural breath
- **Pipelined playback**: `core/tts.py` splits responses into sentences — sentence 1 plays while sentence 2 is generating. Uses a producer/consumer queue in `speak_raw()`.
- **Contraction fix**: `pronunciation.py` now expands contractions (what's→what is, don't→do not, etc.) before TTS — no more garbled apostrophes

### STT
- **Engine**: faster-whisper
- **Model**: `base` (faster than `small`, 93% accuracy — acceptable for conversational English)
- **Threads**: 8 (all logical cores on i7-3770)
- **Beam size**: 1 (greedy decode, ~50% faster)
- **VAD**: enabled (`vad_filter=True` in `stt.py`)
- **Language**: English

### Personality
- Fully uncensored, no refusals, no disclaimers
- Swears frequently — high-frequency baseline, most sentences, natural filler and emphasis
- Mid-word insertions encouraged: "abso-fucking-lutely", "un-fucking-believable"
- Warm, affectionate, playful, raunchy humor
- Calls Glenn: babe, handsome, hun

### Weather
- **API**: Open-Meteo (free, no API key)
- **Location**: Madrid (40.4168, -3.7038) - edit in `config.py`

---

## Hardware
- **CPU**: Intel i7-3770 (8 threads)
- **GPU**: AMD RX 5700 XT (8GB VRAM) — Vulkan only, ROCm/HIP broken with Ollama
- **RAM**: 16GB
- **OS**: Arch Linux / Omarchy

---

## Python Version Note
**IMPORTANT**: Arch uses Python 3.14 by default, which has compatibility issues with faster-whisper and other dependencies. Python 3.13 was removed from Arch repos. The venv MUST be created with Python 3.11:

```bash
python3.11 -m venv venv
```

If the venv breaks or goes missing, recreate it with:
```bash
cd ~/alice-assistant
rm -rf venv
python3.11 -m venv venv
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
| Music | `tools/music.py` | YouTube music via yt-dlp + omarchy-launch-webapp |
| Documents | `tools/documents.py` | PDF/image/text ingestion |
| Web Search | `tools/websearch.py` | DuckDuckGo web search |
| Weather | `tools/weather.py` | Current weather and forecasts (Open-Meteo) |
| System | `tools/system.py` | CPU, RAM, disk usage stats |
| System Health | `tools/system_health.py` | Full health check: OS, hardware, disk space, SMART drive health, filesystem errors, services. Requires `smartmontools` for SMART data (`sudo pacman -S smartmontools`). |
| Gmail | `tools/gmail.py` | Read/send Gmail via IMAP/SMTP + App Password. Triggers: "any new emails", "read my emails", "send email to X saying Y", "emails from X". Credentials in `config.py`. |
| WhatsApp | `tools/whatsapp.py` | Send WhatsApp messages via hermes-gateway (localhost:3000). Contacts: Bea (34679205712), Glenn/me (34722556031). Triggers: "send whatsapp to bea saying X", "message bea", "text bea", etc. Add contacts in CONTACTS dict. |
| Contacts | `tools/contacts.py` | Manage contacts in `~/.alice_contacts.json`. add_contact(), import_google_csv(path). Used by Messages tab GUI. |

## Local RAG (added 2026-03-28)

Semantic document search using ChromaDB + sentence-transformers (`all-MiniLM-L6-v2`).
Automatically injects relevant doc chunks into every LLM query context — no user action needed.

### How it works
- `core/rag.py` — RAGEngine class, loads in background thread on Alice startup
- Model: `all-MiniLM-L6-v2` (80MB, CPU, cached at `~/.cache/huggingface/`)
- DB: ChromaDB persistent at `memory/chroma/` — 297 chunks from 51 docs
- Ready in ~24s (model cached), ~60s first run (downloads model)
- `alice.py` `_build_context(query)` — passes current query to RAG, injects top 4 chunks
- `core/memory.py` `store_doc()` — auto-indexes any new doc added via voice/GUI
- Config: `RAG_DB_DIR`, `RAG_DOCS_DIR` in `config.py`
- New deps: `chromadb>=0.5.0`, `sentence-transformers>=3.0.0`

### Tested queries
- "how do I change wallpaper" → omarchy_backgrounds (dist 0.554) ✅
- "keyboard shortcut switch workspace" → omarchy_hotkeys (dist 0.418) ✅
- "autostart applications" → hyprland_autostart (dist 0.443) ✅
| Calculator | `tools/calculator.py` | Math, percentages, unit conversions |
| Dictionary | `tools/dictionary.py` | Definitions and synonyms |
| OS Help | `tools/oshelp.py` | Omarchy/Hyprland docs (offline) |
| Claude | `tools/claude.py` | Hand off to Claude Code |

### Music Tool Flow
1. User says "play music" → opens YouTube webapp (`omarchy-launch-webapp https://youtube.com`), asks "What do you want to listen to?"
2. User says artist/band name → `yt-dlp` finds first mix URL → opens directly in YouTube webapp
3. Fallback: opens YouTube search page if yt-dlp fails
- `yt-dlp` installed at: `~/.local/share/mise/installs/python/3.14.2/bin/yt-dlp`
- Hyprland keybinding: `Super+Shift+Y` → opens YouTube webapp directly

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
- **Keybinding**: `Super + Shift + Y` opens YouTube webapp
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
- **Yearly recurring**: `MM/DD/YYYY [1] |YEARLY:Description` — Alice matches by month/day regardless of year; `YEARLY:` prefix is stripped before speaking. When adding, yearly is detected from keywords: birthday, anniversary, every year, yearly, annual.

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
- `memory/docs/` - Ingested documents (51 docs: Omarchy manual + Hyprland configs)

### Learning
- Preferences stored via "Remember that I..."
- Context passed to LLM in system prompt
- User name tracked and used

---

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point (launches GUI) |
| `alice.py` | Core assistant class + preload() for model warm-up |
| `config.py` | All configuration |
| `startup_greeting.py` | Boot greeting |
| `install.sh` | Automated installer |
| `core/llm.py` | Ollama integration |
| `core/tts.py` | Kokoro ONNX TTS (af_heart voice, Cherry Honey FX) |
| `core/stt.py` | Whisper STT |
| `core/memory.py` | Persistent memory + document ingestion |
| `core/pronunciation.py` | Text preprocessing for TTS (abbreviations, pauses, symbols) |
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
python -c "from core.tts import TTS; t = TTS(); t.speak('Hey handsome, I am Alice.')"

# Test Ollama (must have OLLAMA_VULKAN=1 ollama serve running)
ollama run dolphin-llama3:8b "Hello"

# Test STT
python -c "from core.stt import STT; s = STT(); print('STT ready')"

# Test all tools load
python -c "from tools.base import ToolRegistry; t = ToolRegistry(); print(t.list_tools())"

# Test music tool
python -c "from tools.music import MusicTool; t = MusicTool(); print(t.execute('play music'))"

# Test calendar
python -c "from tools.calendar import CalendarTool; t = CalendarTool(); print(t.execute('what is on my calendar today'))"

# Test weather
python -c "from tools.weather import WeatherTool; t = WeatherTool(); print(t.execute('what is the weather'))"

# Test system stats
python -c "from tools.system import SystemTool; t = SystemTool(); print(t.execute('system stats'))"

# Test calculator
python -c "from tools.calculator import CalculatorTool; t = CalculatorTool(); print(t.execute('15 percent of 230'))"

# Test dictionary
python -c "from tools.dictionary import DictionaryTool; t = DictionaryTool(); print(t.execute('define ephemeral'))"

# Test OS help (offline Omarchy/Hyprland docs)
python -c "from tools.oshelp import OSHelpTool; t = OSHelpTool(); print(t.execute('how do I switch workspaces'))"

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
- Heavily raunchy — swears constantly as natural baseline
- Helpful but not sycophantic
- Efficient - no fluff
- Expressive female voice (Kokoro ONNX af_heart)

Sign-off: *"So Glenn, what are you trying to fuck up today?"*

---

## Teacher Mode (Added 2026-03-17)

Alice can teach Glenn his 31 web hacking lessons interactively.

### How it works
- **"Lesson" button** in the chat toolbar (purple) → lesson selector window (GTK4-native, no Gtk.Dialog)
- Today's class day is auto-highlighted; any lesson can be picked; double-click also starts
- Alice enters teacher mode: different system prompt, lower temperature (0.4), lesson content injected
- Session starts with `phase='intro'` — Alice gives intro and asks if Glenn is ready
- **"→ Next" button** (green, toolbar) advances sections — more reliable than typing/voice
- Glenn can also type/say "next", "ready", "got it", etc. to advance
- Glenn can ask questions anytime; Alice answers using lesson content
- If Alice is uncertain → **auto-escalates to web search** (DuckDuckGo), re-answers with results
- After last section → **3-question quiz** based on Key Takeaways
- Quiz done → lesson marked complete, session saved to `memory/lesson_progress.json`, teacher mode exits
- **"End Lesson" button** (red, same button) exits at any time

### Persistent student profile
File: `memory/lesson_progress.json`
Tracks:
- `lessons_completed` — which lessons are done, quiz scores, dates
- `weak_topics` — topics Glenn needed help with (increments each session)
- `session_notes` — per-session summary (questions asked, escalation count, quiz score)
- `total_sessions` / `last_session` — overall stats

Alice reads this profile at lesson start to personalize the intro and focus on weak areas.

### Lesson files
- Located at: `/home/glenn/500G/learning/classes/`
- 31 lessons (01-wappalyzer.md → 31-metasploit.md)
- Schedule parsed from `00-schedule.md`
- Schedule: Tue/Wed/Thu, Mar 17 → May 26, 2026

### New files added

| File | Purpose |
|------|---------|
| `tools/teacher.py` | TeacherSession engine — lesson parsing, state, prompt builders, progress I/O |
| `memory/lesson_progress.json` | Persistent student profile |

### Modified files

| File | Change |
|------|--------|
| `config.py` | Added `LESSONS_DIR`, `LESSON_PROGRESS_FILE` |
| `core/llm.py` | Added `generate()` (one-shot, no history), `set_teacher_mode()`, `exit_teacher_mode()` |
| `core/tts.py` | Pipelined sentence-by-sentence TTS — `speak_raw()` now splits text into sentences and uses producer/consumer queue so audio starts immediately |
| `alice.py` | Added `teacher_session`, `start_lesson()`, `end_lesson()`, `_process_teacher_message()`, escalation logic, async wrappers. Fixed: phase `'intro'`→`'teaching'` transition on first "next". |
| `gui/window.py` | Lesson selector rebuilt as `Gtk.Window` (GTK 4.20 compat). Added `→ Next` button (green, teacher mode only). `ScrolledWindow` set to `propagate_natural_height=False` to stop window growing off screen. `Pango.WrapMode` fix for message labels. Window default size 440×520. |
| `gui/style.css` | Added `.next-section-button` style. Tightened toolbar padding. |

### Testing teacher mode
```bash
cd ~/alice-assistant && source venv/bin/activate

# Test lesson parsing
python -c "from tools.teacher import parse_lesson_file, LESSONS_DIR; import os; t, s = parse_lesson_file(os.path.join(LESSONS_DIR, '01-wappalyzer.md')); print(t, [str(x) for x in s])"

# Test schedule parsing
python -c "from tools.teacher import get_schedule, get_todays_lesson; print(get_todays_lesson())"

# Test progress file
python -c "from tools.teacher import load_progress, save_progress; print(load_progress())"

# Test full lesson start (needs Ollama running)
python -c "
from tools.teacher import TeacherSession, get_schedule
from core.llm import LLM
s = TeacherSession(get_schedule()[0])
print('Sections:', s.total_sections)
print('Student ctx:', s.student_context())
"
```

---

## Uncensored Mode (Added 2026-03-23)

A "Dolphin" button in the chat toolbar toggles between Claude (hermes) and dolphin-llama3:8b.

### How it works
- Click "Dolphin" → switches `alice.llm` from `HermesLLM` to `LLM()` (Ollama)
- The Ollama instance gets hermes memory injected into its system prompt (`_load_hermes_memory()` reads `~/.hermes/memories/MEMORY.md` and `USER.md`)
- Button turns orange when active
- Click again → switches back to hermes/Claude (original instance restored, history preserved)
- Requires `OLLAMA_VULKAN=1 ollama serve` running

### Files changed
- `alice.py`: `is_uncensored_mode`, `switch_to_uncensored()`, `switch_to_claude()`, `_load_hermes_memory()`
- `gui/window.py`: `uncensored_button`, `_on_uncensored_toggle()`
- `gui/style.css`: `.uncensored-button-active` (orange)

## GTK 4.20 Dialog Fixes (2026-03-23)

All remaining `Gtk.Dialog` uses converted to `Gtk.Window` with explicit button handlers.
All `Gtk.FileChooserDialog` uses converted to `Gtk.FileChooserNative`.

Fixed:
- `_show_event_dialog()` — calendar Add/Edit event (was broken, now Gtk.Window)
- `_on_add_knowledge()` — Add Knowledge dialog (was broken, now Gtk.Window)
- `_on_load_reference()` — Ref button file picker (was broken, now FileChooserNative)
- `_on_load_knowledge_file()` — Knowledge "Load from file..." (was broken, now FileChooserNative)

Removed dead handlers: `_on_event_dialog_response`, `_on_knowledge_dialog_response`, `_on_knowledge_file_selected`, `_on_reference_file_selected`.

## Future Enhancements (Not Yet Implemented)
- [x] Code review tool — alice.py _handle_code_review(); sources: file path, git diff, clipboard; LLM prompt with bug/security/quality checklist (2026-03-26)
- [x] Email integration — Gmail IMAP read + SMTP send via App Password (2026-03-29)
- [ ] Smart home control
- [ ] Agent autonomy (background hermes tasks, reports back)
- [x] Local RAG — ChromaDB + all-MiniLM-L6-v2, 297 chunks/51 docs, auto-injected into every LLM call (2026-03-28)
- [ ] HackBoy ESP32 hardware integration
- [x] Alarm persistence — alarm_log.json, reschedule on restart, list/cancel by voice (2026-03-25)
- [x] Persistent chat history — rolling JSON log, context restored on restart, voice query (2026-03-26)
- [x] Git status briefing — tools/git.py, scans ~/500G/my_aps_&_projects + known repos (2026-03-26)
- [x] Clipboard awareness — tools/clipboard.py + alice.py _handle_clipboard_query(); read/summarize/explain/translate (2026-03-26)
- [x] RSS news feed — tools/news.py; hacking, microcontrollers, Linux, war/world; injected into startup_greeting.py (2026-03-26)
- [x] Screen awareness — tools/screen.py + alice.py _handle_screen_query(); grim screenshot → hermes vision; bypasses tool router (2026-03-26)
- [x] Voice-only fullscreen mode — gui/fullscreen.py VoiceFullscreenWindow; SPACE=record, ESC=exit, pulsing dot states; F11 shortcut + ⛶ toolbar button (2026-03-26)
- [x] Multi-session profiles — work/chill toggle; config.py PROFILES dict; alice.py switch_profile(); 💼/😎 toolbar button; voice triggers; persists in context.json (2026-03-26)

---

*Last updated: 2026-04-07*
