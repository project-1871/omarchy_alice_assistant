"""Clipboard awareness tool — read clipboard content via wl-clipboard."""
import subprocess
from tools.base import Tool


def get_clipboard() -> str:
    """Read clipboard contents via wl-paste. Returns empty string on failure."""
    try:
        result = subprocess.run(
            ['wl-paste', '--no-newline'],
            capture_output=True, text=True, timeout=3
        )
        return result.stdout if result.returncode == 0 else ''
    except Exception:
        return ''


class ClipboardTool(Tool):
    name = "clipboard"
    description = "Read clipboard content"
    triggers = [
        "what is in my clipboard", "what's in my clipboard",
        "read my clipboard", "read clipboard", "show clipboard",
        "what did i copy", "clipboard content", "show me my clipboard",
        "what is on my clipboard", "whats on my clipboard",
    ]

    def execute(self, query: str) -> str:
        content = get_clipboard().strip()
        if not content:
            return "Your clipboard is empty, babe."
        if len(content) <= 300:
            return f"Your clipboard says: {content}"
        return f"Clipboard has {len(content)} characters. Here's the start:\n{content[:300]}..."
