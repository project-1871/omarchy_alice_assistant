#!/usr/bin/env python3
"""CLI entry point for Alice tools.

Allows any Alice tool to be invoked from the command line:
    python tools/cli.py "what is on my calendar today"
    python tools/cli.py "add dentist appointment Thursday 3pm"
    python tools/cli.py "play some music"

This is the single source of truth for tool logic. Scripts and integrations
that run on the host (cron jobs, shell aliases, etc.) should call this
instead of reimplementing tool behaviour.

NOTE: This requires the Alice venv to be active:
    cd ~/alice-assistant && source venv/bin/activate && python tools/cli.py "QUERY"
"""
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.base import ToolRegistry


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/cli.py \"your query here\"")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    registry = ToolRegistry()
    tool = registry.find_tool(query)

    if tool:
        result = tool.execute(query)
        print(result)
    else:
        print(f"No tool matched query: {query!r}")
        sys.exit(1)


if __name__ == "__main__":
    main()
