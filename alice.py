"""Alice - The core assistant."""
import threading
import re
from typing import Callable

from core.llm import LLM
from core.tts import TTS
from core.stt import STT
from core.memory import Memory
from tools.base import ToolRegistry


class Alice:
    """The main assistant that coordinates everything."""

    def __init__(self):
        self.llm = LLM()
        self.tts = TTS()
        self.stt = STT()
        self.memory = Memory()
        self.tools = ToolRegistry()

    def _parse_thinking(self, response: str) -> tuple[str, str]:
        """Parse thinking tags from response. Returns (thinking, answer)."""
        thinking = ""
        answer = response

        # Try multiple tag formats for thinking
        for tag in ['thinking', 'think', 'thought']:
            pattern = rf'<{tag}>(.*?)</{tag}>'
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                thinking = match.group(1).strip()
                answer = re.sub(pattern, '', response, flags=re.DOTALL | re.IGNORECASE).strip()
                break

        # Clean up common extra tags from answer
        for tag in ['answer', 'response', 'reasoning', 'reason']:
            answer = re.sub(rf'</?{tag}>', '', answer, flags=re.IGNORECASE)

        answer = answer.strip()

        # If model put everything in thinking and left answer empty, use thinking as answer
        if thinking and not answer:
            answer = thinking
            thinking = ""

        return thinking, answer

    def process(self, text: str) -> dict:
        """Process a user message and return a response dict with 'thinking' and 'response'."""
        # Update context
        self.memory.set_context('last_query', text)

        # Check for learning triggers ("remember that I...", "I prefer...")
        learning_response = self._check_learning(text)
        if learning_response:
            return {'thinking': '', 'response': learning_response}

        # Check if a tool can handle this directly
        tool_response, handled = self.tools.execute(text)
        if handled:
            return {'thinking': '', 'response': tool_response}

        # Build context from memory for LLM
        context = self._build_context()

        # Send to LLM with context
        raw_response = self.llm.chat(text, context=context)

        # Parse thinking from response
        thinking, answer = self._parse_thinking(raw_response)
        return {'thinking': thinking, 'response': answer}

    def _check_learning(self, text: str) -> str | None:
        """Check if user is teaching Alice something or triggering special commands."""
        text_lower = text.lower()

        # Reload tools command
        if "reload tools" in text_lower or "refresh tools" in text_lower:
            tools = self.tools.reload_tools()
            return f"Reloaded tools. Available: {', '.join(tools)}"

        # "Remember that I..." or "I prefer..." patterns
        if any(text_lower.startswith(p) for p in ["remember that", "remember i", "note that i", "i prefer", "i like", "i don't like", "i always", "i never"]):
            # Extract the preference/fact
            for prefix in ["remember that ", "remember i ", "note that i ", "note that "]:
                if text_lower.startswith(prefix):
                    fact = text[len(prefix):]
                    break
            else:
                fact = text

            # Store as a learned preference
            self.memory.add_skill(
                name="user_preference",
                description=fact
            )
            return f"Got it, I'll remember that."

        # "My name is..." or "Call me..."
        if "my name is" in text_lower or "call me" in text_lower:
            import re
            match = re.search(r'(?:my name is|call me)\s+(\w+)', text, re.IGNORECASE)
            if match:
                name = match.group(1)
                self.memory.set_context('user_name', name)
                return f"Nice to meet you, {name}. I'll remember that."

        return None

    def _build_context(self) -> str:
        """Build context string from memory for LLM."""
        parts = []

        # Add user name if known
        user_name = self.memory.get_context('user_name')
        if user_name:
            parts.append(f"User's name: {user_name}")

        # Add current project if set
        project = self.memory.get_context('current_project')
        if project:
            parts.append(f"Currently working on: {project}")

        # Add learned preferences (last 10)
        skills = self.memory.get_skills()
        preferences = [s for s in skills if s.get('name') == 'user_preference'][-10:]
        if preferences:
            prefs_text = "\n".join([f"- {p['description']}" for p in preferences])
            parts.append(f"User preferences:\n{prefs_text}")

        # Add permanent knowledge
        knowledge_summary = self.memory.get_knowledge_summary()
        if knowledge_summary:
            parts.append(knowledge_summary)

        # Add session documents (temporary reference material)
        session_context = self.memory.get_session_context()
        if session_context:
            parts.append(session_context)

        if parts:
            return "Context:\n" + "\n".join(parts)
        return ""

    # Methods for GUI to load documents
    def load_session_document(self, file_path: str, name: str = None) -> tuple[bool, str]:
        """Load a document into temporary session memory."""
        return self.memory.load_session_doc(file_path, name)

    def unload_session_document(self, name: str) -> bool:
        """Unload a document from session memory."""
        return self.memory.unload_session_doc(name)

    def get_session_documents(self) -> dict:
        """Get all loaded session documents."""
        return self.memory.get_session_docs()

    def add_knowledge(self, title: str, content: str, category: str = 'general'):
        """Add a permanent knowledge entry."""
        return self.memory.add_knowledge(title, content, category)

    def get_knowledge(self, category: str = None) -> list:
        """Get permanent knowledge entries."""
        return self.memory.get_knowledge(category)

    def process_async(self, text: str, callback: Callable[[dict], None]):
        """Process asynchronously."""
        def worker():
            try:
                response = self.process(text)
                callback(response)
            except Exception as e:
                callback({'thinking': '', 'response': f"Error: {e}"})

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def transcribe(self, audio_file: str) -> str:
        """Transcribe an audio file."""
        return self.stt.transcribe(audio_file)

    def transcribe_async(self, audio_file: str, callback: Callable[[str], None]):
        """Transcribe asynchronously."""
        def worker():
            try:
                text = self.transcribe(audio_file)
                callback(text)
            except Exception as e:
                callback(f"[Error: {e}]")

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def speak(self, text: str) -> bool:
        """Speak text using TTS."""
        return self.tts.speak_raw(text)

    def speak_async(self, text: str, callback: Callable[[bool], None] = None):
        """Speak asynchronously."""
        def worker():
            success = self.speak(text)
            if callback:
                callback(success)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def clear_history(self):
        """Clear conversation history."""
        self.llm.clear_history()

    def preload(self):
        """Preload models for faster first response."""
        self.stt.preload()
