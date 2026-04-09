"""LLM backends: Ollama (local) and Hermes (Claude via hermes-agent subprocess)."""
import requests
import json
import os
import subprocess
from typing import Generator
import sys
sys.path.insert(0, '..')
import config


class LLM:
    """Ollama-based language model interface."""

    def __init__(self, model: str = None, full: bool = False):
        if model:
            self.model = model
        elif full:
            self.model = config.OLLAMA_MODEL_FULL
        else:
            self.model = config.OLLAMA_MODEL

        self.host = config.OLLAMA_HOST
        self.history = []
        self.system_prompt = config.SYSTEM_PROMPT

    def chat(self, message: str, context: str = None) -> str:
        """Send a message and get a response (blocking)."""
        self.history.append({'role': 'user', 'content': message})

        # Build system prompt with optional context
        system = self.system_prompt
        if context:
            system = f"{self.system_prompt}\n\n{context}"

        response = requests.post(
            f'{self.host}/api/chat',
            json={
                'model': self.model,
                'messages': [
                    {'role': 'system', 'content': system},
                    *self.history
                ],
                'stream': False,
                'options': {
                    'temperature': config.OLLAMA_TEMPERATURE,
                    'repeat_penalty': config.OLLAMA_REPEAT_PENALTY,
                }
            },
            timeout=(10, 300)
        )
        response.raise_for_status()

        result = response.json()
        assistant_message = result['message']['content']
        self.history.append({'role': 'assistant', 'content': assistant_message})

        # Keep history from growing too large (last 20 exchanges)
        if len(self.history) > 40:
            self.history = self.history[-40:]

        return assistant_message

    def chat_stream(self, message: str) -> Generator[str, None, None]:
        """Send a message and stream the response."""
        self.history.append({'role': 'user', 'content': message})

        response = requests.post(
            f'{self.host}/api/chat',
            json={
                'model': self.model,
                'messages': [
                    {'role': 'system', 'content': self.system_prompt},
                    *self.history
                ],
                'stream': True,
                'options': {
                    'temperature': config.OLLAMA_TEMPERATURE,
                    'repeat_penalty': config.OLLAMA_REPEAT_PENALTY,
                }
            },
            stream=True,
            timeout=(10, 300)
        )
        response.raise_for_status()

        full_response = []
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                if 'message' in chunk and 'content' in chunk['message']:
                    content = chunk['message']['content']
                    full_response.append(content)
                    yield content

        self.history.append({'role': 'assistant', 'content': ''.join(full_response)})

    def clear_history(self):
        """Clear conversation history."""
        self.history = []

    def set_model(self, model: str):
        """Switch to a different model."""
        self.model = model

    def generate(self, prompt: str, temperature: float = None) -> str:
        """One-shot generation — does NOT add to conversation history.

        Used for: lesson intros, section presentations, quiz generation.
        """
        temp = temperature if temperature is not None else config.OLLAMA_TEMPERATURE
        response = requests.post(
            f'{self.host}/api/chat',
            json={
                'model': self.model,
                'messages': [
                    {'role': 'system', 'content': self.system_prompt},
                    {'role': 'user', 'content': prompt},
                ],
                'stream': False,
                'options': {
                    'temperature': temp,
                    'repeat_penalty': config.OLLAMA_REPEAT_PENALTY,
                }
            },
            timeout=(10, 300)
        )
        response.raise_for_status()
        return response.json()['message']['content']

    def switch_profile(self, profile: dict):
        """Swap personality profile (work / chill). Saves original so teacher mode restore still works."""
        self.system_prompt = profile['system_prompt']
        config.OLLAMA_TEMPERATURE = profile['temperature']

    def set_teacher_mode(self, teacher_system_prompt: str):
        """Switch to teacher mode by replacing the system prompt.

        Saves the original so it can be restored with exit_teacher_mode().
        """
        self._original_system_prompt = self.system_prompt
        self._original_temperature = config.OLLAMA_TEMPERATURE
        self.system_prompt = teacher_system_prompt
        # Teacher mode uses lower temperature for more reliable answers
        config.OLLAMA_TEMPERATURE = 0.4

    def inject_history(self, role: str, text: str):
        """Prepend a message to history (used to restore context from persistent log on startup)."""
        self.history.append({'role': role, 'content': text})
        if len(self.history) > 40:
            self.history = self.history[-40:]

    def exit_teacher_mode(self):
        """Restore normal system prompt and temperature."""
        if hasattr(self, '_original_system_prompt'):
            self.system_prompt = self._original_system_prompt
        if hasattr(self, '_original_temperature'):
            config.OLLAMA_TEMPERATURE = self._original_temperature
        self.clear_history()


class HermesLLM:
    """hermes-agent backend — delegates to `hermes chat` subprocess using Claude."""

    handles_tts = True  # hermes speaks via alice-voice plugin; GUI must skip speak_async

    _CMD = os.path.expanduser("~/.local/share/mise/installs/python/3.14.2/bin/hermes")
    _NOISE_PREFIXES = ('  [', '  ┊', '↻ ', '⚠️', '❌', '⏳')

    def __init__(self):
        self.session_id: str | None = None  # set after first message; in-memory only
        self._teacher_prompt: str | None = None
        self.activity_callback = None  # set by GUI to stream tool/status lines in real-time
        self.active_profile: str = 'chill'  # 'chill' or 'work'

    # ── subprocess execution ─────────────────────────────────────────────────

    def _save_session(self, session_id: str):
        self.session_id = session_id

    def _run(self, message: str, new_session: bool = False) -> str:
        """Run hermes chat and return parsed response text.

        Streams stdout line-by-line. Activity lines (tool calls, status) are
        forwarded to self.activity_callback as they arrive so the GUI can
        display them in real-time.
        """
        if new_session or not self.session_id:
            cmd = [self._CMD, "chat", "-Q", "-q", message]
        else:
            cmd = [self._CMD, "chat", "--resume", self.session_id, "-Q", "-q", message]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Couldn't start hermes: {e}"

        lines = []
        try:
            for raw in proc.stdout:
                line = raw.rstrip('\n')
                lines.append(line)
                if self.activity_callback and any(line.startswith(p) for p in self._NOISE_PREFIXES):
                    self.activity_callback(line)
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            return "Sorry babe, hermes timed out. Try again."
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Hermes connection dropped: {e}"

        return self._parse('\n'.join(lines), save_session=not new_session)

    def _parse(self, output: str, save_session: bool = True) -> str:
        """Extract the final response text and session_id from hermes -Q output.

        hermes output structure (with -Q):
            [optional pre-speak text: "  ┊ 💬 ..."]
            [tool display lines:  "  [tool] ..." / "  [done] ..."]
            FINAL RESPONSE TEXT          ← what we want
            (blank line)
            session_id: XXXX
        """
        lines = output.split('\n')

        # 1. Find session_id line and save it
        session_id_idx = None
        for i, line in enumerate(lines):
            if line.startswith('session_id:'):
                session_id_idx = i
                if save_session:
                    sid = line.split(':', 1)[1].strip()
                    if sid:
                        self._save_session(sid)
                break

        # 2. Find the last tool-display / noise line
        noise_prefixes = ('  [', '  ┊', '↻ ', '⚠️', '❌', '⏳')
        last_tool = -1
        for i, line in enumerate(lines):
            if any(line.startswith(p) for p in noise_prefixes):
                last_tool = i

        # 3. Response = lines between last tool line and session_id line
        end = session_id_idx if session_id_idx is not None else len(lines)
        response_lines = lines[last_tool + 1:end]
        return '\n'.join(response_lines).strip()

    # ── LLM interface (mirrors core/llm.py LLM) ─────────────────────────────

    def switch_profile(self, profile: dict):
        """Set active personality profile. Work mode prepends a focus hint to each message."""
        self.active_profile = profile['label']

    def chat(self, message: str, context: str = None) -> str:
        """Send a message and get a response. Context is ignored — hermes has its own memory."""
        if self.active_profile == 'work':
            message = f"[Work mode — be focused, concise, minimal banter] {message}"
        return self._run(message)

    def generate(self, prompt: str, temperature: float = None) -> str:
        """One-shot generation (teacher mode). Injects teacher context into the prompt."""
        if self._teacher_prompt:
            full = f"[System context for this task: {self._teacher_prompt}]\n\n{prompt}"
        else:
            full = prompt
        return self._run(full, new_session=True)

    def clear_history(self):
        """Start a fresh hermes session (teacher mode exit, etc.)."""
        self.session_id = None

    def set_teacher_mode(self, teacher_system_prompt: str):
        self._teacher_prompt = teacher_system_prompt

    def inject_history(self, role: str, text: str):
        """No-op — hermes manages its own persistent memory."""
        pass

    def exit_teacher_mode(self):
        self._teacher_prompt = None
        self.clear_history()
