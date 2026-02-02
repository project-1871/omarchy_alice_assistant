"""Ollama LLM integration."""
import requests
import json
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
                'stream': False
            },
            timeout=60
        )
        response.raise_for_status()

        result = response.json()
        assistant_message = result['message']['content']
        self.history.append({'role': 'assistant', 'content': assistant_message})

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
                'stream': True
            },
            stream=True,
            timeout=60
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
