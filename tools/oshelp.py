"""OS Help tool - search Omarchy and Hyprland documentation offline"""

import re
from tools.base import Tool
from core.memory import Memory


class OSHelpTool(Tool):
    name = "oshelp"
    description = "Search Omarchy and Hyprland documentation"
    triggers = [
        "omarchy", "hyprland", "hypr", "wayland", "waybar",
        "keybind", "hotkey", "shortcut", "workspace",
        "window", "monitor", "display", "screen",
        "theme", "wallpaper", "background",
        "terminal", "ghostty", "alacritty", "kitty",
        "walker", "launcher", "rofi",
        "notification", "mako",
        "idle", "lock", "hyprlock", "hypridle",
        "screenshot", "screen capture",
        "clipboard", "copy paste",
        "dotfile", "config file",
        "super key", "mod key"
    ]

    def __init__(self):
        self.memory = Memory()

    def execute(self, query: str, **kwargs) -> str:
        query_lower = query.lower()

        # Extract search terms
        search_terms = self._extract_search_terms(query_lower)

        if not search_terms:
            return self._general_help()

        # Search documents
        all_results = []
        for term in search_terms:
            results = self.memory.search_docs(term)
            all_results.extend(results)

        # Deduplicate by doc name
        seen = set()
        unique_results = []
        for r in all_results:
            if r['name'] not in seen:
                seen.add(r['name'])
                unique_results.append(r)

        if not unique_results:
            return f"I couldn't find anything about '{' '.join(search_terms)}' in the Omarchy or Hyprland docs."

        # Build response with relevant snippets
        response_parts = []

        # Get full content from top results for better context
        for result in unique_results[:3]:
            doc = self.memory.get_doc(result['name'])
            if doc:
                content = doc.get('content', '')
                # Find the most relevant section
                snippet = self._extract_relevant_section(content, search_terms)
                if snippet:
                    source = result['name'].replace('omarchy_', '').replace('hyprland_', '').replace('_', ' ').title()
                    response_parts.append(f"From {source}: {snippet}")

        if response_parts:
            return " ".join(response_parts)
        else:
            # Fallback to basic snippets
            snippets = [f"{r['name']}: {r['snippet']}" for r in unique_results[:2]]
            return " ".join(snippets)

    def _extract_search_terms(self, query: str) -> list[str]:
        """Extract meaningful search terms from query."""
        # Remove common question words
        stop_words = {
            'how', 'do', 'i', 'what', 'is', 'the', 'a', 'an', 'to', 'in',
            'can', 'you', 'me', 'tell', 'about', 'show', 'help', 'with',
            'please', 'where', 'when', 'why', 'which', 'does', 'are', 'my'
        }

        words = query.split()
        terms = [w for w in words if w not in stop_words and len(w) > 2]

        # Also try compound terms
        if 'workspace' in query or 'work space' in query:
            terms.append('workspace')
        if 'keybind' in query or 'key bind' in query or 'hotkey' in query:
            terms.append('keybind')
            terms.append('bind')
        if 'screenshot' in query or 'screen shot' in query:
            terms.append('screenshot')
            terms.append('grim')
        if 'wallpaper' in query or 'background' in query:
            terms.append('wallpaper')
            terms.append('background')
        if 'theme' in query:
            terms.append('theme')
            terms.append('omarchy-theme')

        return list(set(terms))

    def _extract_relevant_section(self, content: str, terms: list[str]) -> str:
        """Extract the most relevant section from document content."""
        # Split into paragraphs/sections
        sections = re.split(r'\n\n+', content)

        best_section = ""
        best_score = 0

        for section in sections:
            section_lower = section.lower()
            score = sum(1 for term in terms if term in section_lower)
            if score > best_score and len(section) > 50:
                best_score = score
                best_section = section

        # Truncate if too long
        if len(best_section) > 500:
            best_section = best_section[:500] + "..."

        return best_section.strip()

    def _general_help(self) -> str:
        """Return general Omarchy/Hyprland help."""
        return ("I have the full Omarchy manual and your Hyprland configs stored. "
                "Ask me about hotkeys, workspaces, themes, monitors, terminals, "
                "screenshots, clipboard, dotfiles, or any other Omarchy feature.")
