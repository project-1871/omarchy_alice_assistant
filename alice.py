"""Alice - The core assistant."""
import os
import subprocess
import threading
import re
from typing import Callable

from core.llm import LLM, HermesLLM
from core.tts import TTS
from core.stt import STT
from core.memory import Memory
from core.rag import RAGEngine
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
        self.active_profile: str = 'chill'
        self.profile_change_callback: Callable[[str], None] | None = None  # GUI hook
        self._load_and_apply_profile()

        # RAG — starts indexing in background, ready within ~10s on first run
        self.rag = RAGEngine(
            db_dir=getattr(_cfg, 'RAG_DB_DIR', ''),
            docs_dir=getattr(_cfg, 'RAG_DOCS_DIR', ''),
        )
        self.memory._rag = self.rag  # attach so new docs auto-index

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
        try:
            # Teacher mode intercept — all messages go through teacher logic
            if self.teacher_session is not None:
                result = self._process_teacher_message(text)
                self.memory.log_chat('user', text)
                self.memory.log_chat('alice', result.get('response', ''))
                return result

            # Update context
            self.memory.set_context('last_query', text)

            # Check for learning triggers ("remember that I...", "I prefer...")
            learning_response = self._check_learning(text)
            if learning_response:
                self.memory.log_chat('user', text)
                self.memory.log_chat('alice', learning_response)
                return {'thinking': '', 'response': learning_response, 'speak': True}

            # Profile switch ("work mode", "chill mode", etc.)
            profile_response = self._check_profile_switch(text)
            if profile_response:
                self.memory.log_chat('user', text)
                self.memory.log_chat('alice', profile_response)
                return {'thinking': '', 'response': profile_response, 'speak': True}

            # Chat history query
            history_response = self._check_history_query(text)
            if history_response is not None:
                self.memory.log_chat('user', text)
                self.memory.log_chat('alice', history_response)
                return {'thinking': '', 'response': history_response, 'speak': True}

            # Screen queries — take screenshot, inject path, bypass tool router → go straight to LLM
            screen_result = self._handle_screen_query(text)
            if screen_result is not None:
                if screen_result.startswith('__ERROR__:'):
                    err = screen_result[10:]
                    self.memory.log_chat('user', text)
                    self.memory.log_chat('alice', err)
                    return {'thinking': '', 'response': err, 'speak': True}
                # Bypass tool router — send directly to LLM with screenshot path
                context = self._build_context(text)
                raw_response = self.llm.chat(screen_result, context=context)
                thinking, answer = self._parse_thinking(raw_response)
                self.memory.log_chat('user', text)
                self.memory.log_chat('alice', answer)
                return {'thinking': thinking, 'response': answer}

            # Code review — get code from clipboard/file/git diff, send to LLM
            review_result = self._handle_code_review(text)
            if review_result is not None:
                if review_result.startswith('__ERROR__:'):
                    err = review_result[10:]
                    self.memory.log_chat('user', text)
                    self.memory.log_chat('alice', err)
                    return {'thinking': '', 'response': err, 'speak': True}
                context = self._build_context(text)
                raw_response = self.llm.chat(review_result, context=context)
                thinking, answer = self._parse_thinking(raw_response)
                self.memory.log_chat('user', text)
                self.memory.log_chat('alice', answer)
                return {'thinking': thinking, 'response': answer}

            # Clipboard queries — handled before tool router to avoid oshelp conflict
            clipboard_result = self._handle_clipboard_query(text)
            if clipboard_result is not None:
                if isinstance(clipboard_result, str):
                    # Direct response (read / empty clipboard)
                    self.memory.log_chat('user', text)
                    self.memory.log_chat('alice', clipboard_result)
                    return {'thinking': '', 'response': clipboard_result, 'speak': True}
                else:
                    # Rewritten query — fall through to LLM with new text
                    text = clipboard_result

            # Check if a tool can handle this directly
            tool_response, handled = self.tools.execute(text)
            if handled:
                self.memory.log_chat('user', text)
                self.memory.log_chat('alice', tool_response)
                return {'thinking': '', 'response': tool_response, 'speak': True}

            # Build context from memory for LLM (RAG injects relevant doc chunks)
            context = self._build_context(text)

            # Send to LLM with context
            raw_response = self.llm.chat(text, context=context)

            # Parse thinking from response
            thinking, answer = self._parse_thinking(raw_response)
            self.memory.log_chat('user', text)
            self.memory.log_chat('alice', answer)
            return {'thinking': thinking, 'response': answer}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'thinking': '', 'response': f"Something broke on my end: {e}"}

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

    def _check_history_query(self, text: str) -> str | None:
        """Return a chat history summary if the query asks for it, else None."""
        tl = text.lower()
        history_triggers = [
            "what did we talk about", "what did we discuss", "what have we talked about",
            "show history", "show chat history", "our conversation history",
            "what did i ask you", "what did i say", "remind me what we talked about",
        ]
        if not any(t in tl for t in history_triggers):
            return None

        # Check for a day reference
        from datetime import date, timedelta
        day_str = None
        if "yesterday" in tl:
            day_str = (date.today() - timedelta(days=1)).isoformat()
        elif "today" in tl:
            day_str = date.today().isoformat()

        msgs = self.memory.get_chat_history(limit=20, date_str=day_str)
        if not msgs:
            when = "yesterday" if day_str == (date.today() - timedelta(days=1)).isoformat() else "recently"
            return f"I've got nothing logged {when}, babe. Either we haven't chatted or the log is empty."

        lines = []
        for m in msgs:
            ts = m['ts'][:16].replace('T', ' ')  # YYYY-MM-DD HH:MM
            who = "You" if m['role'] == 'user' else "Me"
            lines.append(f"[{ts}] {who}: {m['text'][:120]}")

        label = f"on {day_str}" if day_str else "recently"
        return f"Here's what we talked about {label}:\n" + "\n".join(lines)

    _SCREEN_TRIGGERS = [
        "what's on my screen", "what is on my screen",
        "look at my screen", "look at the screen",
        "describe my screen", "describe the screen",
        "what do you see on my screen", "read my screen",
        "analyze my screen", "analyse my screen",
        "whats on screen", "what's on screen",
        "screenshot and", "look at this screen",
        "what's on the screen", "what is on the screen",
    ]

    def _handle_screen_query(self, text: str):
        """Take a screenshot and rewrite the query with the image path for hermes vision.

        Returns:
          - str starting with '__ERROR__:' if screenshot failed
          - rewritten query string to send to LLM
          - None if not a screen query
        """
        tl = text.lower()
        if not any(t in tl for t in self._SCREEN_TRIGGERS):
            return None

        from tools.screen import take_screenshot, compress_screenshot
        ok, result = take_screenshot()
        if not ok:
            return f"__ERROR__:Couldn't take a screenshot: {result}"

        path = compress_screenshot(result)

        # Strip the screen-trigger part, keep any extra instruction
        action = tl
        for t in self._SCREEN_TRIGGERS:
            action = action.replace(t, '').strip()
        action = action.strip(' ,.-')

        if action:
            return f"{action}: {path}"
        return f"Describe what you see on this screen: {path}"

    _CODE_REVIEW_TRIGGERS = [
        "review my code", "review this code", "review the code", "review code",
        "code review", "check my code", "what is wrong with my code",
        "what's wrong with my code", "review my changes", "review the diff",
        "review git diff", "review this diff", "review this file", "review the file",
        "review this script", "review this function", "look at my code",
    ]

    def _handle_code_review(self, text: str):
        """Fetch code and build a review prompt for the LLM.

        Returns:
          - str starting with '__ERROR__:' if no code could be fetched
          - review prompt string to send to LLM
          - None if not a code review request
        """
        tl = text.lower()
        if not any(t in tl for t in self._CODE_REVIEW_TRIGGERS):
            return None

        code = None
        source = None

        # Source: file path mentioned in query (any absolute or home-relative path with extension)
        import re as _re
        path_match = _re.search(r'(~?/[\w\./\-]+\.\w+)', text)
        if path_match:
            path = os.path.expanduser(path_match.group(1))
            try:
                with open(path) as f:
                    code = f.read().strip()
                source = f"`{os.path.basename(path)}`"
            except Exception as e:
                return f"__ERROR__:Couldn't read file {path}: {e}"

        # Source: git diff (if query mentions diff/changes/commits)
        if code is None and any(w in tl for w in ('diff', 'changes', 'git')):
            try:
                result = subprocess.run(
                    ['git', 'diff', 'HEAD'],
                    capture_output=True, text=True, timeout=10,
                    cwd=os.path.expanduser('~')
                )
                if result.returncode == 0 and result.stdout.strip():
                    code = result.stdout.strip()
                    source = "git diff HEAD"
                else:
                    # Try staged diff
                    result = subprocess.run(
                        ['git', 'diff', '--cached'],
                        capture_output=True, text=True, timeout=10,
                        cwd=os.path.expanduser('~')
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        code = result.stdout.strip()
                        source = "git staged diff"
            except Exception:
                pass

        # Source: clipboard (default)
        if code is None:
            try:
                from tools.clipboard import get_clipboard
                code = get_clipboard().strip()
                source = "clipboard"
            except Exception:
                pass

        if not code:
            return "__ERROR__:No code to review — clipboard is empty and no file path specified."

        # Truncate if too long
        MAX_CHARS = 8000
        truncated_note = ""
        if len(code) > MAX_CHARS:
            code = code[:MAX_CHARS]
            truncated_note = "\n\n[truncated to 8000 chars]"

        prompt = (
            f"Code review request — source: {source}. Be direct and specific, no padding.\n\n"
            f"Check for:\n"
            f"- Bugs or logic errors\n"
            f"- Security vulnerabilities\n"
            f"- Code quality / readability issues\n"
            f"- Concrete improvement suggestions\n\n"
            f"Code:\n```\n{code}\n```{truncated_note}"
        )
        return prompt

    _CLIPBOARD_READ_TRIGGERS = [
        "what is in my clipboard", "what's in my clipboard", "read my clipboard",
        "read clipboard", "show clipboard", "what did i copy", "clipboard content",
        "show me my clipboard", "what is on my clipboard", "whats on my clipboard",
    ]
    _CLIPBOARD_ACTION_TRIGGERS = [
        "summarize", "summarise", "explain", "translate",
        "search for", "look up", "fix", "correct", "rewrite", "improve",
    ]

    def _handle_clipboard_query(self, text: str):
        """Handle clipboard queries before the tool router.

        Returns:
          - str: a direct response to send immediately (read or empty clipboard)
          - str (rewritten): a new query with clipboard content injected (for LLM)
          - None: not a clipboard query, fall through normally
        """
        tl = text.lower()
        if 'clipboard' not in tl:
            return None

        try:
            from tools.clipboard import get_clipboard
            content = get_clipboard().strip()
        except Exception:
            return None

        # Read queries → direct response
        from tools.base import _expand_contractions
        tl_exp = _expand_contractions(tl)
        if any(_expand_contractions(t) in tl_exp for t in self._CLIPBOARD_READ_TRIGGERS):
            if not content:
                return "Your clipboard is empty, babe."
            if len(content) <= 300:
                return f"Your clipboard says: {content}"
            return f"Clipboard has {len(content)} characters. Here's the start:\n{content[:300]}..."

        # Action queries → rewrite for LLM
        if any(a in tl for a in self._CLIPBOARD_ACTION_TRIGGERS):
            if not content:
                return "Your clipboard is empty — nothing to act on."
            action = tl.replace('clipboard', '').replace(' my ', ' ').strip().rstrip(':').strip()
            return f"{action}:\n\n{content}"  # rewritten query (not a direct response)

        return None

    # ─────────────────────────────────────────────
    # Session profiles — work / chill
    # ─────────────────────────────────────────────

    def _load_and_apply_profile(self):
        """On startup, restore the last active profile from context.json."""
        saved = self.memory.get_context('active_profile', 'chill')
        import config as _cfg
        if saved in _cfg.PROFILES:
            self._apply_profile(saved, persist=False)

    def _apply_profile(self, name: str, persist: bool = True):
        """Swap system prompt + temperature for the given profile name."""
        import config as _cfg
        profile = _cfg.PROFILES.get(name)
        if not profile:
            return
        self.active_profile = name
        self.llm.switch_profile(profile)
        if persist:
            self.memory.set_context('active_profile', name)
        if self.profile_change_callback:
            self.profile_change_callback(name)

    def switch_profile(self, name: str) -> str:
        """Switch to named profile. Returns a confirmation message."""
        import config as _cfg
        if name not in _cfg.PROFILES:
            return f"Unknown profile: {name}"
        if name == self.active_profile:
            return f"Already in {_cfg.PROFILES[name]['display']} mode."
        self._apply_profile(name)
        if name == 'work':
            return "Switching to work mode. Less bullshit, more doing."
        else:
            return "Back to chill mode. Let's have some fun."

    def _check_profile_switch(self, text: str) -> str | None:
        """Detect voice commands to switch profiles. Returns response or None."""
        t = text.lower().strip()
        work_triggers = ['work mode', 'focus mode', 'switch to work', 'go to work mode',
                         'work profile', 'focus profile', 'be professional', 'get serious']
        chill_triggers = ['chill mode', 'relax mode', 'switch to chill', 'go to chill mode',
                          'chill profile', 'relax profile', 'be yourself', 'normal mode']
        if any(tr in t for tr in work_triggers):
            return self.switch_profile('work')
        if any(tr in t for tr in chill_triggers):
            return self.switch_profile('chill')
        return None

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

    def _build_context(self, query: str = "") -> str:
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

        # RAG: inject semantically relevant doc chunks for this query
        if query and hasattr(self, 'rag') and self.rag.is_ready:
            rag_context = self.rag.format_context(query, n=4)
            if rag_context:
                parts.append(rag_context)

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
        self.start_calendar_watcher()
        self._reschedule_alarms()
        self._start_alarm_fired_watcher()
        self._restore_chat_context()
        self.memory.prune_old_chat()

    def _restore_chat_context(self):
        """Inject the last N chat messages into the LLM history so Alice has context continuity."""
        import config as _cfg
        n = getattr(_cfg, 'CHAT_HISTORY_CONTEXT_LINES', 10)
        msgs = self.memory.get_chat_history(limit=n)
        if not msgs:
            return
        for m in msgs:
            role = 'user' if m['role'] == 'user' else 'assistant'
            self.llm.inject_history(role, m['text'])

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

    # ─────────────────────────────────────────────
    # Proactive calendar reminders
    # ─────────────────────────────────────────────

    _NOTIFIED_EVENTS_FILE = os.path.join(os.path.dirname(__file__), 'memory', 'notified_events.json')
    _REMINDER_WINDOW_MIN = 15   # speak reminder this many minutes before event
    _REMINDER_TOLERANCE_MIN = 2  # fire if within [window - tolerance, window + tolerance] minutes

    def _load_notified_events(self) -> set:
        """Load set of already-notified event keys from disk."""
        import json
        try:
            if os.path.exists(self._NOTIFIED_EVENTS_FILE):
                with open(self._NOTIFIED_EVENTS_FILE, 'r') as f:
                    return set(json.load(f))
        except Exception:
            pass
        return set()

    def _save_notified_events(self, notified: set):
        """Persist notified event keys, pruning old entries (keep last 200)."""
        import json
        try:
            pruned = list(notified)[-200:]
            with open(self._NOTIFIED_EVENTS_FILE, 'w') as f:
                json.dump(pruned, f)
        except Exception:
            pass

    def _get_upcoming_events(self, window_start_min: float, window_end_min: float) -> list[tuple[str, str]]:
        """Return list of (event_key, description) for timed events starting within the given minute window.

        Reads ~/.local/share/calcurse/apts directly.
        Timed event line format: MM/DD/YYYY @ HH:MM -> MM/DD/YYYY @ HH:MM |Description
        """
        from datetime import datetime
        import re
        apts_file = os.path.expanduser('~/.local/share/calcurse/apts')
        if not os.path.exists(apts_file):
            return []

        now = datetime.now()
        results = []
        try:
            with open(apts_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Only match timed events (contain @ HH:MM ->)
                    m = re.match(
                        r'(\d{2}/\d{2}/\d{4})\s+@\s+(\d{2}:\d{2})\s+->\s+\S.*?\|(.+)',
                        line
                    )
                    if not m:
                        continue
                    date_str, time_str, desc = m.group(1), m.group(2), m.group(3).strip()
                    if desc.startswith('YEARLY:'):
                        desc = desc[7:]
                    try:
                        event_dt = datetime.strptime(f"{date_str} {time_str}", "%m/%d/%Y %H:%M")
                    except ValueError:
                        continue
                    minutes_until = (event_dt - now).total_seconds() / 60.0
                    if window_start_min <= minutes_until <= window_end_min:
                        key = f"{date_str}@{time_str}:{desc}"
                        results.append((key, desc, int(minutes_until)))
        except Exception:
            pass
        return results

    def start_calendar_watcher(self):
        """Watch calcurse for upcoming events and speak proactive reminders.

        Runs a background daemon thread that polls every 60 seconds.
        Fires a spoken reminder when a timed event is ~15 minutes away.
        Each event is only announced once (tracked in memory/notified_events.json).
        """
        import time
        notified = self._load_notified_events()

        def _watch():
            nonlocal notified
            while True:
                try:
                    low = self._REMINDER_WINDOW_MIN - self._REMINDER_TOLERANCE_MIN
                    high = self._REMINDER_WINDOW_MIN + self._REMINDER_TOLERANCE_MIN
                    upcoming = self._get_upcoming_events(low, high)
                    for key, desc, mins in upcoming:
                        if key not in notified:
                            notified.add(key)
                            self._save_notified_events(notified)
                            self.speak_async(f"Hey, heads up — {desc} in about {mins} minutes.")
                except Exception:
                    pass
                time.sleep(60)

        threading.Thread(target=_watch, daemon=True).start()

    # ─────────────────────────────────────────────
    # Alarm persistence — reschedule + fired watcher
    # ─────────────────────────────────────────────

    def _reschedule_alarms(self):
        """On startup: mark past-due alarms as fired, reschedule future ones via systemd-run."""
        import re as _re
        from datetime import datetime as _dt
        try:
            future_alarms = self.memory.reconcile_alarms()
        except Exception:
            return

        for alarm in future_alarms:
            try:
                scheduled = _dt.fromisoformat(alarm['scheduled_for'])
                seconds_remaining = int((scheduled - _dt.now()).total_seconds())
                if seconds_remaining <= 0:
                    self.memory.mark_alarm_fired(alarm['id'])
                    continue

                alarm_id = alarm['id']
                message = alarm.get('message', 'Alarm!')
                marker_cmd = f'echo {alarm_id} > /tmp/alice_alarm_fired_{alarm_id}'
                notify_cmd = (
                    f'notify-send "Alice" "{message}" && '
                    f'paplay /usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga 2>/dev/null; '
                    f'{marker_cmd}'
                )
                result = subprocess.run(
                    ['systemd-run', '--user', f'--on-active={seconds_remaining}',
                     'bash', '-c', notify_cmd],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    unit_match = _re.search(r'Running as unit:\s*(\S+)', result.stderr)
                    new_unit = unit_match.group(1) if unit_match else 'unknown'
                    self.memory.update_alarm_unit(alarm_id, new_unit)
            except Exception:
                pass

    def _start_alarm_fired_watcher(self):
        """Background thread: watch for /tmp/alice_alarm_fired_<id> files, mark alarms fired."""
        import time, glob as _glob
        def _watch():
            while True:
                try:
                    for path in _glob.glob('/tmp/alice_alarm_fired_*'):
                        try:
                            alarm_id = int(os.path.basename(path).replace('alice_alarm_fired_', ''))
                            self.memory.mark_alarm_fired(alarm_id)
                            os.remove(path)
                        except Exception:
                            pass
                except Exception:
                    pass
                time.sleep(5)
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
