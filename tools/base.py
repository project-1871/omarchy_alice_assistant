"""Base tool class and registry."""
from abc import ABC, abstractmethod
from typing import Any
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_CONTRACTIONS = {
    "what's": "what is",
    "who's": "who is",
    "where's": "where is",
    "when's": "when is",
    "how's": "how is",
    "it's": "it is",
    "that's": "that is",
    "there's": "there is",
    "here's": "here is",
    "what're": "what are",
    "they're": "they are",
    "we're": "we are",
    "you're": "you are",
    "what'll": "what will",
    "i'll": "i will",
    "he'll": "he will",
    "she'll": "she will",
    "it'll": "it will",
    "they'll": "they will",
    "we'll": "we will",
    "you'll": "you will",
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "can't": "cannot",
    "won't": "will not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "weren't": "were not",
    "couldn't": "could not",
    "wouldn't": "would not",
    "shouldn't": "should not",
    "i'm": "i am",
    "i've": "i have",
    "i'd": "i would",
    "they've": "they have",
    "we've": "we have",
    "you've": "you have",
    "he'd": "he would",
    "she'd": "she would",
    "they'd": "they would",
    "we'd": "we would",
    "you'd": "you would",
    "let's": "let us",
}


def _expand_contractions(text: str) -> str:
    """Expand common English contractions for consistent matching."""
    for contraction, expanded in _CONTRACTIONS.items():
        text = text.replace(contraction, expanded)
    return text


class Tool(ABC):
    """Base class for all Alice tools."""

    name: str = "base"
    description: str = "Base tool"
    triggers: list[str] = []  # Keywords that trigger this tool

    @abstractmethod
    def execute(self, query: str, **kwargs) -> str:
        """Execute the tool and return a response."""
        pass

    def can_handle(self, query: str) -> bool:
        """Check if this tool can handle the query."""
        query_normalized = _expand_contractions(query.lower())
        return any(
            _expand_contractions(trigger) in query_normalized
            for trigger in self.triggers
        )


class ToolRegistry:
    """Auto-discovers and manages tools."""

    def __init__(self):
        self.tools: dict[str, Tool] = {}
        self._discover_tools()

    def _discover_tools(self):
        """Auto-discover tools in the tools directory."""
        tools_dir = os.path.dirname(os.path.abspath(__file__))

        for filename in os.listdir(tools_dir):
            if filename.endswith('.py') and filename not in ('__init__.py', 'base.py'):
                module_name = filename[:-3]
                try:
                    module = importlib.import_module(f'tools.{module_name}')
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and
                            issubclass(attr, Tool) and
                            attr is not Tool):
                            tool_instance = attr()
                            self.tools[tool_instance.name] = tool_instance
                except Exception as e:
                    print(f"Failed to load tool {module_name}: {e}")

    def get_tool(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self.tools.get(name)

    def _best_trigger_score(self, tool: 'Tool', query_normalized: str, query_original: str) -> tuple:
        """Return (longest_trigger_len, original_bonus) for the best matching trigger."""
        best = (0, 0)
        for trigger in tool.triggers:
            t_norm = _expand_contractions(trigger)
            if t_norm in query_normalized:
                score = (len(t_norm), 1 if trigger in query_original else 0)
                if score > best:
                    best = score
        return best

    def find_tool(self, query: str) -> Tool | None:
        """Find the most specific tool that can handle the query.

        1. All tools are asked via can_handle() (respects custom overrides).
        2. Websearch is treated as a generic fallback: if any non-websearch tool
           also matches, prefer that.
        3. Among same-tier candidates, pick by longest matching trigger then
           original-query bonus.
        """
        candidates = [t for t in self.tools.values() if t.can_handle(query)]
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        query_normalized = _expand_contractions(query.lower())
        query_original = query.lower()

        # Prefer specific tools over websearch (generic fallback)
        specific = [t for t in candidates if t.name != 'websearch']
        pool = specific if specific else candidates

        return max(pool, key=lambda t: self._best_trigger_score(t, query_normalized, query_original))

    def list_tools(self) -> list[str]:
        """List all available tools."""
        return list(self.tools.keys())

    def reload_tools(self):
        """Re-discover tools (call after adding new tool files)."""
        # Clear cached modules
        tools_to_remove = [key for key in sys.modules.keys() if key.startswith('tools.') and key != 'tools.base']
        for key in tools_to_remove:
            del sys.modules[key]

        # Re-discover
        self.tools = {}
        self._discover_tools()
        return list(self.tools.keys())

    def execute(self, query: str) -> tuple[str, bool]:
        """Find and execute a tool for the query.

        Returns:
            Tuple of (response, was_handled).
        """
        tool = self.find_tool(query)
        if tool:
            result = tool.execute(query)
            return result, True
        return "", False
