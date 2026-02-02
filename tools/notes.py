"""Notes tool - dictation and recall with Mousepad."""
import os
import sys
import re
import subprocess
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.base import Tool
from core.memory import Memory


class NotesTool(Tool):
    """Take and recall dictated notes - opens in Mousepad."""

    name = "notes"
    description = "Take and recall notes"
    triggers = [
        "take a note", "note this", "remember this", "write down",
        "save note", "add note", "new note", "write a note",
        "show notes", "read notes", "my notes", "find note", "search notes"
    ]

    def __init__(self):
        self.memory = Memory()
        # Save to Documents folder
        self.notes_dir = os.path.expanduser("~/Documents/Notes")
        os.makedirs(self.notes_dir, exist_ok=True)

    def execute(self, query: str, **kwargs) -> str:
        query_lower = query.lower()

        # Check if showing/searching notes
        if any(t in query_lower for t in ["show notes", "read notes", "my notes"]):
            return self._show_notes()
        elif any(t in query_lower for t in ["find note", "search notes"]):
            return self._search_notes(query)

        # Otherwise, take a note
        return self._take_note(query)

    def _generate_filename(self, content: str) -> str:
        """Generate a meaningful filename from note content."""
        # Get first line or first few words as the key point
        first_line = content.split('\n')[0].strip()

        # Take first 5-6 words or up to 50 chars
        words = first_line.split()[:6]
        key_point = ' '.join(words)

        # Clean up for filename - remove special chars
        clean_name = re.sub(r'[^\w\s-]', '', key_point)
        clean_name = re.sub(r'\s+', '_', clean_name).strip('_')

        # Limit length and add date
        clean_name = clean_name[:40]
        date_str = datetime.now().strftime("%Y%m%d")

        if clean_name:
            return f"{date_str}_{clean_name}.txt"
        else:
            return f"{date_str}_note.txt"

    def _take_note(self, query: str) -> str:
        """Extract and save a note, then open in Mousepad."""
        # Try to extract the actual note content
        patterns = [
            r"take a note[:\s]+(.+)",
            r"note this[:\s]+(.+)",
            r"remember this[:\s]+(.+)",
            r"write down[:\s]+(.+)",
            r"save note[:\s]+(.+)",
            r"add note[:\s]+(.+)",
            r"new note[:\s]+(.+)",
            r"write a note[:\s]+(.+)",
        ]

        content = None
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE | re.DOTALL)
            if match:
                content = match.group(1).strip()
                break

        if not content:
            # Use the whole query minus common prefixes
            content = query
            for prefix in self.triggers:
                if content.lower().startswith(prefix):
                    content = content[len(prefix):].strip()
                    break

        if not content:
            return "What would you like me to note down?"

        # Save to memory
        self.memory.add_note(content)

        # Generate meaningful filename
        filename = self._generate_filename(content)
        filepath = os.path.join(self.notes_dir, filename)

        # Handle duplicate filenames
        base, ext = os.path.splitext(filepath)
        counter = 1
        while os.path.exists(filepath):
            filepath = f"{base}_{counter}{ext}"
            counter += 1

        # Write the note
        with open(filepath, 'w') as f:
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("-" * 40 + "\n\n")
            f.write(content)

        # Open in terminal with nano (preferred on this system)
        try:
            subprocess.Popen(
                ['ghostty', '-e', 'nano', filepath],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
        except FileNotFoundError:
            # Fallback to GUI editors
            for editor in ['mousepad', 'gedit', 'xed', 'pluma', 'kate']:
                try:
                    subprocess.Popen(
                        [editor, filepath],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )
                    break
                except FileNotFoundError:
                    continue

        return f"Note saved to {filename} and opened in editor."

    def _show_notes(self, limit: int = 5) -> str:
        """Show recent notes."""
        notes = self.memory.get_notes(limit=limit)
        if not notes:
            return "No notes yet. Tell me something to remember."

        response = f"Your last {len(notes)} notes:\n"
        for note in notes[-limit:]:
            date = note['created'][:10]
            content = note['content'][:60] + ('...' if len(note['content']) > 60 else '')
            response += f"• [{date}] {content}\n"

        return response.strip()

    def _search_notes(self, query: str) -> str:
        """Search notes."""
        # Extract search term
        search_term = query.lower()
        for prefix in ["find note", "search notes", "find", "search"]:
            if search_term.startswith(prefix):
                search_term = search_term[len(prefix):].strip()
                break

        if not search_term:
            return "What should I search for?"

        notes = self.memory.search_notes(search_term)
        if not notes:
            return f"No notes found matching '{search_term}'."

        response = f"Found {len(notes)} note(s):\n"
        for note in notes[:5]:
            content = note['content'][:60] + ('...' if len(note['content']) > 60 else '')
            response += f"• {content}\n"

        return response.strip()
