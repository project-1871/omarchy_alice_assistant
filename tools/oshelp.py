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

    # Quick answers for common questions - spoken naturally
    QUICK_ANSWERS = {
        'workspace': {
            'keywords': ['workspace', 'workspaces', 'switch workspace', 'change workspace', 'move workspace'],
            'answer': "For workspaces: Super plus a number switches to that workspace. Super plus Shift plus a number moves the current window there. You have 10 workspaces available."
        },
        'screenshot': {
            'keywords': ['screenshot', 'screen shot', 'capture screen', 'print screen'],
            'answer': "For screenshots: Super plus S captures a region you select. Super plus Shift plus S captures the whole screen. They're saved to your Pictures folder and copied to clipboard."
        },
        'terminal': {
            'keywords': ['terminal', 'open terminal', 'launch terminal', 'ghostty', 'kitty', 'alacritty'],
            'answer': "Super plus T opens your terminal. You're using Ghostty by default. The config is in dot config slash ghostty."
        },
        'launcher': {
            'keywords': ['launcher', 'walker', 'app launcher', 'open app', 'run app', 'rofi'],
            'answer': "Super plus Space opens Walker, your app launcher. Just start typing to search for apps, files, or run commands."
        },
        'window': {
            'keywords': ['close window', 'kill window', 'move window', 'resize window', 'float window', 'fullscreen'],
            'answer': "Window controls: Super plus Q closes a window. Super plus F toggles fullscreen. Super plus V toggles floating mode. Hold Super and drag to move windows, or drag edges to resize."
        },
        'theme': {
            'keywords': ['theme', 'change theme', 'dark mode', 'light mode', 'colors'],
            'answer': "Run omarchy-theme in your terminal to change themes. It'll show you available options and apply your choice to the whole system."
        },
        'wallpaper': {
            'keywords': ['wallpaper', 'background', 'change wallpaper', 'set wallpaper'],
            'answer': "Run omarchy-wallpaper to change your wallpaper. You can also put images in your Pictures slash Wallpapers folder and they'll be available to choose from."
        },
        'lock': {
            'keywords': ['lock', 'lock screen', 'hyprlock', 'idle', 'hypridle'],
            'answer': "Super plus L locks your screen. It'll also lock automatically after being idle. The lock screen config is in dot config slash hypr slash hyprlock.conf."
        },
        'clipboard': {
            'keywords': ['clipboard', 'copy', 'paste', 'clipboard history'],
            'answer': "Super plus C opens clipboard history from Walker. Your recent copies are saved there so you can paste older items."
        },
        'monitor': {
            'keywords': ['monitor', 'display', 'screen', 'resolution', 'refresh rate', 'second monitor'],
            'answer': "Monitor settings are in dot config slash hypr slash monitors.conf. You can set resolution, refresh rate, position, and scale for each display there."
        },
        'notifications': {
            'keywords': ['notification', 'notifications', 'mako', 'dismiss notification'],
            'answer': "Notifications use Mako. Super plus N dismisses all notifications. The config is in dot config slash mako."
        },
        'file_manager': {
            'keywords': ['file manager', 'files', 'thunar', 'browse files'],
            'answer': "Super plus E opens your file manager."
        },
        'browser': {
            'keywords': ['browser', 'web browser', 'firefox', 'open browser'],
            'answer': "Super plus B opens your web browser."
        },
    }

    def __init__(self):
        self.memory = Memory()

    def execute(self, query: str, **kwargs) -> str:
        query_lower = query.lower()

        # Try quick answers first
        quick = self._try_quick_answer(query_lower)
        if quick:
            return quick

        # Fall back to document search
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
            return f"I don't have specific info about that. Try asking about keybindings, workspaces, themes, or other Omarchy features."

        # Get the best matching document and extract a clean response
        return self._build_clean_response(unique_results, search_terms)

    def _try_quick_answer(self, query: str) -> str | None:
        """Check if we have a quick answer for this question."""
        for category, info in self.QUICK_ANSWERS.items():
            for keyword in info['keywords']:
                if keyword in query:
                    return info['answer']
        return None

    def _build_clean_response(self, results: list, terms: list[str]) -> str:
        """Build a clean, conversational response from search results."""
        # Get the top result's full content
        top_result = results[0]
        doc = self.memory.get_doc(top_result['name'])

        if not doc:
            return top_result.get('snippet', "I found something but couldn't read it properly.")

        content = doc.get('content', '')

        # Find the most relevant section
        snippet = self._extract_relevant_section(content, terms)

        if not snippet:
            snippet = top_result.get('snippet', '')

        # Clean up the snippet for speech
        snippet = self._clean_for_speech(snippet)

        if not snippet:
            return "I found some related docs but couldn't extract a clear answer. Try being more specific."

        # Determine source for context
        source = top_result['name']
        if 'hyprland' in source.lower() or 'hypr' in source.lower():
            prefix = "From your Hyprland config:"
        elif 'omarchy' in source.lower():
            prefix = "From the Omarchy docs:"
        else:
            prefix = "Here's what I found:"

        return f"{prefix} {snippet}"

    def _extract_search_terms(self, query: str) -> list[str]:
        """Extract meaningful search terms from query."""
        stop_words = {
            'how', 'do', 'i', 'what', 'is', 'the', 'a', 'an', 'to', 'in',
            'can', 'you', 'me', 'tell', 'about', 'show', 'help', 'with',
            'please', 'where', 'when', 'why', 'which', 'does', 'are', 'my',
            'omarchy', 'hyprland'  # Don't search for these directly
        }

        words = query.split()
        terms = [w for w in words if w not in stop_words and len(w) > 2]

        # Add related terms for common topics
        expansions = {
            'workspace': ['workspace', 'workspaces'],
            'keybind': ['keybind', 'bind', 'bindings'],
            'screenshot': ['screenshot', 'grim', 'capture'],
            'wallpaper': ['wallpaper', 'background', 'swww'],
            'theme': ['theme', 'omarchy-theme', 'colors'],
            'terminal': ['terminal', 'ghostty', 'kitty', 'alacritty'],
            'monitor': ['monitor', 'display', 'screen'],
        }

        for key, related in expansions.items():
            if key in query:
                terms.extend(related)

        return list(set(terms))

    def _extract_relevant_section(self, content: str, terms: list[str]) -> str:
        """Extract the most relevant section from document content."""
        # Split into paragraphs/sections
        sections = re.split(r'\n\n+', content)

        best_section = ""
        best_score = 0

        for section in sections:
            section_lower = section.lower()
            score = sum(2 if term in section_lower else 0 for term in terms)
            # Bonus for sections that look like actual content (not just headers)
            if len(section) > 100:
                score += 1
            if score > best_score:
                best_score = score
                best_section = section

        # Truncate if too long
        if len(best_section) > 400:
            # Try to cut at a sentence boundary
            sentences = re.split(r'[.!?]\s+', best_section[:450])
            if len(sentences) > 1:
                best_section = '. '.join(sentences[:-1]) + '.'
            else:
                best_section = best_section[:400] + "..."

        return best_section.strip()

    def _clean_for_speech(self, text: str) -> str:
        """Clean up text to sound natural when spoken."""
        # Remove markdown formatting
        text = re.sub(r'[#*`_~]', '', text)

        # Convert paths to spoken form
        text = re.sub(r'~/', 'your home folder slash ', text)
        text = re.sub(r'\.config/', 'dot config slash ', text)
        text = re.sub(r'\.local/', 'dot local slash ', text)

        # Clean up code blocks
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)

        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)

        # Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        # Remove orphaned punctuation
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        text = re.sub(r'^[.,!?;:\s]+', '', text)

        return text

    def _general_help(self) -> str:
        """Return general Omarchy/Hyprland help."""
        return ("I know all about Omarchy and your Hyprland setup. "
                "Ask me about keybindings, workspaces, themes, screenshots, "
                "terminals, monitors, or any other feature.")
