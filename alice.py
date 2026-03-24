"""Alice - The core assistant."""
import os
import threading
import re
from typing import Callable

from core.llm import LLM, HermesLLM
from core.tts import TTS
from core.stt import STT
from core.memory import Memory
from tools.base import ToolRegistry
from tools.teacher import TeacherSession


class Alice:
    """The main assistant that coordinates everything."""

    def __init__(self):
        import config as _cfg
        if getattr(_cfg, 'LLM_BACKEND', 'ollama') == 'hermes':
            self.llm = HermesLLM()
        else:
            self.llm = LLM()
        self.tts = TTS()
        self.stt = STT()
        self.memory = Memory()
        self.tools = ToolRegistry()
        self.teacher_session: TeacherSession | None = None  # set when in teacher mode

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
        # Teacher mode intercept — all messages go through teacher logic
        if self.teacher_session is not None:
            return self._process_teacher_message(text)

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

    # ─────────────────────────────────────────────
    # Teacher mode
    # ─────────────────────────────────────────────

    @property
    def is_teacher_mode(self) -> bool:
        return self.teacher_session is not None

    def start_lesson(self, lesson_info: dict) -> str:
        """Initialize teacher mode and return Alice's intro message.

        Called synchronously by the GUI after user picks a lesson.
        Returns the spoken/displayed intro text.
        """
        self.teacher_session = TeacherSession(lesson_info)
        session = self.teacher_session

        # Switch LLM to teacher persona
        self.llm.set_teacher_mode(session.build_teacher_system_prompt())

        # Generate intro via one-shot (not added to chat history)
        raw = self.llm.generate(session.build_intro_prompt(), temperature=0.5)
        _, intro = self._parse_thinking(raw)
        return intro

    def end_lesson(self, save: bool = True) -> str:
        """Exit teacher mode. Returns a brief farewell message."""
        if self.teacher_session and save:
            self.teacher_session.save_results()

        self.teacher_session = None
        self.llm.exit_teacher_mode()  # restores original prompt + clears history

        farewells = [
            "Back to normal mode. Good session.",
            "Teacher hat's off. What else do you need, babe?",
            "Lesson mode off. I'm back to being your regular assistant.",
        ]
        import random
        return random.choice(farewells)

    def get_lesson_section(self) -> str:
        """Generate Alice's presentation of the current lesson section.

        Called after the user says 'next'. Returns spoken/displayed text.
        """
        session = self.teacher_session
        if not session:
            return ""

        # Update system prompt to reflect new current section
        self.llm.set_teacher_mode(session.build_teacher_system_prompt())

        raw = self.llm.generate(session.build_section_prompt(), temperature=0.4)
        _, presentation = self._parse_thinking(raw)
        return presentation

    def _process_teacher_message(self, text: str) -> dict:
        """Handle all messages when in teacher mode."""
        session = self.teacher_session

        # ── Quiz phase ──
        if session.phase == 'quiz':
            return self._handle_quiz_answer(text)

        # ── Step-by-step mode (inside a hands-on section) ──
        if session.in_step_mode:
            if session.is_advance_command(text):
                if session.is_last_step():
                    # All steps in this section done
                    session.exit_step_mode()
                    if session.is_last_section():
                        # Move to quiz
                        session.phase = 'quiz'
                        raw = self.llm.generate(session.build_quiz_start_prompt(), temperature=0.4)
                        _, response = self._parse_thinking(raw)
                    else:
                        response = (
                            "Nice work — that's all the steps for this section. "
                            "Say 'next' whenever you're ready to move on."
                        )
                else:
                    session.advance_step()
                    self.llm.set_teacher_mode(session.build_teacher_system_prompt())
                    raw = self.llm.generate(session.build_step_prompt(), temperature=0.4)
                    _, response = self._parse_thinking(raw)
                return {'thinking': '', 'response': response}
            else:
                # Question during a step — use step-specific prompt
                session.record_question(text)
                response = self._teacher_answer_step_question(text)
                return {'thinking': '', 'response': response}

        # ── Normal section advance ──
        if session.is_advance_command(text) and session.phase in ('intro', 'teaching'):
            if session.phase == 'intro':
                # First "next/ready" after the intro — present section 1 without advancing
                session.phase = 'teaching'
                self.llm.set_teacher_mode(session.build_teacher_system_prompt())
                if session.current_section and session.current_section.is_hands_on():
                    session.enter_step_mode()
                    raw = self.llm.generate(session.build_step_intro_prompt(), temperature=0.4)
                else:
                    raw = self.llm.generate(session.build_section_prompt(), temperature=0.4)
                _, response = self._parse_thinking(raw)
            elif session.is_last_section():
                session.phase = 'quiz'
                raw = self.llm.generate(session.build_quiz_start_prompt(), temperature=0.4)
                _, response = self._parse_thinking(raw)
            else:
                session.advance()
                self.llm.set_teacher_mode(session.build_teacher_system_prompt())
                # If hands-on section → enter step mode
                if session.current_section and session.current_section.is_hands_on():
                    session.enter_step_mode()
                    raw = self.llm.generate(session.build_step_intro_prompt(), temperature=0.4)
                else:
                    raw = self.llm.generate(session.build_section_prompt(), temperature=0.4)
                _, response = self._parse_thinking(raw)
            return {'thinking': '', 'response': response}

        # ── Question during normal teaching ──
        session.record_question(text)
        response = self._teacher_answer_question(text)
        return {'thinking': '', 'response': response}

    def _teacher_answer_step_question(self, question: str) -> str:
        """Answer a question while Glenn is working through a hands-on step."""
        session = self.teacher_session

        prompt = session.build_step_question_prompt(question)
        raw = self.llm.generate(prompt, temperature=0.4)
        _, answer = self._parse_thinking(raw)

        if session.has_uncertainty(answer):
            web_results = self._teacher_web_search(question)
            if web_results:
                session.record_question(question, escalated=True)
                prompt2 = session.build_step_question_prompt(question, web_results=web_results)
                raw2 = self.llm.generate(prompt2, temperature=0.4)
                _, answer = self._parse_thinking(raw2)
                answer = f"[looked that up]\n{answer}"

        return answer

    def _teacher_answer_question(self, question: str) -> str:
        """Answer a student question with escalation: local LLM → web search → retry."""
        session = self.teacher_session

        # Try local LLM first
        prompt = session.build_question_prompt(question)
        raw = self.llm.generate(prompt, temperature=0.4)
        _, answer = self._parse_thinking(raw)

        # Check if LLM is uncertain → escalate to web search
        if session.has_uncertainty(answer):
            web_results = self._teacher_web_search(question)
            if web_results:
                session.record_question(question, escalated=True)
                prompt2 = session.build_question_prompt(question, web_results=web_results)
                raw2 = self.llm.generate(prompt2, temperature=0.4)
                _, answer = self._parse_thinking(raw2)
                # Prepend a note that we looked it up
                answer = f"[looked that up]\n{answer}"

        return answer

    def _teacher_web_search(self, query: str) -> str:
        """Run a web search and return results string, or empty string on failure."""
        try:
            from tools.websearch import WebSearchTool
            searcher = WebSearchTool()
            results = searcher.execute(f"search for {query}")
            if results and 'No results' not in results:
                return results[:1500]
        except Exception:
            pass
        return ''

    def _handle_quiz_answer(self, student_answer: str) -> dict:
        """Process a quiz answer, track score, and ask next question or wrap up."""
        session = self.teacher_session

        # Simple heuristic: treat the answer as "correct" if it's more than a few words
        # The LLM will do actual evaluation in its response
        is_probably_correct = len(student_answer.split()) >= 3

        session.increment_quiz(correct=is_probably_correct)

        if session.quiz_round >= 3:
            # Quiz done — wrap up
            raw = self.llm.generate(
                session.build_quiz_followup_prompt(student_answer), temperature=0.5
            )
            _, response = self._parse_thinking(raw)

            # Auto-save and exit teacher mode
            session.save_results(
                note=f"Quiz: {session.quiz_score}/3. Questions asked: {len(session.questions_asked)}."
            )
            session.phase = 'done'
            self.teacher_session = None
            self.llm.exit_teacher_mode()

            return {'thinking': '', 'response': response}
        else:
            # More questions
            raw = self.llm.generate(
                session.build_quiz_followup_prompt(student_answer), temperature=0.5
            )
            _, response = self._parse_thinking(raw)
            return {'thinking': '', 'response': response}

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

    # ─────────────────────────────────────────────
    # Uncensored mode — switch to local dolphin model
    # ─────────────────────────────────────────────

    @property
    def is_uncensored_mode(self) -> bool:
        """True if currently using the local uncensored model."""
        return hasattr(self, '_claude_llm') and self.llm is not self._claude_llm

    def switch_to_uncensored(self):
        """Switch from hermes/Claude to dolphin-llama3:8b with hermes memory injected."""
        import config as _config
        from core.llm import LLM
        self._claude_llm = self.llm
        ollama = LLM()
        memory_ctx = self._load_hermes_memory()
        if memory_ctx:
            ollama.system_prompt = _config.SYSTEM_PROMPT + "\n\n" + memory_ctx
        self.llm = ollama

    def switch_to_claude(self):
        """Switch back to hermes/Claude."""
        if hasattr(self, '_claude_llm'):
            self.llm = self._claude_llm

    def _load_hermes_memory(self) -> str:
        """Read hermes MEMORY.md and USER.md and return as context string."""
        from pathlib import Path
        parts = []
        for fname, label in [('MEMORY.md', 'Agent Memory'), ('USER.md', 'User Profile')]:
            path = Path.home() / '.hermes' / 'memories' / fname
            if path.exists():
                content = path.read_text().strip()
                if content:
                    parts.append(f"[{label}]\n{content}")
        return '\n\n'.join(parts)

    def preload(self):
        """Preload models for faster first response."""
        self.stt.preload()
        self.tts._get_model()  # warm up TTS so first speak() has no load delay

    # ─────────────────────────────────────────────
    # Hermes IPC — speak requests from external processes
    # ─────────────────────────────────────────────

    HERMES_SPEAK_FILE = "/tmp/alice_speak_request.txt"

    def start_hermes_listener(self):
        """Watch for speak requests from hermes. Call once after preload."""
        import time
        def _watch():
            while True:
                try:
                    if os.path.exists(self.HERMES_SPEAK_FILE):
                        with open(self.HERMES_SPEAK_FILE, 'r') as f:
                            text = f.read().strip()
                        os.remove(self.HERMES_SPEAK_FILE)
                        if text:
                            self.speak_async(text)
                except Exception:
                    pass
                time.sleep(0.3)
        threading.Thread(target=_watch, daemon=True).start()

    def start_lesson_async(self, lesson_info: dict, callback: Callable[[str], None]):
        """Start a lesson asynchronously. Callback receives the intro text."""
        def worker():
            try:
                intro = self.start_lesson(lesson_info)
                callback(intro)
            except Exception as e:
                callback(f"Failed to start lesson: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def end_lesson_async(self, callback: Callable[[str], None]):
        """End the lesson asynchronously. Callback receives farewell text."""
        def worker():
            try:
                msg = self.end_lesson()
                callback(msg)
            except Exception as e:
                callback(f"Error ending lesson: {e}")

        threading.Thread(target=worker, daemon=True).start()
