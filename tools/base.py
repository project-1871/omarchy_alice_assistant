"""Base tool class and registry."""
from abc import ABC, abstractmethod
from typing import Any
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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
        query_lower = query.lower()
        return any(trigger in query_lower for trigger in self.triggers)


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

    def find_tool(self, query: str) -> Tool | None:
        """Find a tool that can handle the query."""
        for tool in self.tools.values():
            if tool.can_handle(query):
                return tool
        return None

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
