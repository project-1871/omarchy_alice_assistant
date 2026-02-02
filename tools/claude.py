"""Claude Code handoff tool."""
import subprocess
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.base import Tool


class ClaudeTool(Tool):
    """Hand off complex tasks to Claude Code."""

    name = "claude"
    description = "Hand off to Claude Code for complex coding tasks"
    triggers = [
        "hey claude", "ask claude", "claude code", "code this",
        "check this code", "review code", "build me", "create a tool",
        "write code", "debug this", "fix this code"
    ]

    def execute(self, query: str, **kwargs) -> str:
        query_lower = query.lower()

        # Extract the actual request
        request = query
        for prefix in self.triggers:
            if query_lower.startswith(prefix):
                request = query[len(prefix):].strip()
                break

        if not request:
            return "What would you like Claude to help with?"

        # Open Claude Code with the request
        # We'll use the terminal since Claude Code is a CLI tool
        try:
            # Option 1: Open in new terminal with the query
            terminal_cmd = [
                'ghostty', '-e', 'bash', '-c',
                f'cd ~ && claude "{request}"; exec bash'
            ]

            subprocess.Popen(
                terminal_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

            return f"Opening Claude Code. I've passed along your request: '{request[:50]}{'...' if len(request) > 50 else ''}'"

        except FileNotFoundError:
            # Try alternative terminals
            for term in ['kitty', 'alacritty', 'gnome-terminal']:
                try:
                    if term == 'gnome-terminal':
                        cmd = [term, '--', 'bash', '-c', f'cd ~ && claude "{request}"; exec bash']
                    else:
                        cmd = [term, '-e', 'bash', '-c', f'cd ~ && claude "{request}"; exec bash']

                    subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )
                    return f"Opening Claude Code in {term}."
                except FileNotFoundError:
                    continue

            return "Couldn't open a terminal. Make sure ghostty, kitty, or alacritty is installed."

    def can_handle(self, query: str) -> bool:
        """Override to also detect complex coding requests."""
        query_lower = query.lower()

        # Direct triggers
        if super().can_handle(query):
            return True

        # Complex coding patterns
        complex_patterns = [
            "write a function", "write a script", "create a class",
            "implement", "refactor", "optimize this",
            "what's wrong with this code", "debug"
        ]

        return any(p in query_lower for p in complex_patterns)
