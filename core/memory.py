"""Persistent memory system."""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
import sys
sys.path.insert(0, '..')
import config

# Optional imports for document ingestion
try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

try:
    import pytesseract
    from PIL import Image
    HAS_OCR = True
except ImportError:
    HAS_OCR = False


class Memory:
    """Persistent memory that grows with you."""

    def __init__(self):
        os.makedirs(config.MEMORY_DIR, exist_ok=True)
        self.context = self._load_json(config.CONTEXT_FILE, {
            'current_project': None,
            'last_interaction': None,
            'preferences': {}
        })
        self.notes = self._load_json(config.NOTES_FILE, {'notes': []})
        self.skills = self._load_json(config.SKILLS_FILE, {'learned': []})
        self.knowledge = self._load_json(config.KNOWLEDGE_FILE, {'entries': []})
        self.alarms = self._load_json(config.ALARM_LOG_FILE, {'alarms': []})

        # Session-only temporary memory (cleared on restart)
        self.session_docs = {}  # {name: {content, type, file_path}}

    def _load_json(self, path: str, default: dict) -> dict:
        """Load JSON file or return default."""
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
        return default

    def _save_json(self, path: str, data: dict):
        """Save data to JSON file."""
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    # Context methods
    def set_context(self, key: str, value: Any):
        """Set a context value."""
        self.context[key] = value
        self.context['last_interaction'] = datetime.now().isoformat()
        self._save_json(config.CONTEXT_FILE, self.context)

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get a context value."""
        return self.context.get(key, default)

    # Notes methods
    def add_note(self, content: str, tags: list = None) -> dict:
        """Add a new note."""
        note = {
            'id': len(self.notes['notes']) + 1,
            'content': content,
            'tags': tags or [],
            'created': datetime.now().isoformat()
        }
        self.notes['notes'].append(note)
        self._save_json(config.NOTES_FILE, self.notes)
        return note

    def get_notes(self, tag: str = None, limit: int = 10) -> list:
        """Get recent notes, optionally filtered by tag."""
        notes = self.notes['notes']
        if tag:
            notes = [n for n in notes if tag in n.get('tags', [])]
        return notes[-limit:]

    def search_notes(self, query: str) -> list:
        """Search notes by content."""
        query = query.lower()
        return [n for n in self.notes['notes'] if query in n['content'].lower()]

    # Skills methods
    def add_skill(self, name: str, description: str):
        """Record a learned skill."""
        skill = {
            'name': name,
            'description': description,
            'learned': datetime.now().isoformat()
        }
        self.skills['learned'].append(skill)
        self._save_json(config.SKILLS_FILE, self.skills)

    def get_skills(self) -> list:
        """Get all learned skills."""
        return self.skills['learned']

    # Knowledge methods (permanent learned facts)
    def add_knowledge(self, title: str, content: str, category: str = 'general'):
        """Add a permanent knowledge entry."""
        entry = {
            'id': len(self.knowledge['entries']) + 1,
            'title': title,
            'content': content,
            'category': category,
            'added': datetime.now().isoformat()
        }
        self.knowledge['entries'].append(entry)
        self._save_json(config.KNOWLEDGE_FILE, self.knowledge)
        return entry

    def get_knowledge(self, category: str = None) -> list:
        """Get knowledge entries, optionally filtered by category."""
        entries = self.knowledge['entries']
        if category:
            entries = [e for e in entries if e.get('category') == category]
        return entries

    def search_knowledge(self, query: str) -> list:
        """Search knowledge by title or content."""
        query = query.lower()
        return [e for e in self.knowledge['entries']
                if query in e['title'].lower() or query in e['content'].lower()]

    def remove_knowledge(self, entry_id: int) -> bool:
        """Remove a knowledge entry by ID."""
        for i, entry in enumerate(self.knowledge['entries']):
            if entry.get('id') == entry_id:
                self.knowledge['entries'].pop(i)
                self._save_json(config.KNOWLEDGE_FILE, self.knowledge)
                return True
        return False

    def get_knowledge_summary(self) -> str:
        """Get a summary of all knowledge for context."""
        if not self.knowledge['entries']:
            return ""
        lines = ["Your permanent knowledge base:"]
        for entry in self.knowledge['entries']:
            lines.append(f"- {entry['title']}: {entry['content'][:100]}...")
        return "\n".join(lines)

    # Session memory methods (temporary, cleared on restart)
    def load_session_doc(self, file_path: str, name: str = None) -> tuple[bool, str]:
        """Load a document into temporary session memory."""
        path = Path(file_path)
        if not path.exists():
            return False, f"File not found: {file_path}"

        if not name:
            name = path.stem

        suffix = path.suffix.lower()

        # Extract content based on file type
        try:
            if suffix == '.pdf':
                if not HAS_PYPDF:
                    return False, "PDF support not installed"
                reader = PdfReader(path)
                content = "\n\n".join(p.extract_text() or "" for p in reader.pages)
            elif suffix in ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff'):
                if not HAS_OCR:
                    return False, "OCR support not installed"
                image = Image.open(path)
                content = pytesseract.image_to_string(image)
            else:
                content = path.read_text()

            self.session_docs[name] = {
                'content': content,
                'type': suffix.lstrip('.'),
                'file_path': str(path)
            }
            return True, f"Loaded '{name}' into session memory ({len(content)} chars)"

        except Exception as e:
            return False, f"Failed to load: {e}"

    def unload_session_doc(self, name: str) -> bool:
        """Remove a document from session memory."""
        if name in self.session_docs:
            del self.session_docs[name]
            return True
        return False

    def get_session_docs(self) -> dict:
        """Get all session documents."""
        return self.session_docs

    def search_session_docs(self, query: str) -> list[dict]:
        """Search session documents."""
        results = []
        query_lower = query.lower()

        for name, doc in self.session_docs.items():
            content = doc.get('content', '')
            if query_lower in content.lower():
                idx = content.lower().find(query_lower)
                start = max(0, idx - 100)
                end = min(len(content), idx + len(query) + 100)
                snippet = content[start:end]

                results.append({
                    'name': name,
                    'type': doc.get('type', 'unknown'),
                    'snippet': snippet,
                    'session': True
                })
        return results

    def get_session_context(self) -> str:
        """Get session documents as context for LLM."""
        if not self.session_docs:
            return ""
        lines = ["Reference documents loaded for this session:"]
        for name, doc in self.session_docs.items():
            content = doc['content']
            # Truncate very long docs
            if len(content) > 5000:
                content = content[:5000] + "... [truncated]"
            lines.append(f"\n--- {name} ({doc['type']}) ---\n{content}")
        return "\n".join(lines)

    # Document storage
    def store_doc(self, name: str, content: str, doc_type: str = 'text'):
        """Store a document in memory and index it in RAG."""
        docs_dir = os.path.join(config.MEMORY_DIR, 'docs')
        os.makedirs(docs_dir, exist_ok=True)

        doc_path = os.path.join(docs_dir, f'{name}.json')
        doc = {
            'name': name,
            'type': doc_type,
            'content': content,
            'stored': datetime.now().isoformat()
        }
        with open(doc_path, 'w') as f:
            json.dump(doc, f, indent=2)

        # Index into RAG if engine is attached
        if hasattr(self, '_rag') and self._rag is not None:
            self._rag.index_document(name, content, doc_type)

    def get_doc(self, name: str) -> dict | None:
        """Retrieve a stored document."""
        doc_path = os.path.join(config.MEMORY_DIR, 'docs', f'{name}.json')
        if os.path.exists(doc_path):
            with open(doc_path, 'r') as f:
                return json.load(f)
        return None

    def list_docs(self) -> list:
        """List all stored documents."""
        docs_dir = os.path.join(config.MEMORY_DIR, 'docs')
        if not os.path.exists(docs_dir):
            return []
        return [f.replace('.json', '') for f in os.listdir(docs_dir) if f.endswith('.json')]

    # Document ingestion methods
    def ingest_file(self, file_path: str, name: str = None) -> tuple[bool, str]:
        """Ingest a file (PDF, image, or text) into memory.

        Returns:
            Tuple of (success, message)
        """
        path = Path(file_path)
        if not path.exists():
            return False, f"File not found: {file_path}"

        # Auto-generate name from filename if not provided
        if not name:
            name = path.stem

        suffix = path.suffix.lower()

        # Route to appropriate extractor
        if suffix == '.pdf':
            return self._ingest_pdf(path, name)
        elif suffix in ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff'):
            return self._ingest_image(path, name)
        elif suffix in ('.txt', '.md', '.json', '.py', '.sh', '.conf'):
            return self._ingest_text(path, name)
        else:
            return False, f"Unsupported file type: {suffix}"

    def _ingest_pdf(self, path: Path, name: str) -> tuple[bool, str]:
        """Extract text from PDF and store it."""
        if not HAS_PYPDF:
            return False, "PDF support not installed. Run: pip install pypdf"

        try:
            reader = PdfReader(path)
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            if not text_parts:
                return False, "Could not extract text from PDF (might be scanned/image-based)"

            content = "\n\n---\n\n".join(text_parts)
            self.store_doc(name, content, doc_type='pdf')
            return True, f"Ingested PDF '{name}' ({len(reader.pages)} pages, {len(content)} chars)"

        except Exception as e:
            return False, f"Failed to read PDF: {e}"

    def _ingest_image(self, path: Path, name: str) -> tuple[bool, str]:
        """Extract text from image using OCR and store it."""
        if not HAS_OCR:
            return False, "OCR support not installed. Run: pip install pytesseract Pillow"

        try:
            image = Image.open(path)
            text = pytesseract.image_to_string(image)

            if not text.strip():
                return False, "No text detected in image"

            self.store_doc(name, text.strip(), doc_type='image')
            return True, f"Ingested image '{name}' ({len(text)} chars extracted)"

        except Exception as e:
            return False, f"Failed to process image: {e}"

    def _ingest_text(self, path: Path, name: str) -> tuple[bool, str]:
        """Read text file and store it."""
        try:
            content = path.read_text()
            self.store_doc(name, content, doc_type='text')
            return True, f"Ingested text file '{name}' ({len(content)} chars)"
        except Exception as e:
            return False, f"Failed to read file: {e}"

    def search_docs(self, query: str) -> list[dict]:
        """Search all documents for a query string."""
        results = []
        query_lower = query.lower()

        for doc_name in self.list_docs():
            doc = self.get_doc(doc_name)
            if doc and query_lower in doc.get('content', '').lower():
                # Find snippet around match
                content = doc['content']
                idx = content.lower().find(query_lower)
                start = max(0, idx - 100)
                end = min(len(content), idx + len(query) + 100)
                snippet = content[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."

                results.append({
                    'name': doc_name,
                    'type': doc.get('type', 'unknown'),
                    'snippet': snippet
                })

        return results

    # ── Alarm log methods ──────────────────────────────────────────────────────

    def add_alarm(self, alarm_type: str, scheduled_for: datetime,
                  duration_seconds: int | None, message: str,
                  systemd_unit: str | None = None) -> int:
        """Log a new alarm/timer. Returns the alarm ID."""
        alarm_id = len(self.alarms['alarms']) + 1
        entry = {
            'id': alarm_id,
            'type': alarm_type,               # 'alarm' or 'timer'
            'created_at': datetime.now().isoformat(),
            'scheduled_for': scheduled_for.isoformat(),
            'duration_seconds': duration_seconds,
            'message': message,
            'systemd_unit': systemd_unit,
            'status': 'scheduled',
            'cancelled_at': None,
        }
        self.alarms['alarms'].append(entry)
        self._save_json(config.ALARM_LOG_FILE, self.alarms)
        return alarm_id

    def update_alarm_unit(self, alarm_id: int, systemd_unit: str):
        """Set the systemd unit name for an alarm after it has been created."""
        for alarm in self.alarms['alarms']:
            if alarm['id'] == alarm_id:
                alarm['systemd_unit'] = systemd_unit
                self._save_json(config.ALARM_LOG_FILE, self.alarms)
                return

    def get_active_alarms(self) -> list[dict]:
        """Return all alarms with status='scheduled'."""
        return [a for a in self.alarms['alarms'] if a['status'] == 'scheduled']

    def mark_alarm_fired(self, alarm_id: int):
        """Mark an alarm as fired."""
        for alarm in self.alarms['alarms']:
            if alarm['id'] == alarm_id:
                alarm['status'] = 'fired'
                self._save_json(config.ALARM_LOG_FILE, self.alarms)
                return

    def cancel_alarm(self, alarm_id: int):
        """Mark an alarm as cancelled."""
        for alarm in self.alarms['alarms']:
            if alarm['id'] == alarm_id:
                alarm['status'] = 'cancelled'
                alarm['cancelled_at'] = datetime.now().isoformat()
                self._save_json(config.ALARM_LOG_FILE, self.alarms)
                return

    # ── Chat history log ──────────────────────────────────────────────────────

    def _ensure_chat_history(self):
        if not hasattr(self, '_chat_history'):
            self._chat_history = self._load_json(config.CHAT_HISTORY_FILE, {'messages': []})

    def log_chat(self, role: str, text: str):
        """Append a message to the persistent chat log. role = 'user' or 'alice'."""
        self._ensure_chat_history()
        self._chat_history['messages'].append({
            'ts': datetime.now().isoformat(),
            'role': role,
            'text': text,
        })
        self._save_json(config.CHAT_HISTORY_FILE, self._chat_history)

    def get_chat_history(self, limit: int = 20, date_str: str = None) -> list[dict]:
        """Return recent chat messages, newest last.

        If date_str is given (YYYY-MM-DD), filter to that day only.
        """
        self._ensure_chat_history()
        msgs = self._chat_history['messages']
        if date_str:
            msgs = [m for m in msgs if m['ts'].startswith(date_str)]
        return msgs[-limit:]

    def prune_old_chat(self, days_to_keep: int = None):
        """Remove messages older than days_to_keep from the log."""
        if days_to_keep is None:
            days_to_keep = config.CHAT_HISTORY_KEEP_DAYS
        self._ensure_chat_history()
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days_to_keep)).isoformat()
        before = len(self._chat_history['messages'])
        self._chat_history['messages'] = [
            m for m in self._chat_history['messages'] if m['ts'] >= cutoff
        ]
        if len(self._chat_history['messages']) < before:
            self._save_json(config.CHAT_HISTORY_FILE, self._chat_history)

    def reconcile_alarms(self) -> list[dict]:
        """Called on startup. Marks past-due scheduled alarms as fired.
        Returns list of future scheduled alarms that need rescheduling.
        """
        now = datetime.now()
        future = []
        changed = False
        for alarm in self.alarms['alarms']:
            if alarm['status'] != 'scheduled':
                continue
            try:
                scheduled = datetime.fromisoformat(alarm['scheduled_for'])
            except (ValueError, KeyError):
                continue
            if scheduled <= now:
                alarm['status'] = 'fired'
                changed = True
            else:
                future.append(alarm)
        if changed:
            self._save_json(config.ALARM_LOG_FILE, self.alarms)
        return future
